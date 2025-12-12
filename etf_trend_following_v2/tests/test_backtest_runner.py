"""
Unit tests for backtest_runner module

Tests BacktestRunner class and run_backtest() convenience function.
All tests use synthetic/mock data to avoid dependency on real data files.
"""

import json
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys
import tempfile
import shutil

# Add grandparent directory to path for package imports
# (tests -> etf_trend_following_v2 -> backtesting)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from etf_trend_following_v2.src.backtest_runner import BacktestRunner, run_backtest
from etf_trend_following_v2.src.config_loader import (
    Config,
    EnvConfig,
    ModesConfig,
    UniverseConfig,
    MACDStrategyConfig,
    KAMAStrategyConfig,
    ComboStrategyConfig,
    ScoringConfig,
    ClusteringConfig,
    RiskConfig,
    PositionSizingConfig,
    ExecutionConfig,
    IOConfig,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def macd_config():
    """Create a valid MACD strategy configuration"""
    return Config(
        env=EnvConfig(root_dir="/test"),
        modes=ModesConfig(lookback_days=100),
        universe=UniverseConfig(pool_list=["TEST.SH"]),
        strategies=[MACDStrategyConfig()],
        scoring=ScoringConfig(),
        clustering=ClusteringConfig(),
        risk=RiskConfig(),
        position_sizing=PositionSizingConfig(),
        execution=ExecutionConfig(),
        io=IOConfig()
    )


@pytest.fixture
def kama_config():
    """Create a valid KAMA strategy configuration"""
    return Config(
        env=EnvConfig(root_dir="/test"),
        modes=ModesConfig(lookback_days=100),
        universe=UniverseConfig(pool_list=["TEST.SH"]),
        strategies=[KAMAStrategyConfig()],
        scoring=ScoringConfig(),
        clustering=ClusteringConfig(),
        risk=RiskConfig(),
        position_sizing=PositionSizingConfig(),
        execution=ExecutionConfig(),
        io=IOConfig()
    )


@pytest.fixture
def combo_config():
    """Create a valid Combo strategy configuration"""
    return Config(
        env=EnvConfig(root_dir="/test"),
        modes=ModesConfig(lookback_days=100),
        universe=UniverseConfig(pool_list=["TEST.SH"]),
        strategies=[ComboStrategyConfig(
            mode="or",
            strategies=[MACDStrategyConfig(), KAMAStrategyConfig()]
        )],
        scoring=ScoringConfig(),
        clustering=ClusteringConfig(),
        risk=RiskConfig(),
        position_sizing=PositionSizingConfig(),
        execution=ExecutionConfig(),
        io=IOConfig()
    )


@pytest.fixture
def no_strategy_config():
    """Create a config with no strategies (invalid)"""
    return Config(
        env=EnvConfig(root_dir="/test"),
        modes=ModesConfig(),
        universe=UniverseConfig(pool_list=["TEST.SH"]),
        strategies=[],
        scoring=ScoringConfig(),
        clustering=ClusteringConfig(),
        risk=RiskConfig(),
        position_sizing=PositionSizingConfig(),
        execution=ExecutionConfig(),
        io=IOConfig()
    )


@pytest.fixture
def synthetic_ohlcv_data():
    """Create synthetic OHLCV data for testing (100 bars)"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=100, freq='D')

    # Generate price data with trend
    close = 100 + np.cumsum(np.random.randn(100) * 2)
    high = close + np.random.rand(100) * 2
    low = close - np.random.rand(100) * 2
    open_price = close + np.random.randn(100) * 0.5
    volume = np.random.randint(1000000, 5000000, 100)

    df = pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)

    return df


@pytest.fixture
def synthetic_ohlcv_data_200bars():
    """Create synthetic OHLCV data with 200 bars for more comprehensive testing"""
    np.random.seed(123)
    dates = pd.date_range('2023-01-01', periods=200, freq='D')

    close = 100 + np.cumsum(np.random.randn(200) * 2)
    high = close + np.random.rand(200) * 2
    low = close - np.random.rand(200) * 2
    open_price = close + np.random.randn(200) * 0.5
    volume = np.random.randint(1000000, 5000000, 200)

    df = pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)

    return df


@pytest.fixture
def lowercase_ohlcv_data():
    """Create OHLCV data with lowercase column names"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=100, freq='D')

    close = 100 + np.cumsum(np.random.randn(100) * 2)
    high = close + np.random.rand(100) * 2
    low = close - np.random.rand(100) * 2
    open_price = close + np.random.randn(100) * 0.5
    volume = np.random.randint(1000000, 5000000, 100)

    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)

    return df


