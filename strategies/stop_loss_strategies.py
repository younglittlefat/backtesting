"""
止损策略集合

基于 SmaCross 策略的止损增强版本，提供三种风险控制方案：
1. SmaCrossWithTrailingStop: 跟踪止损策略
2. SmaCrossWithLossProtection: 连续止损保护策略
3. SmaCrossWithFullRiskControl: 组合止损策略（跟踪止损 + 连续止损保护）

作者: Claude Code
日期: 2025-11-09
"""

import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover


def SMA(values, n):
    """
    简单移动平均线

    Args:
        values: 价格序列
        n: 窗口大小

    Returns:
        移动平均值序列
    """
    return pd.Series(values).rolling(n).mean()


class SmaCrossWithTrailingStop(Strategy):
    """
    带跟踪止损的双均线交叉策略

    在基础双均线策略上增加跟踪止损功能：
    - 持仓时，价格上涨则动态提高止损线
    - 当价格跌破止损线时平仓止损
    - 保护已获利润，让趋势充分延续

    参数:
        n1: 短期均线周期 (默认10)
        n2: 长期均线周期 (默认20)
        trailing_stop_pct: 跟踪止损百分比 (默认0.05，即5%)
    """

    # 策略参数
    n1 = 10
    n2 = 20
    trailing_stop_pct = 0.05  # 5%跟踪止损

    def init(self):
        """初始化策略"""
        # 计算移动平均线
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

        # 跟踪止损状态
        self.highest_price = 0

    def next(self):
        """每个交易日调用一次"""
        # 如果有持仓，检查跟踪止损
        if self.position:
            current_price = self.data.Close[-1]

            # 更新最高价
            if current_price > self.highest_price:
                self.highest_price = current_price

            # 计算止损价格
            stop_price = self.highest_price * (1 - self.trailing_stop_pct)

            # 如果价格跌破止损线，平仓
            if current_price < stop_price:
                self.position.close()
                self.highest_price = 0
                return

        # 原始双均线策略逻辑
        # 短期均线上穿长期均线 -> 买入信号（金叉）
        if crossover(self.sma1, self.sma2):
            if self.position:
                self.position.close()
            self.buy(size=0.9)
            # 记录入场价格作为初始最高价
            self.highest_price = self.data.Close[-1]

        # 短期均线下穿长期均线 -> 卖出信号（死叉）
        elif crossover(self.sma2, self.sma1):
            if self.position:
                self.position.close()
                self.highest_price = 0


class SmaCrossWithLossProtection(Strategy):
    """
    带连续止损保护的双均线交叉策略

    在基础双均线策略上增加连续亏损保护：
    - 跟踪每次交易的盈亏状态
    - 连续N次亏损后暂停交易M个周期
    - 防范策略在不利市况下的连续损失

    参数:
        n1: 短期均线周期 (默认10)
        n2: 长期均线周期 (默认20)
        max_consecutive_losses: 最大连续亏损次数 (默认3)
        pause_bars: 触发保护后暂停的K线数 (默认10)
    """

    # 策略参数
    n1 = 10
    n2 = 20
    max_consecutive_losses = 3
    pause_bars = 10

    def init(self):
        """初始化策略"""
        # 计算移动平均线
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

        # 连续止损保护状态
        self.entry_price = 0
        self.consecutive_losses = 0
        self.paused_until_bar = -1
        self.current_bar = 0

    def next(self):
        """每个交易日调用一次"""
        self.current_bar += 1

        # 检查是否在暂停期内
        if self.current_bar < self.paused_until_bar:
            return

        # 跟踪出场并判断盈亏
        if self.position:
            # 短期均线下穿长期均线 -> 卖出信号（死叉）
            if crossover(self.sma2, self.sma1):
                exit_price = self.data.Close[-1]
                self.position.close()

                # 判断盈亏
                if exit_price < self.entry_price:
                    # 亏损交易
                    self.consecutive_losses += 1
                    # 检查是否达到最大连续亏损
                    if self.consecutive_losses >= self.max_consecutive_losses:
                        # 触发保护，暂停交易
                        self.paused_until_bar = self.current_bar + self.pause_bars
                        self.consecutive_losses = 0
                else:
                    # 盈利交易，重置连续亏损计数
                    self.consecutive_losses = 0

                self.entry_price = 0

        # 入场逻辑：短期均线上穿长期均线 -> 买入信号（金叉）
        elif crossover(self.sma1, self.sma2):
            # 只有不在暂停期才允许入场
            if self.current_bar >= self.paused_until_bar:
                self.buy(size=0.9)
                self.entry_price = self.data.Close[-1]


