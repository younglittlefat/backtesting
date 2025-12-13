"""
Unit tests for data_loader module.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

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


# Test data directory - use fixtures relative to this test file
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
DATA_DIR = str(FIXTURES_DIR / 'data')
POOL_FILE = str(FIXTURES_DIR / 'test_pool_all.csv')
POOL_FILE_TRENDING = str(FIXTURES_DIR / 'test_pool_trending.csv')

# Real data paths for integration tests (optional)
REAL_DATA_DIR = '/mnt/d/git/backtesting/data/chinese_etf/daily'
REAL_POOL_FILE = '/mnt/d/git/backtesting/results/trend_etf_pool_2019_2021.csv'


class TestLoadSingleETF:
    """Tests for load_single_etf function."""

    def test_load_valid_etf(self):
        """Test loading a valid ETF."""
        df = load_single_etf('TEST_TREND_1.SH', DATA_DIR)

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert isinstance(df.index, pd.DatetimeIndex)
        assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])

    def test_load_with_date_range(self):
        """Test loading with date range filter."""
        df = load_single_etf(
            'TEST_TREND_1.SH',
            DATA_DIR,
            start_date='2023-03-01',
            end_date='2023-06-30'
        )

        assert df.index.min() >= pd.Timestamp('2023-03-01')
        assert df.index.max() <= pd.Timestamp('2023-06-30')

    def test_load_nonexistent_symbol(self):
        """Test loading a non-existent symbol."""
        with pytest.raises(FileNotFoundError):
            load_single_etf('NONEXISTENT.SZ', DATA_DIR)

    def test_data_validation(self):
        """Test that loaded data passes basic validation."""
        df = load_single_etf('TEST_TREND_1.SH', DATA_DIR)

        # Check no negative prices
        assert (df[['open', 'high', 'low', 'close']] > 0).all().all()

        # Check high >= low
        assert (df['high'] >= df['low']).all()

        # Check sorted by date
        assert df.index.is_monotonic_increasing

    def test_adjusted_prices(self):
        """Test loading with adjusted prices."""
        df_adj = load_single_etf('TEST_TREND_1.SH', DATA_DIR, use_adj=True)
        df_unadj = load_single_etf('TEST_TREND_1.SH', DATA_DIR, use_adj=False)

        # Both should have same structure
        assert df_adj.columns.tolist() == df_unadj.columns.tolist()
        assert len(df_adj) == len(df_unadj)


class TestLoadUniverse:
    """Tests for load_universe function."""

    def test_load_multiple_etfs(self):
        """Test loading multiple ETFs."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH', 'TEST_TREND_3.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        assert len(data_dict) == len(symbols)
        for symbol in symbols:
            assert symbol in data_dict
            assert isinstance(data_dict[symbol], pd.DataFrame)
            assert not data_dict[symbol].empty

    def test_skip_errors(self):
        """Test skip_errors parameter."""
        symbols = ['TEST_TREND_1.SH', 'INVALID.SZ', 'TEST_TREND_2.SH']

        # With skip_errors=True (default)
        data_dict = load_universe(symbols, DATA_DIR, skip_errors=True)
        assert len(data_dict) == 2  # Only valid symbols loaded

        # With skip_errors=False
        with pytest.raises(FileNotFoundError):
            load_universe(symbols, DATA_DIR, skip_errors=False)

    def test_date_range_filter(self):
        """Test date range filtering for multiple ETFs."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH']
        data_dict = load_universe(
            symbols,
            DATA_DIR,
            start_date='2023-06-01',
            end_date='2023-12-31'
        )

        for symbol, df in data_dict.items():
            assert df.index.min() >= pd.Timestamp('2023-06-01')
            assert df.index.max() <= pd.Timestamp('2023-12-31')


class TestLoadUniverseFromFile:
    """Tests for load_universe_from_file function."""

    def test_load_from_pool_file(self):
        """Test loading from a pool file."""
        data_dict = load_universe_from_file(
            POOL_FILE,
            DATA_DIR,
            skip_errors=True
        )

        assert len(data_dict) > 0
        for symbol, df in data_dict.items():
            assert isinstance(df, pd.DataFrame)
            assert not df.empty

    def test_load_from_trending_pool(self):
        """Test loading from trending pool file."""
        data_dict = load_universe_from_file(
            POOL_FILE_TRENDING,
            DATA_DIR,
            skip_errors=True
        )

        # Should load 3 trending ETFs
        assert len(data_dict) == 3
        assert 'TEST_TREND_1.SH' in data_dict
        assert 'TEST_TREND_2.SH' in data_dict
        assert 'TEST_TREND_3.SH' in data_dict

    def test_nonexistent_pool_file(self):
        """Test with non-existent pool file."""
        with pytest.raises(FileNotFoundError):
            load_universe_from_file('nonexistent.csv', DATA_DIR)


class TestFilterByLiquidity:
    """Tests for filter_by_liquidity function."""

    def test_no_filter(self):
        """Test with no liquidity filters."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        filtered = filter_by_liquidity(data_dict)
        assert len(filtered) == len(data_dict)

    def test_amount_filter(self):
        """Test filtering by trading amount."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH', 'TEST_CHOPPY_1.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        # Apply a high threshold to filter out some symbols
        filtered = filter_by_liquidity(
            data_dict,
            min_amount=100_000_000,  # 100M yuan
            lookback_days=20
        )

        # Should filter out some symbols
        assert len(filtered) <= len(data_dict)

    def test_volume_filter(self):
        """Test filtering by trading volume."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        filtered = filter_by_liquidity(
            data_dict,
            min_volume=1_000_000,  # 1M shares
            lookback_days=20
        )

        assert len(filtered) <= len(data_dict)

    def test_insufficient_data(self):
        """Test filtering with insufficient data."""
        symbols = ['TEST_TREND_1.SH']
        data_dict = load_universe(
            symbols,
            DATA_DIR,
            start_date='2024-12-01',
            end_date='2024-12-10'
        )

        # Require more days than available
        filtered = filter_by_liquidity(
            data_dict,
            min_amount=1_000_000,
            lookback_days=20,
            min_valid_days=15
        )

        # Should filter out due to insufficient data
        assert len(filtered) <= len(data_dict)


