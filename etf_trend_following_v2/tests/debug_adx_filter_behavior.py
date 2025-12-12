#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug ADX Filter Behavior Comparison

This script compares ADX filter behavior between:
1. Existing strategy: strategies/macd_cross.py (using ADXFilter class)
2. v2 wrapper: etf_trend_following_v2/src/strategies/backtest_wrappers.py (MACDBacktestStrategy)

Goal: Identify why there's >100% deviation in backtest results when ADX filter is enabled.

Author: Claude
Date: 2025-12-11
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backtesting import Backtest
from strategies.macd_cross import MacdCross
from etf_trend_following_v2.src.strategies.backtest_wrappers import MACDBacktestStrategy


def load_test_data(symbol='510300.SH', start_date='2023-01-01', end_date='2024-12-31'):
    """Load test data for comparison"""
    data_path = project_root / 'data' / 'chinese_etf' / 'daily' / 'etf' / f'{symbol}.csv'

    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    df = pd.read_csv(data_path)
    # Parse date correctly (format: YYYYMMDD)
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('trade_date')

    # Rename columns to match backtesting.py format
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })

    # Filter date range
    df = df.loc[start_date:end_date]

    # Select required columns
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

    return df


def extract_crossover_events(strategy_instance, data):
    """
    Extract golden cross events and their ADX values from a strategy instance

    Returns:
        List of dicts with: {date, macd, signal, adx, filtered}
    """
    events = []

    # Get indicators
    macd_line = strategy_instance.macd_line
    signal_line = strategy_instance.signal_line

    # Get ADX if available
    adx = None
    if hasattr(strategy_instance, 'adx'):
        adx = strategy_instance.adx

    # Detect crossovers
    for i in range(1, len(macd_line)):
        # Golden cross detection
        if macd_line[i-1] <= signal_line[i-1] and macd_line[i] > signal_line[i]:
            event = {
                'date': data.index[i],
                'bar_index': i,
                'macd': macd_line[i],
                'signal': signal_line[i],
                'adx': adx[i] if adx is not None else None,
                'filtered': False  # Will be determined by filter logic
            }

            # Check if ADX filter would reject this signal
            if adx is not None and not pd.isna(adx[i]):
                event['filtered'] = adx[i] <= 25.0  # Using default threshold

            events.append(event)

    return events


def compare_adx_calculations(data):
    """
    Compare ADX calculations between the two implementations

    Returns:
        DataFrame with ADX values from both implementations
    """
    from strategies.filters.trend_filters import ADXFilter
    from etf_trend_following_v2.src.strategies.macd import MACDSignalGenerator

    # Calculate ADX using existing strategy's filter
    adx_filter = ADXFilter(enabled=True, period=14, threshold=25)
    adx_existing = adx_filter._calculate_adx(
        data['High'].values,
        data['Low'].values,
        data['Close'].values,
        14
    )

    # Calculate ADX using v2 generator
    generator = MACDSignalGenerator(enable_adx_filter=True, adx_period=14, adx_threshold=25)
    adx_v2 = generator.calculate_adx(
        data['High'],
        data['Low'],
        data['Close'],
        14
    )

    # Create comparison DataFrame
    comparison = pd.DataFrame({
        'ADX_Existing': adx_existing,
        'ADX_V2': adx_v2,
        'Difference': adx_existing - adx_v2,
        'Abs_Difference': abs(adx_existing - adx_v2)
    }, index=data.index)

    return comparison


