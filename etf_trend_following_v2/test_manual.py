"""
Manual test script for data_loader module.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_loader import (
    load_single_etf,
    load_universe,
    load_universe_from_file,
    filter_by_liquidity,
    align_dates,
    get_data_date_range,
    validate_data_quality
)

# Test data directory
DATA_DIR = '/mnt/d/git/backtesting/data/chinese_etf/daily'
POOL_FILE = '/mnt/d/git/backtesting/results/trend_etf_pool_2019_2021.csv'


def test_load_single():
    """Test loading a single ETF."""
    print("\n=== Test 1: Load Single ETF ===")
    try:
        df = load_single_etf('150013.SZ', DATA_DIR)
        print(f"✓ Loaded 150013.SZ: {len(df)} rows")
        print(f"  Columns: {df.columns.tolist()}")
        print(f"  Date range: {df.index.min()} to {df.index.max()}")
        print(f"  Sample data:\n{df.head(3)}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_load_with_date_range():
    """Test loading with date range."""
    print("\n=== Test 2: Load with Date Range ===")
    try:
        df = load_single_etf(
            '150013.SZ',
            DATA_DIR,
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        print(f"✓ Loaded with date filter: {len(df)} rows")
        print(f"  Date range: {df.index.min()} to {df.index.max()}")
        assert df.index.min() >= pd.Timestamp('2020-01-01')
        assert df.index.max() <= pd.Timestamp('2020-12-31')
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_load_universe():
    """Test loading multiple ETFs."""
    print("\n=== Test 3: Load Universe ===")
    try:
        symbols = ['150013.SZ', '150016.SZ', '150017.SZ']
        data_dict = load_universe(symbols, DATA_DIR)
        print(f"✓ Loaded {len(data_dict)} symbols")
        for symbol, df in data_dict.items():
            print(f"  {symbol}: {len(df)} rows, {df.index.min()} to {df.index.max()}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_load_from_pool():
    """Test loading from pool file."""
    print("\n=== Test 4: Load from Pool File ===")
    try:
        import os
        if not os.path.exists(POOL_FILE):
            print(f"⊘ Skipped: Pool file not found: {POOL_FILE}")
            return True

        data_dict = load_universe_from_file(
            POOL_FILE,
            DATA_DIR,
            start_date='2020-01-01',
            end_date='2020-12-31',
            skip_errors=True
        )
        print(f"✓ Loaded {len(data_dict)} symbols from pool file")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_liquidity_filter():
    """Test liquidity filtering."""
    print("\n=== Test 5: Liquidity Filter ===")
    try:
        symbols = ['150013.SZ', '150016.SZ', '150017.SZ']
        data_dict = load_universe(symbols, DATA_DIR)
        print(f"  Before filter: {len(data_dict)} symbols")

        filtered = filter_by_liquidity(
            data_dict,
            min_amount=50_000_000,  # 50M yuan
            lookback_days=20
        )
        print(f"✓ After filter: {len(filtered)} symbols")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_align_dates():
    """Test date alignment."""
    print("\n=== Test 6: Align Dates ===")
    try:
        symbols = ['150013.SZ', '150016.SZ', '150017.SZ']
        data_dict = load_universe(
            symbols,
            DATA_DIR,
            start_date='2020-01-01',
            end_date='2020-12-31'
        )

        aligned = align_dates(data_dict, method='intersection')
        print(f"✓ Aligned {len(aligned)} symbols")

        # Check all have same dates
        date_lengths = [len(df) for df in aligned.values()]
        print(f"  Date counts: {date_lengths}")
        assert len(set(date_lengths)) == 1, "Not all symbols have same dates"
        print(f"  All symbols have {date_lengths[0]} common dates")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_full_pipeline():
    """Test complete pipeline."""
    print("\n=== Test 7: Full Pipeline ===")
    try:
        import os
        if not os.path.exists(POOL_FILE):
            print(f"⊘ Skipped: Pool file not found")
            return True

        # Load
        data_dict = load_universe_from_file(
            POOL_FILE,
            DATA_DIR,
            start_date='2020-01-01',
            end_date='2020-12-31',
            skip_errors=True
        )
        print(f"  1. Loaded: {len(data_dict)} symbols")

        # Filter liquidity
        liquid_dict = filter_by_liquidity(
            data_dict,
            min_amount=50_000_000,
            lookback_days=20
        )
        print(f"  2. After liquidity filter: {len(liquid_dict)} symbols")

        # Validate quality
        valid_dict = validate_data_quality(
            liquid_dict,
            min_data_points=100,
            max_missing_pct=0.05
        )
        print(f"  3. After quality validation: {len(valid_dict)} symbols")

        # Align dates
        aligned_dict = align_dates(valid_dict, method='intersection')
        print(f"  4. After date alignment: {len(aligned_dict)} symbols")

        # Get date range
        min_date, max_date = get_data_date_range(aligned_dict)
        print(f"  5. Final date range: {min_date} to {max_date}")

        print(f"✓ Pipeline completed successfully")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import pandas as pd

    print("=" * 60)
    print("Data Loader Manual Tests")
    print("=" * 60)

    results = []
    results.append(test_load_single())
    results.append(test_load_with_date_range())
    results.append(test_load_universe())
    results.append(test_load_from_pool())
    results.append(test_liquidity_filter())
    results.append(test_align_dates())
    results.append(test_full_pipeline())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
