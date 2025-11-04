"""
指数数据抓取器

处理指数基本信息和日线数据的获取
"""

import time
from tqdm import tqdm
from .base_fetcher import BaseFetcher
from .rate_limiter import RateLimiter
from .data_processor import DataProcessor


class IndexFetcher(BaseFetcher):
    """指数数据抓取器"""

    def __init__(self, pro_api, db_manager, rate_limiter: RateLimiter,
                 data_processor: DataProcessor, logger=None):
        """
        初始化指数抓取器

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

                    df = self.pro.index_basic(market=market)

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
        success_count = 0

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
                            self.data_processor.add_data(data)

                        except Exception as e:
                            self.logger.error(f"处理指数数据失败 {row.get('ts_code', 'unknown')}: {e}")
                            continue

                    # 批量插入
                    if self.data_processor.get_buffer_size() >= self.data_processor.batch_size:
                        batch_success = self.data_processor.flush('instrument_daily')
                        success_count += batch_success

                    break

                except Exception as e:
                    self.logger.error(f"获取指数数据失败 {ts_code} (第{retry+1}次): {e}")
                    if retry < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    else:
                        break

            progress_bar.set_postfix({"成功": success_count})
            time.sleep(0.001)

        # 插入剩余数据
        if self.data_processor.get_buffer_size() > 0:
            batch_success = self.data_processor.flush('instrument_daily')
            success_count += batch_success

        progress_bar.close()
        self.logger.info(f"指数数据批量获取完成: {start_date} - {end_date}，成功{success_count}条")
        return success_count