def run_backtest_comparison(data):
    """
    Run backtests with both strategies and compare results

    Returns:
        Tuple of (stats_existing, stats_v2, events_existing, events_v2)
    """
    print("\n" + "="*80)
    print("Running Backtest Comparison")
    print("="*80)

    # Test parameters
    test_params = {
        'enable_adx_filter': True,
        'adx_period': 14,
        'adx_threshold': 25.0,
        'enable_volume_filter': False,
        'enable_slope_filter': False,
        'enable_confirm_filter': False,
        'enable_loss_protection': False,
        'enable_trailing_stop': False,
    }

    # Run existing strategy
    print("\n1. Running existing strategy (strategies/macd_cross.py)...")
    bt_existing = Backtest(data, MacdCross, cash=100000, commission=0.001)
    stats_existing = bt_existing.run(**test_params)

    # Extract strategy instance for analysis - use the instance created during run
    strategy_existing_instance = bt_existing._results._strategy

    print(f"   Return: {stats_existing['Return [%]']:.2f}%")
    print(f"   Sharpe Ratio: {stats_existing['Sharpe Ratio']:.3f}")
    print(f"   # Trades: {stats_existing['# Trades']}")

    # Run v2 wrapper strategy
    print("\n2. Running v2 wrapper strategy (backtest_wrappers.py)...")
    bt_v2 = Backtest(data, MACDBacktestStrategy, cash=100000, commission=0.001)
    stats_v2 = bt_v2.run(**test_params)

    # Extract strategy instance for analysis
    strategy_v2_instance = bt_v2._results._strategy

    print(f"   Return: {stats_v2['Return [%]']:.2f}%")
    print(f"   Sharpe Ratio: {stats_v2['Sharpe Ratio']:.3f}")
    print(f"   # Trades: {stats_v2['# Trades']}")

    # Calculate deviation
    return_deviation = abs(stats_existing['Return [%]'] - stats_v2['Return [%]'])
    trades_deviation = abs(stats_existing['# Trades'] - stats_v2['# Trades'])

    print(f"\n3. Deviation Analysis:")
    print(f"   Return deviation: {return_deviation:.2f}%")
    print(f"   Trades deviation: {trades_deviation}")

    # Extract crossover events
    events_existing = extract_crossover_events(strategy_existing_instance, data)
    events_v2 = extract_crossover_events(strategy_v2_instance, data)

    return stats_existing, stats_v2, events_existing, events_v2


def analyze_crossover_differences(events_existing, events_v2):
    """
    Analyze differences in crossover filtering between implementations
    """
    print("\n" + "="*80)
    print("Crossover Event Analysis")
    print("="*80)

    print(f"\nTotal golden crosses detected:")
    print(f"  Existing strategy: {len(events_existing)}")
    print(f"  V2 wrapper: {len(events_v2)}")

    # Count filtered events
    filtered_existing = sum(1 for e in events_existing if e['filtered'])
    filtered_v2 = sum(1 for e in events_v2 if e['filtered'])

    print(f"\nFiltered by ADX (ADX <= 25):")
    print(f"  Existing strategy: {filtered_existing} / {len(events_existing)} ({filtered_existing/len(events_existing)*100:.1f}%)")
    print(f"  V2 wrapper: {filtered_v2} / {len(events_v2)} ({filtered_v2/len(events_v2)*100:.1f}%)")

    # Find events that differ
    print("\n" + "-"*80)
    print("Detailed Event Comparison (first 10 golden crosses)")
    print("-"*80)

    # Create comparison table
    print(f"\n{'Date':<12} {'MACD':<8} {'Signal':<8} {'ADX_Exist':<10} {'ADX_V2':<10} {'Filt_Exist':<12} {'Filt_V2':<12}")
    print("-"*80)

    for i in range(min(10, len(events_existing), len(events_v2))):
        e_exist = events_existing[i]
        e_v2 = events_v2[i]

        date_str = e_exist['date'].strftime('%Y-%m-%d')
        macd_str = f"{e_exist['macd']:.4f}"
        signal_str = f"{e_exist['signal']:.4f}"
        adx_exist_str = f"{e_exist['adx']:.2f}" if e_exist['adx'] is not None and not pd.isna(e_exist['adx']) else "NaN"
        adx_v2_str = f"{e_v2['adx']:.2f}" if e_v2['adx'] is not None and not pd.isna(e_v2['adx']) else "NaN"
        filt_exist_str = "FILTERED" if e_exist['filtered'] else "PASS"
        filt_v2_str = "FILTERED" if e_v2['filtered'] else "PASS"

        print(f"{date_str:<12} {macd_str:<8} {signal_str:<8} {adx_exist_str:<10} {adx_v2_str:<10} {filt_exist_str:<12} {filt_v2_str:<12}")

    # Find mismatches
    mismatches = []
    for i in range(min(len(events_existing), len(events_v2))):
        e_exist = events_existing[i]
        e_v2 = events_v2[i]

        if e_exist['filtered'] != e_v2['filtered']:
            mismatches.append((i, e_exist, e_v2))

    if mismatches:
        print(f"\n⚠️  Found {len(mismatches)} mismatches in filtering decisions!")
        print("\nFirst 5 mismatches:")
        for i, (idx, e_exist, e_v2) in enumerate(mismatches[:5]):
            print(f"\n  Mismatch #{i+1} (Event #{idx}):")
            print(f"    Date: {e_exist['date']}")

            adx_exist_str = f"{e_exist['adx']:.2f}" if e_exist['adx'] is not None and not pd.isna(e_exist['adx']) else "NaN"
            adx_v2_str = f"{e_v2['adx']:.2f}" if e_v2['adx'] is not None and not pd.isna(e_v2['adx']) else "NaN"

            print(f"    ADX (Existing): {adx_exist_str}")
            print(f"    ADX (V2): {adx_v2_str}")
            print(f"    Filtered (Existing): {e_exist['filtered']}")
            print(f"    Filtered (V2): {e_v2['filtered']}")
    else:
        print("\n✓ No mismatches found in filtering decisions")


