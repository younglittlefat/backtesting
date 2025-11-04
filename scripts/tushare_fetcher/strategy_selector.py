"""
策略选择器

根据时间范围和数据量决定最优获取策略
"""

import logging
from typing import Dict, Optional


class StrategySelector:
    """策略选择器"""

    def __init__(self, etf_fetcher, fund_fetcher, base_fetcher, logger: Optional[logging.Logger] = None):
        """
        初始化策略选择器

        Args:
            etf_fetcher: ETF抓取器实例
            fund_fetcher: 基金抓取器实例
            base_fetcher: 基础抓取器实例（用于获取交易日历）
            logger: 日志记录器
        """
        self.etf_fetcher = etf_fetcher
        self.fund_fetcher = fund_fetcher
        self.base_fetcher = base_fetcher
        self.logger = logger or logging.getLogger(__name__)

    def determine_fetch_strategy(self, start_date: str, end_date: str,
                                 data_type: Optional[str] = None,
                                 forced_by_instrument: bool = False) -> Dict[str, str]:
        """
        根据时间范围和工具数量决定获取策略

        Args:
            start_date: 开始日期
            end_date: 结束日期
            data_type: 数据类型，None表示处理所有类型
            forced_by_instrument: 强制使用by_instrument模式

        Returns:
            Dict[str, str]: 各数据类型的策略 {'etf': 'by_date', 'fund': 'by_instrument', 'index': 'batch'}
        """
        # 计算交易日天数
        trading_dates = self.base_fetcher.get_trading_calendar(start_date, end_date)
        days_count = len(trading_dates)

        strategies = {}

        # 确定需要处理的数据类型
        if data_type is None:
            process_types = ['etf', 'fund']
        elif data_type in ['etf', 'fund']:
            process_types = [data_type]
        else:
            # index类型，使用批量优化
            strategies['index'] = 'batch'
            return strategies

        # 为每种数据类型确定策略
        for dtype in process_types:
            if dtype == 'etf':
                instrument_count = self.etf_fetcher.get_count()
                type_name = "ETF"
            elif dtype == 'fund':
                instrument_count = self.fund_fetcher.get_count()
                type_name = "基金"
            else:
                continue

            if forced_by_instrument:
                strategies[dtype] = 'by_instrument'
                self.logger.info(f"{type_name}数据获取策略: by_instrument (强制模式)")
            elif instrument_count == 0:
                self.logger.warning(f"获取{type_name}数量失败，使用按日期遍历方式")
                strategies[dtype] = 'by_date'
            else:
                # Trade off决策：天数 > 工具数量时，按工具遍历更高效
                strategy = 'by_instrument' if days_count > instrument_count else 'by_date'
                strategies[dtype] = strategy

                self.logger.info(f"{type_name}数据获取策略: {strategy} "
                               f"(交易日: {days_count}天, 工具数: {instrument_count}个)")

        # 指数数据始终使用批量方式（已优化）
        if data_type is None or data_type == 'index':
            strategies['index'] = 'batch'

        return strategies
