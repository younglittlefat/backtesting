"""
Unit tests for dynamic ETF pool functionality.
"""

import unittest
import tempfile
import os
from pathlib import Path
import pandas as pd
import json

from etf_trend_following_v2.src.config_loader import Config, UniverseConfig, create_default_config
from etf_trend_following_v2.src.data_loader import scan_all_etfs, filter_by_dynamic_liquidity


class TestScanAllETFs(unittest.TestCase):
    """Test scan_all_etfs function"""

    def setUp(self):
        """Create temporary directory with mock ETF files"""
        self.temp_dir = tempfile.mkdtemp()
        self.etf_dir = Path(self.temp_dir) / 'etf'
        self.etf_dir.mkdir(parents=True, exist_ok=True)

        # Create mock ETF CSV files
        self.symbols = ['159915.SZ', '510050.SH', '512880.SH']
        for symbol in self.symbols:
            csv_path = self.etf_dir / f"{symbol}.csv"
            # Create a minimal CSV file
            df = pd.DataFrame({
                'trade_date': ['20240101', '20240102'],
                'open': [10.0, 10.1],
                'high': [10.2, 10.3],
                'low': [9.9, 10.0],
                'close': [10.1, 10.2],
                'volume': [1000000, 1100000],
                'amount': [10000000, 11000000]
            })
            df.to_csv(csv_path, index=False)

        # Create a non-ETF file (should be ignored)
        readme_path = self.etf_dir / 'README.txt'
        readme_path.write_text('This is a readme file')

    def tearDown(self):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_scan_all_etfs_with_etf_subdir(self):
        """Test scanning with etf subdirectory"""
        symbols = scan_all_etfs(self.temp_dir)
        self.assertEqual(sorted(symbols), sorted(self.symbols))

    def test_scan_all_etfs_direct_path(self):
        """Test scanning without etf subdirectory"""
        symbols = scan_all_etfs(str(self.etf_dir))
        self.assertEqual(sorted(symbols), sorted(self.symbols))

    def test_scan_all_etfs_nonexistent_dir(self):
        """Test scanning non-existent directory"""
        symbols = scan_all_etfs('/nonexistent/path')
        self.assertEqual(symbols, [])


class TestFilterByDynamicLiquidity(unittest.TestCase):
    """Test filter_by_dynamic_liquidity function"""

    def setUp(self):
        """Create temporary directory with mock ETF data"""
        self.temp_dir = tempfile.mkdtemp()
        self.etf_dir = Path(self.temp_dir) / 'etf'
        self.etf_dir.mkdir(parents=True, exist_ok=True)

        # Create ETF with good liquidity (should pass)
        self._create_etf_csv(
            '159915.SZ',
            days=100,
            avg_amount=10_000_000,  # 10M yuan
            avg_volume=1_000_000     # 1M shares
        )

        # Create ETF with low liquidity (should fail)
        self._create_etf_csv(
            '510050.SH',
            days=100,
            avg_amount=1_000_000,    # 1M yuan (too low)
            avg_volume=100_000       # 100k shares (too low)
        )

        # Create newly listed ETF (should fail min_listing_days)
        self._create_etf_csv(
            '512880.SH',
            days=30,  # Only 30 days (< 60 required)
            avg_amount=10_000_000,
            avg_volume=1_000_000
        )

    def tearDown(self):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_etf_csv(self, symbol: str, days: int, avg_amount: float, avg_volume: float):
        """Helper to create mock ETF CSV with specified characteristics"""
        dates = pd.date_range(end='2024-01-02', periods=days, freq='D')
        df = pd.DataFrame({
            'trade_date': dates.strftime('%Y%m%d'),
            'open': [10.0] * days,
            'high': [10.2] * days,
            'low': [9.9] * days,
            'close': [10.1] * days,
            'volume': [avg_volume] * days,
            'amount': [avg_amount] * days
        })
        csv_path = self.etf_dir / f"{symbol}.csv"
        df.to_csv(csv_path, index=False)

    def test_filter_by_dynamic_liquidity_basic(self):
        """Test basic filtering with liquidity thresholds"""
        symbols = ['159915.SZ', '510050.SH', '512880.SH']
        passed = filter_by_dynamic_liquidity(
            symbols=symbols,
            data_dir=self.temp_dir,
            as_of_date='2024-01-02',
            min_amount=5_000_000,   # 5M yuan
            min_volume=500_000,      # 500k shares
            lookback_days=5,
            min_listing_days=60,
            use_adj=False
        )

        # Only 159915.SZ should pass (good liquidity + enough listing days)
        self.assertEqual(passed, ['159915.SZ'])

    def test_filter_by_dynamic_liquidity_no_thresholds(self):
        """Test filtering with no liquidity thresholds (only listing days)"""
        symbols = ['159915.SZ', '510050.SH', '512880.SH']
        passed = filter_by_dynamic_liquidity(
            symbols=symbols,
            data_dir=self.temp_dir,
            as_of_date='2024-01-02',
            min_amount=None,
            min_volume=None,
            lookback_days=5,
            min_listing_days=60,
            use_adj=False
        )

        # 159915 and 510050 should pass (both have >= 60 days)
        self.assertEqual(sorted(passed), ['159915.SZ', '510050.SH'])

    def test_filter_by_dynamic_liquidity_empty_list(self):
        """Test filtering with empty symbol list"""
        passed = filter_by_dynamic_liquidity(
            symbols=[],
            data_dir=self.temp_dir,
            as_of_date='2024-01-02',
            min_amount=5_000_000,
            min_volume=500_000,
            lookback_days=5,
            min_listing_days=60,
            use_adj=False
        )
        self.assertEqual(passed, [])