def main():
    """Main debug script"""
    print("="*80)
    print("ADX Filter Behavior Debug Script")
    print("="*80)

    # Load test data
    print("\nLoading test data (510300.SH, 2023-01-01 to 2024-12-31)...")
    try:
        data = load_test_data()
        print(f"✓ Loaded {len(data)} bars")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return

    # Compare ADX calculations
    print("\n" + "="*80)
    print("ADX Calculation Comparison")
    print("="*80)

    adx_comparison = compare_adx_calculations(data)

    # Show statistics
    print(f"\nADX Calculation Statistics:")
    print(f"  Mean difference: {adx_comparison['Difference'].mean():.6f}")
    print(f"  Max absolute difference: {adx_comparison['Abs_Difference'].max():.6f}")
    print(f"  Std of difference: {adx_comparison['Difference'].std():.6f}")

    # Check if calculations are identical
    max_diff = adx_comparison['Abs_Difference'].max()
    if max_diff < 1e-10:
        print(f"  ✓ ADX calculations are identical (max diff: {max_diff:.2e})")
    else:
        print(f"  ⚠️  ADX calculations differ (max diff: {max_diff:.6f})")

        # Show first few rows with differences
        print("\nFirst 5 rows with largest differences:")
        top_diffs = adx_comparison.nlargest(5, 'Abs_Difference')
        print(top_diffs)

    # Run backtest comparison
    stats_existing, stats_v2, events_existing, events_v2 = run_backtest_comparison(data)

    # Analyze crossover differences
    analyze_crossover_differences(events_existing, events_v2)

    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)

    return_deviation = abs(stats_existing['Return [%]'] - stats_v2['Return [%]'])
    trades_deviation = abs(stats_existing['# Trades'] - stats_v2['# Trades'])

    print(f"\nBacktest Results Comparison:")
    print(f"  Existing Strategy:")
    print(f"    Return: {stats_existing['Return [%]']:.2f}%")
    print(f"    Sharpe: {stats_existing['Sharpe Ratio']:.3f}")
    print(f"    Trades: {stats_existing['# Trades']}")
    print(f"\n  V2 Wrapper:")
    print(f"    Return: {stats_v2['Return [%]']:.2f}%")
    print(f"    Sharpe: {stats_v2['Sharpe Ratio']:.3f}")
    print(f"    Trades: {stats_v2['# Trades']}")
    print(f"\n  Deviation:")
    print(f"    Return: {return_deviation:.2f}%")
    print(f"    Trades: {trades_deviation}")

    if return_deviation > 10:
        print(f"\n⚠️  WARNING: Large return deviation detected ({return_deviation:.2f}%)")
        print("    This suggests significant differences in signal filtering logic.")
    else:
        print(f"\n✓ Return deviation is acceptable ({return_deviation:.2f}%)")

    print("\n" + "="*80)
    print("Debug script completed")
    print("="*80)


if __name__ == '__main__':
    main()
