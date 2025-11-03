"""
Tushare数据获取脚本

从Tushare获取ETF、指数和公募基金的基本信息和历史行情数据，存储到MySQL数据库中。

使用方法:
    python scripts/fetch_tushare_data.py --start_date 20240820 --end_date 20240830
    python scripts/fetch_tushare_data.py --start_date 20100101 --end_date 20240830
"""

import sys
import os
import logging
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

import tushare as ts
import pandas as pd
from tqdm import tqdm
from common.mysql_manager import MySQLManager


class TushareDataFetcher:
    """
    Tushare数据获取器
    
    支持获取ETF、指数、基金的基本信息和行情数据
    """
    
    # 基金公司白名单
    FUND_COMPANY_WHITELIST = [
        "易方达", "华夏", "南方", "嘉实", "博时", 
        "广发", "招商", "富国", "汇添富", "中欧", "银河"
    ]
    
    def __init__(self, token: str, mode: str = 'append', data_type_filter: str = None, batch_size: int = 10000, forced_by_instrument: bool = False):
        """
        初始化数据获取器
        
        Args:
            token: Tushare token
            mode: 数据处理模式 ('append', 'replace', 'clean_append')
            data_type_filter: 数据类型过滤 ('etf', 'index', 'fund')
            batch_size: 批处理大小，默认1000条
        """
        self.logger = logging.getLogger(__name__)
        self.mode = mode
        self.data_type_filter = data_type_filter
        self.batch_size = batch_size
        self.forced_by_instrument = forced_by_instrument
        
        # 初始化Tushare
        ts.set_token(token)
        self.pro = ts.pro_api()
        
        # 初始化数据库管理器
        self.db_manager = MySQLManager()
        
        self.logger.info(f"TushareDataFetcher初始化完成 - 模式: {mode}, 数据类型过滤: {data_type_filter}, 批处理大小: {batch_size}, 强行使用by_instrument模式: {forced_by_instrument}")
        self.logger.info(f"基金公司白名单: {self.FUND_COMPANY_WHITELIST}")
    
    def _is_whitelisted_fund_company(self, management: str) -> bool:
        """
        判断基金公司是否在白名单中
        
        Args:
            management: 基金管理公司名称
            
        Returns:
            bool: 是否在白名单中
        """
        if not management:
            return False
        
        management = str(management).strip()
        for company in self.FUND_COMPANY_WHITELIST:
            if company in management:
                return True
        return False
    
    def _get_fund_management_from_db(self, ts_code: str) -> Optional[str]:
        """
        从数据库获取基金管理公司信息
        
        Args:
            ts_code: 基金代码
            
        Returns:
            Optional[str]: 基金管理公司名称，如果未找到返回None
        """
        try:
            result = self.db_manager.get_instrument_basic(data_type='fund', ts_code=ts_code)
            if result and 'management' in result:
                return result['management']
            return None
        except Exception as e:
            self.logger.error(f"获取基金管理公司信息失败 {ts_code}: {e}")
            return None
    
    def prepare_data_mode(self, start_date: str, end_date: str):
        """
        根据数据处理模式准备数据环境
        
        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
        """
        if self.mode == 'clean_append':
            self.logger.info("执行clean_append模式: 清空所有相关数据")
            result = self.db_manager.clear_all_instrument_data(data_type=self.data_type_filter)
            self.logger.info(f"清空数据完成: {result}")
            
        elif self.mode == 'replace':
            self.logger.info(f"执行replace模式: 清空{start_date}-{end_date}范围内的数据")
            result = self.db_manager.clear_instrument_data_by_date_range(
                data_type=self.data_type_filter,
                start_date=start_date,
                end_date=end_date
            )
            self.logger.info(f"清空指定范围数据完成: {result}")
            
        elif self.mode == 'append':
            self.logger.info("执行append模式: 直接追加数据")
            
        else:
            raise ValueError(f"未知的数据处理模式: {self.mode}")
    
    def should_process_data_type(self, data_type: str) -> bool:
        """
        检查是否应该处理指定的数据类型
        
        Args:
            data_type: 数据类型 ('etf', 'index', 'fund')
            
        Returns:
            bool: 是否应该处理
        """
        return self.data_type_filter is None or self.data_type_filter == data_type
    
    def _clean_data(self, data: Dict) -> Dict:
        """
        清理数据，去除None值和NaN值
        
        Args:
            data: 待清理的数据字典
            
        Returns:
            Dict: 清理后的数据字典
        """
        cleaned_data = {}
        for k, v in data.items():
            if v is not None and v != '':
                if isinstance(v, float) and pd.isna(v):
                    continue
                cleaned_data[k] = v
        return cleaned_data
    
    def _safe_concat_dataframes(self, df_list: List[pd.DataFrame]) -> pd.DataFrame:
        """
        安全地合并DataFrame列表，过滤掉空的DataFrame以避免FutureWarning
        
        Args:
            df_list: DataFrame列表
            
        Returns:
            pd.DataFrame: 合并后的DataFrame，如果所有都为空则返回空DataFrame
        """
        if not df_list:
            return pd.DataFrame()
        
        # 过滤掉空的DataFrame
        non_empty_dfs = [df for df in df_list if not df.empty]
        
        if not non_empty_dfs:
            # 如果所有DataFrame都为空，返回空DataFrame
            return pd.DataFrame()
        
        # 只合并非空的DataFrame，避免FutureWarning
        return pd.concat(non_empty_dfs, axis=0, ignore_index=True)
    
    def get_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            
        Returns:
            List[str]: 交易日期列表
        """
        try:
            self.logger.info(f"获取交易日历: {start_date} - {end_date}")
            
            df = self.pro.trade_cal(
                exchange='SSE',
                is_open='1',
                start_date=start_date,
                end_date=end_date,
                fields='cal_date'
            )
            
            if df.empty:
                self.logger.warning("未获取到交易日期")
                return []
            
            trading_dates = df['cal_date'].tolist()
            self.logger.info(f"获取到{len(trading_dates)}个交易日")
            return trading_dates
            
        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            return []
    
    def fetch_etf_basic_info(self) -> int:
        """
        获取ETF基本信息
        
        Returns:
            int: 成功获取的ETF数量
        """
        try:
            self.logger.info("开始获取ETF基本信息")
            
            # 获取场内基金（主要是ETF）
            df = self.pro.fund_basic(market='E', status='L')
            
            if df.empty:
                self.logger.warning("未获取到ETF基本信息")
                return 0
            
            success_count = 0
            # 添加进度条显示
            progress_bar = tqdm(df.iterrows(), total=len(df), desc="获取ETF基本信息", unit="条")
            
            for _, row in progress_bar:
                try:
                    # 映射字段
                    data = {
                        'symbol': row.get('ts_code', '').split('.')[0] if row.get('ts_code') else None,
                        'market': 'SH' if row.get('ts_code', '').endswith('.SH') else 'SZ',
                        'fullname': row.get('name'),
                        'management': row.get('management'),
                        'custodian': row.get('custodian'),
                        'fund_type': row.get('fund_type'),
                        'invest_type': row.get('invest_type'),
                        'found_date': row.get('found_date'),
                        'list_date': row.get('list_date'),
                        'delist_date': row.get('delist_date'),
                        'm_fee': row.get('m_fee'),
                        'c_fee': row.get('c_fee'),
                        'min_amount': row.get('min_amount'),
                        'benchmark': row.get('benchmark'),
                        'status': row.get('status', 'L')
                    }
                    
                    # 过滤None值和NaN值
                    data = self._clean_data(data)
                    
                    success = self.db_manager.add_instrument_basic(
                        data_type='etf',
                        ts_code=row['ts_code'],
                        name=row['name'],
                        **data
                    )
                    
                    if success:
                        success_count += 1
                    
                    # 更新进度条显示成功数量
                    progress_bar.set_postfix({"成功": success_count})
                        
                except Exception as e:
                    self.logger.error(f"添加ETF基本信息失败 {row.get('ts_code', 'unknown')}: {e}")
                    continue
            
            progress_bar.close()
            self.logger.info(f"ETF基本信息获取完成，成功{success_count}条")
            return success_count
            
        except Exception as e:
            self.logger.error(f"获取ETF基本信息失败: {e}")
            return 0
    
    def fetch_index_basic_info(self) -> int:
        """
        获取指数基本信息
        
        Returns:
            int: 成功获取的指数数量
        """
        try:
            self.logger.info("开始获取指数基本信息")
            
            success_count = 0
            
            # 获取各个市场的指数
            markets = ['SSE', 'SZSE', 'CSI', 'SW']  # 上交所、深交所、中证、申万
            
            # 创建总体进度条
            market_progress = tqdm(markets, desc="获取指数市场", unit="个市场")
            
            for market in market_progress:
                try:
                    self.logger.info(f"获取{market}指数信息")
                    market_progress.set_description(f"获取{market}指数")
                    
                    df = self.pro.index_basic(market=market)
                    
                    if df.empty:
                        self.logger.warning(f"{market}指数信息为空")
                        continue
                    
                    # 为每个市场创建进度条
                    index_progress = tqdm(
                        df.iterrows(), 
                        total=len(df), 
                        desc=f"{market}指数", 
                        unit="条", 
                        leave=False
                    )
                    
                    market_success = 0
                    for _, row in index_progress:
                        try:
                            # 映射字段
                            data = {
                                'symbol': row.get('ts_code', '').split('.')[0] if row.get('ts_code') else None,
                                'market': market,
                                'fullname': row.get('fullname'),
                                'publisher': row.get('publisher'),
                                'index_type': row.get('index_type'),
                                'category': row.get('category'),
                                'base_date': row.get('base_date'),
                                'base_point': row.get('base_point'),
                                'list_date': row.get('list_date'),
                                'weight_rule': row.get('weight_rule'),
                                'description': row.get('desc'),
                            }
                            
                            # 过滤None值和NaN值
                            data = self._clean_data(data)
                            
                            success = self.db_manager.add_instrument_basic(
                                data_type='index',
                                ts_code=row['ts_code'],
                                name=row['name'],
                                **data
                            )
                            
                            if success:
                                success_count += 1
                                market_success += 1
                            
                            # 更新进度条显示
                            index_progress.set_postfix({"市场成功": market_success, "总成功": success_count})
                                
                        except Exception as e:
                            self.logger.error(f"添加指数基本信息失败 {row.get('ts_code', 'unknown')}: {e}")
                            continue
                    
                    index_progress.close()
                    market_progress.set_postfix({"总成功": success_count})
                    
                    # 防止频繁调用
                    time.sleep(0.2)
                    
                except Exception as e:
                    self.logger.error(f"获取{market}指数基本信息失败: {e}")
                    continue
            
            market_progress.close()
            self.logger.info(f"指数基本信息获取完成，成功{success_count}条")
            return success_count
            
        except Exception as e:
            self.logger.error(f"获取指数基本信息失败: {e}")
            return 0
    
    def fetch_fund_basic_info(self) -> int:
        """
        获取公募基金基本信息（仅白名单内基金公司）
        
        Returns:
            int: 成功获取的基金数量
        """
        try:
            self.logger.info("开始获取公募基金基本信息（仅白名单内基金公司）")
            
            # 获取场外基金（公募基金）
            df = self.pro.fund_basic(market='O', status='L')
            
            if df.empty:
                self.logger.warning("未获取到公募基金基本信息")
                return 0
            
            # 应用白名单过滤
            original_count = len(df)
            df = df[df['management'].apply(lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False)]
            filtered_count = len(df)
            
            self.logger.info(f"基金白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")
            
            if df.empty:
                self.logger.warning("白名单过滤后无公募基金数据")
                return 0
            
            success_count = 0
            # 添加进度条显示
            progress_bar = tqdm(df.iterrows(), total=len(df), desc="获取基金基本信息", unit="条")
            
            for _, row in progress_bar:
                try:
                    # 映射字段
                    data = {
                        'symbol': row.get('ts_code', '').split('.')[0] if row.get('ts_code') else None,
                        'market': 'O',  # 场外
                        'fullname': row.get('name'),
                        'management': row.get('management'),
                        'custodian': row.get('custodian'),
                        'fund_type': row.get('fund_type'),
                        'invest_type': row.get('invest_type'),
                        'found_date': row.get('found_date'),
                        'due_date': row.get('due_date'),
                        'm_fee': row.get('m_fee'),
                        'c_fee': row.get('c_fee'),
                        'min_amount': row.get('min_amount'),
                        'benchmark': row.get('benchmark'),
                        'status': row.get('status', 'L')
                    }
                    
                    # 过滤None值和NaN值
                    data = self._clean_data(data)
                    
                    success = self.db_manager.add_instrument_basic(
                        data_type='fund',
                        ts_code=row['ts_code'],
                        name=row['name'],
                        **data
                    )
                    
                    if success:
                        success_count += 1
                    
                    # 更新进度条显示成功数量
                    progress_bar.set_postfix({"成功": success_count})
                        
                except Exception as e:
                    self.logger.error(f"添加基金基本信息失败 {row.get('ts_code', 'unknown')}: {e}")
                    continue
            
            progress_bar.close()
            self.logger.info(f"公募基金基本信息获取完成，成功{success_count}条（白名单内）")
            return success_count
            
        except Exception as e:
            self.logger.error(f"获取公募基金基本信息失败: {e}")
            return 0
    
    def fetch_etf_daily_data(self, trade_date: str, max_retries: int = 3) -> int:
        """
        获取指定日期的ETF日线数据
        
        Args:
            trade_date: 交易日期(YYYYMMDD)
            max_retries: 最大重试次数
            
        Returns:
            int: 成功获取的数据条数
        """
        for retry in range(max_retries):
            try:
                self.logger.info(f"获取ETF日线数据: {trade_date} (第{retry+1}次尝试)")
                
                df = self.pro.fund_daily(trade_date=trade_date)
                
                if df.empty:
                    self.logger.warning(f"未获取到{trade_date}的ETF日线数据")
                    return 0
                
                success_count = 0
                # 添加进度条
                progress_bar = tqdm(df.iterrows(), total=len(df), 
                                  desc=f"ETF日线[{trade_date}]", unit="条", leave=False)
                
                for _, row in progress_bar:
                    try:
                        # 映射字段
                        data = {
                            'open_price': row.get('open'),
                            'high_price': row.get('high'),
                            'low_price': row.get('low'),
                            'close_price': row.get('close'),
                            'pre_close': row.get('pre_close'),
                            'change_amount': row.get('change'),
                            'pct_change': row.get('pct_chg'),
                            'volume': row.get('vol'),
                            'amount': row.get('amount')
                        }
                        
                        # 过滤None值和NaN值
                        data = self._clean_data(data)
                        
                        success = self.db_manager.add_instrument_daily(
                            data_type='etf',
                            ts_code=row['ts_code'],
                            trade_date=row['trade_date'],
                            **data
                        )
                        
                        if success:
                            success_count += 1
                        
                        # 更新进度条显示
                        progress_bar.set_postfix({"成功": success_count})
                            
                    except Exception as e:
                        self.logger.error(f"添加ETF日线数据失败 {row.get('ts_code', 'unknown')}: {e}")
                        continue
                
                progress_bar.close()
                self.logger.info(f"ETF日线数据获取完成 {trade_date}，成功{success_count}条")
                return success_count
                
            except Exception as e:
                self.logger.error(f"获取ETF日线数据失败 {trade_date} (第{retry+1}次): {e}")
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return 0
        
        return 0
    
    def fetch_index_daily_data_optimized(self, start_date: str, end_date: str, max_retries: int = 3) -> int:
        """
        优化后的指数日线数据获取（批量模式）
        
        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            max_retries: 最大重试次数
            
        Returns:
            int: 成功获取的数据条数
        """
        # 先获取所有指数代码
        index_codes = self.db_manager.get_instrument_basic(data_type='index')
        if not index_codes:
            self.logger.warning("未找到指数基本信息，请先获取指数基本信息")
            return 0
        
        self.logger.info(f"开始批量获取指数数据: {start_date} - {end_date}, 共{len(index_codes)}个指数")
        success_count = 0
        all_data = []
        
        # 创建进度条
        progress_bar = tqdm(index_codes, desc="批量获取指数数据", unit="个指数")
        
        for index_info in progress_bar:
            ts_code = index_info['ts_code']
            
            for retry in range(max_retries):
                try:
                    # 一次性获取整个日期范围的数据
                    df = self.pro.index_daily(
                        ts_code=ts_code, 
                        start_date=start_date, 
                        end_date=end_date
                    )
                    
                    if df.empty:
                        break  # 该指数在此日期范围无数据，跳过
                    
                    # 处理每一行数据
                    for _, row in df.iterrows():
                        try:
                            # 映射字段并添加data_type
                            data = {
                                'data_type': 'index',
                                'ts_code': row['ts_code'],
                                'trade_date': row['trade_date'],
                                'open_price': row.get('open'),
                                'high_price': row.get('high'),
                                'low_price': row.get('low'),
                                'close_price': row.get('close'),
                                'pre_close': row.get('pre_close'),
                                'change_amount': row.get('change'),
                                'pct_change': row.get('pct_chg'),
                                'volume': row.get('vol'),
                                'amount': row.get('amount')
                            }
                            
                            # 过滤None值和NaN值
                            data = self._clean_data(data)
                            all_data.append(data)
                            
                        except Exception as e:
                            self.logger.error(f"处理指数数据失败 {row.get('ts_code', 'unknown')}: {e}")
                            continue
                    
                    # 达到批处理大小时进行批量插入
                    if len(all_data) >= self.batch_size:
                        batch_success = self.db_manager.batch_insert_instrument_daily(
                            all_data, batch_size=self.batch_size
                        )
                        success_count += batch_success
                        all_data = []  # 清空已处理的数据
                    
                    break  # 成功获取，跳出重试循环
                    
                except Exception as e:
                    self.logger.error(f"获取指数数据失败 {ts_code} (第{retry+1}次): {e}")
                    if retry < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    else:
                        break
            
            # 更新进度条显示
            progress_bar.set_postfix({"已收集": len(all_data), "已插入": success_count})
            
            # 防止频繁调用
            time.sleep(0.001)
        
        # 插入剩余数据
        if all_data:
            batch_success = self.db_manager.batch_insert_instrument_daily(
                all_data, batch_size=self.batch_size
            )
            success_count += batch_success
        
        progress_bar.close()
        self.logger.info(f"指数数据批量获取完成: {start_date} - {end_date}，成功{success_count}条")
        return success_count
    
    def fetch_fund_nav_data(self, nav_date: str, max_retries: int = 3) -> int:
        """
        获取指定日期的基金净值数据（仅白名单内基金公司）
        
        Args:
            nav_date: 净值日期(YYYYMMDD)
            max_retries: 最大重试次数
            
        Returns:
            int: 成功获取的数据条数
        """
        for retry in range(max_retries):
            try:
                self.logger.info(f"获取基金净值数据: {nav_date} (第{retry+1}次尝试)")
                
                df = self.pro.fund_nav(nav_date=nav_date)
                
                if df.empty:
                    self.logger.warning(f"未获取到{nav_date}的基金净值数据")
                    return 0
                
                success_count = 0
                whitelisted_count = 0
                # 添加进度条
                progress_bar = tqdm(df.iterrows(), total=len(df), 
                                  desc=f"基金净值[{nav_date}]", unit="条", leave=False)
                
                for _, row in progress_bar:
                    try:
                        # 检查基金是否在白名单内
                        ts_code = row['ts_code']
                        management = self._get_fund_management_from_db(ts_code)
                        
                        if not self._is_whitelisted_fund_company(management):
                            continue  # 跳过非白名单基金
                        
                        whitelisted_count += 1
                        
                        # 映射字段
                        data = {
                            'unit_nav': row.get('unit_nav'),
                            'accum_nav': row.get('accum_nav'),
                            'adj_nav': row.get('adj_nav'),
                            'accum_div': row.get('accum_div'),
                            'net_asset': row.get('net_asset'),
                            'total_netasset': row.get('total_netasset'),
                            'ann_date': row.get('ann_date')
                        }
                        
                        # 过滤None值和NaN值
                        data = self._clean_data(data)
                        
                        success = self.db_manager.add_instrument_daily(
                            data_type='fund',
                            ts_code=ts_code,
                            trade_date=row['nav_date'],
                            **data
                        )
                        
                        if success:
                            success_count += 1
                        
                        # 更新进度条显示
                        progress_bar.set_postfix({"白名单": whitelisted_count, "成功": success_count})
                            
                    except Exception as e:
                        self.logger.error(f"添加基金净值数据失败 {row.get('ts_code', 'unknown')}: {e}")
                        continue
                
                progress_bar.close()
                self.logger.info(f"基金净值数据获取完成 {nav_date}，白名单内{whitelisted_count}只，成功{success_count}条")
                return success_count
                
            except Exception as e:
                self.logger.error(f"获取基金净值数据失败 {nav_date} (第{retry+1}次): {e}")
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return 0
        
        return 0
    
    def get_latest_trade_date(self) -> str:
        """
        获取最新交易日
        
        Returns:
            str: 最新交易日(YYYYMMDD格式)
        """
        try:
            # 获取最近10天的交易日历，取最新的一个
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
            
            df = self.pro.trade_cal(
                exchange='SSE',
                is_open='1',
                start_date=start_date,
                end_date=end_date,
                fields='cal_date'
            )
            
            if df.empty:
                self.logger.warning("未获取到最新交易日，使用当前日期")
                return datetime.now().strftime('%Y%m%d')
            
            # 返回最新的交易日
            latest_date = df['cal_date'].iloc[-1]
            self.logger.info(f"获取到最新交易日: {latest_date}")
            return latest_date
            
        except Exception as e:
            self.logger.error(f"获取最新交易日失败: {e}")
            return datetime.now().strftime('%Y%m%d')
    
    def get_etf_count(self) -> int:
        """
        从Tushare API获取ETF数量
        通过获取最新一天的ETF日线行情数据来统计ETF数量
        
        Returns:
            int: ETF数量
        """
        try:
            # 获取最新交易日
            latest_date = self.get_latest_trade_date()
            
            self.logger.info(f"通过{latest_date}日线数据统计ETF数量")
            
            # 获取该日ETF日线数据来统计数量
            df = self.pro.fund_daily(trade_date=latest_date)
            
            if df.empty:
                self.logger.warning(f"未获取到{latest_date}的ETF数据，使用基金基本信息统计")
                # 备用方法：通过基金基本信息获取ETF数量
                df_basic = self.pro.fund_basic(market='E', status='L')
                etf_count = len(df_basic) if not df_basic.empty else 0
            else:
                etf_count = len(df)
            
            self.logger.info(f"从API获取到ETF数量: {etf_count}")
            return etf_count
            
        except Exception as e:
            self.logger.error(f"获取ETF数量失败: {e}")
            return 0
    
    def get_fund_count(self) -> int:
        """
        从Tushare API获取公募基金数量（仅白名单内基金公司）
        调用公募基金列表接口
        
        Returns:
            int: 基金数量
        """
        try:
            self.logger.info("通过基金基本信息接口统计基金数量（仅白名单内）")
            
            # 获取场外基金（公募基金）基本信息
            df = self.pro.fund_basic(market='O', status='L')
            
            if df.empty:
                self.logger.warning("未获取到公募基金列表")
                return 0
            
            # 应用白名单过滤
            original_count = len(df)
            df = df[df['management'].apply(lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False)]
            filtered_count = len(df)
            
            self.logger.info(f"基金数量统计 - 白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")
            
            return filtered_count
            
        except Exception as e:
            self.logger.error(f"获取公募基金数量失败: {e}")
            return 0
    
    def determine_fetch_strategy(self, start_date: str, end_date: str, data_type: str = None) -> Dict[str, str]:
        """
        根据时间范围和工具数量决定获取策略
        
        Args:
            start_date: 开始日期
            end_date: 结束日期  
            data_type: 数据类型，None表示处理所有类型
        
        Returns:
            Dict[str, str]: 各数据类型的策略 {'etf': 'by_date', 'fund': 'by_instrument', 'index': 'batch'}
        """
        # 计算交易日天数
        trading_dates = self.get_trading_calendar(start_date, end_date)
        days_count = len(trading_dates)
        
        strategies = {}
        
        # 确定需要处理的数据类型
        if data_type is None:
            # 未指定data_type，处理所有类型
            process_types = ['etf', 'fund']  # index已经有批量优化，不需要策略判断
        elif data_type in ['etf', 'fund']:
            process_types = [data_type]
        else:
            # index或其他类型，保持现有逻辑
            if self.should_process_data_type('index'):
                strategies['index'] = 'batch'
            return strategies
        
        # 为每种数据类型确定策略
        for dtype in process_types:
            if self.should_process_data_type(dtype):
                if dtype == 'etf':
                    instrument_count = self.get_etf_count()
                    type_name = "ETF"
                elif dtype == 'fund':
                    instrument_count = self.get_fund_count() 
                    type_name = "基金"
                else:
                    continue
                
                if instrument_count == 0:
                    self.logger.warning(f"获取{type_name}数量失败，使用按日期遍历方式")
                    strategies[dtype] = 'by_date'
                else:
                    # Trade off决策：天数 > 工具数量时，按工具遍历更高效
                    strategy = 'by_instrument' if days_count > instrument_count else 'by_date'
                    strategies[dtype] = strategy
                    
                    self.logger.info(f"{type_name}数据获取策略: {strategy} "
                                   f"(交易日: {days_count}天, 工具数: {instrument_count}个)")
            else:
                # 该类型被过滤，跳过
                pass
        
        # 指数数据始终使用批量方式（已优化）
        if self.should_process_data_type('index'):
            strategies['index'] = 'batch'
        
        return strategies
    
    def fetch_all_basic_info(self) -> Dict[str, int]:
        results = {}
        
        # 获取ETF基本信息
        if self.should_process_data_type('etf'):
            results['etf'] = self.fetch_etf_basic_info()
            time.sleep(1)
        else:
            results['etf'] = 0
            self.logger.info("跳过ETF基本信息获取")
        
        # 获取指数基本信息
        if self.should_process_data_type('index'):
            results['index'] = self.fetch_index_basic_info()
            time.sleep(1)
        else:
            results['index'] = 0
            self.logger.info("跳过指数基本信息获取")
        
        # 获取基金基本信息
        if self.should_process_data_type('fund'):
            results['fund'] = self.fetch_fund_basic_info()
        else:
            results['fund'] = 0
        return results
    
    def calculate_date_chunks_for_etf(self, start_date: str, end_date: str, max_records: int = 2000) -> List[tuple]:
        """
        为ETF数据获取计算日期分割块
        考虑ETF单次最大2000条的限制
        
        Args:
            start_date: 开始日期
            end_date: 结束日期  
            max_records: 单次最大记录数，默认2000
            
        Returns:
            List[tuple]: 日期分割块列表 [(start1, end1), (start2, end2), ...]
        """
        # 获取交易日历
        trading_dates = self.get_trading_calendar(start_date, end_date)
        if not trading_dates:
            return []
        
        # 按最大记录数分割日期
        chunks = []
        total_days = len(trading_dates)
        
        if total_days <= max_records:
            # 日期范围内的交易日数量 <= 2000，一次获取
            chunks.append((start_date, end_date))
        else:
            # 需要分割，每个块包含最多max_records个交易日
            for i in range(0, total_days, max_records):
                chunk_start_date = trading_dates[i]
                chunk_end_index = min(i + max_records - 1, total_days - 1)
                chunk_end_date = trading_dates[chunk_end_index]
                if int(chunk_start_date) < int(chunk_end_date):
                    chunks.append((chunk_start_date, chunk_end_date))
                else:
                    chunks.append((chunk_end_date, chunk_start_date))
        
        self.logger.info(f"ETF数据分割: 总交易日{total_days}天，分{len(chunks)}个块")
        return chunks
    
    def calculate_date_chunks_for_fund(self, start_date: str, end_date: str, max_records: int = 5000) -> List[tuple]:
        """
        为基金净值数据计算日期分割块
        基金净值更新频率较低，可以使用更大的分割块
        
        Args:
            start_date: 开始日期
            end_date: 结束日期  
            max_records: 单次最大记录数，默认5000
            
        Returns:
            List[tuple]: 日期分割块列表
        """
        # 使用与ETF相同的逻辑，但允许更大的块
        return self.calculate_date_chunks_for_etf(start_date, end_date, max_records)
    
    def fetch_etf_daily_data_by_instrument_chunked(self, start_date: str, end_date: str) -> int:
        """
        按ETF工具遍历获取日线数据（支持数据分割）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        try:
            # 获取ETF基本信息列表
            df_basic = self.pro.fund_basic(market='E', status='L')
            if df_basic.empty:
                self.logger.warning("未获取到ETF基本信息")
                return 0
            self.logger.info(f"ETF日线获取，共获取到 {len(df_basic)} 个ETF")
            
            # 计算日期分割块
            date_chunks = self.calculate_date_chunks_for_etf(start_date, end_date)
            if not date_chunks:
                self.logger.error("无法计算日期分割块")
                return 0
            
            success_count = 0
            all_data = []
            etf_count = len(df_basic)
            
            # 创建进度条 - 总任务数 = ETF数量 × 分块数量
            total_tasks = etf_count * len(date_chunks)
            self.logger.info(f"现在开始遍历ETF获取日线，总ETF数量: {etf_count}, 分块数量: {date_chunks}, 总任务数: {total_tasks}")
            progress_bar = tqdm(total=total_tasks, desc="按ETF获取分块数据", unit="任务")

            max_num_per_minute = 400
            now_req_times = 0

            # 获取该ETF在当前日期块的数据
            for _, etf_info in df_basic.iterrows():
                ts_code = etf_info['ts_code']
                try:
                    # 获取该ETF在当前日期块的数据
                    self.logger.info(f"【分块】开始获取代码 {ts_code}")
                    df_list = []
                    for chunk_start, chunk_end in date_chunks:
                        # 获取该ETF在当前日期块的数据
                        now_df = self.pro.fund_daily(
                            ts_code=ts_code,
                            start_date=chunk_start,
                            end_date=chunk_end
                        )
                        now_req_times += 1
                        df_list.append(now_df)
                    df = self._safe_concat_dataframes(df_list)
                    
                    if len(df) == 0:
                        self.logger.info("【分块】获取失败！尝试获取完整周期数据")
                        df = self.pro.fund_daily(
                            ts_code=ts_code
                        )
                        now_req_times += 1
                        if len(df) == 0:
                            self.logger.error("【不分块】获取失败！请检查接口问题")
                        else:
                            self.logger.info(f"【不分块】获取成功。当前ETF代码：{ts_code}，日线数据量: {len(df)}")
                    else:
                        self.logger.info(f"【分块】获取完整周期成功，ts_code: {ts_code}，日线数据量: {len(df)}")
                    
                    if not df.empty:
                        # 批量处理数据
                        for _, row in df.iterrows():
                            data = {
                                'data_type': 'etf',
                                'ts_code': row['ts_code'],
                                'trade_date': row['trade_date'],
                                'open_price': row.get('open'),
                                'high_price': row.get('high'),
                                'low_price': row.get('low'),
                                'close_price': row.get('close'),
                                'pre_close': row.get('pre_close'),
                                'change_amount': row.get('change'),
                                'pct_change': row.get('pct_chg'),
                                'volume': row.get('vol'),
                                'amount': row.get('amount')
                            }
                            data = self._clean_data(data)
                            all_data.append(data)
                    
                    # 达到批处理大小时进行批量插入
                    if len(all_data) >= self.batch_size:
                        batch_success = self.db_manager.batch_insert_instrument_daily(
                            all_data, batch_size=self.batch_size
                        )
                        success_count += batch_success
                        all_data = []
                    
                    time.sleep(0.001)  # 防止频繁调用
                    
                except Exception as e:
                    self.logger.error(f"获取ETF数据失败 {ts_code}: {e}")
                
                finally:
                    progress_bar.update(1)
                    progress_bar.set_postfix({
                        "ETF": ts_code, 
                        "成功": success_count
                    })

                
                # if now_idx > 10:
                #     break
                if now_req_times >= max_num_per_minute:
                    self.logger.info(f"【频繁度控制】ETF接口已请求 {now_req_times} 次，现在休息70秒")
                    time.sleep(70)
                    now_req_times = 0
                    self.logger.info(f"【频繁度控制】休息结束，现在继续执行")
            
            # 插入剩余数据
            if all_data:
                batch_success = self.db_manager.batch_insert_instrument_daily(
                    all_data, batch_size=self.batch_size
                )
                success_count += batch_success
            
            progress_bar.close()
            self.logger.info(f"按ETF遍历获取分块数据完成: {success_count}条")
            return success_count
            
        except Exception as e:
            self.logger.error(f"按ETF遍历获取分块数据失败: {e}")
            return 0
    
    def fetch_fund_nav_data_by_instrument(self, start_date: str, end_date: str) -> int:
        """
        按基金工具遍历获取净值数据（无需数据分割，仅白名单内基金公司）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        try:
            # 获取公募基金基本信息列表
            df_basic = self.pro.fund_basic(market='O', status='L')
            if df_basic.empty:
                self.logger.warning("未获取到基金基本信息")
                return 0
            
            # 应用白名单过滤
            original_count = len(df_basic)
            df_basic = df_basic[df_basic['management'].apply(lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False)]
            filtered_count = len(df_basic)
            
            self.logger.info(f"按工具获取基金净值 - 白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")
            
            if df_basic.empty:
                self.logger.warning("白名单过滤后无基金数据")
                return 0
            
            success_count = 0
            all_data = []
            fund_count = len(df_basic)
            
            # 创建进度条
            progress_bar = tqdm(total=fund_count, desc="按基金获取净值数据", unit="个基金")
            
            for _, fund_info in df_basic.iterrows():
                ts_code = fund_info['ts_code']
                
                try:
                    # 直接获取该基金的全周期净值数据
                    df = self.pro.fund_nav(ts_code=ts_code)
                    
                    if not df.empty:
                        # 按日期范围过滤数据
                        df = df[(df['nav_date'] >= start_date) & (df['nav_date'] <= end_date)]
                        
                        # 批量处理数据
                        for _, row in df.iterrows():
                            data = {
                                'data_type': 'fund',
                                'ts_code': row['ts_code'],
                                'trade_date': row['nav_date'],
                                'unit_nav': row.get('unit_nav'),
                                'accum_nav': row.get('accum_nav'),
                                'adj_nav': row.get('adj_nav'),
                                'accum_div': row.get('accum_div'),
                                'net_asset': row.get('net_asset'),
                                'total_netasset': row.get('total_netasset'),
                                'ann_date': row.get('ann_date')
                            }
                            data = self._clean_data(data)
                            all_data.append(data)
                    
                    # 批量插入
                    if len(all_data) >= self.batch_size:
                        batch_success = self.db_manager.batch_insert_instrument_daily(
                            all_data, batch_size=self.batch_size
                        )
                        success_count += batch_success
                        all_data = []
                    
                    time.sleep(0.001)
                    
                except Exception as e:
                    self.logger.error(f"获取基金净值失败 {ts_code}: {e}")
                
                finally:
                    progress_bar.update(1)
                    progress_bar.set_postfix({
                        "基金": ts_code,
                        "成功": success_count
                    })
            
            # 插入剩余数据
            if all_data:
                batch_success = self.db_manager.batch_insert_instrument_daily(
                    all_data, batch_size=self.batch_size
                )
                success_count += batch_success
            
            progress_bar.close()
            self.logger.info(f"按基金遍历获取净值数据完成: {success_count}条（白名单内）")
            return success_count
            
        except Exception as e:
            self.logger.error(f"按基金遍历获取净值数据失败: {e}")
            return 0
    
    def _fetch_etf_by_date_range(self, start_date: str, end_date: str) -> int:
        """
        按日期范围获取ETF数据（原有逻辑）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        trading_dates = self.get_trading_calendar(start_date, end_date)
        if not trading_dates:
            return 0
        
        total_count = 0
        date_progress = tqdm(trading_dates, desc="按日期获取ETF数据", unit="天")
        
        for trade_date in date_progress:
            etf_count = self.fetch_etf_daily_data(trade_date)
            total_count += etf_count
            date_progress.set_postfix({"总计": total_count})
            time.sleep(0.5)
        
        date_progress.close()
        return total_count
    
    def _fetch_fund_by_date_range(self, start_date: str, end_date: str) -> int:
        """
        按日期范围获取基金数据（原有逻辑）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        trading_dates = self.get_trading_calendar(start_date, end_date)
        if not trading_dates:
            return 0
        
        total_count = 0  
        date_progress = tqdm(trading_dates, desc="按日期获取基金数据", unit="天")
        
        for trade_date in date_progress:
            fund_count = self.fetch_fund_nav_data(trade_date)
            total_count += fund_count
            date_progress.set_postfix({"总计": total_count})
            time.sleep(0.5)
        
        date_progress.close()
        return total_count
    
    def fetch_daily_data_by_date_range(self, start_date: str, end_date: str) -> Dict[str, int]:
        """
        按日期范围获取日线数据 - 支持自适应策略选择和数据分割
        
        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            
        Returns:
            Dict[str, int]: 各类型数据的获取数量
        """
        results = {'etf': 0, 'index': 0, 'fund': 0}
        
        # 获取各数据类型的最优策略
        strategies = self.determine_fetch_strategy(start_date, end_date, self.data_type_filter)
        self.logger.info(f"数据获取策略: {strategies}")
        
        # 1. 处理指数数据（始终使用批量方式，已优化）
        if 'index' in strategies and strategies['index'] == 'batch':
            self.logger.info("开始批量获取指数数据")
            index_count = self.fetch_index_daily_data_optimized(start_date, end_date)
            results['index'] = index_count
            self.logger.info(f"指数数据批量获取完成: {index_count}条")
        
        # 2. 处理ETF数据
        if 'etf' in strategies:
            if strategies['etf'] == 'by_instrument' or self.forced_by_instrument:
                self.logger.info("使用按ETF工具遍历策略（支持分块）")
                etf_count = self.fetch_etf_daily_data_by_instrument_chunked(start_date, end_date)
                results['etf'] = etf_count
                self.logger.info(f"ETF数据按工具获取完成: {etf_count}条")
            elif strategies['etf'] == 'by_date':
                self.logger.info("使用按日期遍历ETF策略")
                results['etf'] = self._fetch_etf_by_date_range(start_date, end_date)
        
        # 3. 处理基金数据
        if 'fund' in strategies:
            if strategies['fund'] == 'by_instrument':
                self.logger.info("使用按基金工具遍历策略")
                fund_count = self.fetch_fund_nav_data_by_instrument(start_date, end_date)
                results['fund'] = fund_count
                self.logger.info(f"基金数据按工具获取完成: {fund_count}条")
            elif strategies['fund'] == 'by_date':
                self.logger.info("使用按日期遍历基金策略")  
                results['fund'] = self._fetch_fund_by_date_range(start_date, end_date)
        
        return results

    def fetch_fund_dividend_data(self, start_date: str, end_date: str) -> Dict[str, int]:
        """
        获取基金分红数据
        
        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            
        Returns:
            Dict[str, int]: 获取结果统计
        """
        self.logger.info(f"开始获取基金分红数据: {start_date} - {end_date}")
        
        # 按基金代码获取（推荐方式，更高效）
        try:
            total_records = self._fetch_dividend_by_fund_codes(start_date, end_date)
            
            results = {
                'dividend_records': total_records,
                'method': 'by_fund_codes'
            }
            
            self.logger.info(f"基金分红数据获取完成: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"获取基金分红数据失败: {e}")
            return {'dividend_records': 0, 'method': 'failed'}
    
    def fetch_fund_share_data(self, start_date: str, end_date: str) -> Dict[str, any]:
        """
        获取基金规模数据，自动选择最优策略
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict[str, any]: 获取结果信息
        """
        try:
            self.logger.info(f"开始获取基金规模数据: {start_date} - {end_date}")
            
            # 使用与基金净值相同的策略决策逻辑
            trading_dates = self.get_trading_calendar(start_date, end_date)
            days_count = len(trading_dates)
            
            # 获取白名单内基金数量
            fund_count = self.get_fund_count()
            
            if fund_count == 0:
                self.logger.warning("获取基金数量失败，使用按日期遍历方式")
                strategy = 'by_date'
            else:
                # Trade off决策：天数 > 工具数量时，按工具遍历更高效
                strategy = 'by_instrument' if days_count > fund_count else 'by_date'
            
            self.logger.info(f"基金规模数据获取策略: {strategy} (交易日: {days_count}天, 基金数: {fund_count}个)")
            
            if strategy == 'by_instrument':
                share_count = self.fetch_fund_share_by_instrument(start_date, end_date)
                return {'share_records': share_count, 'method': 'by_instrument'}
            else:
                share_count = self.fetch_fund_share_by_date(start_date, end_date)
                return {'share_records': share_count, 'method': 'by_date'}
                
        except Exception as e:
            self.logger.error(f"获取基金规模数据失败: {e}")
            return {'share_records': 0, 'method': 'failed'}
    
    def fetch_fund_share_by_instrument_chunked(self, start_date: str, end_date: str) -> int:
        """
        按基金工具遍历获取规模数据（支持数据分块，先尝试分块，失败后使用全周期获取）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        try:
            # 获取公募基金基本信息列表
            df_basic = self.pro.fund_basic(market='E', status='L')  # 场内基金，支持fund_share接口
            if df_basic.empty:
                self.logger.warning("未获取到基金基本信息")
                return 0
            
            # 应用白名单过滤
            original_count = len(df_basic)
            df_basic = df_basic[df_basic['management'].apply(lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False)]
            filtered_count = len(df_basic)
            
            self.logger.info(f"按工具获取基金规模 - 白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")
            
            if df_basic.empty:
                self.logger.warning("白名单过滤后无基金数据")
                return 0
            
            # 计算日期分割块
            date_chunks = self.calculate_date_chunks_for_fund(start_date, end_date, max_records=2000)
            if not date_chunks:
                self.logger.error("无法计算日期分割块")
                return 0
                
            self.logger.info(f"基金规模数据分块策略: {len(date_chunks)}个时间块，每块最多2000条记录")
            
            success_count = 0
            all_data = []
            fund_count = len(df_basic)
            
            # 添加频率控制参数（fund_share接口限制每分钟400次）
            max_requests_per_minute = 300  # 设置为300，留出安全余量
            request_count = 0
            start_time = time.time()
            
            # 创建进度条
            progress_bar = tqdm(total=fund_count, desc="按基金获取规模数据（分块）", unit="个基金")
            
            for _, fund_info in df_basic.iterrows():
                ts_code = fund_info['ts_code']
                
                try:
                    # 调用API前检查频率
                    if request_count >= max_requests_per_minute:
                        elapsed_time = time.time() - start_time
                        if elapsed_time < 60:
                            sleep_time = 60 - elapsed_time + 5
                            self.logger.info(f"【频率控制】基金规模数据已请求 {request_count} 次，休息 {sleep_time:.1f} 秒")
                            time.sleep(sleep_time)
                        request_count = 0
                        start_time = time.time()
                    
                    # 【分块获取】首先尝试按时间块获取数据
                    self.logger.debug(f"【分块】开始获取基金规模数据 {ts_code}")
                    df_list = []
                    chunk_requests = 0
                    
                    for chunk_start, chunk_end in date_chunks:
                        # 频率控制检查（包括分块请求）
                        if request_count + chunk_requests >= max_requests_per_minute:
                            elapsed_time = time.time() - start_time
                            if elapsed_time < 60:
                                sleep_time = 60 - elapsed_time + 5
                                self.logger.info(f"【频率控制】分块过程中需要休息 {sleep_time:.1f} 秒")
                                time.sleep(sleep_time)
                            request_count = 0
                            start_time = time.time()
                            chunk_requests = 0
                        
                        # 获取该基金在当前日期块的数据
                        chunk_df = self.pro.fund_share(
                            ts_code=ts_code,
                            start_date=chunk_start,
                            end_date=chunk_end
                        )
                        chunk_requests += 1
                        df_list.append(chunk_df)
                    
                    request_count += chunk_requests
                    
                    # 合并所有分块数据
                    if df_list:
                        df = self._safe_concat_dataframes(df_list)
                    else:
                        df = pd.DataFrame()
                    
                    # 【回退机制】如果分块获取结果为空，尝试全周期获取
                    if df.empty:
                        self.logger.info(f"【回退】基金 {ts_code} 分块获取失败，尝试获取全周期数据")
                        
                        # 频率控制检查（全周期请求）
                        if request_count >= max_requests_per_minute:
                            elapsed_time = time.time() - start_time
                            if elapsed_time < 60:
                                sleep_time = 60 - elapsed_time + 5
                                self.logger.info(f"【频率控制】回退过程中需要休息 {sleep_time:.1f} 秒")
                                time.sleep(sleep_time)
                            request_count = 0
                            start_time = time.time()
                        
                        df = self.pro.fund_share(ts_code=ts_code)
                        request_count += 1
                        
                        if df.empty:
                            self.logger.warning(f"【回退】基金 {ts_code} 全周期获取也失败，跳过")
                        else:
                            self.logger.info(f"【回退】基金 {ts_code} 全周期获取成功，数据量: {len(df)}")
                            # 按日期范围过滤数据
                            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
                    else:
                        self.logger.debug(f"【分块】基金 {ts_code} 分块获取成功，数据量: {len(df)}")
                    
                    if not df.empty:
                        # 批量处理数据
                        for _, row in df.iterrows():
                            data = {
                                'data_type': 'fund_share',
                                'ts_code': row['ts_code'],
                                'trade_date': row['trade_date'],
                                'fd_share': row.get('fd_share')
                            }
                            data = self._clean_data(data)
                            all_data.append(data)
                    
                    # 批量插入
                    if len(all_data) >= self.batch_size:
                        batch_success = self.db_manager.batch_insert_fund_share_data(
                            all_data, batch_size=self.batch_size
                        )
                        success_count += batch_success
                        all_data = []
                    
                    time.sleep(0.2)  # 额外的保险延迟
                    
                except Exception as e:
                    self.logger.error(f"获取基金规模失败 {ts_code}: {e}")
                
                finally:
                    progress_bar.update(1)
                    progress_bar.set_postfix({
                        "基金": ts_code,
                        "成功": success_count,
                        "请求数": request_count
                    })
            
            # 插入剩余数据
            if all_data:
                batch_success = self.db_manager.batch_insert_fund_share_data(
                    all_data, batch_size=self.batch_size
                )
                success_count += batch_success
            
            progress_bar.close()
            self.logger.info(f"按基金遍历获取规模数据完成: {success_count}条（白名单内，支持分块）")
            return success_count
            
        except Exception as e:
            self.logger.error(f"按基金遍历获取规模数据失败: {e}")
            return 0

    def fetch_fund_share_by_instrument(self, start_date: str, end_date: str) -> int:
        """
        按基金工具遍历获取规模数据（兼容性方法，调用分块版本）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        return self.fetch_fund_share_by_instrument_chunked(start_date, end_date)
    
    def fetch_fund_share_by_date(self, start_date: str, end_date: str) -> int:
        """
        按日期遍历获取基金规模数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的数据条数
        """
        trading_dates = self.get_trading_calendar(start_date, end_date)
        if not trading_dates:
            return 0
        
        total_count = 0  
        date_progress = tqdm(trading_dates, desc="按日期获取基金规模", unit="天")
        
        for trade_date in date_progress:
            share_count = self.fetch_fund_share_single_date(trade_date)
            total_count += share_count
            date_progress.set_postfix({"总计": total_count})
            time.sleep(0.2)
        
        date_progress.close()
        return total_count
    
    def fetch_fund_share_single_date(self, trade_date: str) -> int:
        """
        获取单个日期的基金规模数据
        
        Args:
            trade_date: 交易日期(YYYYMMDD)
            
        Returns:
            int: 成功获取的数据条数
        """
        try:
            df = self.pro.fund_share(trade_date=trade_date)
            
            if df.empty:
                self.logger.debug(f"未获取到 {trade_date} 的基金规模数据")
                return 0
            
            # 应用白名单过滤
            original_count = len(df)
            
            # 获取基金管理公司信息用于过滤
            filtered_data = []
            for _, row in df.iterrows():
                ts_code = row['ts_code']
                management = self._get_fund_management_from_db(ts_code)
                
                if management and self._is_whitelisted_fund_company(management):
                    data = {
                        'data_type': 'fund_share',
                        'ts_code': row['ts_code'],
                        'trade_date': row['trade_date'],
                        'fd_share': row.get('fd_share')
                    }
                    data = self._clean_data(data)
                    filtered_data.append(data)
            
            if filtered_data:
                success_count = self.db_manager.batch_insert_fund_share_data(
                    filtered_data, batch_size=self.batch_size
                )
                self.logger.debug(f"{trade_date}: 获取{original_count}条 -> 白名单过滤{len(filtered_data)}条 -> 成功{success_count}条")
                return success_count
            else:
                self.logger.debug(f"{trade_date}: 白名单过滤后无数据")
                return 0
            
        except Exception as e:
            self.logger.error(f"获取{trade_date}基金规模数据失败: {e}")
            return 0
    
    def _fetch_dividend_by_fund_codes(self, start_date: str, end_date: str) -> int:
        """
        按基金代码循环获取基金分红数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 成功获取的记录数
        """
        total_count = 0
        
        # 从Tushare API获取基金列表
        try:
            self.logger.info("从Tushare API获取公募基金列表")
            df_funds = self.pro.fund_basic(market='O', status='L')  # 场外基金，存续状态
            
            if df_funds.empty:
                self.logger.warning("从Tushare API未获取到基金列表")
                return 0
            
            self.logger.info(f"从API获取到{len(df_funds)}只基金")
            
            # 应用白名单过滤
            original_count = len(df_funds)
            df_funds = df_funds[df_funds['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]
            filtered_count = len(df_funds)
            
            self.logger.info(f"基金白名单过滤: 原始{original_count}只 -> 过滤后{filtered_count}只")
            
            if df_funds.empty:
                self.logger.warning("白名单过滤后无基金数据")
                return 0
                
        except Exception as e:
            self.logger.error(f"获取基金列表失败: {e}")
            return 0
        
        self.logger.info(f"开始遍历{len(df_funds)}个白名单基金获取分红数据")
        
        # 添加频率控制参数
        max_requests_per_minute = 300  # 设置为300，留出安全余量
        request_count = 0
        start_time = time.time()
        processed_count = 0
        
        # 为每个基金获取分红数据
        from tqdm import tqdm
        progress_bar = tqdm(df_funds.iterrows(), total=len(df_funds), desc="获取基金分红数据", unit="个基金")
        
        for _, fund_info in progress_bar:
            ts_code = fund_info['ts_code']
            fund_name = fund_info['name']
            processed_count += 1
            
            try:
                # 调用Tushare API前检查频率
                if request_count >= max_requests_per_minute:
                    # 计算已用时间
                    elapsed_time = time.time() - start_time
                    if elapsed_time < 60:  # 如果还没到1分钟
                        sleep_time = 60 - elapsed_time + 5  # 多等5秒作为缓冲
                        remaining_funds = len(df_funds) - processed_count + 1
                        estimated_minutes = remaining_funds / max_requests_per_minute
                        
                        self.logger.info(f"【频率控制】已处理 {processed_count-1}/{len(df_funds)} 个基金")
                        self.logger.info(f"【频率控制】当前分钟已请求 {request_count} 次，休息 {sleep_time:.1f} 秒")
                        self.logger.info(f"【频率控制】预计还需 {estimated_minutes:.1f} 分钟完成剩余 {remaining_funds} 个基金")
                        
                        time.sleep(sleep_time)
                    
                    # 重置计数器和时间
                    request_count = 0
                    start_time = time.time()
                
                # 调用Tushare API获取该基金的分红数据
                df = self.pro.fund_div(ts_code=ts_code)
                request_count += 1
                
                if df is not None and not df.empty:
                    # 按日期范围过滤数据
                    df = df[(df['ex_date'] >= start_date) & (df['ex_date'] <= end_date)]
                    
                    if not df.empty:
                        # 转换为记录列表
                        dividend_records = []
                        for _, row in df.iterrows():
                            dividend_record = row.to_dict()
                            dividend_records.append(dividend_record)
                        
                        # 批量保存到数据库
                        if dividend_records:
                            success_count = self.db_manager.insert_fund_dividend_data(dividend_records)
                            total_count += success_count
                            
                            self.logger.info(f"基金 {ts_code} ({fund_name}): 获取{len(dividend_records)}条分红记录，成功保存{success_count}条")
                        
                        # 更新进度条显示
                        progress_bar.set_postfix({
                            "基金": ts_code,
                            "请求数": request_count,
                            "本次": len(dividend_records), 
                            "总计": total_count
                        })
                    else:
                        # 更新进度条显示（无分红记录的情况）
                        progress_bar.set_postfix({
                            "基金": ts_code,
                            "请求数": request_count,
                            "本次": 0,
                            "总计": total_count
                        })
                        self.logger.debug(f"基金 {ts_code} ({fund_name}): 指定日期范围内无分红记录")
                else:
                    # 更新进度条显示（无数据的情况）
                    progress_bar.set_postfix({
                        "基金": ts_code,
                        "请求数": request_count,
                        "本次": 0,
                        "总计": total_count
                    })
                    self.logger.debug(f"基金 {ts_code} ({fund_name}): 无分红数据")
                
            except Exception as e:
                self.logger.error(f"获取基金 {ts_code} ({fund_name}) 分红数据失败: {e}")
                # 如果是频率限制错误，也要计入请求次数
                if "每分钟最多访问" in str(e):
                    request_count += 1
                continue
        
        progress_bar.close()
        self.logger.info(f"基金分红数据获取完成，总共成功保存 {total_count} 条记录")
        return total_count


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/fetch_tushare_data.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='从Tushare获取ETF、指数、基金数据')
    parser.add_argument('--start_date', required=True, help='开始日期(YYYYMMDD格式)')
    parser.add_argument('--end_date', required=True, help='结束日期(YYYYMMDD格式)')
    parser.add_argument('--basic_info', action='store_true', help='是否获取基本信息')
    parser.add_argument('--daily_data', action='store_true', help='是否获取日线数据')
    parser.add_argument('--fetch_dividend', action='store_true', help='是否获取基金分红数据')
    parser.add_argument('--fetch_fund_share', action='store_true', help='是否获取基金规模数据')
    parser.add_argument('--mode', choices=['append', 'replace', 'clean_append'], 
                        default='append', help='数据处理模式: append(追加), replace(替换指定范围), clean_append(清空后追加)')
    parser.add_argument('--data_type', choices=['etf', 'index', 'fund'], 
                        help='数据类型过滤，为空时处理所有类型')
    parser.add_argument('--batch_size', type=int, default=10000, 
                        help='批处理大小，默认10000条')
    parser.add_argument('--show_stats', action='store_true', help='显示数据统计信息')
    parser.add_argument('--validate', action='store_true', help='验证数据完整性')
    parser.add_argument('--forced_by_instrument', action='store_true', help='强行使用遍历每个指数获取全周期数据的模式')
    
    args = parser.parse_args()
    
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("=== Tushare数据获取开始 ===")
    logger.info(f"参数: start_date={args.start_date}, end_date={args.end_date}, mode={args.mode}, data_type={args.data_type}, batch_size={args.batch_size}")
    
    try:
        # 读取token
        # with open('docs/tushare_token.txt', 'r') as f:
        #     token = f.read().strip()
        token = '18e20abc9ab15f381594da84aac654a11890ecf119a35e2ed70283f0'
        
        # 初始化数据获取器
        fetcher = TushareDataFetcher(token, mode=args.mode, data_type_filter=args.data_type, batch_size=args.batch_size, forced_by_instrument=args.forced_by_instrument)
        
        # 显示当前数据统计（如果需要）
        if args.show_stats:
            logger.info("=== 当前数据统计 ===")
            stats = fetcher.db_manager.get_data_statistics(data_type=args.data_type)
            logger.info(f"数据统计: {stats}")
        
        # 根据模式准备数据环境
        fetcher.prepare_data_mode(args.start_date, args.end_date)
        
        # 获取基本信息
        if args.basic_info:
            logger.info("开始获取基本信息")
            basic_results = fetcher.fetch_all_basic_info()
            logger.info(f"基本信息获取完成: {basic_results}")
        
        # 获取日线数据
        if args.daily_data:
            logger.info(f"开始获取日线数据: {args.start_date} - {args.end_date}")
            daily_results = fetcher.fetch_daily_data_by_date_range(args.start_date, args.end_date)
            logger.info(f"日线数据获取完成: {daily_results}")
        
        # 获取基金分红数据（如果需要）
        if args.fetch_dividend:
            logger.info(f"开始获取基金分红数据: {args.start_date} - {args.end_date}")
            if args.data_type and args.data_type != 'fund':
                logger.warning("分红数据仅适用于基金，但当前数据类型不是fund，跳过分红数据获取")
            else:
                dividend_results = fetcher.fetch_fund_dividend_data(args.start_date, args.end_date)
                logger.info(f"基金分红数据获取完成: {dividend_results}")
        
        # 获取基金规模数据（如果需要）
        if args.fetch_fund_share:
            logger.info(f"开始获取基金规模数据: {args.start_date} - {args.end_date}")
            if args.data_type and args.data_type != 'fund':
                logger.warning("基金规模数据仅适用于基金，但当前数据类型不是fund，跳过基金规模数据获取")
            else:
                fund_share_results = fetcher.fetch_fund_share_data(args.start_date, args.end_date)
                logger.info(f"基金规模数据获取完成: {fund_share_results}")
        
        # 数据验证（如果需要）
        if args.validate:
            logger.info("=== 数据完整性验证 ===")
            data_types = [args.data_type] if args.data_type else ['etf', 'index', 'fund']
            for dtype in data_types:
                if fetcher.should_process_data_type(dtype):
                    report = fetcher.db_manager.validate_data_completeness(
                        dtype, args.start_date, args.end_date
                    )
                    logger.info(f"{dtype.upper()}数据完整性报告: {report}")
        
        # 显示最终数据统计
        if args.show_stats:
            logger.info("=== 最终数据统计 ===")
            final_stats = fetcher.db_manager.get_data_statistics(data_type=args.data_type)
            logger.info(f"最终数据统计: {final_stats}")
        
        logger.info("=== Tushare数据获取完成 ===")
        
    except Exception as e:
        logger.error(f"数据获取过程中发生异常: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()