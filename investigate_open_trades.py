#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调查未平仓交易对实盘信号的影响

分析：
1. 未平仓交易发生的原因
2. 对实盘信号生成的影响
3. finalize_trades 的必要性
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# 不禁用进度条和警告，以便观察问题
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import GOOG


def SMA(values, n):
    """简单移动平均线"""
    return pd.Series(values).rolling(n).mean()


class SmaCross(Strategy):
    """双均线交叉策略"""
    n1 = 10
    n2 = 20

    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy(size=0.90)
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell(size=0.90)


def analyze_scenario(scenario_name, data, finalize_trades=False):
    """分析不同场景"""
    print(f"\n{'='*70}")
    print(f"场景: {scenario_name}")
    print(f"finalize_trades: {finalize_trades}")
    print(f"{'='*70}")

    bt = Backtest(data, SmaCross, cash=10000, commission=0.002,
                  finalize_trades=finalize_trades)

    # 捕获警告
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        stats = bt.run()

        if w:
            print(f"\n⚠️  警告信息: {w[0].message}")
        else:
            print(f"\n✓ 无警告信息")

    # 获取策略实例
    strategy = stats._strategy

    # 分析最后一个bar的状态
    print(f"\n策略状态:")
    print(f"  数据长度: {len(data)}")
    print(f"  最后收盘价: ${data['Close'].iloc[-1]:.2f}")
    print(f"  短期均线(最后): {strategy.sma1[-1]:.2f}")
    print(f"  长期均线(最后): {strategy.sma2[-1]:.2f}")
    print(f"  短期均线(倒数第二): {strategy.sma1[-2]:.2f}")
    print(f"  长期均线(倒数第二): {strategy.sma2[-2]:.2f}")

    # 判断信号类型
    sma_short = strategy.sma1[-1]
    sma_long = strategy.sma2[-1]
    sma_short_prev = strategy.sma1[-2]
    sma_long_prev = strategy.sma2[-2]

    if sma_short_prev <= sma_long_prev and sma_short > sma_long:
        signal = "BUY (金叉)"
    elif sma_short_prev >= sma_long_prev and sma_short < sma_long:
        signal = "SELL (死叉)"
    elif sma_short > sma_long:
        signal = "HOLD_LONG (持有多头)"
    else:
        signal = "HOLD_SHORT (持有空头)"

    print(f"  当前信号: {signal}")

    # 分析回测统计
    print(f"\n回测统计:")
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  总交易数: {stats['# Trades']}")

    # 检查是否有未平仓交易（通过 _strategy._broker.trades）
    try:
        from backtesting.backtesting import Trade as BacktestTrade
        broker = stats._strategy._broker
        if hasattr(broker, 'trades') and broker.trades:
            print(f"  未平仓交易数: {len(broker.trades)}")
            for i, trade in enumerate(broker.trades):
                print(f"    交易{i+1}: Size={trade.size} @ Entry=${trade.entry_price:.2f}")
        else:
            print(f"  未平仓交易数: 0")
    except Exception as e:
        print(f"  未平仓交易数: 无法获取 ({e})")

    return stats, signal


def main():
    print("="*70)
    print("未平仓交易影响调查")
    print("="*70)

    # 场景1: 使用测试数据 - 正常情况
    print("\n\n场景1: 使用测试数据（GOOG）")
    print("-"*70)

    # 不启用 finalize_trades
    stats1, signal1 = analyze_scenario(
        "不启用 finalize_trades",
        GOOG,
        finalize_trades=False
    )

    # 启用 finalize_trades
    stats2, signal2 = analyze_scenario(
        "启用 finalize_trades",
        GOOG,
        finalize_trades=True
    )

    # 场景2: 构造一个最后有持仓的数据集
    print("\n\n场景2: 最后一个bar明确持有多头")
    print("-"*70)

    # 创建合成数据：最后明确有金叉信号
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    np.random.seed(42)

    # 构造一个上升趋势，最后形成金叉
    close_prices = np.linspace(100, 150, 80).tolist()
    close_prices += np.linspace(150, 155, 20).tolist()  # 最后加速上涨形成金叉

    synthetic_data = pd.DataFrame({
        'Open': close_prices,
        'High': [p * 1.02 for p in close_prices],
        'Low': [p * 0.98 for p in close_prices],
        'Close': close_prices,
        'Volume': [100000] * 100
    }, index=dates)

    stats3, signal3 = analyze_scenario(
        "合成数据 - 不启用 finalize_trades",
        synthetic_data,
        finalize_trades=False
    )

    stats4, signal4 = analyze_scenario(
        "合成数据 - 启用 finalize_trades",
        synthetic_data,
        finalize_trades=True
    )

    # 总结分析
    print("\n\n" + "="*70)
    print("分析结论")
    print("="*70)

    print("\n1. 未平仓交易发生的原因:")
    print("   - 当回测结束时，如果策略仍持有仓位（多头或空头），")
    print("   - 且没有触发平仓信号，这些交易就会保持未平仓状态。")

    print("\n2. 对实盘信号生成的影响:")
    print("   - generate_signals.py 只使用策略的指标值（sma1, sma2）")
    print("   - 并不直接依赖于 position 或 trades 状态")
    print("   - 信号判断是通过均线交叉逻辑独立计算的")
    print("   - 因此，未平仓交易 ⚠️ 不会影响信号生成的准确性")

    print("\n3. finalize_trades 的作用:")
    print("   - finalize_trades=True 会在回测结束时强制平仓所有未平仓交易")
    print("   - 这样可以获得更准确的回测统计数据（包括最后的交易盈亏）")
    print("   - 但对于信号生成来说，由于我们只关心指标值，所以不是必需的")

    print("\n4. 最佳实践建议:")
    print("   ✓ 对于实盘信号生成：可以抑制警告，因为不影响信号准确性")
    print("   ✓ 对于回测统计分析：应该启用 finalize_trades=True")
    print("   ✓ 对于参数优化：应该启用 finalize_trades=True 以获得准确统计")

    print("\n5. 验证信号一致性:")
    print(f"   场景1 - 信号: {signal1} vs {signal2} - {'✓ 一致' if signal1 == signal2 else '✗ 不一致'}")
    print(f"   场景2 - 信号: {signal3} vs {signal4} - {'✓ 一致' if signal3 == signal4 else '✗ 不一致'}")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
