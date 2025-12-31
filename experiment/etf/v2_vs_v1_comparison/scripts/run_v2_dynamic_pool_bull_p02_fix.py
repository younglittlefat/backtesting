#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V2 Portfolio Backtest Runner - Bull Market Dynamic Pool with P0-2 Liquidity Unit Fix
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
    config_path = 'experiment/etf/v2_vs_v1_comparison/configs/v2_dynamic_pool_bull.json'
    output_dir = 'results/v2_dynamic_pool_bull_p02_fix'

    print("=" * 80)
    print("V2 Dynamic Pool Backtest - Bull Market with P0-2 Liquidity Unit Fix")
    print("=" * 80)
    print(f"Config: {config_path}")
    print(f"Output: {output_dir}")
    print(f"Period: 2024-01-01 ~ 2025-11-30")
    print(f"Initial Capital: 1,000,000")
    print("=" * 80)
    print("\nP0-2 Fix Details:")
    print("- Added liquidity_unit: 'tushare' to config to avoid double scaling")
    print("- Liquidity thresholds now correctly applied at 500万元/50万股")
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
        print('V2 Dynamic Pool Bull Market Backtest Results (P0-2 Fix)')
        print('=' * 80)
        print(f'年化收益率: {stats.get("annualized_return", 0)*100:.2f}%')
        print(f'夏普比率: {stats.get("sharpe_ratio", 0):.2f}')
        print(f'最大回撤: {stats.get("max_drawdown", 0)*100:.2f}%')
        print(f'胜率: {stats.get("win_rate", 0)*100:.1f}%')
        print(f'总收益: {stats.get("total_return", 0)*100:.2f}%')
        print(f'交易次数: {stats.get("num_trades", 0)}')
        print(f'平均持仓数: {stats.get("avg_positions", 0):.2f}')
        print('=' * 80)

        print('\n对比修复前结果 (预期):')
        print('-' * 80)
        print('修复前 - 年化收益: +13.28%')
        print('修复前 - 夏普比率: 0.33')
        print('修复前 - 最大回撤: -25.81%')
        print('修复前 - 平均持仓: 7.50')
        print('-' * 80)
        print('预期修复后有显著改善 (流动性阈值被正确应用)')
        print('=' * 80)

        return results

    except Exception as e:
        print(f'\n[ERROR] Backtest failed: {str(e)}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    main()
