#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MACD Signal Generator for ETF Trend Following v2

Independent signal generator that doesn't depend on backtesting.py's Strategy class.
Designed for efficient full-pool scanning and signal generation.

Features:
- MACD golden cross (buy) and death cross (sell) signals
- Optional filters: ADX, Volume, Slope, Confirmation, Zero-axis, Hysteresis
- All filters are disabled by default (baseline mode)
- Compatible with Python 3.9+

Reference:
- Based on /mnt/d/git/backtesting/strategies/macd_cross.py
- Adapted for standalone signal generation without backtesting.py dependency
"""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np


class MACDSignalGenerator:
    """
    MACD Signal Generator

    Generates buy/sell signals based on MACD golden cross and death cross.
    All filters are optional and disabled by default.

    Parameters:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

        # Optional Filters (all default to False/disabled)
        enable_adx_filter: Enable ADX trend strength filter
        adx_period: ADX calculation period (default: 14)
        adx_threshold: ADX threshold (default: 25)

        enable_volume_filter: Enable volume confirmation filter
        volume_period: Volume MA period (default: 20)
        volume_ratio: Volume amplification ratio (default: 1.2)

        enable_slope_filter: Enable MACD slope filter
        slope_lookback: Slope lookback period (default: 5)

        enable_confirm_filter: Enable continuous confirmation filter
        confirm_bars: Number of bars for confirmation (default: 2)

        enable_zero_axis: Enable zero-axis constraint
        zero_axis_mode: Zero-axis mode (default: 'symmetric')

        enable_hysteresis: Enable hysteresis/anti-whipsaw filter
        hysteresis_mode: 'std' or 'abs' (default: 'std')
        hysteresis_k: Multiplier for std mode (default: 0.5)
        hysteresis_window: Rolling window for std mode (default: 20)
        hysteresis_abs: Absolute threshold for abs mode (default: 0.001)

        confirm_bars_sell: Sell confirmation bars (default: 0, disabled)
        min_hold_bars: Minimum holding period (default: 0, disabled)
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        # ADX Filter
        enable_adx_filter: bool = False,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        # Volume Filter
        enable_volume_filter: bool = False,
        volume_period: int = 20,
        volume_ratio: float = 1.2,
        # Slope Filter
        enable_slope_filter: bool = False,
        slope_lookback: int = 5,
        # Confirmation Filter
        enable_confirm_filter: bool = False,
        confirm_bars: int = 2,
        # Zero-axis Constraint
        enable_zero_axis: bool = False,
        zero_axis_mode: str = 'symmetric',
        # Hysteresis/Anti-whipsaw
        enable_hysteresis: bool = False,
        hysteresis_mode: str = 'std',
        hysteresis_k: float = 0.5,
        hysteresis_window: int = 20,
        hysteresis_abs: float = 0.001,
        # Sell-side controls
        confirm_bars_sell: int = 0,
        min_hold_bars: int = 0,
        **kwargs
    ):
        # Core parameters
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

        # Validate core parameters
        if fast_period >= slow_period:
            raise ValueError(f"fast_period ({fast_period}) must be < slow_period ({slow_period})")

        # ADX Filter
        self.enable_adx_filter = enable_adx_filter
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

        # Volume Filter
        self.enable_volume_filter = enable_volume_filter
        self.volume_period = volume_period
        self.volume_ratio = volume_ratio

        # Slope Filter
        self.enable_slope_filter = enable_slope_filter
        self.slope_lookback = slope_lookback

        # Confirmation Filter
        self.enable_confirm_filter = enable_confirm_filter
        self.confirm_bars = confirm_bars

        # Zero-axis Constraint
        self.enable_zero_axis = enable_zero_axis
        self.zero_axis_mode = zero_axis_mode

        # Hysteresis
        self.enable_hysteresis = enable_hysteresis
        self.hysteresis_mode = hysteresis_mode
        self.hysteresis_k = hysteresis_k
        self.hysteresis_window = hysteresis_window
        self.hysteresis_abs = hysteresis_abs

        # Sell-side controls
        self.confirm_bars_sell = confirm_bars_sell
        self.min_hold_bars = min_hold_bars

        # Store any additional kwargs for future extensibility
        self.extra_params = kwargs

    def calculate_macd(
        self,
        close: pd.Series,
        fast_period: Optional[int] = None,
        slow_period: Optional[int] = None,
        signal_period: Optional[int] = None
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD indicator

        Args:
            close: Close price series
            fast_period: Fast EMA period (uses instance default if None)
            slow_period: Slow EMA period (uses instance default if None)
            signal_period: Signal line period (uses instance default if None)

        Returns:
            tuple: (macd_line, signal_line, histogram)
        """
        fast = fast_period or self.fast_period
        slow = slow_period or self.slow_period
        signal = signal_period or self.signal_period

        # Calculate fast and slow EMAs
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        # MACD line (DIF)
        macd_line = ema_fast - ema_slow

        # Signal line (DEA)
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()

        # Histogram
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def calculate_adx(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate ADX (Average Directional Index)

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ADX period (uses instance default if None)

        Returns:
            ADX series
        """
        period = period or self.adx_period

        # Calculate +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

        # Calculate TR (True Range)
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)

        # Smooth +DM, -DM and TR
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * pd.Series(plus_dm, index=high.index).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm, index=high.index).rolling(window=period).mean() / atr

        # Calculate DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # Calculate ADX (moving average of DX)
        adx = dx.rolling(window=period).mean()

        return adx

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate MACD and all filter indicators

        Args:
            df: DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)

        Returns:
            DataFrame with added indicator columns:
                - macd_line, signal_line, histogram
                - adx (if ADX filter enabled)
                - volume_ma (if volume filter enabled)
        """
        result = df.copy()

        # Calculate MACD
        macd_line, signal_line, histogram = self.calculate_macd(df['Close'])
        result['macd_line'] = macd_line
        result['signal_line'] = signal_line
        result['histogram'] = histogram

        # Calculate ADX if enabled
        if self.enable_adx_filter:
            result['adx'] = self.calculate_adx(df['High'], df['Low'], df['Close'])

        # Calculate volume MA if enabled
        if self.enable_volume_filter:
            result['volume_ma'] = df['Volume'].rolling(window=self.volume_period).mean()

        return result

    def _check_adx_filter(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if ADX filter passes"""
        if not self.enable_adx_filter:
            return True

        if 'adx' not in df.columns:
            return True

        adx_value = df['adx'].iloc[idx]
        if pd.isna(adx_value):
            return False

        return adx_value > self.adx_threshold

    def _check_volume_filter(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if volume filter passes"""
        if not self.enable_volume_filter:
            return True

        if 'volume_ma' not in df.columns or 'Volume' not in df.columns:
            return True

        volume = df['Volume'].iloc[idx]
        volume_ma = df['volume_ma'].iloc[idx]

        if pd.isna(volume_ma) or volume_ma == 0:
            return False

        return volume > volume_ma * self.volume_ratio

    def _check_slope_filter(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if MACD slope filter passes"""
        if not self.enable_slope_filter:
            return True

        if idx < self.slope_lookback:
            return False

        macd_current = df['macd_line'].iloc[idx]
        macd_past = df['macd_line'].iloc[idx - self.slope_lookback]

        if pd.isna(macd_current) or pd.isna(macd_past):
            return False

        slope = (macd_current - macd_past) / self.slope_lookback
        return slope > 0

    def _check_confirm_filter(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if confirmation filter passes (for buy signals)"""
        if not self.enable_confirm_filter or self.confirm_bars <= 1:
            return True

        if idx < self.confirm_bars - 1:
            return False

        # Check if MACD line has been above signal line for confirm_bars
        for i in range(self.confirm_bars):
            check_idx = idx - i
            macd = df['macd_line'].iloc[check_idx]
            signal = df['signal_line'].iloc[check_idx]

            if pd.isna(macd) or pd.isna(signal) or macd <= signal:
                return False

        return True

    def _check_zero_axis(self, df: pd.DataFrame, idx: int, signal_type: str) -> bool:
        """Check if zero-axis constraint passes"""
        if not self.enable_zero_axis:
            return True

        macd = df['macd_line'].iloc[idx]
        signal = df['signal_line'].iloc[idx]

        if pd.isna(macd) or pd.isna(signal):
            return False

        if self.zero_axis_mode == 'symmetric':
            if signal_type == 'buy':
                return macd > 0 and signal > 0
            else:  # sell
                return macd < 0 and signal < 0

        return True

    def _check_hysteresis(self, df: pd.DataFrame, idx: int, signal_type: str) -> bool:
        """Check if hysteresis/anti-whipsaw filter passes"""
        if not self.enable_hysteresis:
            return True

        hist = df['histogram'].iloc[idx]

        if pd.isna(hist):
            return False

        # Direction consistency check
        if signal_type == 'buy' and hist <= 0:
            return False
        if signal_type == 'sell' and hist >= 0:
            return False

        # Threshold check
        if self.hysteresis_mode == 'std':
            window = max(5, self.hysteresis_window)
            if idx < window - 1:
                return False

            hist_window = df['histogram'].iloc[max(0, idx - window + 1):idx + 1]
            threshold = hist_window.std() * self.hysteresis_k
            threshold = max(threshold, 0.0)

            return abs(hist) > threshold
        else:  # abs mode
            return abs(hist) > self.hysteresis_abs

    def _check_sell_confirmation(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if sell confirmation passes"""
        if self.confirm_bars_sell <= 1:
            return True

        if idx < self.confirm_bars_sell - 1:
            return False

        # Check if MACD line has been below signal line for confirm_bars_sell
        for i in range(self.confirm_bars_sell):
            check_idx = idx - i
            macd = df['macd_line'].iloc[check_idx]
            signal = df['signal_line'].iloc[check_idx]

            if pd.isna(macd) or pd.isna(signal) or macd >= signal:
                return False

        return True

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate buy/sell signals for the entire DataFrame

        Args:
            df: DataFrame with calculated indicators (from calculate_indicators)

        Returns:
            Series with signals: 1 = buy, -1 = sell, 0 = hold/no signal
        """
        signals = pd.Series(0, index=df.index)

        # Need at least 2 bars to detect crossover
        if len(df) < 2:
            return signals

        macd = df['macd_line']
        signal_line = df['signal_line']

        for i in range(1, len(df)):
            # Detect crossovers
            macd_prev = macd.iloc[i - 1]
            signal_prev = signal_line.iloc[i - 1]
            macd_curr = macd.iloc[i]
            signal_curr = signal_line.iloc[i]

            # Skip if any value is NaN
            if pd.isna(macd_prev) or pd.isna(signal_prev) or \
               pd.isna(macd_curr) or pd.isna(signal_curr):
                continue

            # Golden cross (buy signal)
            if macd_prev <= signal_prev and macd_curr > signal_curr:
                # Apply all filters
                if (self._check_adx_filter(df, i) and
                    self._check_volume_filter(df, i) and
                    self._check_slope_filter(df, i) and
                    self._check_confirm_filter(df, i) and
                    self._check_zero_axis(df, i, 'buy') and
                    self._check_hysteresis(df, i, 'buy')):
                    signals.iloc[i] = 1

            # Death cross (sell signal)
            elif macd_prev >= signal_prev and macd_curr < signal_curr:
                # Apply all filters
                if (self._check_zero_axis(df, i, 'sell') and
                    self._check_hysteresis(df, i, 'sell') and
                    self._check_sell_confirmation(df, i)):
                    signals.iloc[i] = -1

        return signals

    def get_signal_for_date(
        self,
        df: pd.DataFrame,
        date: str,
        return_details: bool = False
    ) -> int | Dict[str, Any]:
        """
        Get signal for a specific date

        Args:
            df: DataFrame with OHLCV data
            date: Date string (format should match df.index)
            return_details: If True, return dict with signal and details

        Returns:
            Signal value (1=buy, -1=sell, 0=hold) or dict with details
        """
        # Calculate indicators if not already present
        if 'macd_line' not in df.columns:
            df = self.calculate_indicators(df)

        # Generate signals
        signals = self.generate_signals(df)

        # Get signal for the specific date
        try:
            if date in df.index:
                signal = signals.loc[date]
            else:
                # Try to find the date
                date_idx = pd.to_datetime(date)
                if date_idx in df.index:
                    signal = signals.loc[date_idx]
                else:
                    signal = 0
        except (KeyError, ValueError):
            signal = 0

        if not return_details:
            return int(signal)

        # Return detailed information
        try:
            idx = df.index.get_loc(date) if date in df.index else df.index.get_loc(pd.to_datetime(date))

            details = {
                'signal': int(signal),
                'macd_line': float(df['macd_line'].iloc[idx]) if not pd.isna(df['macd_line'].iloc[idx]) else None,
                'signal_line': float(df['signal_line'].iloc[idx]) if not pd.isna(df['signal_line'].iloc[idx]) else None,
                'histogram': float(df['histogram'].iloc[idx]) if not pd.isna(df['histogram'].iloc[idx]) else None,
            }

            # Add filter details if enabled
            if self.enable_adx_filter and 'adx' in df.columns:
                details['adx'] = float(df['adx'].iloc[idx]) if not pd.isna(df['adx'].iloc[idx]) else None

            if self.enable_volume_filter and 'volume_ma' in df.columns:
                details['volume'] = float(df['Volume'].iloc[idx])
                details['volume_ma'] = float(df['volume_ma'].iloc[idx]) if not pd.isna(df['volume_ma'].iloc[idx]) else None

            return details
        except (KeyError, ValueError):
            return {'signal': 0, 'error': 'Date not found'}

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration as a dictionary

        Returns:
            Dictionary with all parameters
        """
        return {
            # Core parameters
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'signal_period': self.signal_period,
            # ADX Filter
            'enable_adx_filter': self.enable_adx_filter,
            'adx_period': self.adx_period,
            'adx_threshold': self.adx_threshold,
            # Volume Filter
            'enable_volume_filter': self.enable_volume_filter,
            'volume_period': self.volume_period,
            'volume_ratio': self.volume_ratio,
            # Slope Filter
            'enable_slope_filter': self.enable_slope_filter,
            'slope_lookback': self.slope_lookback,
            # Confirmation Filter
            'enable_confirm_filter': self.enable_confirm_filter,
            'confirm_bars': self.confirm_bars,
            # Zero-axis
            'enable_zero_axis': self.enable_zero_axis,
            'zero_axis_mode': self.zero_axis_mode,
            # Hysteresis
            'enable_hysteresis': self.enable_hysteresis,
            'hysteresis_mode': self.hysteresis_mode,
            'hysteresis_k': self.hysteresis_k,
            'hysteresis_window': self.hysteresis_window,
            'hysteresis_abs': self.hysteresis_abs,
            # Sell-side controls
            'confirm_bars_sell': self.confirm_bars_sell,
            'min_hold_bars': self.min_hold_bars,
        }

    def __repr__(self) -> str:
        """String representation"""
        filters_enabled = []
        if self.enable_adx_filter:
            filters_enabled.append('ADX')
        if self.enable_volume_filter:
            filters_enabled.append('Volume')
        if self.enable_slope_filter:
            filters_enabled.append('Slope')
        if self.enable_confirm_filter:
            filters_enabled.append('Confirm')
        if self.enable_zero_axis:
            filters_enabled.append('ZeroAxis')
        if self.enable_hysteresis:
            filters_enabled.append('Hysteresis')

        filters_str = f", filters={filters_enabled}" if filters_enabled else ""

        return (f"MACDSignalGenerator(fast={self.fast_period}, slow={self.slow_period}, "
                f"signal={self.signal_period}{filters_str})")


if __name__ == '__main__':
    """Test the signal generator with sample data"""

    # Create sample data
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    np.random.seed(42)

    # Generate synthetic price data with trend
    close_prices = 100 + np.cumsum(np.random.randn(100) * 2)
    high_prices = close_prices + np.random.rand(100) * 2
    low_prices = close_prices - np.random.rand(100) * 2
    open_prices = close_prices + np.random.randn(100)
    volumes = np.random.randint(1000000, 5000000, 100)

    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)

    print("=" * 60)
    print("MACD Signal Generator Test")
    print("=" * 60)
    print()

    # Test 1: Baseline (no filters)
    print("Test 1: Baseline MACD (no filters)")
    generator = MACDSignalGenerator()
    print(f"  Generator: {generator}")

    df_with_indicators = generator.calculate_indicators(df)
    signals = generator.generate_signals(df_with_indicators)

    buy_signals = (signals == 1).sum()
    sell_signals = (signals == -1).sum()
    print(f"  Buy signals: {buy_signals}")
    print(f"  Sell signals: {sell_signals}")
    print()

    # Test 2: With ADX filter
    print("Test 2: MACD with ADX filter")
    generator_adx = MACDSignalGenerator(
        enable_adx_filter=True,
        adx_threshold=25
    )
    print(f"  Generator: {generator_adx}")

    df_with_indicators = generator_adx.calculate_indicators(df)
    signals_adx = generator_adx.generate_signals(df_with_indicators)

    buy_signals_adx = (signals_adx == 1).sum()
    sell_signals_adx = (signals_adx == -1).sum()
    print(f"  Buy signals: {buy_signals_adx}")
    print(f"  Sell signals: {sell_signals_adx}")
    print()

    # Test 3: Get signal for specific date
    print("Test 3: Get signal for specific date")
    test_date = dates[50]
    signal_detail = generator.get_signal_for_date(df, str(test_date), return_details=True)
    print(f"  Date: {test_date}")
    print(f"  Signal: {signal_detail['signal']}")
    print(f"  MACD: {signal_detail['macd_line']:.4f}")
    print(f"  Signal Line: {signal_detail['signal_line']:.4f}")
    print(f"  Histogram: {signal_detail['histogram']:.4f}")
    print()

    # Test 4: Configuration export
    print("Test 4: Configuration export")
    config = generator.get_config()
    print(f"  Config keys: {list(config.keys())[:5]}...")
    print(f"  Fast period: {config['fast_period']}")
    print(f"  Slow period: {config['slow_period']}")
    print()

    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
