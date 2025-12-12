#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtest Strategy Wrappers for ETF Trend Following v2

This module provides backtesting.py Strategy wrappers that integrate with
the standalone signal generators (MACD/KAMA) for use with backtesting.Backtest.

Key Features:
- Wraps MACDSignalGenerator and KAMASignalGenerator as backtesting.Strategy
- Parameter alignment with existing strategies/macd_cross.py and strategies/kama_cross.py
- Supports all filters and loss protection features
- Enables result comparison with existing backtest framework

Architecture:
- MACDBacktestStrategy: Wraps MACDSignalGenerator
- KAMABacktestStrategy: Wraps KAMASignalGenerator
- ComboBacktestStrategy: Combines MACD + KAMA signals

Author: Claude
Date: 2025-12-11
"""

from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover

from .macd import MACDSignalGenerator
from .kama import KAMASignalGenerator


class MACDBacktestStrategy(Strategy):
    """
    MACD Backtest Strategy Wrapper

    Wraps MACDSignalGenerator for use with backtesting.Backtest.
    Parameter-aligned with strategies/macd_cross.py for result comparison.

    All parameters are class variables (can be optimized via Backtest.optimize).
    """

    # Phase 1: Core MACD parameters
    fast_period = 12
    slow_period = 26
    signal_period = 9

    # Phase 2: Filter switches
    enable_adx_filter = False
    enable_volume_filter = False
    enable_slope_filter = False
    enable_confirm_filter = False

    # Phase 2: Filter parameters
    adx_period = 14
    adx_threshold = 25.0
    volume_period = 20
    volume_ratio = 1.2
    slope_lookback = 5
    confirm_bars = 2

    # Phase 3: Loss protection
    enable_loss_protection = False
    max_consecutive_losses = 3
    pause_bars = 10

    # Trailing stop
    enable_trailing_stop = False
    trailing_stop_pct = 0.05

    # Anti-Whipsaw features
    enable_hysteresis = False
    hysteresis_mode = 'std'
    hysteresis_k = 0.5
    hysteresis_window = 20
    hysteresis_abs = 0.001
    confirm_bars_sell = 0
    min_hold_bars = 0
    enable_zero_axis = False
    zero_axis_mode = 'symmetric'

    # Long-only mode (A-share market does not allow short selling)
    long_only = True

    def init(self):
        """Initialize indicators and state"""
        # Create MACD signal generator
        self.generator = MACDSignalGenerator(
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            signal_period=self.signal_period,
            enable_adx_filter=self.enable_adx_filter,
            adx_period=self.adx_period,
            adx_threshold=self.adx_threshold,
            enable_volume_filter=self.enable_volume_filter,
            volume_period=self.volume_period,
            volume_ratio=self.volume_ratio,
            enable_slope_filter=self.enable_slope_filter,
            slope_lookback=self.slope_lookback,
            enable_confirm_filter=self.enable_confirm_filter,
            confirm_bars=self.confirm_bars,
            enable_zero_axis=self.enable_zero_axis,
            zero_axis_mode=self.zero_axis_mode,
            enable_hysteresis=self.enable_hysteresis,
            hysteresis_mode=self.hysteresis_mode,
            hysteresis_k=self.hysteresis_k,
            hysteresis_window=self.hysteresis_window,
            hysteresis_abs=self.hysteresis_abs,
            confirm_bars_sell=self.confirm_bars_sell,
            min_hold_bars=self.min_hold_bars
        )

        # Calculate MACD using self.I()
        # Note: self.data.Close is a numpy array, need to convert to pandas Series
        def macd_indicator(close):
            close_series = pd.Series(close)
            macd_line, signal_line, histogram = self.generator.calculate_macd(close_series)
            return macd_line, signal_line, histogram

        self.macd_line, self.signal_line, self.histogram = self.I(
            macd_indicator,
            self.data.Close,
            name=('MACD', 'Signal', 'Histogram')
        )

        # Calculate ADX if enabled
        if self.enable_adx_filter:
            def adx_indicator(high, low, close):
                high_series = pd.Series(high)
                low_series = pd.Series(low)
                close_series = pd.Series(close)
                return self.generator.calculate_adx(high_series, low_series, close_series, self.adx_period)

            self.adx = self.I(
                adx_indicator,
                self.data.High,
                self.data.Low,
                self.data.Close,
                name='ADX'
            )

        # Loss protection state
        self.consecutive_losses = 0
        self.paused_until_bar = -1
        self.current_bar = 0

        # Trailing stop state
        self.trailing_stop_price = None

        # Min hold state
        self.entry_bar = -1

    def next(self):
        """Execute strategy logic for each bar"""
        self.current_bar += 1

        # Check if in pause period (loss protection)
        if self.enable_loss_protection and self.current_bar <= self.paused_until_bar:
            return

        # Check min hold period
        if self.position and self.min_hold_bars > 0:
            bars_held = self.current_bar - self.entry_bar
            if bars_held < self.min_hold_bars:
                # Update trailing stop if enabled
                if self.enable_trailing_stop and self.trailing_stop_price is not None:
                    self._update_trailing_stop()
                return

        # Detect crossovers
        if len(self.macd_line) < 2:
            return

        # Golden cross (buy signal)
        if crossover(self.macd_line, self.signal_line):
            # Apply filters
            if self._apply_filters('buy'):
                # Close existing position if any (reversal)
                if self.position:
                    self.position.close()
                    self._record_trade_result()

                # Buy - use 90% of available cash to avoid margin issues
                self.buy(size=0.90)
                self.entry_bar = self.current_bar

                # Initialize trailing stop
                if self.enable_trailing_stop:
                    self.trailing_stop_price = self.data.Close[-1] * (1 - self.trailing_stop_pct)

        # Death cross (sell signal)
        elif crossover(self.signal_line, self.macd_line):
            # Close existing long position if any
            if self.position and self.position.is_long:
                self.position.close()
                self._record_trade_result()
                self.trailing_stop_price = None

            # Only go short if long_only is disabled (A-share market does not allow short selling)
            if not self.long_only and not self.position:
                self.sell(size=0.90)
                self.entry_bar = self.current_bar

                # Initialize trailing stop for short position
                if self.enable_trailing_stop:
                    self.trailing_stop_price = self.data.Close[-1] * (1 + self.trailing_stop_pct)

        # Check trailing stop
        elif self.position and self.enable_trailing_stop:
            if self.trailing_stop_price is not None:
                # Long position: stop if price drops below stop
                if self.position.is_long and self.data.Close[-1] <= self.trailing_stop_price:
                    self.position.close()
                    self._record_trade_result()
                    self.trailing_stop_price = None
                # Short position: stop if price rises above stop (only when long_only is disabled)
                elif not self.long_only and self.position.is_short and self.data.Close[-1] >= self.trailing_stop_price:
                    self.position.close()
                    self._record_trade_result()
                    self.trailing_stop_price = None
                else:
                    self._update_trailing_stop()

    def _apply_filters(self, signal_type: str) -> bool:
        """Apply all enabled filters"""
        # ADX filter
        if self.enable_adx_filter:
            if hasattr(self, 'adx') and len(self.adx) > 0:
                if self.adx[-1] < self.adx_threshold:
                    return False

        # Volume filter
        if self.enable_volume_filter:
            if len(self.data.Volume) >= self.volume_period:
                vol_ma = np.mean(self.data.Volume[-self.volume_period:])
                if self.data.Volume[-1] < vol_ma * self.volume_ratio:
                    return False

        # Slope filter
        if self.enable_slope_filter:
            if len(self.macd_line) > self.slope_lookback:
                slope = self.macd_line[-1] - self.macd_line[-self.slope_lookback]
                if slope <= 0:
                    return False

        # Confirmation filter (check if signal persists for N bars)
        if self.enable_confirm_filter and self.confirm_bars > 1:
            if len(self.macd_line) < self.confirm_bars:
                return False

            for i in range(self.confirm_bars):
                if self.macd_line[-(i+1)] <= self.signal_line[-(i+1)]:
                    return False

        # Zero-axis constraint
        if self.enable_zero_axis:
            if self.zero_axis_mode == 'symmetric':
                if signal_type == 'buy':
                    if self.macd_line[-1] <= 0 or self.signal_line[-1] <= 0:
                        return False

        # Hysteresis filter
        if self.enable_hysteresis:
            hist = self.histogram[-1]

            if signal_type == 'buy' and hist <= 0:
                return False

            if self.hysteresis_mode == 'std':
                if len(self.histogram) >= self.hysteresis_window:
                    threshold = np.std(self.histogram[-self.hysteresis_window:]) * self.hysteresis_k
                    if abs(hist) <= threshold:
                        return False
            else:  # abs mode
                if abs(hist) <= self.hysteresis_abs:
                    return False

        return True

    def _update_trailing_stop(self):
        """Update trailing stop price"""
        if self.trailing_stop_price is not None and self.position:
            if self.position.is_long:
                # Long position: raise stop as price rises
                new_stop = self.data.Close[-1] * (1 - self.trailing_stop_pct)
                if new_stop > self.trailing_stop_price:
                    self.trailing_stop_price = new_stop
            elif not self.long_only and self.position.is_short:
                # Short position: lower stop as price falls (only when long_only is disabled)
                new_stop = self.data.Close[-1] * (1 + self.trailing_stop_pct)
                if new_stop < self.trailing_stop_price:
                    self.trailing_stop_price = new_stop

    def _record_trade_result(self):
        """Record trade result for loss protection"""
        if not self.enable_loss_protection:
            return

        # Check if last trade was a loss
        if len(self.closed_trades) > 0:
            last_trade = self.closed_trades[-1]
            if last_trade.pl < 0:
                self.consecutive_losses += 1

                if self.consecutive_losses >= self.max_consecutive_losses:
                    # Pause trading
                    self.paused_until_bar = self.current_bar + self.pause_bars
                    self.consecutive_losses = 0
            else:
                # Reset on winning trade
                self.consecutive_losses = 0


class KAMABacktestStrategy(Strategy):
    """
    KAMA Backtest Strategy Wrapper

    Wraps KAMASignalGenerator for use with backtesting.Backtest.
    Parameter-aligned with strategies/kama_cross.py for result comparison.
    """

    # KAMA core parameters
    kama_period = 20
    kama_fast = 2
    kama_slow = 30

    # Phase 1: KAMA-specific filters
    enable_efficiency_filter = False
    min_efficiency_ratio = 0.3
    enable_slope_confirmation = False
    min_slope_periods = 3

    # Phase 2: Generic filters
    enable_slope_filter = False
    enable_adx_filter = False
    enable_volume_filter = False

    # Phase 2: Filter parameters
    slope_lookback = 5
    adx_period = 14
    adx_threshold = 25.0
    volume_period = 20
    volume_ratio = 1.2

    # Phase 3: Loss protection
    enable_loss_protection = False
    max_consecutive_losses = 3
    pause_bars = 10

    # Long-only mode (A-share market does not allow short selling)
    long_only = True

    def init(self):
        """Initialize indicators and state"""
        # Create KAMA signal generator
        self.generator = KAMASignalGenerator(
            kama_period=self.kama_period,
            kama_fast=self.kama_fast,
            kama_slow=self.kama_slow,
            enable_efficiency_filter=self.enable_efficiency_filter,
            min_efficiency_ratio=self.min_efficiency_ratio,
            enable_slope_confirmation=self.enable_slope_confirmation,
            min_slope_periods=self.min_slope_periods,
            enable_adx_filter=self.enable_adx_filter,
            adx_period=self.adx_period,
            adx_threshold=self.adx_threshold,
            enable_volume_filter=self.enable_volume_filter,
            volume_period=self.volume_period,
            volume_ratio=self.volume_ratio,
            enable_slope_filter=self.enable_slope_filter,
            slope_lookback=self.slope_lookback
        )

        # Calculate KAMA using self.I()
        def kama_indicator(close):
            close_series = pd.Series(close)
            return self.generator.calculate_kama(close_series)

        self.kama = self.I(
            kama_indicator,
            self.data.Close,
            name='KAMA'
        )

        # Calculate efficiency ratio if enabled
        if self.enable_efficiency_filter:
            def er_indicator(close):
                close_series = pd.Series(close)
                return self.generator.calculate_efficiency_ratio(close_series)

            self.efficiency_ratio = self.I(
                er_indicator,
                self.data.Close,
                name='EfficiencyRatio'
            )

        # Calculate KAMA slope if enabled
        if self.enable_slope_confirmation:
            def slope_indicator(series):
                series_pd = pd.Series(series)
                return self.generator.calculate_slope(series_pd, self.min_slope_periods)

            self.kama_slope = self.I(
                slope_indicator,
                self.kama,
                name='KamaSlope'
            )

        # Calculate ADX if enabled
        if self.enable_adx_filter:
            def adx_indicator(high, low, close):
                high_series = pd.Series(high)
                low_series = pd.Series(low)
                close_series = pd.Series(close)
                return self.generator.calculate_adx(high_series, low_series, close_series, self.adx_period)

            self.adx = self.I(
                adx_indicator,
                self.data.High,
                self.data.Low,
                self.data.Close,
                name='ADX'
            )

        # Loss protection state
        self.consecutive_losses = 0
        self.paused_until_bar = -1
        self.current_bar = 0

    def next(self):
        """Execute strategy logic for each bar"""
        self.current_bar += 1

        # Check if in pause period (loss protection)
        if self.enable_loss_protection and self.current_bar <= self.paused_until_bar:
            return

        # Detect crossovers
        if len(self.kama) < 2:
            return

        # Price crosses above KAMA (buy signal)
        if crossover(self.data.Close, self.kama):
            if not self.position:
                # Apply filters
                if self._apply_filters('buy'):
                    self.buy()

        # Price crosses below KAMA (sell signal)
        elif crossover(self.kama, self.data.Close):
            if self.position:
                self.position.close()
                self._record_trade_result()

    def _apply_filters(self, signal_type: str) -> bool:
        """Apply all enabled filters"""
        # Efficiency ratio filter
        if self.enable_efficiency_filter:
            if hasattr(self, 'efficiency_ratio') and len(self.efficiency_ratio) > 0:
                if self.efficiency_ratio[-1] < self.min_efficiency_ratio:
                    return False

        # KAMA slope confirmation
        if self.enable_slope_confirmation:
            if hasattr(self, 'kama_slope') and len(self.kama_slope) > 0:
                if self.kama_slope[-1] <= 0:
                    return False

        # Price slope filter
        if self.enable_slope_filter:
            if len(self.data.Close) > self.slope_lookback:
                slope = self.data.Close[-1] - self.data.Close[-self.slope_lookback]
                if slope <= 0:
                    return False

        # ADX filter
        if self.enable_adx_filter:
            if hasattr(self, 'adx') and len(self.adx) > 0:
                if self.adx[-1] < self.adx_threshold:
                    return False

        # Volume filter
        if self.enable_volume_filter:
            if len(self.data.Volume) >= self.volume_period:
                vol_ma = np.mean(self.data.Volume[-self.volume_period:])
                if self.data.Volume[-1] < vol_ma * self.volume_ratio:
                    return False

        return True

    def _record_trade_result(self):
        """Record trade result for loss protection"""
        if not self.enable_loss_protection:
            return

        # Check if last trade was a loss
        if len(self.closed_trades) > 0:
            last_trade = self.closed_trades[-1]
            if last_trade.pl < 0:
                self.consecutive_losses += 1

                if self.consecutive_losses >= self.max_consecutive_losses:
                    # Pause trading
                    self.paused_until_bar = self.current_bar + self.pause_bars
                    self.consecutive_losses = 0
            else:
                # Reset on winning trade
                self.consecutive_losses = 0


class ComboBacktestStrategy(Strategy):
    """
    Combo Backtest Strategy Wrapper

    Combines MACD and KAMA signals with configurable logic (OR/AND/SPLIT).

    Note: This is a simplified implementation. For full combo support,
    consider using separate backtests and combining results.
    """

    # Strategy mode
    combo_mode = 'or'  # 'or', 'and', 'split'

    # MACD parameters
    macd_fast_period = 12
    macd_slow_period = 26
    macd_signal_period = 9

    # KAMA parameters
    kama_period = 20
    kama_fast = 2
    kama_slow = 30

    # Loss protection
    enable_loss_protection = False
    max_consecutive_losses = 3
    pause_bars = 10

    # Long-only mode (A-share market does not allow short selling)
    long_only = True

    def init(self):
        """Initialize both MACD and KAMA indicators"""
        # MACD generator
        self.macd_generator = MACDSignalGenerator(
            fast_period=self.macd_fast_period,
            slow_period=self.macd_slow_period,
            signal_period=self.macd_signal_period
        )

        # KAMA generator
        self.kama_generator = KAMASignalGenerator(
            kama_period=self.kama_period,
            kama_fast=self.kama_fast,
            kama_slow=self.kama_slow
        )

        # Calculate MACD
        def macd_indicator(close):
            close_series = pd.Series(close)
            macd_line, signal_line, _ = self.macd_generator.calculate_macd(close_series)
            return macd_line, signal_line

        self.macd_line, self.macd_signal = self.I(
            macd_indicator,
            self.data.Close,
            name=('MACD', 'MACDSignal')
        )

        # Calculate KAMA
        def kama_indicator(close):
            close_series = pd.Series(close)
            return self.kama_generator.calculate_kama(close_series)

        self.kama = self.I(
            kama_indicator,
            self.data.Close,
            name='KAMA'
        )

        # Loss protection state
        self.consecutive_losses = 0
        self.paused_until_bar = -1
        self.current_bar = 0

    def next(self):
        """Execute combo strategy logic"""
        self.current_bar += 1

        # Check if in pause period
        if self.enable_loss_protection and self.current_bar <= self.paused_until_bar:
            return

        if len(self.macd_line) < 2 or len(self.kama) < 2:
            return

        # Detect signals
        macd_buy = crossover(self.macd_line, self.macd_signal)
        macd_sell = crossover(self.macd_signal, self.macd_line)
        kama_buy = crossover(self.data.Close, self.kama)
        kama_sell = crossover(self.kama, self.data.Close)

        # Combine signals based on mode
        if self.combo_mode == 'or':
            buy_signal = macd_buy or kama_buy
            sell_signal = macd_sell or kama_sell
        elif self.combo_mode == 'and':
            buy_signal = macd_buy and kama_buy
            sell_signal = macd_sell and kama_sell
        else:  # split mode - use MACD only (simplified)
            buy_signal = macd_buy
            sell_signal = macd_sell

        # Execute trades
        if buy_signal and not self.position:
            self.buy()
        elif sell_signal and self.position:
            self.position.close()
            self._record_trade_result()

    def _record_trade_result(self):
        """Record trade result for loss protection"""
        if not self.enable_loss_protection:
            return

        if len(self.closed_trades) > 0:
            last_trade = self.closed_trades[-1]
            if last_trade.pl < 0:
                self.consecutive_losses += 1

                if self.consecutive_losses >= self.max_consecutive_losses:
                    self.paused_until_bar = self.current_bar + self.pause_bars
                    self.consecutive_losses = 0
            else:
                self.consecutive_losses = 0


# Strategy mapping for convenience
STRATEGY_MAP = {
    'macd': MACDBacktestStrategy,
    'kama': KAMABacktestStrategy,
    'combo': ComboBacktestStrategy,
}


def get_strategy_class(strategy_type: str) -> type:
    """
    Get strategy class by type name

    Args:
        strategy_type: 'macd', 'kama', or 'combo'

    Returns:
        Strategy class

    Raises:
        ValueError: If strategy type is unknown
    """
    if strategy_type not in STRATEGY_MAP:
        raise ValueError(f"Unknown strategy type: {strategy_type}. "
                        f"Available: {list(STRATEGY_MAP.keys())}")

    return STRATEGY_MAP[strategy_type]


if __name__ == '__main__':
    """Test the strategy wrappers with sample data"""
    import pandas as pd
    from backtesting import Backtest

    # Create sample data
    dates = pd.date_range('2023-01-01', periods=200, freq='D')
    np.random.seed(42)

    # Generate synthetic price data with trend
    close_prices = 100 + np.cumsum(np.random.randn(200) * 2)
    high_prices = close_prices + np.random.rand(200) * 2
    low_prices = close_prices - np.random.rand(200) * 2
    open_prices = close_prices + np.random.randn(200)
    volumes = np.random.randint(1000000, 5000000, 200)

    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)

    print("=" * 80)
    print("Backtest Strategy Wrappers Test")
    print("=" * 80)
    print()

    # Test 1: MACD Strategy
    print("Test 1: MACD Backtest Strategy")
    bt_macd = Backtest(df, MACDBacktestStrategy, cash=100000, commission=0.001)
    stats_macd = bt_macd.run()
    print(f"  Return: {stats_macd['Return [%]']:.2f}%")
    print(f"  Sharpe Ratio: {stats_macd['Sharpe Ratio']:.3f}")
    print(f"  Max Drawdown: {stats_macd['Max. Drawdown [%]']:.2f}%")
    print(f"  # Trades: {stats_macd['# Trades']}")
    print()

    # Test 2: KAMA Strategy
    print("Test 2: KAMA Backtest Strategy")
    bt_kama = Backtest(df, KAMABacktestStrategy, cash=100000, commission=0.001)
    stats_kama = bt_kama.run()
    print(f"  Return: {stats_kama['Return [%]']:.2f}%")
    print(f"  Sharpe Ratio: {stats_kama['Sharpe Ratio']:.3f}")
    print(f"  Max Drawdown: {stats_kama['Max. Drawdown [%]']:.2f}%")
    print(f"  # Trades: {stats_kama['# Trades']}")
    print()

    # Test 3: Combo Strategy
    print("Test 3: Combo Backtest Strategy (OR mode)")
    bt_combo = Backtest(df, ComboBacktestStrategy, cash=100000, commission=0.001)
    stats_combo = bt_combo.run()
    print(f"  Return: {stats_combo['Return [%]']:.2f}%")
    print(f"  Sharpe Ratio: {stats_combo['Sharpe Ratio']:.3f}")
    print(f"  Max Drawdown: {stats_combo['Max. Drawdown [%]']:.2f}%")
    print(f"  # Trades: {stats_combo['# Trades']}")
    print()

    print("=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)
