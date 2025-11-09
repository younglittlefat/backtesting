"""
MACD金叉死叉策略 (MACD Crossover Strategy)

MACD (Moving Average Convergence Divergence) 是经典的动量趋势跟踪指标，
通过快速EMA和慢速EMA的差值来捕捉趋势变化。

策略逻辑:
- MACD线上穿信号线 -> 买入信号（金叉）
- MACD线下穿信号线 -> 卖出信号（死叉）

Phase 1: 基础金叉死叉信号（当前版本）
Phase 2: 信号质量过滤器（ADX、成交量、斜率、确认）
Phase 3: 连续止损保护
Phase 4: 增强信号（零轴交叉、双重金叉、背离）
"""

import sys
from pathlib import Path
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover

# 添加项目根目录到路径（用于直接运行）
if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from strategies.filters import ADXFilter, VolumeFilter


def MACD(close, fast_period=12, slow_period=26, signal_period=9):
    """
    计算MACD指标

    MACD由三个部分组成:
    1. MACD线 (DIF): 快速EMA - 慢速EMA
    2. 信号线 (DEA): MACD线的EMA
    3. 柱状图 (Histogram): MACD线 - 信号线

    Args:
        close: 收盘价序列
        fast_period: 快速EMA周期 (默认12)
        slow_period: 慢速EMA周期 (默认26)
        signal_period: 信号线EMA周期 (默认9)

    Returns:
        tuple: (macd_line, signal_line, histogram)
    """
    close_series = pd.Series(close)

    # 计算快速和慢速EMA
    ema_fast = close_series.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close_series.ewm(span=slow_period, adjust=False).mean()

    # MACD线 (DIF)
    macd_line = ema_fast - ema_slow

    # 信号线 (DEA)
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

    # 柱状图
    histogram = macd_line - signal_line

    return macd_line.values, signal_line.values, histogram.values


