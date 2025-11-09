"""
成交量确认类过滤器

包含:
- VolumeFilter: 成交量放大确认过滤器
"""

import pandas as pd
from .base import BaseFilter


class VolumeFilter(BaseFilter):
    """
    成交量放大确认过滤器

    过滤逻辑：金叉时成交量需高于均值

    参数:
        period: 成交量均值计算周期，默认20
        ratio: 成交量放大倍数，默认1.2（即放大20%）
    """

    def __init__(self, enabled=True, period=20, ratio=1.2):
        super().__init__(enabled=enabled)
        self.period = period
        self.ratio = ratio

    def filter_signal(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数

        Returns:
            bool: True表示信号通过过滤
        """
        # 只过滤买入信号（金叉）
        if signal_type != 'buy':
            return True

        # 获取成交量数据
        if not hasattr(strategy, 'data') or not hasattr(strategy.data, 'Volume'):
            return True  # 无成交量数据，放行

        volume = strategy.data.Volume

        # 检查数据长度
        if len(volume) < self.period + 1:
            return False  # 数据不足，不交易

        # 计算成交量均值
        volume_series = pd.Series(volume)
        volume_ma = volume_series.rolling(window=self.period).mean()

        # 获取当前成交量和均值
        current_volume = volume[-1]
        current_ma = volume_ma.iloc[-1]

        if pd.isna(current_ma) or current_ma == 0:
            return False

        # 检查成交量是否放大
        return current_volume > current_ma * self.ratio
