#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V2 Portfolio Backtest Runner - Bear Market Period (2022-2023)
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
    config_path = 'experiment/etf/v2_vs_v1_comparison/configs/v2_kama_bear.json'
    output_dir = 'experiment/etf/v2_vs_v1_comparison/results/v2_bear_market'

    print("=" * 80)
    print("V2 Portfolio Backtest - Bear Market Period (2022-01-01 ~ 2023-12-31)")
    print("=" * 80)
    print(f"Config: {config_path}")
    print(f"Output: {output_dir}")
    print(f"Initial Capital: 1,000,000")
    print("=" * 80)

    try:
        results = run_portfolio_backtest(
            config_path=config_path,
            start_date='2022-01-01',
            end_date='2023-12-31',
            output_dir=output_dir,
            initial_capital=1000000
        )

        stats = results.get('stats', {})

        print('\n' + '=' * 80)
        print('V2 Bear Market Backtest Results (2022-01 ~ 2023-12)')
        print('=' * 80)
        print(f'年化收益率: {stats.get("annualized_return", 0)*100:.2f}%')
        print(f'夏普比率: {stats.get("sharpe_ratio", 0):.2f}')
        print(f'最大回撤: {stats.get("max_drawdown", 0)*100:.2f}%')
        print(f'胜率: {stats.get("win_rate", 0)*100:.1f}%')
        print(f'总收益: {stats.get("total_return", 0)*100:.2f}%')
        print(f'交易次数: {stats.get("num_trades", 0)}')
        print('=' * 80)

        return results

    except Exception as e:
        print(f'\n[ERROR] Backtest failed: {str(e)}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    main()
