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

        计算MACD指标
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

        # Phase 2: 初始化过滤器（后续实现）
        # Phase 3: 初始化止损追踪（后续实现）

    def next(self):
        """
        每个交易日调用一次

        根据MACD金叉死叉信号决定买入或卖出
        """
        # Phase 3: 检查止损状态（后续实现）

        # MACD金叉 - 买入信号
        if crossover(self.macd_line, self.signal_line):
            # Phase 2: 应用过滤器（后续实现）
            # Phase 4: 检查增强信号（后续实现）

            # 如果有仓位，先平仓
            if self.position:
                self.position.close()

            # 买入 - 使用90%的可用资金，避免保证金不足
            self.buy(size=0.90)

        # MACD死叉 - 卖出信号
        elif crossover(self.signal_line, self.macd_line):
            # Phase 2: 应用过滤器（后续实现）
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
