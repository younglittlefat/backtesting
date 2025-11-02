"""
双均线交叉策略 (Simple Moving Average Crossover Strategy)

经典的技术分析策略，当短期均线上穿长期均线时买入，下穿时卖出。

策略逻辑:
- 短期均线上穿长期均线 -> 买入信号（金叉）
- 短期均线下穿长期均线 -> 卖出信号（死叉）
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


class SmaCross(Strategy):
    """
    双均线交叉策略

    参数:
        n1: 短期均线周期 (默认10)
        n2: 长期均线周期 (默认20)
    """

    # 策略参数 - 定义为类变量以便优化
    n1 = 10  # 短期均线周期
    n2 = 20  # 长期均线周期

    def init(self):
        """
        初始化策略

        计算短期和长期移动平均线
        """
        # 计算短期移动平均线
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        # 计算长期移动平均线
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        """
        每个交易日调用一次

        根据均线交叉信号决定买入或卖出
        """
        # 短期均线上穿长期均线 -> 买入信号（金叉）
        if crossover(self.sma1, self.sma2):
            # 如果有空头仓位，先平仓
            self.position.close()
            # 买入
            self.buy()

        # 短期均线下穿长期均线 -> 卖出信号（死叉）
        elif crossover(self.sma2, self.sma1):
            # 如果有多头仓位，先平仓
            self.position.close()
            # 卖出（做空）
            self.sell()


# 参数优化配置
OPTIMIZE_PARAMS = {
    'n1': range(5, 51, 5),      # 短期均线: 5, 10, 15, ..., 50
    'n2': range(20, 201, 20),   # 长期均线: 20, 40, 60, ..., 200
}

# 参数约束: 短期均线必须小于长期均线
CONSTRAINTS = lambda p: p.n1 < p.n2


if __name__ == '__main__':
    """测试策略"""
    from backtesting import Backtest
    from backtesting.test import GOOG

    print("=" * 60)
    print("测试双均线交叉策略")
    print("=" * 60)
    print()

    # 使用示例数据测试
    bt = Backtest(GOOG, SmaCross, cash=10000, commission=0.002)

    print("运行回测...")
    stats = bt.run()

    print("\n回测结果:")
    print(stats)

    print("\n关键指标:")
    print(f"  初始资金: ${stats['Start']}")
    print(f"  最终资金: ${stats['Equity Final [$]']:.2f}")
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  年化收益率: {stats['Return (Ann.) [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")

    print("\n策略参数:")
    print(f"  短期均线 (n1): {stats['_strategy'].n1}")
    print(f"  长期均线 (n2): {stats['_strategy'].n2}")
