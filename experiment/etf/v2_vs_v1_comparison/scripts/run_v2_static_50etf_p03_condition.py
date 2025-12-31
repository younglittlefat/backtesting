#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V2 Portfolio Backtest Runner - 50 ETF Static Pool with P0-3 Trend State Mode Fix (Condition)
"""
import sys
import os
import logging

# Add V2 source path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'etf_trend_following_v2'))

from src.portfolio_backtest_runner import run_portfolio_backtest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    config_path = 'experiment/etf/v2_vs_v1_comparison/configs/tuning/v2_bull_50etf_cluster3_condition.json'
    output_dir = 'results/v2_50etf_cluster3_p03_condition'

    print("=" * 80)
    print("V2 Static 50 ETF Pool Backtest - P0-3 Trend State Mode (Condition)")
    print("=" * 80)
    print(f"Config: {config_path}")
    print(f"Output: {output_dir}")
    print(f"Period: 2024-01-01 ~ 2025-11-30")
    print(f"Initial Capital: 1,000,000")
    print("=" * 80)
    print("\nP0-3 Fix Details:")
    print("- trend_state_mode: 'condition' (NEW)")
    print("- Trend ON when Close > KAMA (not just after crossover)")
    print("- Expected: capture more in-trend assets without recent crossovers")
    print("=" * 80)

    try:
        results = run_portfolio_backtest(
            config_path=config_path,
            start_date='2024-01-01',
            end_date='2025-11-30',
            output_dir=output_dir,
            initial_capital=1000000
        )

        stats = results.get('stats', {})

        print('\n' + '=' * 80)
        print('V2 50 ETF Cluster3 - Condition Mode Results (P0-3 Fix)')
        print('=' * 80)
        print(f'年化收益率: {stats.get("annualized_return", 0)*100:.2f}%')
        print(f'夏普比率: {stats.get("sharpe_ratio", 0):.2f}')
        print(f'最大回撤: {stats.get("max_drawdown", 0)*100:.2f}%')
        print(f'胜率: {stats.get("win_rate", 0)*100:.1f}%')
        print(f'总收益: {stats.get("total_return", 0)*100:.2f}%')
        print(f'交易次数: {stats.get("num_trades", 0)}')
        print(f'平均持仓数: {stats.get("avg_positions", 0):.2f}')
        print('=' * 80)

        print('\n对比基准 (Event Mode):')
        print('-' * 80)
        print('Event Mode - 年化收益: +23.77%')
        print('Event Mode - 夏普比率: 0.77')
        print('Event Mode - 最大回撤: -20.58%')
        print('Event Mode - 平均持仓: 4.9')
        print('-' * 80)
        print('预期 Condition Mode 提升平均持仓数和收益')
        print('=' * 80)

        return results

    except Exception as e:
        print(f'\n[ERROR] Backtest failed: {str(e)}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    main()