class TestUniverseConfigValidation(unittest.TestCase):
    """Test UniverseConfig validation for dynamic pool"""

    def test_dynamic_pool_requires_all_etf_data_dir(self):
        """Test that dynamic_pool=True requires all_etf_data_dir"""
        config = UniverseConfig(
            dynamic_pool=True,
            all_etf_data_dir=None
        )
        errors = config.validate(require_pool=False)
        self.assertTrue(any('all_etf_data_dir' in e for e in errors))

    def test_dynamic_pool_with_all_etf_data_dir(self):
        """Test that dynamic_pool=True with all_etf_data_dir is valid"""
        config = UniverseConfig(
            dynamic_pool=True,
            all_etf_data_dir='/path/to/data'
        )
        errors = config.validate(require_pool=False)
        # Should not have all_etf_data_dir error
        self.assertFalse(any('all_etf_data_dir' in e for e in errors))

    def test_dynamic_pool_false_requires_pool(self):
        """Test that dynamic_pool=False requires pool_file or pool_list"""
        config = UniverseConfig(
            dynamic_pool=False,
            pool_file=None,
            pool_list=None
        )
        errors = config.validate(require_pool=True)
        self.assertTrue(any('pool_file' in e or 'pool_list' in e for e in errors))

    def test_dynamic_pool_false_with_pool_file(self):
        """Test that dynamic_pool=False with pool_file is valid"""
        config = UniverseConfig(
            dynamic_pool=False,
            pool_file='/path/to/pool.csv'
        )
        errors = config.validate(require_pool=True)
        # Should not have pool requirement error
        self.assertFalse(any('pool_file' in e or 'pool_list' in e for e in errors))


class TestDynamicPoolIntegration(unittest.TestCase):
    """Integration tests for dynamic pool in portfolio runner"""

    def setUp(self):
        """Create temporary directory with mock ETF data"""
        self.temp_dir = tempfile.mkdtemp()
        self.etf_dir = Path(self.temp_dir) / 'etf'
        self.etf_dir.mkdir(parents=True, exist_ok=True)

        # Create multiple ETFs with varying liquidity over time
        self._create_time_varying_etf('159915.SZ', start_date='2023-01-01', days=400)
        self._create_time_varying_etf('510050.SH', start_date='2023-06-01', days=200)
        self._create_time_varying_etf('512880.SH', start_date='2023-11-01', days=50)

    def tearDown(self):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_time_varying_etf(self, symbol: str, start_date: str, days: int):
        """Create ETF CSV with time-varying liquidity"""
        dates = pd.date_range(start=start_date, periods=days, freq='D')
        # Simulate increasing liquidity over time
        # Start with higher base amounts to ensure early ETFs pass thresholds
        amounts = [5_000_000 + i * 50_000 for i in range(days)]
        volumes = [500_000 + i * 5_000 for i in range(days)]

        df = pd.DataFrame({
            'trade_date': dates.strftime('%Y%m%d'),
            'open': [10.0] * days,
            'high': [10.2] * days,
            'low': [9.9] * days,
            'close': [10.1] * days,
            'volume': volumes,
            'amount': amounts
        })
        csv_path = self.etf_dir / f"{symbol}.csv"
        df.to_csv(csv_path, index=False)

    def test_dynamic_pool_changes_over_time(self):
        """Test that dynamic pool changes as ETFs meet liquidity criteria"""
        symbols = ['159915.SZ', '510050.SH', '512880.SH']

        # Test on early date (2023-03-01): only 159915 should qualify
        # 159915 started 2023-01-01, has 60+ days by 2023-03-01
        passed_early = filter_by_dynamic_liquidity(
            symbols=symbols,
            data_dir=self.temp_dir,
            as_of_date='2023-03-01',
            min_amount=5_000_000,
            min_volume=500_000,
            lookback_days=5,
            min_listing_days=60,
            use_adj=False
        )
        # 159915 should pass, others not yet listed or don't have 60 days
        self.assertEqual(len(passed_early), 1)
        self.assertIn('159915.SZ', passed_early)

        # Test on later date (2023-08-15): 159915 and 510050 should qualify
        # 510050 started 2023-06-01, should have 60+ days by 2023-08-15
        passed_later = filter_by_dynamic_liquidity(
            symbols=symbols,
            data_dir=self.temp_dir,
            as_of_date='2023-08-15',
            min_amount=5_000_000,
            min_volume=500_000,
            lookback_days=5,
            min_listing_days=60,
            use_adj=False
        )
        # Both 159915 and 510050 should pass now
        self.assertGreaterEqual(len(passed_later), 2)
        self.assertIn('159915.SZ', passed_later)
        self.assertIn('510050.SH', passed_later)


if __name__ == '__main__':
    unittest.main()
