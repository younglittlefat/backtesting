#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate synthetic test fixture data for unit tests

This script creates small, deterministic OHLCV datasets that can be
used in unit tests without depending on real market data files.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def generate_trending_data(
    symbol: str,
    start_date: str = '2023-01-01',
    periods: int = 250,
    initial_price: float = 100.0,
    trend_slope: float = 0.1,
    volatility: float = 2.0,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with upward trend

    Args:
        symbol: ETF symbol (for filename)
        start_date: Start date
        periods: Number of trading days
        initial_price: Starting price
        trend_slope: Daily trend increment
        volatility: Price volatility (std dev of noise)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(seed)
    dates = pd.date_range(start_date, periods=periods, freq='D')

    # Generate trending close prices
    trend = np.linspace(0, trend_slope * periods, periods)
    noise = np.random.randn(periods) * volatility
    close_prices = initial_price + trend + noise

    # Generate OHLC from close
    high_prices = close_prices + np.abs(np.random.randn(periods)) * 1.5
    low_prices = close_prices - np.abs(np.random.randn(periods)) * 1.5
    open_prices = close_prices + np.random.randn(periods) * 0.5

    # Generate volume and amount
    volumes = np.random.randint(1_000_000, 10_000_000, periods)
    amounts = close_prices * volumes  # amount = price * volume

    # Format dates as YYYYMMDD (required by data_loader)
    date_strings = dates.strftime('%Y%m%d')

    df = pd.DataFrame({
        'trade_date': date_strings,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes,
        'amount': amounts,
        'ts_code': symbol
    })

    return df


def generate_choppy_data(
    symbol: str,
    start_date: str = '2023-01-01',
    periods: int = 250,
    mean_price: float = 100.0,
    volatility: float = 3.0,
    seed: int = 123
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with sideways/choppy movement

    Args:
        symbol: ETF symbol
        start_date: Start date
        periods: Number of trading days
        mean_price: Average price level
        volatility: Price volatility
        seed: Random seed

    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(seed)
    dates = pd.date_range(start_date, periods=periods, freq='D')

    # Sideways movement with noise
    close_prices = mean_price + np.random.randn(periods) * volatility

    high_prices = close_prices + np.abs(np.random.randn(periods)) * 1.5
    low_prices = close_prices - np.abs(np.random.randn(periods)) * 1.5
    open_prices = close_prices + np.random.randn(periods) * 0.5
    volumes = np.random.randint(1_000_000, 10_000_000, periods)
    amounts = close_prices * volumes  # amount = price * volume

    # Format dates as YYYYMMDD (required by data_loader)
    date_strings = dates.strftime('%Y%m%d')

    df = pd.DataFrame({
        'trade_date': date_strings,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes,
        'amount': amounts,
        'ts_code': symbol
    })

    return df


def generate_downtrend_data(
    symbol: str,
    start_date: str = '2023-01-01',
    periods: int = 250,
    initial_price: float = 120.0,
    trend_slope: float = -0.15,
    volatility: float = 2.0,
    seed: int = 456
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with downward trend

    Args:
        symbol: ETF symbol
        start_date: Start date
        periods: Number of trading days
        initial_price: Starting price
        trend_slope: Daily trend decrement (negative)
        volatility: Price volatility
        seed: Random seed

    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(seed)
    dates = pd.date_range(start_date, periods=periods, freq='D')

    # Generate downtrending close prices
    trend = np.linspace(0, trend_slope * periods, periods)
    noise = np.random.randn(periods) * volatility
    close_prices = initial_price + trend + noise

    high_prices = close_prices + np.abs(np.random.randn(periods)) * 1.5
    low_prices = close_prices - np.abs(np.random.randn(periods)) * 1.5
    open_prices = close_prices + np.random.randn(periods) * 0.5
    volumes = np.random.randint(1_000_000, 10_000_000, periods)
    amounts = close_prices * volumes  # amount = price * volume

    # Format dates as YYYYMMDD (required by data_loader)
    date_strings = dates.strftime('%Y%m%d')

    df = pd.DataFrame({
        'trade_date': date_strings,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes,
        'amount': amounts,
        'ts_code': symbol
    })

    return df


def generate_pool_file(symbols: list, output_path: Path):
    """
    Generate a pool file (CSV) with symbol list

    Args:
        symbols: List of symbols
        output_path: Output file path
    """
    df = pd.DataFrame({
        'ts_code': symbols,
        'name': [f'Test ETF {i+1}' for i in range(len(symbols))],
        'score': [0.8 - i*0.05 for i in range(len(symbols))]
    })

    df.to_csv(output_path, index=False)
    print(f"Created pool file: {output_path}")


def main():
    """Generate all test fixture data"""
    fixtures_dir = Path(__file__).parent
    data_dir = fixtures_dir / 'data'
    data_dir.mkdir(exist_ok=True)

    print("Generating test fixture data...")
    print(f"Output directory: {data_dir}")
    print()

    # Generate 3 trending ETFs
    symbols_trending = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH', 'TEST_TREND_3.SH']
    for i, symbol in enumerate(symbols_trending):
        df = generate_trending_data(
            symbol,
            start_date='2023-01-01',
            periods=250,
            initial_price=100.0 + i*10,
            trend_slope=0.1,
            seed=42 + i
        )
        output_file = data_dir / f'{symbol}.csv'
        df.to_csv(output_file)
        print(f"Created: {output_file} ({len(df)} bars)")

    # Generate 2 choppy ETFs
    symbols_choppy = ['TEST_CHOPPY_1.SH', 'TEST_CHOPPY_2.SH']
    for i, symbol in enumerate(symbols_choppy):
        df = generate_choppy_data(
            symbol,
            start_date='2023-01-01',
            periods=250,
            mean_price=100.0,
            seed=123 + i
        )
        output_file = data_dir / f'{symbol}.csv'
        df.to_csv(output_file)
        print(f"Created: {output_file} ({len(df)} bars)")

    # Generate 1 downtrend ETF
    symbol_down = 'TEST_DOWN_1.SH'
    df = generate_downtrend_data(
        symbol_down,
        start_date='2023-01-01',
        periods=250,
        initial_price=120.0,
        seed=456
    )
    output_file = data_dir / f'{symbol_down}.csv'
    df.to_csv(output_file)
    print(f"Created: {output_file} ({len(df)} bars)")

    # Generate pool files
    all_symbols = symbols_trending + symbols_choppy + [symbol_down]
    generate_pool_file(all_symbols, fixtures_dir / 'test_pool_all.csv')
    generate_pool_file(symbols_trending, fixtures_dir / 'test_pool_trending.csv')

    print()
    print("✓ All test fixture data generated successfully")
    print(f"  Total symbols: {len(all_symbols)}")
    print(f"  Data files: {len(all_symbols)}")
    print(f"  Pool files: 2")


if __name__ == '__main__':
    main()
