#!/usr/bin/env python
"""
Position Sizing Module - Usage Example

This script demonstrates how to use the position_sizing module in a real-world
ETF trend following system scenario.

Usage:
    python etf_trend_following_v2/examples/position_sizing_example.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from position_sizing import (
    calculate_portfolio_positions,
    calculate_rebalance_trades,
    get_position_summary,
    validate_portfolio_constraints,
    calculate_volatility
)


def generate_sample_data():
    """Generate synthetic ETF price data for demonstration"""
    print("Generating synthetic ETF data...")

    dates = pd.date_range('2023-01-01', '2025-11-30', freq='D')
    np.random.seed(42)

    data = {}

    # ETF 1: 创业板ETF (159915.SZ) - 中等波动
    returns_1 = np.random.normal(0.0005, 0.015, len(dates))
    prices_1 = 2.5 * np.exp(np.cumsum(returns_1))
    data['159915.SZ'] = pd.DataFrame({'close': prices_1}, index=dates)

    # ETF 2: 券商ETF (512880.SH) - 高波动
    returns_2 = np.random.normal(0.0008, 0.025, len(dates))
    prices_2 = 1.8 * np.exp(np.cumsum(returns_2))
    data['512880.SH'] = pd.DataFrame({'close': prices_2}, index=dates)

    # ETF 3: 证券ETF (512690.SH) - 高波动（与券商相关）
    returns_3 = np.random.normal(0.0007, 0.023, len(dates))
    prices_3 = 0.9 * np.exp(np.cumsum(returns_3))
    data['512690.SH'] = pd.DataFrame({'close': prices_3}, index=dates)

    # ETF 4: 国债ETF (511010.SH) - 低波动
    returns_4 = np.random.normal(0.0001, 0.001, len(dates))
    prices_4 = 100 * np.exp(np.cumsum(returns_4))
    data['511010.SH'] = pd.DataFrame({'close': prices_4}, index=dates)

    # ETF 5: 医药ETF (512010.SH) - 中等波动
    returns_5 = np.random.normal(0.0006, 0.018, len(dates))
    prices_5 = 3.2 * np.exp(np.cumsum(returns_5))
    data['512010.SH'] = pd.DataFrame({'close': prices_5}, index=dates)

    return data


def example_1_basic_portfolio():
    """示例1: 基础投资组合（无簇约束）"""
    print("\n" + "="*70)
    print("示例1: 基础投资组合（无簇约束）")
    print("="*70)

    # 生成数据
    data_dict = generate_sample_data()
    symbols = list(data_dict.keys())
    total_capital = 1_000_000

    print(f"\n账户资金: {total_capital:,} CNY")
    print(f"标的数量: {len(symbols)}")
    print(f"标的列表: {', '.join(symbols)}")

    # 计算仓位
    positions = calculate_portfolio_positions(
        data_dict=data_dict,
        symbols=symbols,
        total_capital=total_capital,
        target_risk_pct=0.005,       # 0.5% 日风险
        max_position_pct=0.25,       # 单标的最大25%
        max_cluster_pct=None,        # 不限制簇
        volatility_method='ewma'
    )

    # 显示结果
    print("\n仓位配置:")
    summary = get_position_summary(positions, total_capital)
    print(summary.to_string(index=False, float_format=lambda x: f'{x:.2f}'))

    # 验证约束
    is_valid, errors = validate_portfolio_constraints(
        positions,
        max_position_pct=0.25,
        max_total_pct=1.0
    )
    print(f"\n约束验证: {'✓ 通过' if is_valid else '✗ 失败'}")
    if errors:
        for error in errors:
            print(f"  - {error}")


def example_2_cluster_constraints():
    """示例2: 带簇约束的投资组合"""
    print("\n" + "="*70)
    print("示例2: 带簇约束的投资组合")
    print("="*70)

    # 生成数据
    data_dict = generate_sample_data()
    total_capital = 1_000_000

    # 定义簇（基于行业分类）
    cluster_map = {
        '159915.SZ': 0,  # 成长股 - 簇0
        '512880.SH': 1,  # 金融 - 簇1
        '512690.SH': 1,  # 金融 - 簇1（同簇）
        '511010.SH': 2,  # 固收 - 簇2
        '512010.SH': 3,  # 医药 - 簇3
    }

    cluster_names = {0: '成长股', 1: '金融', 2: '固收', 3: '医药'}

    print(f"\n账户资金: {total_capital:,} CNY")
    print(f"簇配置:")
    for symbol, cluster_id in cluster_map.items():
        print(f"  {symbol} → 簇{cluster_id} ({cluster_names[cluster_id]})")

    # 计算仓位
    positions = calculate_portfolio_positions(
        data_dict=data_dict,
        symbols=list(cluster_map.keys()),
        total_capital=total_capital,
        target_risk_pct=0.005,
        max_position_pct=0.2,        # 单标的最大20%
        max_cluster_pct=0.25,        # 单簇最大25%
        cluster_assignments=cluster_map,
        volatility_method='ewma'
    )

    # 显示结果
    print("\n仓位配置:")
    summary = get_position_summary(positions, total_capital)
    print(summary.to_string(index=False, float_format=lambda x: f'{x:.2f}'))

    # 簇级别汇总
    print("\n簇级别汇总:")
    from collections import defaultdict
    cluster_totals = defaultdict(float)
    for symbol, pos in positions.items():
        cluster_id = cluster_map.get(symbol)
        if cluster_id is not None:
            cluster_totals[cluster_id] += pos['target_weight']

    for cluster_id in sorted(cluster_totals.keys()):
        cluster_weight = cluster_totals[cluster_id] * 100
        print(f"  簇{cluster_id} ({cluster_names[cluster_id]}): {cluster_weight:.2f}%")

    # 验证约束
    is_valid, errors = validate_portfolio_constraints(
        positions,
        max_position_pct=0.2,
        max_cluster_pct=0.25,
        max_total_pct=1.0,
        cluster_assignments=cluster_map
    )
    print(f"\n约束验证: {'✓ 通过' if is_valid else '✗ 失败'}")


def example_3_rebalancing():
    """示例3: 调仓交易计算"""
    print("\n" + "="*70)
    print("示例3: 调仓交易计算")
    print("="*70)

    # 生成数据
    data_dict = generate_sample_data()
    symbols = ['159915.SZ', '512880.SH', '511010.SH']
    total_capital = 1_000_000

    # 计算目标仓位
    positions = calculate_portfolio_positions(
        data_dict=data_dict,
        symbols=symbols,
        total_capital=total_capital,
        target_risk_pct=0.005,
        max_position_pct=0.3,
        volatility_method='ewma'
    )

    # 模拟当前持仓（部分持仓）
    current_holdings = {
        '159915.SZ': 100_000,   # 10万（低于目标）
        '512880.SH': 150_000,   # 15万（可能高于目标）
        '511010.SH': 0          # 无持仓
    }

    # 目标持仓
    target_holdings = {
        symbol: pos['target_capital']
        for symbol, pos in positions.items()
    }

    # 当前价格（从最新数据获取）
    current_prices = {
        symbol: df['close'].iloc[-1]
        for symbol, df in data_dict.items()
        if symbol in symbols
    }

    print("\n当前持仓 vs 目标持仓:")
    print(f"{'标的':<12} {'当前持仓':>12} {'目标持仓':>12} {'差额':>12}")
    print("-" * 50)
    for symbol in symbols:
        current = current_holdings.get(symbol, 0)
        target = target_holdings.get(symbol, 0)
        delta = target - current
        print(f"{symbol:<12} {current:>12,.0f} {target:>12,.0f} {delta:>12,.0f}")

    # 计算调仓交易
    trades = calculate_rebalance_trades(
        current_positions=current_holdings,
        target_positions=target_holdings,
        current_prices=current_prices,
        min_trade_amount=1000,
        lot_size=100
    )

    print("\n调仓指令:")
    if not trades:
        print("  无需调仓（所有仓位在误差范围内）")
    else:
        print(f"{'标的':<12} {'操作':>6} {'股数':>10} {'金额':>12} {'价格':>8}")
        print("-" * 52)
        for symbol, trade in trades.items():
            action = '买入' if trade['action'] == 'buy' else '卖出'
            price = current_prices[symbol]
            print(f"{symbol:<12} {action:>6} {trade['shares']:>10,} {trade['amount']:>12,.0f} {price:>8.2f}")


def example_4_volatility_comparison():
    """示例4: 波动率计算方法对比"""
    print("\n" + "="*70)
    print("示例4: 波动率计算方法对比（EWMA vs STD）")
    print("="*70)

    # 生成数据
    data_dict = generate_sample_data()

    print("\n波动率对比（日波动率%）:")
    print(f"{'标的':<12} {'EWMA (λ=0.94)':>16} {'STD (60天)':>16} {'差异':>8}")
    print("-" * 55)

    for symbol, df in data_dict.items():
        vol_ewma = calculate_volatility(df, method='ewma', ewma_lambda=0.94)
        vol_std = calculate_volatility(df, method='std', window=60)
        diff = (vol_ewma - vol_std) / vol_std * 100

        print(f"{symbol:<12} {vol_ewma*100:>16.4f} {vol_std*100:>16.4f} {diff:>7.1f}%")

    print("\n说明:")
    print("  - EWMA: 对近期数据权重更高，响应快")
    print("  - STD:  平滑长期趋势，稳定性好")
    print("  - 差异: (EWMA - STD) / STD × 100%")


def example_5_parameter_sensitivity():
    """示例5: 参数敏感性分析"""
    print("\n" + "="*70)
    print("示例5: 参数敏感性分析（target_risk_pct）")
    print("="*70)

    # 生成数据
    data_dict = generate_sample_data()
    symbols = list(data_dict.keys())
    total_capital = 1_000_000

    # 测试不同的target_risk
    risk_levels = [0.003, 0.005, 0.008]
    risk_names = ['保守 (0.3%)', '中性 (0.5%)', '激进 (0.8%)']

    print(f"\n总资金: {total_capital:,} CNY")
    print(f"标的数: {len(symbols)}")

    results = []
    for risk_pct, risk_name in zip(risk_levels, risk_names):
        positions = calculate_portfolio_positions(
            data_dict=data_dict,
            symbols=symbols,
            total_capital=total_capital,
            target_risk_pct=risk_pct,
            max_position_pct=0.3,
            volatility_method='ewma'
        )

        total_allocated = sum(pos['target_capital'] for pos in positions.values())
        total_weight = sum(pos['target_weight'] for pos in positions.values())
        avg_position = total_allocated / len(positions)

        results.append({
            'risk_name': risk_name,
            'total_allocated': total_allocated,
            'total_weight': total_weight,
            'avg_position': avg_position
        })

    print("\n" + "风险参数影响:")
    print(f"{'风格':<15} {'总配置金额':>15} {'总仓位%':>12} {'平均单仓':>15}")
    print("-" * 60)
    for r in results:
        print(f"{r['risk_name']:<15} {r['total_allocated']:>15,.0f} "
              f"{r['total_weight']*100:>11.1f}% {r['avg_position']:>15,.0f}")

    print("\n观察:")
    print("  - 风险参数越高，配置金额越多（但受单标的上限约束）")
    print("  - 保守策略可能无法满仓（总仓位<100%）")
    print("  - 激进策略单标的更容易触及上限")


def main():
    """运行所有示例"""
    print("\n" + "="*70)
    print("Position Sizing Module - 使用示例集")
    print("="*70)

    example_1_basic_portfolio()
    example_2_cluster_constraints()
    example_3_rebalancing()
    example_4_volatility_comparison()
    example_5_parameter_sensitivity()

    print("\n" + "="*70)
    print("所有示例运行完成!")
    print("="*70)
    print("\n提示:")
    print("  - 完整文档: etf_trend_following_v2/src/README_position_sizing.md")
    print("  - 快速参考: etf_trend_following_v2/src/QUICK_REFERENCE_position_sizing.txt")
    print("  - 单元测试: pytest etf_trend_following_v2/tests/test_position_sizing.py -v")
    print()


if __name__ == '__main__':
    main()