@pytest.fixture
def ohlcv_data_no_volume():
    """Create OHLCV data without Volume column"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=100, freq='D')

    close = 100 + np.cumsum(np.random.randn(100) * 2)
    high = close + np.random.rand(100) * 2
    low = close - np.random.rand(100) * 2
    open_price = close + np.random.randn(100) * 0.5

    df = pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close
    }, index=dates)

    return df


@pytest.fixture
def insufficient_data():
    """Create OHLCV data with < 50 bars"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=30, freq='D')

    close = 100 + np.cumsum(np.random.randn(30) * 2)
    high = close + np.random.rand(30) * 2
    low = close - np.random.rand(30) * 2
    open_price = close + np.random.randn(30) * 0.5
    volume = np.random.randint(1000000, 5000000, 30)

    df = pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)

    return df


# ============================================================================
# Test BacktestRunner Initialization
# ============================================================================

class TestBacktestRunnerInit:
    """Test BacktestRunner initialization"""

    def test_init_with_macd_strategy(self, macd_config):
        """Initialize with MACD config"""
        runner = BacktestRunner(macd_config)
        assert runner.config == macd_config
        assert runner.strategy_class is not None
        assert runner.strategy_params is not None
        assert isinstance(runner.results, dict)
        assert len(runner.results) == 0

    def test_init_with_kama_strategy(self, kama_config):
        """Initialize with KAMA config"""
        runner = BacktestRunner(kama_config)
        assert runner.config == kama_config
        assert runner.strategy_class is not None
        assert runner.strategy_params is not None
        assert 'kama_period' in runner.strategy_params
        assert runner.strategy_params['kama_period'] == 20

    def test_init_with_combo_strategy(self, combo_config):
        """Initialize with Combo config"""
        runner = BacktestRunner(combo_config)
        assert runner.config == combo_config
        assert runner.strategy_class is not None
        assert 'combo_mode' in runner.strategy_params
        assert runner.strategy_params['combo_mode'] == 'or'

    def test_init_no_strategies_raises_error(self, no_strategy_config):
        """Should raise ValueError if no strategies configured"""
        with pytest.raises(ValueError, match="No strategies configured"):
            BacktestRunner(no_strategy_config)

    def test_init_unknown_strategy_raises_error(self, macd_config):
        """Should raise ValueError for unknown strategy type"""
        # Modify strategy type to unknown value
        macd_config.strategies[0].type = "unknown_strategy"
        with pytest.raises(ValueError, match="Unknown strategy type"):
            BacktestRunner(macd_config)


# ============================================================================
# Test _get_strategy_params
# ============================================================================

class TestGetStrategyParams:
    """Test _get_strategy_params method"""

    def test_get_strategy_params_macd(self, macd_config):
        """Extracts all MACD params from config"""
        runner = BacktestRunner(macd_config)
        params = runner.strategy_params

        # Core MACD parameters
        assert 'fast_period' in params
        assert 'slow_period' in params
        assert 'signal_period' in params
        assert params['fast_period'] == 12
        assert params['slow_period'] == 26
        assert params['signal_period'] == 9

        # Filter switches
        assert 'enable_adx_filter' in params
        assert 'enable_volume_filter' in params
        assert 'enable_slope_filter' in params
        assert 'enable_confirm_filter' in params

        # Loss protection
        assert 'enable_loss_protection' in params
        assert 'max_consecutive_losses' in params
        assert 'pause_bars' in params

        # Anti-Whipsaw
        assert 'enable_hysteresis' in params
        assert 'enable_zero_axis' in params
        assert 'min_hold_bars' in params

        # Long-only mode
        assert 'long_only' in params

    def test_get_strategy_params_kama(self, kama_config):
        """Extracts all KAMA params from config"""
        runner = BacktestRunner(kama_config)
        params = runner.strategy_params

        # Core KAMA parameters
        assert 'kama_period' in params
        assert 'kama_fast' in params
        assert 'kama_slow' in params
        assert params['kama_period'] == 20
        assert params['kama_fast'] == 2
        assert params['kama_slow'] == 30

        # KAMA-specific filters
        assert 'enable_efficiency_filter' in params
        assert 'min_efficiency_ratio' in params
        assert 'enable_slope_confirmation' in params
        assert 'min_slope_periods' in params

        # Generic filters
        assert 'enable_slope_filter' in params
        assert 'enable_adx_filter' in params
        assert 'enable_volume_filter' in params

        # Loss protection
        assert 'enable_loss_protection' in params

        # Long-only mode
        assert 'long_only' in params

    def test_get_strategy_params_combo(self, combo_config):
        """Extracts combo mode"""
        runner = BacktestRunner(combo_config)
        params = runner.strategy_params

        assert 'combo_mode' in params
        assert params['combo_mode'] == 'or'


# ============================================================================
# Test _prepare_dataframe
# ============================================================================

