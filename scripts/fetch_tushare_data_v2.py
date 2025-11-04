"""
Tushare数据获取脚本 V2.0 (重构版)

使用模块化架构获取ETF、指数和公募基金的基本信息和历史行情数据

使用方法:
    python scripts/fetch_tushare_data_v2.py --start_date 20240101 --end_date 20240131 --daily_data --data_type etf
    python scripts/fetch_tushare_data_v2.py --start_date 20240101 --end_date 20240131 --daily_data --ts_code 159300.SZ
"""

import sys
import os
import logging
import argparse

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

import tushare as ts
from common.mysql_manager import MySQLManager
from tushare_fetcher import (
    ETFFetcher, IndexFetcher, FundFetcher,
    StrategySelector, RateLimiter, DataProcessor, BaseFetcher
)


class TushareDataFetcherV2:
    """Tushare数据获取器 V2.0 (重构版)"""

    def __init__(self, token: str, mode: str = 'append', data_type_filter: str = None,
                 batch_size: int = 10000, forced_by_instrument: bool = False):
        """
        初始化数据获取器

        Args:
            token: Tushare token
            mode: 数据处理模式 ('append', 'replace', 'clean_append')
            data_type_filter: 数据类型过滤 ('etf', 'index', 'fund')
            batch_size: 批处理大小
            forced_by_instrument: 强制使用by_instrument模式
        """
        self.logger = logging.getLogger(__name__)
        self.mode = mode
        self.data_type_filter = data_type_filter
        self.forced_by_instrument = forced_by_instrument

        # 初始化Tushare
        ts.set_token(token)
        self.pro = ts.pro_api()

        # 初始化数据库管理器
        self.db_manager = MySQLManager()

        # 初始化工具组件
        self.rate_limiter = RateLimiter(max_requests_per_minute=400, logger=self.logger)
        self.data_processor = DataProcessor(self.db_manager, batch_size, logger=self.logger)
        self.base_fetcher = BaseFetcher(self.pro, self.db_manager, logger=self.logger)

        # 初始化各数据类型抓取器
        self.etf_fetcher = ETFFetcher(self.pro, self.db_manager, self.rate_limiter,
                                      self.data_processor, logger=self.logger)
        self.index_fetcher = IndexFetcher(self.pro, self.db_manager, self.rate_limiter,
                                         self.data_processor, logger=self.logger)
        self.fund_fetcher = FundFetcher(self.pro, self.db_manager, self.rate_limiter,
                                       self.data_processor, logger=self.logger)

        # 初始化策略选择器
        self.strategy_selector = StrategySelector(
            self.etf_fetcher, self.fund_fetcher, self.base_fetcher, logger=self.logger
        )

        self.logger.info(f"TushareDataFetcherV2 初始化完成 - 模式: {mode}, "
                        f"数据类型: {data_type_filter}, 批处理: {batch_size}")

    def should_process_data_type(self, data_type: str) -> bool:
        """检查是否应该处理指定的数据类型"""
        return self.data_type_filter is None or self.data_type_filter == data_type

    def prepare_data_mode(self, start_date: str, end_date: str):
        """根据数据处理模式准备数据环境"""
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

    def fetch_basic_info(self):
        """获取基本信息"""
        results = {}

        if self.should_process_data_type('etf'):
            results['etf'] = self.etf_fetcher.fetch_basic_info()
        else:
            results['etf'] = 0

        if self.should_process_data_type('index'):
            results['index'] = self.index_fetcher.fetch_basic_info()
        else:
            results['index'] = 0

        if self.should_process_data_type('fund'):
            results['fund'] = self.fund_fetcher.fetch_basic_info()
        else:
            results['fund'] = 0

        return results

    def fetch_daily_data(self, start_date: str, end_date: str, ts_code: str = None):
        """
        获取日线数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            ts_code: 指定标的代码（可选，用于单标的测试）
        """
        results = {'etf': 0, 'index': 0, 'fund': 0}

        # 如果指定了ts_code，直接使用by_instrument模式
        if ts_code:
            self.logger.info(f"单标的测试模式: {ts_code}")
            if self.should_process_data_type('etf'):
                etf_count = self.etf_fetcher.fetch_daily_by_instrument_chunked(
                    start_date, end_date, ts_code=ts_code
                )
                results['etf'] = etf_count
            return results

        # 获取策略
        strategies = self.strategy_selector.determine_fetch_strategy(
            start_date, end_date, self.data_type_filter, self.forced_by_instrument
        )
        self.logger.info(f"数据获取策略: {strategies}")

        # 处理ETF数据
        if 'etf' in strategies:
            if strategies['etf'] == 'by_instrument' or self.forced_by_instrument:
                self.logger.info("使用按ETF工具遍历策略（支持分块）")
                etf_count = self.etf_fetcher.fetch_daily_by_instrument_chunked(start_date, end_date)
                results['etf'] = etf_count
            # 注：by_date模式暂未实现

        # 处理指数数据
        if 'index' in strategies and strategies['index'] == 'batch':
            self.logger.info("开始批量获取指数数据")
            index_count = self.index_fetcher.fetch_daily_optimized(start_date, end_date)
            results['index'] = index_count

        # 处理基金数据（暂未实现）
        results['fund'] = 0

        return results


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/fetch_tushare_data_v2.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='从Tushare获取ETF、指数、基金数据 (重构版V2)')
    parser.add_argument('--start_date', required=True, help='开始日期(YYYYMMDD格式)')
    parser.add_argument('--end_date', required=True, help='结束日期(YYYYMMDD格式)')
    parser.add_argument('--basic_info', action='store_true', help='是否获取基本信息')
    parser.add_argument('--daily_data', action='store_true', help='是否获取日线数据')
    parser.add_argument('--mode', choices=['append', 'replace', 'clean_append'],
                       default='append', help='数据处理模式')
    parser.add_argument('--data_type', choices=['etf', 'index', 'fund'],
                       help='数据类型过滤，为空时处理所有类型')
    parser.add_argument('--batch_size', type=int, default=10000, help='批处理大小')
    parser.add_argument('--forced_by_instrument', action='store_true',
                       help='强行使用遍历每个指数获取全周期数据的模式')
    parser.add_argument('--ts_code', type=str, help='指定单个标的代码（用于测试）')

    args = parser.parse_args()

    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("=== Tushare数据获取开始 (V2重构版) ===")
    logger.info(f"参数: start_date={args.start_date}, end_date={args.end_date}, "
               f"mode={args.mode}, data_type={args.data_type}, ts_code={args.ts_code}")

    try:
        # 读取token
        token = '18e20abc9ab15f381594da84aac654a11890ecf119a35e2ed70283f0'

        # 初始化数据获取器
        fetcher = TushareDataFetcherV2(
            token, mode=args.mode, data_type_filter=args.data_type,
            batch_size=args.batch_size, forced_by_instrument=args.forced_by_instrument
        )

        # 根据模式准备数据环境
        fetcher.prepare_data_mode(args.start_date, args.end_date)

        # 获取基本信息
        if args.basic_info:
            logger.info("开始获取基本信息")
            basic_results = fetcher.fetch_basic_info()
            logger.info(f"基本信息获取完成: {basic_results}")

        # 获取日线数据
        if args.daily_data:
            logger.info(f"开始获取日线数据: {args.start_date} - {args.end_date}")
            daily_results = fetcher.fetch_daily_data(
                args.start_date, args.end_date, ts_code=args.ts_code
            )
            logger.info(f"日线数据获取完成: {daily_results}")

        logger.info("=== Tushare数据获取完成 (V2重构版) ===")

    except Exception as e:
        logger.error(f"数据获取过程中发生异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
