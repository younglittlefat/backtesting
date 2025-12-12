#!/usr/bin/env python3
"""
Example script demonstrating the scoring module functionality.

This script shows:
1. Loading ETF data
2. Calculating momentum scores
3. Applying inertia bonus
4. Generating trading signals with hysteresis
5. Backtesting with historical scores
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data_loader import load_universe_from_file, filter_by_liquidity
from scoring import (
    calculate_universe_scores,
    apply_inertia_bonus,
    get_trading_signals,
    calculate_historical_scores,
    get_scores_for_date,
    validate_scoring_params
)


def example_daily_signal_generation():
    """Example 1: Generate trading signals for a single day (live trading scenario)."""
    print("=" * 80)
    print("Example 1: Daily Signal Generation (Live Trading)")
    print("=" * 80)

    # Configuration
    pool_file = 'results/trend_etf_pool.csv'
    data_dir = 'data/chinese_etf/daily'
    as_of_date = '2023-12-29'  # Last trading day of 2023
    current_holdings = ['159915.SZ', '510300.SH', '512690.SH']  # Example holdings

    print(f"\nAs of date: {as_of_date}")
    print(f"Current holdings: {current_holdings}")

    # Step 1: Load data
    print("\n[1/5] Loading ETF data...")
    try:
        data_dict = load_universe_from_file(
            pool_file=pool_file,
            data_dir=data_dir,
            end_date=as_of_date,
            use_adj=True,
            skip_errors=True
        )
        print(f"Loaded {len(data_dict)} ETFs")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Skipping this example (data files not found)")
        return

    # Step 2: Filter by liquidity
    print("\n[2/5] Filtering by liquidity...")
    data_dict = filter_by_liquidity(
        data_dict=data_dict,
        min_amount=100_000_000,  # 100M yuan daily volume
        lookback_days=20
    )
    print(f"After liquidity filter: {len(data_dict)} ETFs")

    # Step 3: Calculate scores
    print("\n[3/5] Calculating momentum scores...")
    scores_df = calculate_universe_scores(
        data_dict=data_dict,
        as_of_date=as_of_date,
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3]
    )

    print(f"\nTop 10 by raw score:")
    print(scores_df.head(10)[['symbol', 'raw_score', 'rank']].to_string(index=False))

    # Step 4: Apply inertia bonus
    print("\n[4/5] Applying inertia bonus to holdings...")
    adjusted_scores = apply_inertia_bonus(
        scores_df=scores_df,
        current_holdings=current_holdings,
        bonus_pct=0.1  # 10% bonus
    )

    # Show which holdings got bonus
    holdings_in_universe = adjusted_scores[
        adjusted_scores['has_inertia']
    ][['symbol', 'raw_score', 'rank', 'adjusted_score', 'adjusted_rank']]

    if not holdings_in_universe.empty:
        print(f"\nHoldings with inertia bonus:")
        print(holdings_in_universe.to_string(index=False))

    # Step 5: Generate trading signals
    print("\n[5/5] Generating trading signals...")
    signals = get_trading_signals(
        scores_df=adjusted_scores,
        current_holdings=current_holdings,
        buy_top_n=10,
        hold_until_rank=15,
        use_adjusted_rank=True
    )

    print(f"\nTrading Signals:")
    print(f"  To Buy ({len(signals['to_buy'])}): {signals['to_buy']}")
    print(f"  To Hold ({len(signals['to_hold'])}): {signals['to_hold']}")
    print(f"  To Sell ({len(signals['to_sell'])}): {signals['to_sell']}")
    print(f"  Final Holdings ({len(signals['final_holdings'])}): {signals['final_holdings']}")

    # Show buy reasons
    if signals['metadata']['buy_reasons']:
        print(f"\nBuy Reasons:")
        for symbol, reason in signals['metadata']['buy_reasons'].items():
            print(f"  {symbol}: {reason}")

    # Show sell reasons
    if signals['metadata']['sell_reasons']:
        print(f"\nSell Reasons:")
        for symbol, reason in signals['metadata']['sell_reasons'].items():
            print(f"  {symbol}: {reason}")


def example_simple_backtest():
    """Example 2: Simple momentum backtest with monthly rebalancing."""
    print("\n" + "=" * 80)
    print("Example 2: Simple Backtest with Historical Scores")
    print("=" * 80)

    # Configuration
    pool_file = 'results/trend_etf_pool.csv'
    data_dir = 'data/chinese_etf/daily'
    start_date = '2023-01-01'
    end_date = '2023-12-31'

    print(f"\nBacktest period: {start_date} to {end_date}")
    print(f"Rebalance frequency: Monthly")

    # Load data
    print("\n[1/3] Loading ETF data...")
    try:
        data_dict = load_universe_from_file(
            pool_file=pool_file,
            data_dir=data_dir,
            start_date='2022-06-01',  # Extra data for warmup
            end_date=end_date,
            use_adj=True,
            skip_errors=True
        )
        print(f"Loaded {len(data_dict)} ETFs")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Skipping this example (data files not found)")
        return

    # Calculate historical scores
    print("\n[2/3] Calculating historical scores (this may take a while)...")
    historical_scores = calculate_historical_scores(
        data_dict=data_dict,
        start_date=start_date,
        end_date=end_date,
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3],
        frequency='daily'
    )

    print(f"Calculated scores for {len(historical_scores.index.get_level_values(0).unique())} dates")

    # Simulate monthly rebalancing
    print("\n[3/3] Simulating monthly rebalancing...")
    rebalance_dates = pd.date_range(start_date, end_date, freq='M')

    portfolio = []
    portfolio_history = []

    for date in rebalance_dates:
        date_str = date.strftime('%Y-%m-%d')

        # Get scores for this date
        scores = get_scores_for_date(historical_scores, date_str)

        if scores.empty:
            # Skip if no scores available
            continue

        # Apply inertia bonus
        adjusted = apply_inertia_bonus(
            scores_df=scores,
            current_holdings=portfolio,
            bonus_pct=0.1
        )

        # Generate signals
        signals = get_trading_signals(
            scores_df=adjusted,
            current_holdings=portfolio,
            buy_top_n=10,
            hold_until_rank=15,
            use_adjusted_rank=True
        )

        # Update portfolio
        portfolio = signals['final_holdings']

        # Record
        portfolio_history.append({
            'date': date_str,
            'holdings': len(portfolio),
            'buys': len(signals['to_buy']),
            'sells': len(signals['to_sell'])
        })

        print(f"{date_str}: {len(portfolio)} holdings "
              f"(+{len(signals['to_buy'])} buys, -{len(signals['to_sell'])} sells)")

    # Summary
    history_df = pd.DataFrame(portfolio_history)
    print(f"\nBacktest Summary:")
    print(f"  Total rebalances: {len(history_df)}")
    print(f"  Average holdings: {history_df['holdings'].mean():.1f}")
    print(f"  Total buys: {history_df['buys'].sum()}")
    print(f"  Total sells: {history_df['sells'].sum()}")
    print(f"  Turnover per rebalance: {(history_df['buys'].sum() + history_df['sells'].sum()) / len(history_df):.1f}")


def example_parameter_validation():
    """Example 3: Validate scoring parameters before running backtest."""
    print("\n" + "=" * 80)
    print("Example 3: Parameter Validation")
    print("=" * 80)

    # Test valid parameters
    print("\nTest 1: Valid parameters")
    is_valid, error = validate_scoring_params(
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3],
        buy_top_n=10,
        hold_until_rank=15
    )
    print(f"Result: {'PASS' if is_valid else 'FAIL'}")
    if error:
        print(f"Error: {error}")

    # Test invalid weights
    print("\nTest 2: Invalid weights (don't sum to 1.0)")
    is_valid, error = validate_scoring_params(
        periods=[20, 60, 120],
        weights=[0.5, 0.3, 0.3],
        buy_top_n=10,
        hold_until_rank=15
    )
    print(f"Result: {'PASS' if is_valid else 'FAIL'}")
    if error:
        print(f"Error: {error}")

    # Test invalid hysteresis
    print("\nTest 3: Invalid hysteresis (hold < buy)")
    is_valid, error = validate_scoring_params(
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3],
        buy_top_n=15,
        hold_until_rank=10
    )
    print(f"Result: {'PASS' if is_valid else 'FAIL'}")
    if error:
        print(f"Error: {error}")


def example_synthetic_data():
    """Example 4: Demo with synthetic data (always works, no external dependencies)."""
    print("\n" + "=" * 80)
    print("Example 4: Synthetic Data Demo")
    print("=" * 80)

    # Generate synthetic ETF data
    print("\nGenerating synthetic data for 10 ETFs...")
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')

    data_dict = {}
    for i in range(10):
        # Create ETF with varying momentum
        base = 100
        trend_strength = -0.05 + i * 0.02  # Range from -5% to +13% annual
        trend = base * (1 + trend_strength * np.arange(len(dates)) / 365)
        noise = np.random.randn(len(dates)) * 1.5
        close = trend + noise

        df = pd.DataFrame({
            'open': close * 0.99,
            'high': close * 1.01,
            'low': close * 0.98,
            'close': close,
            'volume': np.random.randint(1_000_000, 10_000_000, len(dates))
        }, index=dates)

        data_dict[f'ETF{i+1:02d}'] = df

    # Calculate scores
    print("\nCalculating scores as of 2023-12-31...")
    scores_df = calculate_universe_scores(
        data_dict=data_dict,
        as_of_date='2023-12-31'
    )

    print("\nAll ETF scores:")
    print(scores_df[['symbol', 'raw_score', 'rank']].to_string(index=False))

    # Apply inertia and generate signals
    current_holdings = ['ETF05', 'ETF06', 'ETF07']  # Mid-ranked holdings
    print(f"\nCurrent holdings: {current_holdings}")

    adjusted = apply_inertia_bonus(scores_df, current_holdings, bonus_pct=0.15)
    signals = get_trading_signals(
        adjusted, current_holdings, buy_top_n=5, hold_until_rank=7
    )

    print(f"\nSignals (buy top 5, hold until rank 7):")
    print(f"  To Buy: {signals['to_buy']}")
    print(f"  To Hold: {signals['to_hold']}")
    print(f"  To Sell: {signals['to_sell']}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("SCORING MODULE EXAMPLES")
    print("=" * 80)

    # Always run synthetic data example (no dependencies)
    example_synthetic_data()

    # Run parameter validation (no dependencies)
    example_parameter_validation()

    # Try to run examples that need real data
    # These will gracefully skip if data is not available
    example_daily_signal_generation()
    example_simple_backtest()

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)


if __name__ == '__main__':
    main()