class SmaCrossWithFullRiskControl(Strategy):
    """
    完整风险控制的双均线交叉策略

    综合跟踪止损和连续止损保护两种方案：
    - 跟踪止损：持仓过程中动态保护利润
    - 连续止损保护：连续亏损后暂停交易
    - 双层保护，既限制单笔亏损又防范连续失误

    参数:
        n1: 短期均线周期 (默认10)
        n2: 长期均线周期 (默认20)
        trailing_stop_pct: 跟踪止损百分比 (默认0.05，即5%)
        max_consecutive_losses: 最大连续亏损次数 (默认3)
        pause_bars: 触发保护后暂停的K线数 (默认10)
    """

    # 策略参数
    n1 = 10
    n2 = 20
    trailing_stop_pct = 0.05
    max_consecutive_losses = 3
    pause_bars = 10

    def init(self):
        """初始化策略"""
        # 计算移动平均线
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

        # 跟踪止损状态
        self.highest_price = 0
        self.entry_price = 0

        # 连续止损保护状态
        self.consecutive_losses = 0
        self.paused_until_bar = -1
        self.current_bar = 0

    def next(self):
        """每个交易日调用一次"""
        self.current_bar += 1

        # 检查暂停期
        if self.current_bar < self.paused_until_bar:
            return

        # 如果有持仓，检查跟踪止损
        if self.position:
            current_price = self.data.Close[-1]

            # 更新最高价
            if current_price > self.highest_price:
                self.highest_price = current_price

            # 计算止损价格
            stop_price = self.highest_price * (1 - self.trailing_stop_pct)

            # 如果价格跌破止损线，触发跟踪止损
            if current_price < stop_price:
                exit_price = self.data.Close[-1]
                self.position.close()

                # 判断盈亏并更新连续亏损计数
                if exit_price < self.entry_price:
                    self.consecutive_losses += 1
                    if self.consecutive_losses >= self.max_consecutive_losses:
                        self.paused_until_bar = self.current_bar + self.pause_bars
                        self.consecutive_losses = 0
                else:
                    self.consecutive_losses = 0

                self.highest_price = 0
                self.entry_price = 0
                return

            # 检查死叉信号
            if crossover(self.sma2, self.sma1):
                exit_price = self.data.Close[-1]
                self.position.close()

                # 判断盈亏并更新连续亏损计数
                if exit_price < self.entry_price:
                    self.consecutive_losses += 1
                    if self.consecutive_losses >= self.max_consecutive_losses:
                        self.paused_until_bar = self.current_bar + self.pause_bars
                        self.consecutive_losses = 0
                else:
                    self.consecutive_losses = 0

                self.highest_price = 0
                self.entry_price = 0

        # 入场信号：短期均线上穿长期均线 -> 买入信号（金叉）
        elif crossover(self.sma1, self.sma2):
            # 只有不在暂停期才允许入场
            if self.current_bar >= self.paused_until_bar:
                self.buy(size=0.9)
                self.highest_price = self.data.Close[-1]
                self.entry_price = self.data.Close[-1]


# 参数优化配置
OPTIMIZE_PARAMS_TRAILING = {
    'n1': range(5, 51, 5),
    'n2': range(20, 201, 20),
    'trailing_stop_pct': [0.03, 0.05, 0.07],
}

OPTIMIZE_PARAMS_LOSS_PROTECTION = {
    'n1': range(5, 51, 5),
    'n2': range(20, 201, 20),
    'max_consecutive_losses': [2, 3, 4],
    'pause_bars': [5, 10, 15],
}

OPTIMIZE_PARAMS_FULL = {
    'n1': range(5, 51, 5),
    'n2': range(20, 201, 20),
    'trailing_stop_pct': [0.03, 0.05, 0.07],
    'max_consecutive_losses': [2, 3, 4],
    'pause_bars': [5, 10, 15],
}

# 参数约束: 短期均线必须小于长期均线
CONSTRAINTS = lambda p: p.n1 < p.n2


if __name__ == '__main__':
    """测试策略"""
    from backtesting import Backtest
    from backtesting.test import GOOG

    print("=" * 70)
    print("测试止损策略")
    print("=" * 70)
    print()

    # 测试1: 跟踪止损策略
    print("测试1: 跟踪止损策略")
    print("-" * 70)
    bt1 = Backtest(GOOG, SmaCrossWithTrailingStop,
                   cash=10000, commission=0.002)
    stats1 = bt1.run()
    print(f"收益率: {stats1['Return [%]']:.2f}%")
    print(f"夏普比率: {stats1['Sharpe Ratio']:.2f}")
    print(f"最大回撤: {stats1['Max. Drawdown [%]']:.2f}%")
    print(f"胜率: {stats1['Win Rate [%]']:.2f}%")
    print()

    # 测试2: 连续止损保护策略
    print("测试2: 连续止损保护策略")
    print("-" * 70)
    bt2 = Backtest(GOOG, SmaCrossWithLossProtection,
                   cash=10000, commission=0.002)
    stats2 = bt2.run()
    print(f"收益率: {stats2['Return [%]']:.2f}%")
    print(f"夏普比率: {stats2['Sharpe Ratio']:.2f}")
    print(f"最大回撤: {stats2['Max. Drawdown [%]']:.2f}%")
    print(f"胜率: {stats2['Win Rate [%]']:.2f}%")
    print()

    # 测试3: 组合止损策略
    print("测试3: 组合止损策略")
    print("-" * 70)
    bt3 = Backtest(GOOG, SmaCrossWithFullRiskControl,
                   cash=10000, commission=0.002)
    stats3 = bt3.run()
    print(f"收益率: {stats3['Return [%]']:.2f}%")
    print(f"夏普比率: {stats3['Sharpe Ratio']:.2f}")
    print(f"最大回撤: {stats3['Max. Drawdown [%]']:.2f}%")
    print(f"胜率: {stats3['Win Rate [%]']:.2f}%")
    print()

    print("=" * 70)
    print("测试完成")
    print("=" * 70)