class MACDSlopeFilter:
    """
    MACD斜率过滤器

    过滤逻辑：买入信号时MACD线必须向上（斜率为正）

    参数:
        enabled: 是否启用过滤器
        lookback: 斜率计算的回溯周期，默认5
    """

    def __init__(self, enabled=True, lookback=5):
        self.enabled = enabled
        self.lookback = lookback

    def __call__(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数，应包含 'macd_line'

        Returns:
            bool: True表示信号通过过滤
        """
        if not self.enabled:
            return True

        # 只过滤买入信号（金叉）
        if signal_type != 'buy':
            return True

        macd_line = kwargs.get('macd_line')

        if macd_line is None:
            # 尝试从策略实例获取
            if hasattr(strategy, 'macd_line'):
                macd_line = strategy.macd_line
            else:
                return True  # 无法获取数据，放行

        # 检查数据长度
        if len(macd_line) < self.lookback + 1:
            return False  # 数据不足，不交易

        # 计算MACD线斜率
        macd_slope = (macd_line[-1] - macd_line[-self.lookback - 1]) / self.lookback

        # 判断斜率是否向上
        return macd_slope > 0


class MACDConfirmationFilter:
    """
    MACD持续确认过滤器（防假突破）

    过滤逻辑：金叉后需持续N根K线MACD线持续在信号线上方才确认

    参数:
        enabled: 是否启用过滤器
        confirm_bars: 确认所需的K线数量，默认2
    """

    def __init__(self, enabled=True, confirm_bars=2):
        self.enabled = enabled
        self.confirm_bars = confirm_bars

    def __call__(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数，应包含 'macd_line' 和 'signal_line'

        Returns:
            bool: True表示信号通过过滤
        """
        if not self.enabled:
            return True

        # 只过滤买入信号（金叉）
        if signal_type != 'buy':
            return True

        macd_line = kwargs.get('macd_line')
        signal_line = kwargs.get('signal_line')

        if macd_line is None or signal_line is None:
            # 尝试从策略实例获取
            if hasattr(strategy, 'macd_line') and hasattr(strategy, 'signal_line'):
                macd_line = strategy.macd_line
                signal_line = strategy.signal_line
            else:
                return True  # 无法获取数据，放行

        # 检查数据长度
        if len(macd_line) < self.confirm_bars or len(signal_line) < self.confirm_bars:
            return False  # 数据不足，不交易

        # 检查过去N根K线，MACD线是否持续在信号线上方
        cross_bars = 0
        for i in range(1, self.confirm_bars + 1):
            if macd_line[-i] > signal_line[-i]:
                cross_bars += 1
            else:
                break  # 如果有一根不满足，立即中断

        # 只有连续N根K线都满足条件才通过
        return cross_bars >= self.confirm_bars


class MacdCross(Strategy):
    """
    MACD金叉死叉策略（功能完整版）

    支持:
    - Phase 1: 基础金叉死叉信号 ✅
    - Phase 2: 信号质量过滤器（ADX、成交量、斜率、确认）🔲
    - Phase 3: 连续止损保护 🔲
    - Phase 4: 增强信号（零轴交叉、双重金叉、背离）🔲

    参数:
        fast_period: 快速EMA周期 (默认12)
        slow_period: 慢速EMA周期 (默认26)
        signal_period: 信号线EMA周期 (默认9)

        # Phase 2: 过滤器开关
        enable_adx_filter: 启用ADX趋势强度过滤器 (默认False)
        enable_volume_filter: 启用成交量确认过滤器 (默认False)
        enable_slope_filter: 启用MACD斜率过滤器 (默认False)
        enable_confirm_filter: 启用持续确认过滤器 (默认False)

        # Phase 2: 过滤器参数
        adx_period: ADX计算周期 (默认14)
        adx_threshold: ADX阈值 (默认25)
        volume_period: 成交量均值周期 (默认20)
        volume_ratio: 成交量放大倍数 (默认1.2)
        slope_lookback: 斜率回溯周期 (默认5)
        confirm_bars: 持续确认K线数 (默认2)

        # Phase 3: 止损保护
        enable_loss_protection: 启用连续止损保护 (默认False)
        max_consecutive_losses: 连续亏损次数阈值 (默认3)
        pause_bars: 暂停交易K线数 (默认10)

        # Phase 4: 增强信号
        enable_zero_cross: 启用零轴交叉信号 (默认False)
        enable_double_golden: 启用双重金叉信号 (默认False)
        enable_divergence: 启用背离信号检测 (默认False)
        divergence_lookback: 背离检测回溯周期 (默认20)
    """

    # === Phase 1: 核心参数 ===
    fast_period = 12
    slow_period = 26
    signal_period = 9

    # === Phase 2: 过滤器开关（后续实现） ===
    enable_adx_filter = False
    enable_volume_filter = False
    enable_slope_filter = False
    enable_confirm_filter = False

    # 过滤器参数
    adx_period = 14
    adx_threshold = 25
    volume_period = 20
    volume_ratio = 1.2
    slope_lookback = 5
    confirm_bars = 2

    # === Phase 3: 止损保护（后续实现） ===
    enable_loss_protection = False
    max_consecutive_losses = 3
    pause_bars = 10

    # === Phase 4: 增强信号（后续实现） ===
    enable_zero_cross = False
    enable_double_golden = False
    enable_divergence = False
    divergence_lookback = 20

    def init(self):
        """
        初始化策略

        计算MACD指标并初始化过滤器
        """
        # 计算MACD指标
        macd_line, signal_line, histogram = self.I(
            MACD,
            self.data.Close,
            self.fast_period,
            self.slow_period,
            self.signal_period
        )

        self.macd_line = macd_line
        self.signal_line = signal_line
        self.histogram = histogram

        # Phase 2: 初始化过滤器
        self.adx_filter = ADXFilter(
            enabled=self.enable_adx_filter,
            period=self.adx_period,
            threshold=self.adx_threshold
        )
        self.volume_filter = VolumeFilter(
            enabled=self.enable_volume_filter,
            period=self.volume_period,
            ratio=self.volume_ratio
        )
        self.slope_filter = MACDSlopeFilter(
            enabled=self.enable_slope_filter,
            lookback=self.slope_lookback
        )
        self.confirm_filter = MACDConfirmationFilter(
            enabled=self.enable_confirm_filter,
            confirm_bars=self.confirm_bars
        )

        # Phase 3: 初始化止损追踪（后续实现）

    def _apply_filters(self, signal_type):
        """
        应用所有启用的过滤器

        Args:
            signal_type: 'buy' 或 'sell'

        Returns:
            bool: True表示信号通过所有过滤器
        """
        filters = [
            self.adx_filter,
            self.volume_filter,
            self.slope_filter,
            self.confirm_filter
        ]

        # 准备上下文信息
        kwargs = {
            'macd_line': self.macd_line,
            'signal_line': self.signal_line
        }

        # 检查所有过滤器
        for f in filters:
            if not f(self, signal_type, **kwargs):
                return False

        return True

    def next(self):
        """
        每个交易日调用一次

        根据MACD金叉死叉信号和过滤器决定买入或卖出
        """
        # Phase 3: 检查止损状态（后续实现）

        # MACD金叉 - 买入信号
        if crossover(self.macd_line, self.signal_line):
            # Phase 2: 应用过滤器
            if not self._apply_filters('buy'):
                return  # 信号被过滤，不交易

            # Phase 4: 检查增强信号（后续实现）

            # 如果有仓位，先平仓
            if self.position:
                self.position.close()

            # 买入 - 使用90%的可用资金，避免保证金不足
            self.buy(size=0.90)

        # MACD死叉 - 卖出信号
        elif crossover(self.signal_line, self.macd_line):
            # Phase 2: 应用过滤器
            if not self._apply_filters('sell'):
                return  # 信号被过滤，不交易

            # Phase 4: 检查增强信号（后续实现）

            # 如果有仓位，先平仓
            if self.position:
                self.position.close()

            # 卖出（做空）- 使用90%的可用资金
            self.sell(size=0.90)


# 参数优化配置 - Phase 1基础参数
OPTIMIZE_PARAMS = {
    'fast_period': range(8, 21, 2),      # 快速EMA: 8, 10, 12, ..., 20
    'slow_period': range(20, 41, 2),     # 慢速EMA: 20, 22, 24, ..., 40
    'signal_period': range(6, 15, 2),    # 信号线: 6, 8, 10, ..., 14
}

# 参数约束: 快速周期必须小于慢速周期
CONSTRAINTS = lambda p: p.fast_period < p.slow_period


if __name__ == '__main__':
    """测试策略"""
    from backtesting import Backtest
    from backtesting.test import GOOG

    print("=" * 60)
    print("测试MACD金叉死叉策略")
    print("=" * 60)
    print()

    # 测试1: 默认参数
    print("测试1: 默认参数 (12, 26, 9)")
    bt = Backtest(GOOG, MacdCross, cash=10000, commission=0.002)
    stats = bt.run()
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    # 测试2: 短期参数（更灵敏）
    print("测试2: 短期参数 (8, 20, 6)")
    bt = Backtest(GOOG, MacdCross, cash=10000, commission=0.002)
    stats = bt.run(fast_period=8, slow_period=20, signal_period=6)
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    # 测试3: 长期参数（更平滑）
    print("测试3: 长期参数 (15, 30, 10)")
    bt = Backtest(GOOG, MacdCross, cash=10000, commission=0.002)
    stats = bt.run(fast_period=15, slow_period=30, signal_period=10)
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)
