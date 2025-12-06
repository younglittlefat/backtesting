"""
指数数据抓取器

处理指数基本信息和日线数据的获取
"""

import time
from typing import List, Optional
from tqdm import tqdm
from .base_fetcher import BaseFetcher
from .rate_limiter import RateLimiter
from .data_processor import DataProcessor


# 常用基准指数列表（精选大盘指数）
# 这些指数用于策略对标和基准收益比较
BENCHMARK_INDICES = {
    # CSI指数（中证指数公司）- 最常用的基准指数
    '000300.SH': '沪深300',      # 最常用基准
    '000905.SH': '中证500',      # 中盘股基准
    '000852.SH': '中证1000',     # 小盘股基准
    '000985.SH': '中证全指',     # 全市场基准
    '000016.SH': '上证50',       # 大盘蓝筹基准
    # SSE指数（上交所）
    '000001.SH': '上证综指',     # 上海市场整体
    # SZSE指数（深交所）
    '399001.SZ': '深证成指',     # 深圳市场主要成分
    '399006.SZ': '创业板指',     # 创业板基准
    '399673.SZ': '创业板50',     # 创业板龙头
}


class IndexFetcher(BaseFetcher):
    """指数数据抓取器"""

    # 指数接口频率限制：每分钟500次
    INDEX_API_RATE_LIMIT = 500

    def __init__(self, pro_api, db_manager, rate_limiter: RateLimiter,
                 data_processor: DataProcessor, logger=None):
        """
        初始化指数抓取器

        Args:
            pro_api: Tushare Pro API实例
            db_manager: 数据库管理器
            rate_limiter: 频率限制器（会被忽略，使用独立的指数接口限流器）
            data_processor: 数据处理器
            logger: 日志记录器
        """
        super().__init__(pro_api, db_manager, logger)
        # 使用独立的频率限制器，指数接口限制为500次/分钟
        self.rate_limiter = RateLimiter(
            max_requests_per_minute=self.INDEX_API_RATE_LIMIT,
            logger=self.logger
        )
        self.data_processor = data_processor

    def fetch_basic_info(self) -> int:
        """
        获取指数基本信息

        Returns:
            int: 成功获取的指数数量
        """
        try:
            self.logger.info("开始获取指数基本信息")

            success_count = 0
            markets = ['SSE', 'SZSE', 'CSI', 'SW']

            market_progress = tqdm(markets, desc="获取指数市场", unit="个市场")

            for market in market_progress:
                try:
                    self.logger.info(f"获取{market}指数信息")
                    market_progress.set_description(f"获取{market}指数")

                    # 频率限制检查
                    self.rate_limiter.check_and_wait()
                    df = self.pro.index_basic(market=market)
                    self.rate_limiter.increment()

                    if df.empty:
                        self.logger.warning(f"{market}指数信息为空")
                        continue

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

                            index_progress.set_postfix({"市场成功": market_success, "总成功": success_count})

                        except Exception as e:
                            self.logger.error(f"添加指数基本信息失败 {row.get('ts_code', 'unknown')}: {e}")
                            continue

                    index_progress.close()
                    market_progress.set_postfix({"总成功": success_count})

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

    def fetch_daily_optimized(self, start_date: str, end_date: str, max_retries: int = 3) -> int:
        """
        优化后的指数日线数据获取（批量模式）

        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            max_retries: 最大重试次数

        Returns:
            int: 成功获取的数据条数
        """
        index_codes = self.db_manager.get_instrument_basic(data_type='index')
        if not index_codes:
            self.logger.warning("未找到指数基本信息，请先获取指数基本信息")
            return 0

        self.logger.info(f"开始批量获取指数数据: {start_date} - {end_date}, 共{len(index_codes)}个指数")

        # 重置 data_processor 的成功计数
        self.data_processor.success_count = 0

        progress_bar = tqdm(index_codes, desc="批量获取指数数据", unit="个指数")

        for index_info in progress_bar:
            ts_code = index_info['ts_code']

            for retry in range(max_retries):
                try:
                    # 频率限制检查：在请求前检查是否需要等待
                    self.rate_limiter.check_and_wait()

                    # 一次性获取整个日期范围的数据
                    df = self.pro.index_daily(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date
                    )

                    # 记录本次请求
                    self.rate_limiter.increment()

                    if df.empty:
                        break

                    for _, row in df.iterrows():
                        try:
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

                            data = self._clean_data(data)
                            # add_data 内部会在缓冲区满时自动 flush
                            self.data_processor.add_data(data)

                        except Exception as e:
                            self.logger.error(f"处理指数数据失败 {row.get('ts_code', 'unknown')}: {e}")
                            continue

                    break

                except Exception as e:
                    self.logger.error(f"获取指数数据失败 {ts_code} (第{retry+1}次): {e}")
                    # 如果是频率限制错误，等待后重试
                    if '每分钟最多访问' in str(e):
                        self.logger.warning(f"触发频率限制，等待65秒后重试...")
                        time.sleep(65)
                        self.rate_limiter.reset()
                    elif retry < max_retries - 1:
                        time.sleep(0.5)  # 增加重试间隔
                    continue

            progress_bar.set_postfix({"已处理": self.data_processor.get_success_count(), "请求数": self.rate_limiter.get_count()})

        # 插入剩余数据
        if self.data_processor.get_buffer_size() > 0:
            self.data_processor.flush('instrument_daily')

        success_count = self.data_processor.get_success_count()
        progress_bar.close()
        self.logger.info(f"指数数据批量获取完成: {start_date} - {end_date}，成功{success_count}条")
        return success_count

    def fetch_benchmark_basic_info(self) -> int:
        """
        仅获取基准指数的基本信息

        Returns:
            int: 成功获取的指数数量
        """
        try:
            self.logger.info(f"开始获取基准指数基本信息，共{len(BENCHMARK_INDICES)}个")
            success_count = 0

            progress_bar = tqdm(BENCHMARK_INDICES.items(), desc="获取基准指数信息", unit="个")

            for ts_code, name in progress_bar:
                try:
                    # 频率限制检查
                    self.rate_limiter.check_and_wait()

                    # 获取单个指数的基本信息
                    df = self.pro.index_basic(ts_code=ts_code)
                    self.rate_limiter.increment()

                    if df.empty:
                        self.logger.warning(f"指数 {ts_code} ({name}) 基本信息为空")
                        continue

                    row = df.iloc[0]
                    data = {
                        'symbol': ts_code.split('.')[0],
                        'market': 'SH' if ts_code.endswith('.SH') else 'SZ',
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

                    data = self._clean_data(data)

                    success = self.db_manager.add_instrument_basic(
                        data_type='index',
                        ts_code=ts_code,
                        name=row.get('name', name),
                        **data
                    )

                    if success:
                        success_count += 1

                    progress_bar.set_postfix({"成功": success_count})

                except Exception as e:
                    self.logger.error(f"获取基准指数基本信息失败 {ts_code}: {e}")
                    continue

            progress_bar.close()
            self.logger.info(f"基准指数基本信息获取完成，成功{success_count}条")
            return success_count

        except Exception as e:
            self.logger.error(f"获取基准指数基本信息失败: {e}")
            return 0

    def fetch_benchmark_daily(self, start_date: str, end_date: str, max_retries: int = 3) -> int:
        """
        仅获取基准指数的日线数据

        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)
            max_retries: 最大重试次数

        Returns:
            int: 成功获取的数据条数
        """
        self.logger.info(f"开始获取基准指数日线数据: {start_date} - {end_date}, 共{len(BENCHMARK_INDICES)}个")

        # 重置 data_processor 的成功计数
        self.data_processor.success_count = 0

        progress_bar = tqdm(BENCHMARK_INDICES.items(), desc="获取基准指数日线", unit="个")

        for ts_code, name in progress_bar:
            for retry in range(max_retries):
                try:
                    # 频率限制检查
                    self.rate_limiter.check_and_wait()

                    df = self.pro.index_daily(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date
                    )
                    self.rate_limiter.increment()

                    if df.empty:
                        self.logger.debug(f"指数 {ts_code} ({name}) 在 {start_date}-{end_date} 无数据")
                        break

                    for _, row in df.iterrows():
                        try:
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

                            data = self._clean_data(data)
                            # add_data 内部会在缓冲区满时自动 flush
                            self.data_processor.add_data(data)

                        except Exception as e:
                            self.logger.error(f"处理指数数据失败 {row.get('ts_code', 'unknown')}: {e}")
                            continue

                    break

                except Exception as e:
                    self.logger.error(f"获取基准指数数据失败 {ts_code} (第{retry+1}次): {e}")
                    if '每分钟最多访问' in str(e):
                        self.logger.warning(f"触发频率限制，等待65秒后重试...")
                        time.sleep(65)
                        self.rate_limiter.reset()
                    elif retry < max_retries - 1:
                        time.sleep(0.5)
                    continue

            progress_bar.set_postfix({"已处理": self.data_processor.get_success_count(), "请求数": self.rate_limiter.get_count()})

        # 插入剩余数据
        if self.data_processor.get_buffer_size() > 0:
            self.data_processor.flush('instrument_daily')

        success_count = self.data_processor.get_success_count()
        progress_bar.close()
        self.logger.info(f"基准指数日线数据获取完成: {start_date} - {end_date}，成功{success_count}条")
        return success_count
