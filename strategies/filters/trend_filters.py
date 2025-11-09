"""
趋势确认类过滤器

包含:
- SlopeFilter: 均线斜率过滤器
- ADXFilter: ADX趋势强度过滤器
"""

import numpy as np
import pandas as pd
from .base import BaseFilter


class SlopeFilter(BaseFilter):
    """
    均线斜率过滤器

    过滤逻辑：金叉时短均线和长均线必须同时向上

    参数:
        lookback: 斜率计算的回溯周期，默认5
        require_both: 是否要求短期和长期均线都向上，默认True
    """

    def __init__(self, enabled=True, lookback=5, require_both=True):
        super().__init__(enabled=enabled)
        self.lookback = lookback
        self.require_both = require_both

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
        if len(sma_short) < self.lookback + 1 or len(sma_long) < self.lookback + 1:
            return False  # 数据不足，不交易

        # 计算短期均线斜率
        short_slope = (sma_short[-1] - sma_short[-self.lookback - 1]) / self.lookback

        # 计算长期均线斜率
        long_slope = (sma_long[-1] - sma_long[-self.lookback - 1]) / self.lookback

        # 判断斜率是否向上
        if self.require_both:
            return short_slope > 0 and long_slope > 0
        else:
            return short_slope > 0


class ADXFilter(BaseFilter):
    """
    ADX趋势强度过滤器

    过滤逻辑：ADX > 阈值才交易，确保趋势足够强

    参数:
        period: ADX计算周期，默认14
        threshold: ADX阈值，默认25
    """

    def __init__(self, enabled=True, period=14, threshold=25):
        super().__init__(enabled=enabled)
        self.period = period
        self.threshold = threshold

    def _calculate_adx(self, high, low, close, period):
        """
        计算ADX指标

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 计算周期

        Returns:
            ADX值序列
        """
        # 转换为pandas Series以便计算
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)

        # 计算+DM和-DM
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

        # 计算TR (True Range)
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)

        # 平滑+DM, -DM和TR
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr

        # 计算DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # 计算ADX (DX的移动平均)
        adx = dx.rolling(window=period).mean()

        return adx

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
        # 获取价格数据
        if not hasattr(strategy, 'data'):
            return True

        high = strategy.data.High
        low = strategy.data.Low
        close = strategy.data.Close

        # 检查数据长度
        min_length = self.period * 2 + 1
        if len(high) < min_length:
            return False

        # 计算ADX
        adx = self._calculate_adx(high, low, close, self.period)

        # 获取当前ADX值
        current_adx = adx.iloc[-1]

        # 检查ADX是否超过阈值
        if pd.isna(current_adx):
            return False

        return current_adx > self.threshold