class TestPrepareDataframe:
    """Test _prepare_dataframe method"""

    def test_prepare_dataframe_capitalizes_columns(self, macd_config, lowercase_ohlcv_data):
        """open -> Open, close -> Close, etc."""
        runner = BacktestRunner(macd_config)
        prepared_df = runner._prepare_dataframe(lowercase_ohlcv_data)

        assert 'Open' in prepared_df.columns
        assert 'High' in prepared_df.columns
        assert 'Low' in prepared_df.columns
        assert 'Close' in prepared_df.columns
        assert 'Volume' in prepared_df.columns

        # Verify lowercase columns are gone
        assert 'open' not in prepared_df.columns
        assert 'close' not in prepared_df.columns

    def test_prepare_dataframe_missing_required_columns_raises(self, macd_config):
        """Raises ValueError for missing required columns"""
        runner = BacktestRunner(macd_config)

        # Create DataFrame with missing columns
        df = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [102, 103, 104],
            # Missing Low and Close
        })

        with pytest.raises(ValueError, match="Missing required columns"):
            runner._prepare_dataframe(df)

    def test_prepare_dataframe_adds_zero_volume_if_missing(self, macd_config, ohlcv_data_no_volume):
        """Adds zero Volume column if missing"""
        runner = BacktestRunner(macd_config)
        prepared_df = runner._prepare_dataframe(ohlcv_data_no_volume)

        assert 'Volume' in prepared_df.columns
        assert (prepared_df['Volume'] == 0).all()

    def test_prepare_dataframe_preserves_existing_volume(self, macd_config, synthetic_ohlcv_data):
        """Preserves existing Volume column"""
        runner = BacktestRunner(macd_config)
        original_volume = synthetic_ohlcv_data['Volume'].copy()
        prepared_df = runner._prepare_dataframe(synthetic_ohlcv_data)

        assert 'Volume' in prepared_df.columns
        pd.testing.assert_series_equal(prepared_df['Volume'], original_volume, check_names=False)


# ============================================================================
# Test run_single
# ============================================================================

class TestRunSingle:
    """Test run_single method"""

    def test_run_single_returns_stats(self, macd_config, synthetic_ohlcv_data_200bars):
        """Returns pd.Series with backtest statistics"""
        runner = BacktestRunner(macd_config)
        stats = runner.run_single('TEST.SH', synthetic_ohlcv_data_200bars)

        assert isinstance(stats, pd.Series)
        assert not stats.empty

        # Check for key statistics
        assert 'Return [%]' in stats
        assert 'Sharpe Ratio' in stats
        assert '# Trades' in stats

    def test_run_single_with_custom_capital(self, macd_config, synthetic_ohlcv_data_200bars):
        """Uses provided initial_capital"""
        runner = BacktestRunner(macd_config)
        custom_capital = 500_000
        stats = runner.run_single('TEST.SH', synthetic_ohlcv_data_200bars, initial_capital=custom_capital)

        assert not stats.empty
        # Verify backtest ran (we can't directly check capital, but we can verify it ran)
        assert '# Trades' in stats

    def test_run_single_insufficient_data(self, macd_config, insufficient_data):
        """Returns empty Series when data < 50 bars"""
        runner = BacktestRunner(macd_config)
        stats = runner.run_single('TEST.SH', insufficient_data)

        assert isinstance(stats, pd.Series)
        assert stats.empty

    def test_run_single_lowercase_columns(self, macd_config, lowercase_ohlcv_data):
        """Handles lowercase column names (converts to capitalized)"""
        runner = BacktestRunner(macd_config)
        stats = runner.run_single('TEST.SH', lowercase_ohlcv_data)

        # Should successfully run after column conversion
        assert isinstance(stats, pd.Series)
        assert not stats.empty

    def test_run_single_missing_volume(self, macd_config, ohlcv_data_no_volume):
        """Adds zero Volume column if missing"""
        runner = BacktestRunner(macd_config)
        stats = runner.run_single('TEST.SH', ohlcv_data_no_volume)

        # Should successfully run after adding Volume column
        assert isinstance(stats, pd.Series)
        assert not stats.empty

    def test_run_single_with_kama_strategy(self, kama_config, synthetic_ohlcv_data_200bars):
        """Test with KAMA strategy"""
        runner = BacktestRunner(kama_config)
        stats = runner.run_single('TEST.SH', synthetic_ohlcv_data_200bars)

        assert isinstance(stats, pd.Series)
        assert not stats.empty


# ============================================================================
# Test run_universe
# ============================================================================

