"""
Backtest Runner for ETF Trend Following v2 System (Refactored)

This module implements a backtesting engine that maximizes reuse of the
backtesting.py framework by delegating to backtesting.Backtest for execution.

Key Changes from Original:
- REMOVED: Portfolio class (uses backtesting.py's internal broker)
- REMOVED: Custom order matching logic
- REMOVED: Manual equity curve tracking
- ADDED: run_single() for single-asset backtests
- ADDED: run_universe() for multi-asset backtests
- KEPT: Configuration integration
- KEPT: Statistics aggregation and reporting

Architecture:
- Uses backtest_wrappers.py Strategy classes (MACDBacktestStrategy, KAMABacktestStrategy)
- Delegates all execution to backtesting.Backtest
- Aggregates results across multiple symbols for universe backtests
- Maintains compatibility with config_loader.py

Author: Claude
Date: 2025-12-11
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import json

# Import backtesting.py framework
from backtesting import Backtest

# Import project modules
from .config_loader import Config, MACDStrategyConfig, KAMAStrategyConfig, ComboStrategyConfig
from .data_loader import load_universe_from_file, load_universe
from .strategies.backtest_wrappers import (
    MACDBacktestStrategy,
    KAMABacktestStrategy,
    ComboBacktestStrategy,
    STRATEGY_MAP
)

logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Backtesting engine that maximizes reuse of backtesting.py framework.

    Supports:
    - Single-asset backtests via run_single()
    - Multi-asset universe backtests via run_universe()
    - Full integration with config_loader.py
    - Aggregated statistics and reporting
    """

    def __init__(self, config: Config):
        """
        Initialize backtest runner.

        Args:
            config: Configuration object from config_loader
        """
        self.config = config
        self.strategy_class = self._get_strategy_class()
        self.strategy_params = self._get_strategy_params()
        self.results: Dict[str, pd.Series] = {}

        logger.info(f"Initialized BacktestRunner with strategy: {self.config.strategies[0].type}")

    def _get_strategy_class(self) -> type:
        """Get strategy class from config."""
        if not self.config.strategies:
            raise ValueError("No strategies configured")

        strategy_config = self.config.strategies[0]
        strategy_type = strategy_config.type

        if strategy_type not in STRATEGY_MAP:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        return STRATEGY_MAP[strategy_type]

    def _get_strategy_params(self) -> dict:
        """Extract strategy parameters from config."""
        if not self.config.strategies:
            return {}

        strategy_config = self.config.strategies[0]
        params = {}

        if isinstance(strategy_config, MACDStrategyConfig):
            params = {
                # Core MACD parameters
                'fast_period': strategy_config.fast_period,
                'slow_period': strategy_config.slow_period,
                'signal_period': strategy_config.signal_period,
                # Phase 2: Filter switches
                'enable_adx_filter': strategy_config.enable_adx_filter,
                'adx_period': strategy_config.adx_period,
                'adx_threshold': strategy_config.adx_threshold,
                'enable_volume_filter': strategy_config.enable_volume_filter,
                'volume_period': strategy_config.volume_period,
                'volume_ratio': strategy_config.volume_ratio,
                'enable_slope_filter': strategy_config.enable_slope_filter,
                'slope_lookback': strategy_config.slope_lookback,
                'enable_confirm_filter': strategy_config.enable_confirm_filter,
                'confirm_bars': strategy_config.confirm_bars,
                # Phase 3: Loss protection
                'enable_loss_protection': strategy_config.enable_loss_protection,
                'max_consecutive_losses': strategy_config.max_consecutive_losses,
                'pause_bars': strategy_config.pause_bars,
                # Trailing stop
                'enable_trailing_stop': strategy_config.enable_trailing_stop,
                'trailing_stop_pct': strategy_config.trailing_stop_pct,
                # Anti-Whipsaw features
                'enable_hysteresis': strategy_config.enable_hysteresis,
                'hysteresis_mode': strategy_config.hysteresis_mode,
                'hysteresis_k': strategy_config.hysteresis_k,
                'hysteresis_window': strategy_config.hysteresis_window,
                'hysteresis_abs': strategy_config.hysteresis_abs,
                'confirm_bars_sell': strategy_config.confirm_bars_sell,
                'min_hold_bars': strategy_config.min_hold_bars,
                'enable_zero_axis': strategy_config.enable_zero_axis,
                'zero_axis_mode': strategy_config.zero_axis_mode,
                # Long-only mode
                'long_only': strategy_config.long_only,
            }

        elif isinstance(strategy_config, KAMAStrategyConfig):
            params = {
                # Core KAMA parameters
                'kama_period': strategy_config.kama_period,
                'kama_fast': strategy_config.kama_fast,
                'kama_slow': strategy_config.kama_slow,
                # Phase 1: KAMA-specific filters
                'enable_efficiency_filter': strategy_config.enable_efficiency_filter,
                'min_efficiency_ratio': strategy_config.min_efficiency_ratio,
                'enable_slope_confirmation': strategy_config.enable_slope_confirmation,
                'min_slope_periods': strategy_config.min_slope_periods,
                # Phase 2: Generic filters
                'enable_slope_filter': strategy_config.enable_slope_filter,
                'slope_lookback': strategy_config.slope_lookback,
                'enable_adx_filter': strategy_config.enable_adx_filter,
                'adx_period': strategy_config.adx_period,
                'adx_threshold': strategy_config.adx_threshold,
                'enable_volume_filter': strategy_config.enable_volume_filter,
                'volume_period': strategy_config.volume_period,
                'volume_ratio': strategy_config.volume_ratio,
                # Phase 3: Loss protection
                'enable_loss_protection': strategy_config.enable_loss_protection,
                'max_consecutive_losses': strategy_config.max_consecutive_losses,
                'pause_bars': strategy_config.pause_bars,
                # Long-only mode
                'long_only': strategy_config.long_only,
            }

        elif isinstance(strategy_config, ComboStrategyConfig):
            params = {
                'combo_mode': strategy_config.mode,
                # TODO: Add sub-strategy parameters
            }

        return params

    def run_single(
        self,
        symbol: str,
        df: pd.DataFrame,
        initial_capital: Optional[float] = None
    ) -> pd.Series:
        """
        Run backtest on a single asset using backtesting.Backtest.

        Args:
            symbol: Symbol identifier
            df: OHLCV DataFrame with datetime index
            initial_capital: Initial capital (uses config default if None)

        Returns:
            pd.Series with backtest statistics from backtesting.py
        """
        if initial_capital is None:
            initial_capital = 1_000_000  # Default

        # Ensure column names match backtesting.py requirements (capitalized)
        df = self._prepare_dataframe(df)

        # Validate data
        if len(df) < 50:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} bars")
            return pd.Series()

        # Create Backtest instance
        bt = Backtest(
            df,
            self.strategy_class,
            cash=initial_capital,
            commission=self.config.position_sizing.commission_rate,
            trade_on_close=(self.config.execution.order_time_strategy == 'close'),
            exclusive_orders=True
        )

        # Run backtest with strategy parameters
        try:
            stats = bt.run(**self.strategy_params)
            logger.info(
                f"{symbol}: Return={stats['Return [%]']:.2f}%, "
                f"Sharpe={stats['Sharpe Ratio']:.3f}, "
                f"Trades={stats['# Trades']}"
            )
            return stats

        except Exception as e:
            logger.error(f"Backtest failed for {symbol}: {e}")
            return pd.Series()

    def run_universe(
        self,
        data_dict: Dict[str, pd.DataFrame],
        initial_capital: Optional[float] = None,
        parallel: bool = False
    ) -> Dict[str, pd.Series]:
        """
        Run backtests across multiple assets (universe).

        Each asset is backtested independently with the same initial capital.
        Results are aggregated for portfolio-level statistics.

        Args:
            data_dict: Dictionary of {symbol: OHLCV DataFrame}
            initial_capital: Initial capital per asset (uses config default if None)
            parallel: Enable parallel execution (not implemented yet)

        Returns:
            Dictionary of {symbol: stats Series}
        """
        if initial_capital is None:
            initial_capital = 1_000_000  # Default

        logger.info(f"Running universe backtest on {len(data_dict)} symbols")

        results = {}

        for i, (symbol, df) in enumerate(data_dict.items(), 1):
            logger.info(f"Processing {i}/{len(data_dict)}: {symbol}")

            try:
                stats = self.run_single(symbol, df, initial_capital)
                if not stats.empty:
                    results[symbol] = stats
            except Exception as e:
                logger.error(f"Failed to backtest {symbol}: {e}")
                continue

        self.results = results
        logger.info(f"Universe backtest completed: {len(results)}/{len(data_dict)} successful")

        return results

    def run(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000,
        data_dict: Optional[Dict[str, pd.DataFrame]] = None
    ) -> Dict[str, Any]:
        """
        Run backtest over specified date range.

        This is the main entry point that loads data from config and runs
        universe backtest.

        Args:
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_capital: Initial capital per asset
            data_dict: Pre-loaded data (optional, will load from config if None)

        Returns:
            Dictionary with aggregated results:
            {
                'individual_results': Dict[str, pd.Series],
                'aggregate_stats': dict,
                'metadata': dict
            }
        """
        logger.info(f"Starting backtest: {start_date} to {end_date}")
        logger.info(f"Initial capital per asset: {initial_capital:,.0f}")

        # Load data if not provided
        if data_dict is None:
            data_dict = self._load_data(start_date, end_date)

        logger.info(f"Loaded data for {len(data_dict)} symbols")

        # Run universe backtest
        individual_results = self.run_universe(data_dict, initial_capital)

        # Calculate aggregate statistics
        aggregate_stats = self.get_aggregate_stats()

        # Compile results
        results = {
            'individual_results': individual_results,
            'aggregate_stats': aggregate_stats,
            'metadata': {
                'start_date': start_date,
                'end_date': end_date,
                'initial_capital': initial_capital,
                'num_symbols': len(data_dict),
                'num_successful': len(individual_results),
                'strategy_type': self.config.strategies[0].type,
                'strategy_params': self.strategy_params,
                'config': self.config.to_dict()
            }
        }

        logger.info("Backtest completed successfully")
        return results

    def _load_data(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, pd.DataFrame]:
        """Load data from config."""
        # Calculate lookback start date
        start_dt = pd.to_datetime(start_date)
        lookback_days = self.config.modes.lookback_days
        data_start = (start_dt - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        # Load universe
        if self.config.universe.pool_file:
            data_dict = load_universe_from_file(
                pool_file=self.config.universe.pool_file,
                data_dir=self.config.env.data_dir,
                start_date=data_start,
                end_date=end_date,
                use_adj=True,
                skip_errors=True
            )
        elif self.config.universe.pool_list:
            data_dict = load_universe(
                symbols=self.config.universe.pool_list,
                data_dir=self.config.env.data_dir,
                start_date=data_start,
                end_date=end_date,
                use_adj=True,
                skip_errors=True
            )
        else:
            raise ValueError("No universe configured")

        return data_dict

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare DataFrame for backtesting.py (ensure capitalized column names).

        Args:
            df: Input DataFrame with OHLCV data

        Returns:
            DataFrame with properly formatted columns
        """
        # Create a copy to avoid modifying original
        df = df.copy()

        # Map lowercase to capitalized column names
        column_mapping = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }

        # Rename columns if they exist in lowercase
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)

        # Verify required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Ensure Volume column exists (use zeros if missing)
        if 'Volume' not in df.columns:
            df['Volume'] = 0

        return df

    def get_aggregate_stats(self) -> dict:
        """
        Calculate aggregate statistics across all symbols.

        Returns:
            Dictionary of aggregated performance metrics
        """
        if not self.results:
            return {}

        # Extract key metrics from individual results
        returns = []
        sharpes = []
        drawdowns = []
        num_trades = []
        win_rates = []

        for symbol, stats in self.results.items():
            if not stats.empty:
                returns.append(stats.get('Return [%]', 0))
                sharpes.append(stats.get('Sharpe Ratio', 0))
                drawdowns.append(stats.get('Max. Drawdown [%]', 0))
                num_trades.append(stats.get('# Trades', 0))
                win_rate = stats.get('Win Rate [%]', 0)
                win_rates.append(win_rate)

        # Calculate aggregate statistics
        aggregate = {
            'total_symbols': len(self.results),
            'mean_return': np.mean(returns) if returns else 0,
            'median_return': np.median(returns) if returns else 0,
            'std_return': np.std(returns) if returns else 0,
            'mean_sharpe': np.mean(sharpes) if sharpes else 0,
            'median_sharpe': np.median(sharpes) if sharpes else 0,
            'std_sharpe': np.std(sharpes) if sharpes else 0,
            'mean_drawdown': np.mean(drawdowns) if drawdowns else 0,
            'median_drawdown': np.median(drawdowns) if drawdowns else 0,
            'total_trades': sum(num_trades),
            'mean_trades_per_symbol': np.mean(num_trades) if num_trades else 0,
            'mean_win_rate': np.mean(win_rates) if win_rates else 0,
            'positive_return_count': sum(1 for r in returns if r > 0),
            'negative_return_count': sum(1 for r in returns if r < 0),
        }

        return aggregate

    def generate_report(self, output_dir: str) -> None:
        """
        Generate backtest report with statistics and charts.

        Args:
            output_dir: Directory to save report files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if not self.results:
            logger.warning("No results to report - run backtest first")
            return

        # Save individual results as CSV
        results_file = output_path / 'individual_results.csv'
        results_df = pd.DataFrame(self.results).T
        results_df.to_csv(results_file)
        logger.info(f"Saved individual results to {results_file}")

        # Save aggregate statistics as JSON
        aggregate_stats = self.get_aggregate_stats()
        stats_file = output_path / 'aggregate_stats.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(aggregate_stats, f, indent=2, default=str)
        logger.info(f"Saved aggregate statistics to {stats_file}")

        # Print summary to console
        self._print_summary()

    def _print_summary(self) -> None:
        """Print backtest summary to console."""
        aggregate = self.get_aggregate_stats()

        print("\n" + "=" * 80)
        print("BACKTEST SUMMARY (Universe)")
        print("=" * 80)
        print(f"\nTotal Symbols: {aggregate['total_symbols']}")
        print(f"Positive Returns: {aggregate['positive_return_count']}")
        print(f"Negative Returns: {aggregate['negative_return_count']}")
        print()
        print(f"Mean Return: {aggregate['mean_return']:.2f}%")
        print(f"Median Return: {aggregate['median_return']:.2f}%")
        print(f"Std Return: {aggregate['std_return']:.2f}%")
        print()
        print(f"Mean Sharpe Ratio: {aggregate['mean_sharpe']:.3f}")
        print(f"Median Sharpe Ratio: {aggregate['median_sharpe']:.3f}")
        print(f"Std Sharpe Ratio: {aggregate['std_sharpe']:.3f}")
        print()
        print(f"Mean Max Drawdown: {aggregate['mean_drawdown']:.2f}%")
        print(f"Median Max Drawdown: {aggregate['median_drawdown']:.2f}%")
        print()
        print(f"Total Trades: {aggregate['total_trades']}")
        print(f"Mean Trades per Symbol: {aggregate['mean_trades_per_symbol']:.1f}")
        print(f"Mean Win Rate: {aggregate['mean_win_rate']:.2f}%")
        print("=" * 80 + "\n")


# Convenience function for CLI usage
def run_backtest(
    config_path: str,
    start_date: str,
    end_date: str,
    output_dir: Optional[str] = None,
    initial_capital: float = 1_000_000
) -> dict:
    """
    Convenience function to run backtest from config file.

    Args:
        config_path: Path to configuration JSON file
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        output_dir: Output directory for results (optional)
        initial_capital: Initial capital per asset (default: 1,000,000)

    Returns:
        Dictionary of backtest results
    """
    from .config_loader import load_config

    # Load configuration
    config = load_config(config_path)

    # Validate configuration
    errors = config.validate()
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    # Create backtest runner
    runner = BacktestRunner(config)

    # Run backtest
    results = runner.run(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital
    )

    # Generate report if output directory specified
    if output_dir:
        runner.generate_report(output_dir)

    return results


if __name__ == '__main__':
    # Example usage
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 4:
        print("Usage: python backtest_runner.py <config_path> <start_date> <end_date> [output_dir]")
        sys.exit(1)

    config_path = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    output_dir = sys.argv[4] if len(sys.argv) > 4 else None

    results = run_backtest(
        config_path=config_path,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir
    )

    print("\nBacktest completed successfully!")
