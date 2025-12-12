"""
Example usage of the data_loader module.

This script demonstrates how to load ETF data, filter by liquidity,
and prepare data for backtesting or signal generation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data_loader import (
    load_single_etf,
    load_universe,
    load_universe_from_file,
    filter_by_liquidity,
    align_dates,
    get_data_date_range,
    validate_data_quality
)


def example_1_load_single():
    """Example 1: Load a single ETF."""
    print("\n" + "="*60)
    print("Example 1: Load Single ETF")
    print("="*60)

    # Load data for a single ETF
    df = load_single_etf(
        symbol='150013.SZ',
        data_dir='/mnt/d/git/backtesting/data/chinese_etf/daily',
        start_date='2020-01-01',
        end_date='2020-12-31',
        use_adj=True  # Use adjusted prices
    )

    print(f"Loaded {len(df)} rows of data")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print(f"\nFirst 5 rows:\n{df.head()}")
    print(f"\nLast 5 rows:\n{df.tail()}")


def example_2_load_multiple():
    """Example 2: Load multiple ETFs."""
    print("\n" + "="*60)
    print("Example 2: Load Multiple ETFs")
    print("="*60)

    symbols = ['150013.SZ', '150016.SZ', '150017.SZ']
    data_dict = load_universe(
        symbols=symbols,
        data_dir='/mnt/d/git/backtesting/data/chinese_etf/daily',
        start_date='2020-01-01',
        end_date='2020-12-31',
        use_adj=True,
        skip_errors=True
    )

    print(f"Loaded {len(data_dict)} symbols")
    for symbol, df in data_dict.items():
        print(f"  {symbol}: {len(df)} rows, "
              f"{df.index.min().date()} to {df.index.max().date()}")


def example_3_load_from_pool():
    """Example 3: Load from a pool file."""
    print("\n" + "="*60)
    print("Example 3: Load from Pool File")
    print("="*60)

    pool_file = '/mnt/d/git/backtesting/results/trend_etf_pool_2019_2021.csv'
    data_dir = '/mnt/d/git/backtesting/data/chinese_etf/daily'

    try:
        data_dict = load_universe_from_file(
            pool_file=pool_file,
            data_dir=data_dir,
            start_date='2020-01-01',
            end_date='2020-12-31',
            skip_errors=True
        )

        print(f"Loaded {len(data_dict)} symbols from pool file")

        # Get overall date range
        min_date, max_date = get_data_date_range(data_dict)
        print(f"Overall date range: {min_date.date()} to {max_date.date()}")

    except FileNotFoundError:
        print(f"Pool file not found: {pool_file}")


def example_4_filter_and_align():
    """Example 4: Filter by liquidity and align dates."""
    print("\n" + "="*60)
    print("Example 4: Filter and Align")
    print("="*60)

    # Load data
    symbols = ['150013.SZ', '150016.SZ', '150017.SZ', '150018.SZ', '150019.SZ']
    data_dict = load_universe(
        symbols=symbols,
        data_dir='/mnt/d/git/backtesting/data/chinese_etf/daily',
        start_date='2020-01-01',
        end_date='2020-12-31',
        skip_errors=True
    )
    print(f"1. Loaded: {len(data_dict)} symbols")

    # Filter by liquidity
    liquid_dict = filter_by_liquidity(
        data_dict,
        min_amount=10_000_000,  # 10M yuan daily average
        lookback_days=20
    )
    print(f"2. After liquidity filter: {len(liquid_dict)} symbols")

    # Validate data quality
    valid_dict = validate_data_quality(
        liquid_dict,
        min_data_points=100,
        max_missing_pct=0.05
    )
    print(f"3. After quality validation: {len(valid_dict)} symbols")

    # Align dates (use intersection for common dates)
    aligned_dict = align_dates(valid_dict, method='intersection')
    print(f"4. After date alignment: {len(aligned_dict)} symbols")

    if aligned_dict:
        # Check that all have same dates
        date_counts = [len(df) for df in aligned_dict.values()]
        print(f"   All symbols have {date_counts[0]} common trading days")

        # Show sample data from first symbol
        first_symbol = list(aligned_dict.keys())[0]
        print(f"\nSample data from {first_symbol}:")
        print(aligned_dict[first_symbol].head())


def example_5_complete_pipeline():
    """Example 5: Complete data loading pipeline."""
    print("\n" + "="*60)
    print("Example 5: Complete Pipeline")
    print("="*60)

    pool_file = '/mnt/d/git/backtesting/results/trend_etf_pool_2019_2021.csv'
    data_dir = '/mnt/d/git/backtesting/data/chinese_etf/daily'

    try:
        # Step 1: Load from pool file
        print("Step 1: Loading data from pool file...")
        data_dict = load_universe_from_file(
            pool_file=pool_file,
            data_dir=data_dir,
            start_date='2020-01-01',
            end_date='2020-12-31',
            skip_errors=True
        )
        print(f"  Loaded {len(data_dict)} symbols")

        # Step 2: Filter by liquidity
        print("\nStep 2: Filtering by liquidity...")
        liquid_dict = filter_by_liquidity(
            data_dict,
            min_amount=50_000_000,  # 50M yuan
            lookback_days=20
        )
        print(f"  {len(liquid_dict)} symbols passed liquidity filter")

        # Step 3: Validate data quality
        print("\nStep 3: Validating data quality...")
        valid_dict = validate_data_quality(
            liquid_dict,
            min_data_points=150,
            max_missing_pct=0.05
        )
        print(f"  {len(valid_dict)} symbols passed quality validation")

        # Step 4: Align dates
        print("\nStep 4: Aligning dates...")
        aligned_dict = align_dates(valid_dict, method='intersection')
        print(f"  {len(aligned_dict)} symbols after alignment")

        if aligned_dict:
            # Get statistics
            min_date, max_date = get_data_date_range(aligned_dict)
            num_days = len(list(aligned_dict.values())[0])

            print(f"\nFinal dataset:")
            print(f"  Symbols: {len(aligned_dict)}")
            print(f"  Date range: {min_date.date()} to {max_date.date()}")
            print(f"  Trading days: {num_days}")
            print(f"  Symbol list: {list(aligned_dict.keys())}")

            # Calculate some statistics
            print(f"\nData statistics:")
            for symbol, df in list(aligned_dict.items())[:3]:  # Show first 3
                avg_volume = df['volume'].mean()
                avg_amount = df['amount'].mean() if 'amount' in df.columns else 0
                print(f"  {symbol}:")
                print(f"    Avg daily volume: {avg_volume:,.0f}")
                print(f"    Avg daily amount: {avg_amount:,.0f} yuan")

    except FileNotFoundError as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    # Run all examples
    example_1_load_single()
    example_2_load_multiple()
    example_3_load_from_pool()
    example_4_filter_and_align()
    example_5_complete_pipeline()

    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)