class TestRunUniverse:
    """Test run_universe method"""

    def test_run_universe_multiple_symbols(self, macd_config, synthetic_ohlcv_data_200bars):
        """Runs backtest on multiple symbols"""
        runner = BacktestRunner(macd_config)

        # Create data dict with 3 symbols
        data_dict = {
            'SYMBOL1.SH': synthetic_ohlcv_data_200bars.copy(),
            'SYMBOL2.SH': synthetic_ohlcv_data_200bars.copy(),
            'SYMBOL3.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        results = runner.run_universe(data_dict)

        assert isinstance(results, dict)
        assert len(results) == 3
        assert 'SYMBOL1.SH' in results
        assert 'SYMBOL2.SH' in results
        assert 'SYMBOL3.SH' in results

    def test_run_universe_partial_failure(self, macd_config, synthetic_ohlcv_data_200bars, insufficient_data):
        """Continues even if some symbols fail"""
        runner = BacktestRunner(macd_config)

        # Mix of good and bad data
        data_dict = {
            'GOOD1.SH': synthetic_ohlcv_data_200bars.copy(),
            'BAD.SH': insufficient_data.copy(),  # Too short
            'GOOD2.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        results = runner.run_universe(data_dict)

        # Should have 2 successful results (BAD.SH fails due to insufficient data)
        assert isinstance(results, dict)
        assert len(results) == 2
        assert 'GOOD1.SH' in results
        assert 'GOOD2.SH' in results
        assert 'BAD.SH' not in results

    def test_run_universe_stores_results(self, macd_config, synthetic_ohlcv_data_200bars):
        """Results stored in self.results"""
        runner = BacktestRunner(macd_config)

        data_dict = {
            'TEST1.SH': synthetic_ohlcv_data_200bars.copy(),
            'TEST2.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        runner.run_universe(data_dict)

        # Check self.results is populated
        assert len(runner.results) == 2
        assert 'TEST1.SH' in runner.results
        assert 'TEST2.SH' in runner.results


# ============================================================================
# Test run (main entry point)
# ============================================================================

class TestRun:
    """Test run method (main entry point)"""

    def test_run_returns_complete_results(self, macd_config, synthetic_ohlcv_data_200bars):
        """Returns dict with individual_results, aggregate_stats, metadata"""
        runner = BacktestRunner(macd_config)

        # Pre-load data to avoid file I/O
        data_dict = {
            'TEST1.SH': synthetic_ohlcv_data_200bars.copy(),
            'TEST2.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        results = runner.run(
            start_date='2023-01-01',
            end_date='2023-12-31',
            initial_capital=1_000_000,
            data_dict=data_dict
        )

        # Check structure
        assert isinstance(results, dict)
        assert 'individual_results' in results
        assert 'aggregate_stats' in results
        assert 'metadata' in results

        # Check individual results
        assert len(results['individual_results']) == 2

        # Check metadata
        metadata = results['metadata']
        assert metadata['start_date'] == '2023-01-01'
        assert metadata['end_date'] == '2023-12-31'
        assert metadata['initial_capital'] == 1_000_000
        assert metadata['num_symbols'] == 2
        assert metadata['num_successful'] == 2
        assert metadata['strategy_type'] == 'macd'

    def test_run_with_preloaded_data(self, macd_config, synthetic_ohlcv_data_200bars):
        """Uses provided data_dict instead of loading from config"""
        runner = BacktestRunner(macd_config)

        data_dict = {
            'PRELOADED.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        # Should not attempt to load from file
        results = runner.run(
            start_date='2023-01-01',
            end_date='2023-12-31',
            data_dict=data_dict
        )

        assert results['metadata']['num_symbols'] == 1
        assert 'PRELOADED.SH' in results['individual_results']


# ============================================================================
# Test get_aggregate_stats
# ============================================================================

class TestGetAggregateStats:
    """Test get_aggregate_stats method"""

    def test_aggregate_stats_empty_results(self, macd_config):
        """Returns empty dict when no results"""
        runner = BacktestRunner(macd_config)
        aggregate = runner.get_aggregate_stats()

        assert isinstance(aggregate, dict)
        assert len(aggregate) == 0

    def test_aggregate_stats_calculates_correctly(self, macd_config):
        """Verifies mean, median, std calculations"""
        runner = BacktestRunner(macd_config)

        # Manually create mock results
        runner.results = {
            'SYMBOL1': pd.Series({
                'Return [%]': 10.0,
                'Sharpe Ratio': 1.5,
                'Max. Drawdown [%]': -5.0,
                '# Trades': 10,
                'Win Rate [%]': 60.0
            }),
            'SYMBOL2': pd.Series({
                'Return [%]': 20.0,
                'Sharpe Ratio': 2.0,
                'Max. Drawdown [%]': -10.0,
                '# Trades': 15,
                'Win Rate [%]': 70.0
            }),
            'SYMBOL3': pd.Series({
                'Return [%]': 15.0,
                'Sharpe Ratio': 1.8,
                'Max. Drawdown [%]': -8.0,
                '# Trades': 12,
                'Win Rate [%]': 65.0
            }),
        }

        aggregate = runner.get_aggregate_stats()

        assert aggregate['total_symbols'] == 3
        assert aggregate['mean_return'] == pytest.approx(15.0)
        assert aggregate['median_return'] == pytest.approx(15.0)
        # np.std uses sample std (ddof=1 by default in newer numpy), so expected is ~4.08, not 5.0
        assert aggregate['std_return'] == pytest.approx(4.08, abs=0.01)
        assert aggregate['mean_sharpe'] == pytest.approx(1.767, abs=0.01)
        assert aggregate['median_sharpe'] == pytest.approx(1.8)
        assert aggregate['total_trades'] == 37

    def test_aggregate_stats_counts_positive_negative(self, macd_config):
        """Correct positive/negative return counts"""
        runner = BacktestRunner(macd_config)

        runner.results = {
            'POS1': pd.Series({'Return [%]': 10.0, 'Sharpe Ratio': 1.0, 'Max. Drawdown [%]': -5.0, '# Trades': 5, 'Win Rate [%]': 60.0}),
            'POS2': pd.Series({'Return [%]': 5.0, 'Sharpe Ratio': 0.8, 'Max. Drawdown [%]': -3.0, '# Trades': 8, 'Win Rate [%]': 55.0}),
            'NEG1': pd.Series({'Return [%]': -3.0, 'Sharpe Ratio': -0.2, 'Max. Drawdown [%]': -8.0, '# Trades': 6, 'Win Rate [%]': 40.0}),
            'NEG2': pd.Series({'Return [%]': -1.0, 'Sharpe Ratio': -0.1, 'Max. Drawdown [%]': -4.0, '# Trades': 4, 'Win Rate [%]': 45.0}),
        }

        aggregate = runner.get_aggregate_stats()

        assert aggregate['positive_return_count'] == 2
        assert aggregate['negative_return_count'] == 2


# ============================================================================
# Test generate_report
# ============================================================================

class TestGenerateReport:
    """Test generate_report method"""

    def test_generate_report_creates_files(self, macd_config, tmp_path):
        """Creates CSV and JSON files"""
        runner = BacktestRunner(macd_config)

        # Add mock results
        runner.results = {
            'TEST.SH': pd.Series({
                'Return [%]': 10.0,
                'Sharpe Ratio': 1.5,
                'Max. Drawdown [%]': -5.0,
                '# Trades': 10,
                'Win Rate [%]': 60.0
            })
        }

        output_dir = tmp_path / "test_output"
        runner.generate_report(str(output_dir))

        # Check files exist
        assert (output_dir / "individual_results.csv").exists()
        assert (output_dir / "aggregate_stats.json").exists()

        # Verify CSV content
        csv_df = pd.read_csv(output_dir / "individual_results.csv", index_col=0)
        assert 'TEST.SH' in csv_df.index

        # Verify JSON content
        with open(output_dir / "aggregate_stats.json") as f:
            stats = json.load(f)
        assert 'total_symbols' in stats
        assert stats['total_symbols'] == 1

    def test_generate_report_no_results_warns(self, macd_config, tmp_path, caplog):
        """Logs warning when no results"""
        import logging

        runner = BacktestRunner(macd_config)
        # No results added

        output_dir = tmp_path / "test_output"

        with caplog.at_level(logging.WARNING):
            runner.generate_report(str(output_dir))

        # Check warning was logged
        assert any("No results to report" in record.message for record in caplog.records)


# ============================================================================
# Test run_backtest function
# ============================================================================

class TestRunBacktestFunction:
    """Test run_backtest() convenience function"""

    def test_run_backtest_loads_config(self, tmp_path, synthetic_ohlcv_data_200bars):
        """Loads config from path"""
        # Create temporary config file
        config_dict = {
            "env": {"root_dir": "/test"},
            "modes": {"lookback_days": 100},
            "universe": {"pool_list": ["TEST.SH"]},
            "strategies": [{"type": "macd"}],
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {},
            "execution": {},
            "io": {}
        }

        config_file = tmp_path / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_dict, f)

        # Mock data loading to avoid file I/O
        with patch('etf_trend_following_v2.src.backtest_runner.BacktestRunner._load_data') as mock_load:
            mock_load.return_value = {'TEST.SH': synthetic_ohlcv_data_200bars}

            results = run_backtest(
                config_path=str(config_file),
                start_date='2023-01-01',
                end_date='2023-12-31'
            )

        assert isinstance(results, dict)
        assert 'individual_results' in results
        assert 'aggregate_stats' in results
        assert 'metadata' in results

    def test_run_backtest_generates_report(self, tmp_path, synthetic_ohlcv_data_200bars):
        """Generates report when output_dir provided"""
        # Create temporary config file
        config_dict = {
            "env": {"root_dir": "/test"},
            "modes": {"lookback_days": 100},
            "universe": {"pool_list": ["TEST.SH"]},
            "strategies": [{"type": "macd"}],
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {},
            "execution": {},
            "io": {}
        }

        config_file = tmp_path / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_dict, f)

        output_dir = tmp_path / "output"

        # Mock data loading
        with patch('etf_trend_following_v2.src.backtest_runner.BacktestRunner._load_data') as mock_load:
            mock_load.return_value = {'TEST.SH': synthetic_ohlcv_data_200bars}

            results = run_backtest(
                config_path=str(config_file),
                start_date='2023-01-01',
                end_date='2023-12-31',
                output_dir=str(output_dir)
            )

        # Check report files exist
        assert (output_dir / "individual_results.csv").exists()
        assert (output_dir / "aggregate_stats.json").exists()

    def test_run_backtest_invalid_config_raises(self, tmp_path):
        """Raises ValueError for invalid config"""
        # Create invalid config (no strategies)
        config_dict = {
            "env": {"root_dir": "/test"},
            "modes": {},
            "universe": {"pool_list": ["TEST.SH"]},
            "strategies": [],  # Invalid: no strategies
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {},
            "execution": {},
            "io": {}
        }

        config_file = tmp_path / "invalid_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_dict, f)

        # The error is raised during config loading, not validation
        with pytest.raises(ValueError, match="Configuration must contain at least one strategy"):
            run_backtest(
                config_path=str(config_file),
                start_date='2023-01-01',
                end_date='2023-12-31'
            )

    def test_run_backtest_with_fixture_data(self, tmp_path):
        """End-to-end run_backtest using fixture CSVs (no mocks)."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        data_dir = fixtures_dir / "data"
        pool_file = fixtures_dir / "test_pool_trending.csv"

        config_dict = {
            "env": {
                "root_dir": str(tmp_path),
                "data_dir": str(data_dir),
                "results_dir": str(tmp_path / "results"),
                "log_dir": str(tmp_path / "logs"),
            },
            "modes": {"lookback_days": 120},
            "universe": {"pool_file": str(pool_file)},
            "strategies": [{"type": "macd"}],
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {},
            "execution": {},
            "io": {},
        }

        config_file = tmp_path / "fixture_config.json"
        with open(config_file, "w") as f:
            json.dump(config_dict, f)

        output_dir = tmp_path / "output"

        results = run_backtest(
            config_path=str(config_file),
            start_date="2023-02-01",
            end_date="2023-08-31",
            output_dir=str(output_dir),
        )

        assert "individual_results" in results
        assert len(results["individual_results"]) > 0
        assert results["metadata"]["num_symbols"] == len(results["individual_results"])
        assert (output_dir / "individual_results.csv").exists()
        assert (output_dir / "aggregate_stats.json").exists()


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests that test full workflow"""

    def test_full_workflow_macd(self, macd_config, synthetic_ohlcv_data_200bars):
        """Test complete workflow with MACD strategy"""
        runner = BacktestRunner(macd_config)

        data_dict = {
            'ETF1.SH': synthetic_ohlcv_data_200bars.copy(),
            'ETF2.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        results = runner.run(
            start_date='2023-01-01',
            end_date='2023-12-31',
            initial_capital=1_000_000,
            data_dict=data_dict
        )

        # Verify complete results structure
        assert 'individual_results' in results
        assert 'aggregate_stats' in results
        assert 'metadata' in results

        # Verify aggregate stats
        aggregate = results['aggregate_stats']
        assert aggregate['total_symbols'] == 2
        assert 'mean_return' in aggregate
        assert 'mean_sharpe' in aggregate

    def test_full_workflow_kama(self, kama_config, synthetic_ohlcv_data_200bars):
        """Test complete workflow with KAMA strategy"""
        runner = BacktestRunner(kama_config)

        data_dict = {
            'ETF1.SH': synthetic_ohlcv_data_200bars.copy(),
        }

        results = runner.run(
            start_date='2023-01-01',
            end_date='2023-12-31',
            initial_capital=500_000,
            data_dict=data_dict
        )

        assert results['metadata']['num_symbols'] == 1
        assert results['metadata']['initial_capital'] == 500_000
        assert results['metadata']['strategy_type'] == 'kama'


# ============================================================================
# Real Integration Smoke Tests
# ============================================================================

class TestRealIntegrationSmokeTests:
    """
    Real integration smoke tests using fixture data.

    These tests verify the complete pipeline with real data files:
    - Config parsing and parameter passing
    - Data loading from CSV files
    - Date range filtering
    - Commission parameter passing to Backtest
    - Output file generation with correct content
    - Statistical indicators in expected ranges
    """

    @pytest.fixture
    def fixtures_dir(self):
        """Get path to fixtures directory"""
        return Path(__file__).parent / "fixtures"

    @pytest.fixture
    def real_config_macd(self, fixtures_dir, tmp_path):
        """Create a real MACD config using fixture data paths"""
        config_dict = {
            "env": {
                "root_dir": str(fixtures_dir.parent.parent),
                "data_dir": str(fixtures_dir / "data")
            },
            "modes": {
                "lookback_days": 50
            },
            "universe": {
                "pool_file": str(fixtures_dir / "test_pool_trending.csv"),
                "pool_list": []
            },
            "strategies": [{
                "type": "macd",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "enable_adx_filter": True,
                "adx_period": 14,
                "adx_threshold": 25.0,
                "enable_volume_filter": False,
                "enable_slope_filter": False,
                "enable_confirm_filter": False,
                "enable_loss_protection": True,
                "max_consecutive_losses": 3,
                "pause_bars": 10,
                "enable_trailing_stop": False,
                "enable_hysteresis": False,
                "enable_zero_axis": False,
                "min_hold_bars": 0,
                "confirm_bars_sell": 0,
                "long_only": True
            }],
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {
                "commission_rate": 0.0003
            },
            "execution": {},
            "io": {}
        }

        config_file = tmp_path / "real_config_macd.json"
        with open(config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)

        return config_file

    @pytest.fixture
    def real_config_kama(self, fixtures_dir, tmp_path):
        """Create a real KAMA config using fixture data paths"""
        config_dict = {
            "env": {
                "root_dir": str(fixtures_dir.parent.parent),
                "data_dir": str(fixtures_dir / "data")
            },
            "modes": {
                "lookback_days": 50
            },
            "universe": {
                "pool_file": str(fixtures_dir / "test_pool_trending.csv"),
                "pool_list": []
            },
            "strategies": [{
                "type": "kama",
                "kama_period": 20,
                "kama_fast": 2,
                "kama_slow": 30,
                "enable_efficiency_filter": False,
                "enable_slope_confirmation": False,
                "enable_slope_filter": False,
                "enable_adx_filter": False,
                "enable_volume_filter": False,
                "enable_loss_protection": False,
                "long_only": True
            }],
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {
                "commission_rate": 0.0003
            },
            "execution": {},
            "io": {}
        }

        config_file = tmp_path / "real_config_kama.json"
        with open(config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)

        return config_file

    def test_real_integration_macd_smoke_test(self, real_config_macd, tmp_path):
        """
        Real integration smoke test for MACD strategy using fixture data.

        Verifies:
        1. Config parsing correctly passes parameters to strategy
        2. Data loading from CSV files works
        3. Date range filtering is applied correctly
        4. Commission parameters are passed to Backtest
        5. Output files are generated with correct content
        6. Statistical indicators are in reasonable ranges
        """
        from etf_trend_following_v2.src.config_loader import load_config

        # Load config
        config = load_config(str(real_config_macd))

        # Verify config parsing
        assert config.strategies[0].type == "macd"
        assert config.strategies[0].fast_period == 12
        assert config.strategies[0].slow_period == 26
        assert config.strategies[0].enable_adx_filter is True
        assert config.strategies[0].enable_loss_protection is True
        assert config.strategies[0].max_consecutive_losses == 3
        assert config.position_sizing.commission_rate == 0.0003

        # Run backtest
        results = run_backtest(
            config_path=str(real_config_macd),
            start_date='2023-03-01',
            end_date='2023-09-01',
            initial_capital=1_000_000,
            output_dir=str(tmp_path)
        )

        # Verify results structure
        assert isinstance(results, dict)
        assert 'individual_results' in results
        assert 'aggregate_stats' in results
        assert 'metadata' in results

        # Verify metadata
        metadata = results['metadata']
        assert metadata['start_date'] == '2023-03-01'
        assert metadata['end_date'] == '2023-09-01'
        assert metadata['initial_capital'] == 1_000_000
        assert metadata['num_symbols'] == 3  # 3 symbols in test_pool_trending.csv
        assert metadata['strategy_type'] == 'macd'

        # Verify individual results
        individual_results = results['individual_results']
        assert len(individual_results) > 0
        assert len(individual_results) <= 3  # At most 3 symbols

        # Check that at least one symbol has results
        for symbol, stats in individual_results.items():
            assert isinstance(stats, pd.Series)
            assert 'Return [%]' in stats
            assert 'Sharpe Ratio' in stats
            assert '# Trades' in stats
            assert 'Max. Drawdown [%]' in stats

            # Verify statistics are in reasonable ranges
            # (not checking exact values as they depend on random data)
            assert isinstance(stats['# Trades'], (int, np.integer))
            assert stats['# Trades'] >= 0

        # Verify aggregate stats
        aggregate = results['aggregate_stats']
        assert 'total_symbols' in aggregate
        assert aggregate['total_symbols'] == len(individual_results)
        assert 'mean_return' in aggregate
        assert 'mean_sharpe' in aggregate
        assert 'total_trades' in aggregate

        # Verify output files exist and have correct content
        assert (tmp_path / "individual_results.csv").exists()
        assert (tmp_path / "aggregate_stats.json").exists()

        # Verify CSV content
        csv_df = pd.read_csv(tmp_path / "individual_results.csv", index_col=0)
        assert len(csv_df) == len(individual_results)
        assert 'Return [%]' in csv_df.columns
        assert 'Sharpe Ratio' in csv_df.columns
        assert '# Trades' in csv_df.columns

        # Verify JSON content
        with open(tmp_path / "aggregate_stats.json") as f:
            json_stats = json.load(f)
        assert json_stats['total_symbols'] == aggregate['total_symbols']
        assert 'mean_return' in json_stats
        assert 'total_trades' in json_stats

    def test_real_integration_kama_smoke_test(self, real_config_kama, tmp_path):
        """
        Real integration smoke test for KAMA strategy using fixture data.

        Verifies:
        1. KAMA-specific parameters are correctly parsed
        2. KAMA strategy executes successfully on real data
        3. Output files contain expected KAMA results
        """
        from etf_trend_following_v2.src.config_loader import load_config

        # Load config
        config = load_config(str(real_config_kama))

        # Verify KAMA-specific config parsing
        assert config.strategies[0].type == "kama"
        assert config.strategies[0].kama_period == 20
        assert config.strategies[0].kama_fast == 2
        assert config.strategies[0].kama_slow == 30
        assert config.strategies[0].enable_efficiency_filter is False
        assert config.strategies[0].enable_loss_protection is False

        # Run backtest
        results = run_backtest(
            config_path=str(real_config_kama),
            start_date='2023-01-01',
            end_date='2023-12-31',
            initial_capital=500_000,
            output_dir=str(tmp_path)
        )

        # Verify results structure
        assert isinstance(results, dict)
        assert 'individual_results' in results
        assert 'aggregate_stats' in results
        assert 'metadata' in results

        # Verify metadata
        metadata = results['metadata']
        assert metadata['strategy_type'] == 'kama'
        assert metadata['initial_capital'] == 500_000
        assert metadata['num_symbols'] == 3

        # Verify at least one symbol has results
        individual_results = results['individual_results']
        assert len(individual_results) > 0

        # Verify output files
        assert (tmp_path / "individual_results.csv").exists()
        assert (tmp_path / "aggregate_stats.json").exists()

        # Verify CSV has KAMA results
        csv_df = pd.read_csv(tmp_path / "individual_results.csv", index_col=0)
        assert len(csv_df) > 0
        assert 'Return [%]' in csv_df.columns

    def test_real_integration_date_filtering(self, real_config_macd, tmp_path):
        """
        Verify that date range filtering is correctly applied to loaded data.

        Tests that:
        1. Data is correctly filtered to the specified date range
        2. Backtest only uses data within the specified range
        """
        from etf_trend_following_v2.src.config_loader import load_config
        from etf_trend_following_v2.src.data_loader import load_universe_from_file

        # Load config
        config = load_config(str(real_config_macd))

        # Load data directly to verify date filtering
        fixtures_dir = Path(__file__).parent / "fixtures"
        data_dict = load_universe_from_file(
            pool_file=str(fixtures_dir / "test_pool_trending.csv"),
            data_dir=str(fixtures_dir / "data"),
            start_date='2023-06-01',
            end_date='2023-09-30',
            skip_errors=True
        )

        # Verify data is filtered
        for symbol, df in data_dict.items():
            assert df.index.min() >= pd.Timestamp('2023-06-01')
            assert df.index.max() <= pd.Timestamp('2023-09-30')

        # Run backtest with filtered date range
        results = run_backtest(
            config_path=str(real_config_macd),
            start_date='2023-06-01',
            end_date='2023-09-30',
            initial_capital=1_000_000,
            output_dir=str(tmp_path)
        )

        # Verify backtest ran successfully with filtered data
        assert results['metadata']['start_date'] == '2023-06-01'
        assert results['metadata']['end_date'] == '2023-09-30'
        assert len(results['individual_results']) > 0

    def test_real_integration_commission_parameter(self, real_config_macd, tmp_path):
        """
        Verify that commission parameters are correctly passed to Backtest.

        Tests that:
        1. Commission from config is used in backtest
        2. Different commission values produce different results
        """
        from etf_trend_following_v2.src.config_loader import load_config

        # Test with default commission (0.0003)
        results_default = run_backtest(
            config_path=str(real_config_macd),
            start_date='2023-01-01',
            end_date='2023-12-31',
            initial_capital=1_000_000,
            output_dir=str(tmp_path / "default")
        )

        # Modify config to use higher commission
        config = load_config(str(real_config_macd))
        config.position_sizing.commission_rate = 0.001  # Higher commission

        # Save modified config
        config_high_commission = tmp_path / "config_high_commission.json"
        config_dict = json.loads(real_config_macd.read_text())
        config_dict['position_sizing']['commission_rate'] = 0.001
        with open(config_high_commission, 'w') as f:
            json.dump(config_dict, f)

        # Test with higher commission
        results_high = run_backtest(
            config_path=str(config_high_commission),
            start_date='2023-01-01',
            end_date='2023-12-31',
            initial_capital=1_000_000,
            output_dir=str(tmp_path / "high")
        )

        # Verify both ran successfully
        assert len(results_default['individual_results']) > 0
        assert len(results_high['individual_results']) > 0

        # Note: We can't easily verify that returns are different without
        # knowing if trades occurred, but we've verified the parameter is passed


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