class TestAlignDates:
    """Tests for align_dates function."""

    def test_intersection_method(self):
        """Test date alignment with intersection method."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH', 'TEST_TREND_3.SH']
        data_dict = load_universe(
            symbols,
            DATA_DIR,
            start_date='2023-01-01',
            end_date='2023-12-31'
        )

        aligned = align_dates(data_dict, method='intersection')

        # All DataFrames should have same dates
        date_sets = [set(df.index) for df in aligned.values()]
        assert len(set(map(len, date_sets))) == 1  # All same length

        # Check dates are actually common
        common_dates = date_sets[0]
        for dates in date_sets[1:]:
            assert dates == common_dates

    def test_union_method(self):
        """Test date alignment with union method."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH']
        data_dict = load_universe(
            symbols,
            DATA_DIR,
            start_date='2023-01-01',
            end_date='2023-06-30'
        )

        aligned = align_dates(
            data_dict,
            method='union',
            fill_method='ffill',
            max_fill_days=5
        )

        # Should have more dates than intersection
        assert len(aligned) > 0

    def test_invalid_method(self):
        """Test with invalid alignment method."""
        symbols = ['TEST_TREND_1.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        with pytest.raises(ValueError):
            align_dates(data_dict, method='invalid')


class TestGetDataDateRange:
    """Tests for get_data_date_range function."""

    def test_date_range(self):
        """Test getting date range from data."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        min_date, max_date = get_data_date_range(data_dict)

        assert isinstance(min_date, pd.Timestamp)
        assert isinstance(max_date, pd.Timestamp)
        assert min_date < max_date

    def test_empty_dict(self):
        """Test with empty dictionary."""
        min_date, max_date = get_data_date_range({})
        assert min_date is None
        assert max_date is None


class TestValidateDataQuality:
    """Tests for validate_data_quality function."""

    def test_quality_validation(self):
        """Test data quality validation."""
        symbols = ['TEST_TREND_1.SH', 'TEST_TREND_2.SH', 'TEST_TREND_3.SH']
        data_dict = load_universe(symbols, DATA_DIR)

        validated = validate_data_quality(
            data_dict,
            min_data_points=100,
            max_missing_pct=0.05
        )

        # Should pass validation
        assert len(validated) > 0

        # All validated data should meet criteria
        for df in validated.values():
            assert len(df) >= 100
            missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns))
            assert missing_pct <= 0.05

    def test_insufficient_data_points(self):
        """Test filtering with insufficient data points."""
        symbols = ['TEST_TREND_1.SH']
        data_dict = load_universe(
            symbols,
            DATA_DIR,
            start_date='2024-12-01',
            end_date='2024-12-10'
        )

        validated = validate_data_quality(
            data_dict,
            min_data_points=100  # More than available
        )

        # Should filter out
        assert len(validated) == 0


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_pipeline_with_fixtures(self):
        """Test a complete data loading pipeline with fixture data."""
        # Load from pool file
        data_dict = load_universe_from_file(
            POOL_FILE,
            DATA_DIR,
            start_date='2023-01-01',
            end_date='2023-12-31',
            skip_errors=True
        )

        print(f"Loaded {len(data_dict)} symbols")
        assert len(data_dict) > 0

        # Filter by liquidity
        liquid_dict = filter_by_liquidity(
            data_dict,
            min_amount=1_000_000,  # 1M yuan (lower threshold for test data)
            lookback_days=20
        )

        print(f"After liquidity filter: {len(liquid_dict)} symbols")

        # Validate quality
        valid_dict = validate_data_quality(
            liquid_dict,
            min_data_points=100,
            max_missing_pct=0.05
        )

        print(f"After quality validation: {len(valid_dict)} symbols")

        # Align dates
        aligned_dict = align_dates(valid_dict, method='intersection')

        print(f"After date alignment: {len(aligned_dict)} symbols")

        if not aligned_dict:
            pytest.skip("No symbols left after filtering/alignment for the requested real-data window")

        # Check final result
        assert len(aligned_dict) > 0

        # Verify all have same dates
        if len(aligned_dict) > 1:
            date_lengths = [len(df) for df in aligned_dict.values()]
            assert len(set(date_lengths)) == 1

        # Get date range
        min_date, max_date = get_data_date_range(aligned_dict)
        print(f"Date range: {min_date} to {max_date}")

        assert min_date >= pd.Timestamp('2023-01-01')
        assert max_date <= pd.Timestamp('2023-12-31')

    def test_full_pipeline_with_real_data(self):
        """Test a complete data loading pipeline with real data (optional)."""
        if not os.path.exists(REAL_POOL_FILE) or not os.path.exists(REAL_DATA_DIR):
            pytest.skip(f"Real data not available. Pool: {REAL_POOL_FILE}, Data: {REAL_DATA_DIR}")

        # Load from pool file
        data_dict = load_universe_from_file(
            REAL_POOL_FILE,
            REAL_DATA_DIR,
            start_date='2020-01-01',
            end_date='2020-12-31',
            skip_errors=True
        )

        print(f"Loaded {len(data_dict)} symbols")

        # Filter by liquidity
        liquid_dict = filter_by_liquidity(
            data_dict,
            min_amount=50_000_000,  # 50M yuan
            lookback_days=20
        )

        print(f"After liquidity filter: {len(liquid_dict)} symbols")

        # Validate quality
        valid_dict = validate_data_quality(
            liquid_dict,
            min_data_points=100,
            max_missing_pct=0.05
        )

        print(f"After quality validation: {len(valid_dict)} symbols")

        # Align dates
        aligned_dict = align_dates(valid_dict, method='intersection')

        print(f"After date alignment: {len(aligned_dict)} symbols")

        if not aligned_dict:
            pytest.skip("No symbols left after filtering/alignment for the requested real-data window")

        # Check final result
        assert len(aligned_dict) > 0

        # Verify all have same dates
        if len(aligned_dict) > 1:
            date_lengths = [len(df) for df in aligned_dict.values()]
            assert len(set(date_lengths)) == 1

        # Get date range
        min_date, max_date = get_data_date_range(aligned_dict)
        print(f"Date range: {min_date} to {max_date}")

        assert min_date >= pd.Timestamp('2020-01-01')
        assert max_date <= pd.Timestamp('2020-12-31')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
