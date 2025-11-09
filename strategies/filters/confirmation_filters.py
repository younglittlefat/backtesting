"""
信号确认类过滤器

包含:
- ConfirmationFilter: 持续确认过滤器（防假突破）
"""

from .base import BaseFilter


class ConfirmationFilter(BaseFilter):
    """
    持续确认过滤器（防假突破）

    过滤逻辑：金叉后需持续N根K线才确认

    参数:
        confirm_bars: 确认所需的K线数量，默认3
    """

    def __init__(self, enabled=True, confirm_bars=3):
        super().__init__(enabled=enabled)
        self.confirm_bars = confirm_bars

    def filter_signal(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数，应包含 'sma_short' 和 'sma_long'

        Returns:
            bool: True表示信号通过过滤
        """
        # 只过滤买入信号（金叉）
        if signal_type != 'buy':
            return True

        sma_short = kwargs.get('sma_short')
        sma_long = kwargs.get('sma_long')

        if sma_short is None or sma_long is None:
            # 如果没有提供均线数据，尝试从策略实例获取
            if hasattr(strategy, 'sma1') and hasattr(strategy, 'sma2'):
                sma_short = strategy.sma1
                sma_long = strategy.sma2
            else:
                return True  # 无法获取数据，放行

        # 检查数据长度
        if len(sma_short) < self.confirm_bars or len(sma_long) < self.confirm_bars:
            return False  # 数据不足，不交易

        # 检查过去N根K线，短均线是否持续在长均线上方
        cross_bars = 0
        for i in range(1, self.confirm_bars + 1):
            if sma_short[-i] > sma_long[-i]:
                cross_bars += 1
            else:
                break  # 如果有一根不满足，立即中断

        # 只有连续N根K线都满足条件才通过
        return cross_bars >= self.confirm_bars
