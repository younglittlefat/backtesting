"""
ETF数据抓取器

处理ETF基本信息和日线数据的获取
"""

import time
import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from tqdm import tqdm

from .base_fetcher import BaseFetcher
from .rate_limiter import RateLimiter
from .data_processor import DataProcessor


class ETFFetcher(BaseFetcher):
    """ETF数据抓取器"""

    def __init__(self, pro_api, db_manager, rate_limiter: RateLimiter,
                 data_processor: DataProcessor, logger=None):
        """
        初始化ETF抓取器

        Args:
            pro_api: Tushare Pro API实例
            db_manager: 数据库管理器
            rate_limiter: 频率限制器
            data_processor: 数据处理器
            logger: 日志记录器
        """
        super().__init__(pro_api, db_manager, logger)
        self.rate_limiter = rate_limiter
        self.data_processor = data_processor

    def fetch_basic_info(self) -> int:
        """
        获取ETF基本信息（使用批量插入优化）

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

            # 准备批量插入数据
            data_list = []
            progress_bar = tqdm(df.iterrows(), total=len(df), desc="准备ETF基本信息", unit="条")

            for _, row in progress_bar:
                try:
                    # 映射字段
                    data = {
                        'data_type': 'etf',
                        'ts_code': row['ts_code'],
                        'name': row['name'],
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
                    data_list.append(data)

                except Exception as e:
                    self.logger.error(f"准备ETF基本信息失败 {row.get('ts_code', 'unknown')}: {e}")
                    continue

            progress_bar.close()

            # 批量插入数据
            if data_list:
                self.logger.info(f"开始批量插入{len(data_list)}条ETF基本信息")
                success_count = self.db_manager.batch_insert_instrument_basic(
                    data_list, batch_size=1000
                )
                self.logger.info(f"ETF基本信息获取完成，成功{success_count}条")
                return success_count
            else:
                self.logger.warning("没有准备好的ETF基本信息数据")
                return 0

        except Exception as e:
            self.logger.error(f"获取ETF基本信息失败: {e}")
            return 0

    def fetch_daily_by_date(self, trade_date: str, max_retries: int = 3) -> int:
        """
        获取指定日期的ETF日线数据（包含复权信息，使用批量插入优化）

        Args:
            trade_date: 交易日期(YYYYMMDD)
            max_retries: 最大重试次数

        Returns:
            int: 成功获取的数据条数
        """
        for retry in range(max_retries):
            try:
                self.logger.info(f"获取ETF日线数据: {trade_date} (第{retry+1}次尝试)")

                # 获取日线数据
                df = self.pro.fund_daily(trade_date=trade_date)
                self.rate_limiter.increment()

                if df.empty:
                    self.logger.warning(f"未获取到{trade_date}的ETF日线数据")
                    return 0

                # 获取复权因子数据
                df_adj = self.pro.fund_adj(trade_date=trade_date)
                self.rate_limiter.increment()

                # 合并复权因子
                if not df_adj.empty:
                    df = pd.merge(df, df_adj[['ts_code', 'trade_date', 'adj_factor']],
                                on=['ts_code', 'trade_date'], how='left')
                    self.logger.debug(f"成功合并复权因子，日期: {trade_date}")
                else:
                    self.logger.warning(f"未获取到{trade_date}的复权因子数据")
                    # 添加空的adj_factor列
                    df['adj_factor'] = None

                # 准备批量插入数据
                data_list = []
                progress_bar = tqdm(df.iterrows(), total=len(df),
                                  desc=f"准备ETF日线[{trade_date}]", unit="条", leave=False)

                for _, row in progress_bar:
                    try:
                        # 映射字段
                        data = {
                            'data_type': 'etf',
                            'ts_code': row['ts_code'],
                            'trade_date': row['trade_date'],
                            'open_price': row.get('open'),
                            'high_price': row.get('high'),
                            'low_price': row.get('low'),
                            'close_price': row.get('close'),
                            'pre_close': row.get('pre_close'),
                            'adj_factor': row.get('adj_factor'),
                            'change_amount': row.get('change'),
                            'pct_change': row.get('pct_chg'),
                            'volume': row.get('vol'),
                            'amount': row.get('amount')
                        }

                        # 过滤None值和NaN值
                        data = self._clean_data(data)
                        data_list.append(data)

                    except Exception as e:
                        self.logger.error(f"准备ETF日线数据失败 {row.get('ts_code', 'unknown')}: {e}")
                        continue

                progress_bar.close()

                # 批量插入数据
                if data_list:
                    self.logger.info(f"开始批量插入{len(data_list)}条ETF日线数据")
                    success_count = self.db_manager.batch_insert_instrument_daily(
                        data_list, batch_size=1000
                    )
                    self.logger.info(f"ETF日线数据获取完成 {trade_date}，成功{success_count}条")
                    return success_count
                else:
                    self.logger.warning(f"没有准备好的ETF日线数据")
                    return 0

            except Exception as e:
                self.logger.error(f"获取ETF日线数据失败 {trade_date} (第{retry+1}次): {e}")
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return 0

        return 0

    def fetch_daily_by_instrument_chunked(self, start_date: str, end_date: str,
                                          ts_code: Optional[str] = None) -> int:
        """
        按ETF工具遍历获取日线数据（支持数据分割）

        Args:
            start_date: 开始日期
            end_date: 结束日期
            ts_code: 指定ETF代码（可选，用于单标的测试）

        Returns:
            int: 成功获取的数据条数
        """
        try:
            # 获取ETF列表
            if ts_code:
                # 单标的测试模式
                df_basic = self.pro.fund_basic(ts_code=ts_code)
                self.logger.info(f"单标的测试模式: {ts_code}")
            else:
                # 全量模式
                df_basic = self.pro.fund_basic(market='E', status='L')

            if df_basic.empty:
                self.logger.warning("未获取到ETF基本信息")
                return 0

            self.logger.info(f"ETF日线获取，共 {len(df_basic)} 个ETF")

            # 计算日期分割块
            trading_dates = self.get_trading_calendar(start_date, end_date)
            date_chunks = self.data_processor.calculate_date_chunks(trading_dates, max_records=2000)

            if not date_chunks:
                self.logger.error("无法计算日期分割块")
                return 0

            success_count = 0
            etf_count = len(df_basic)

            # 创建进度条
            progress_bar = tqdm(total=etf_count, desc="按ETF获取分块数据", unit="个ETF")

            for _, etf_info in df_basic.iterrows():
                etf_code = etf_info['ts_code']
                try:
                    self.logger.debug(f"开始获取 {etf_code} 数据")

                    df_list = []
                    df_adj_list = []

                    for chunk_start, chunk_end in date_chunks:
                        # 频率控制
                        self.rate_limiter.check_and_wait()

                        # 获取日线数据
                        now_df = self.pro.fund_daily(
                            ts_code=etf_code,
                            start_date=chunk_start,
                            end_date=chunk_end
                        )
                        self.rate_limiter.increment()
                        df_list.append(now_df)

                        # 获取复权因子
                        now_df_adj = self.pro.fund_adj(
                            ts_code=etf_code,
                            start_date=chunk_start,
                            end_date=chunk_end
                        )
                        self.rate_limiter.increment()
                        df_adj_list.append(now_df_adj)

                    # 合并数据
                    df = self._safe_concat_dataframes(df_list)
                    df_adj = self._safe_concat_dataframes(df_adj_list)

                    # 合并复权因子
                    if not df.empty and not df_adj.empty:
                        df = pd.merge(df, df_adj[['trade_date', 'adj_factor']],
                                    on='trade_date', how='left')
                        self.logger.debug(f"成功合并复权因子，ts_code: {etf_code}")

                    # 如果分块获取失败，尝试全周期
                    if df.empty:
                        self.logger.info(f"分块获取失败，尝试全周期: {etf_code}")
                        self.rate_limiter.check_and_wait()

                        df = self.pro.fund_daily(ts_code=etf_code)
                        self.rate_limiter.increment()

                        df_adj = self.pro.fund_adj(ts_code=etf_code)
                        self.rate_limiter.increment()

                        if not df.empty and not df_adj.empty:
                            df = pd.merge(df, df_adj[['trade_date', 'adj_factor']],
                                        on='trade_date', how='left')

                        # 过滤日期范围
                        if not df.empty:
                            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
                            self.logger.info(f"全周期数据过滤后: {len(df)}条")

                    if not df.empty:
                        # 向量化处理数据（优化性能）
                        # 重命名列以匹配数据库字段
                        df_renamed = df.rename(columns={
                            'open': 'open_price',
                            'high': 'high_price',
                            'low': 'low_price',
                            'close': 'close_price',
                            'change': 'change_amount',
                            'pct_chg': 'pct_change',
                            'vol': 'volume'
                        })

                        # 添加data_type列
                        df_renamed['data_type'] = 'etf'

                        # 转换为字典列表
                        records = df_renamed.to_dict('records')

                        # 批量添加数据
                        for record in records:
                            data = self._clean_data(record)
                            self.data_processor.add_data(data)

                        # 定期刷新缓冲区
                        if self.data_processor.get_buffer_size() >= self.data_processor.batch_size:
                            batch_success = self.data_processor.flush('instrument_daily')
                            success_count += batch_success

                    time.sleep(0.001)

                except Exception as e:
                    self.logger.error(f"获取ETF数据失败 {etf_code}: {e}")

                finally:
                    progress_bar.update(1)
                    progress_bar.set_postfix({
                        "ETF": etf_code,
                        "成功": success_count
                    })

            # 插入剩余数据
            if self.data_processor.get_buffer_size() > 0:
                batch_success = self.data_processor.flush('instrument_daily')
                success_count += batch_success

            progress_bar.close()
            self.logger.info(f"按ETF遍历获取分块数据完成: {success_count}条")
            return success_count

        except Exception as e:
            self.logger.error(f"按ETF遍历获取分块数据失败: {e}")
            return 0

    def get_count(self) -> int:
        """
        从Tushare API获取ETF数量

        Returns:
            int: ETF数量
        """
        try:
            # 获取最新交易日
            latest_date = self._get_latest_trade_date()

            self.logger.info(f"通过{latest_date}日线数据统计ETF数量")

            # 获取该日ETF日线数据来统计数量
            df = self.pro.fund_daily(trade_date=latest_date)

            if df.empty:
                self.logger.warning(f"未获取到{latest_date}的ETF数据，使用基金基本信息统计")
                df_basic = self.pro.fund_basic(market='E', status='L')
                etf_count = len(df_basic) if not df_basic.empty else 0
            else:
                etf_count = len(df)

            self.logger.info(f"从API获取到ETF数量: {etf_count}")
            return etf_count

        except Exception as e:
            self.logger.error(f"获取ETF数量失败: {e}")
            return 0

    def _get_latest_trade_date(self) -> str:
        """
        获取最新交易日

        Returns:
            str: 最新交易日(YYYYMMDD格式)
        """
        try:
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

            latest_date = df['cal_date'].iloc[0]
            self.logger.info(f"获取到最新交易日: {latest_date}")
            return latest_date

        except Exception as e:
            self.logger.error(f"获取最新交易日失败: {e}")
            return datetime.now().strftime('%Y%m%d')
