#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KAMA Signal Generator for ETF Trend Following v2

Independent signal generator that doesn't depend on backtesting.py's Strategy class.
Designed for efficient full-pool scanning and signal generation.

Features:
- KAMA (Kaufman's Adaptive Moving Average) crossover signals
- Adaptive to market efficiency: fast in trends, smooth in consolidations
- Optional filters: Efficiency Ratio, Slope, ADX, Volume
- All filters are disabled by default (baseline mode)
- Compatible with Python 3.9+

Reference:
- Based on /mnt/d/git/backtesting/strategies/kama_cross.py
- Adapted for standalone signal generation without backtesting.py dependency

KAMA Algorithm:
1. Efficiency Ratio (ER) = |Price_change| / Sum(|Daily_change|)
2. Smoothing Constant (SC) = [ER × (fast_sc - slow_sc) + slow_sc]²
3. KAMA_t = KAMA_{t-1} + SC × (Price_t - KAMA_{t-1})
"""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np


class KAMASignalGenerator:
    """
    KAMA Signal Generator

    Generates buy/sell signals based on price crossing KAMA line.
    KAMA adapts to market efficiency: responsive in trends, smooth in noise.

    Parameters:
        kama_period: KAMA efficiency ratio calculation period (default: 20)
        kama_fast: Fast smoothing period (default: 2)
        kama_slow: Slow smoothing period (default: 30)

        # Optional KAMA-specific Filters (all default to False/disabled)
        enable_efficiency_filter: Enable efficiency ratio filter
        min_efficiency_ratio: Minimum ER threshold (default: 0.3)
        enable_slope_confirmation: Enable KAMA slope confirmation
        min_slope_periods: KAMA slope lookback period (default: 3)

        # Optional Generic Filters (all default to False/disabled)
        enable_adx_filter: Enable ADX trend strength filter
        adx_period: ADX calculation period (default: 14)
        adx_threshold: ADX threshold (default: 25)

        enable_volume_filter: Enable volume confirmation filter
        volume_period: Volume MA period (default: 20)
        volume_ratio: Volume amplification ratio (default: 1.2)

        enable_slope_filter: Enable price slope filter
        slope_lookback: Price slope lookback period (default: 5)
    """

    def __init__(
        self,
        kama_period: int = 20,
        kama_fast: int = 2,
        kama_slow: int = 30,
        # KAMA-specific filters
        enable_efficiency_filter: bool = False,
        min_efficiency_ratio: float = 0.3,
        enable_slope_confirmation: bool = False,
        min_slope_periods: int = 3,
        # Generic filters
        enable_adx_filter: bool = False,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        enable_volume_filter: bool = False,
        volume_period: int = 20,
        volume_ratio: float = 1.2,
        enable_slope_filter: bool = False,
        slope_lookback: int = 5,
        **kwargs
    ):
        # Core KAMA parameters
        self.kama_period = kama_period
        self.kama_fast = kama_fast
        self.kama_slow = kama_slow

        # Validate core parameters
        if kama_fast >= kama_slow:
            raise ValueError(f"kama_fast ({kama_fast}) must be < kama_slow ({kama_slow})")

        if kama_period < 2:
            raise ValueError(f"kama_period ({kama_period}) must be at least 2")

        # KAMA-specific filters
        self.enable_efficiency_filter = enable_efficiency_filter
        self.min_efficiency_ratio = min_efficiency_ratio
        self.enable_slope_confirmation = enable_slope_confirmation
        self.min_slope_periods = min_slope_periods

        # Generic filters
        self.enable_adx_filter = enable_adx_filter
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

        self.enable_volume_filter = enable_volume_filter
        self.volume_period = volume_period
        self.volume_ratio = volume_ratio

        self.enable_slope_filter = enable_slope_filter
        self.slope_lookback = slope_lookback

        # Store any additional kwargs for future extensibility
        self.extra_params = kwargs

    def calculate_kama(
        self,
        close: pd.Series,
        period: Optional[int] = None,
        fast_period: Optional[int] = None,
        slow_period: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate KAMA (Kaufman's Adaptive Moving Average)

        KAMA adjusts its smoothing constant based on market efficiency,
        responding quickly in trends and slowly in consolidations.

        Args:
            close: Close price series
            period: Efficiency ratio calculation period (uses instance default if None)
            fast_period: Fast smoothing period (uses instance default if None)
            slow_period: Slow smoothing period (uses instance default if None)

        Returns:
            KAMA series
        """
        period = period or self.kama_period
        fast = fast_period or self.kama_fast
        slow = slow_period or self.kama_slow

        prices = pd.Series(close)
        n = len(prices)

        # Initialize result series
        kama = pd.Series(index=prices.index, dtype=float)

        # Calculate smoothing constants
        fastest_sc = 2.0 / (fast + 1)  # Fast EMA smoothing constant
        slowest_sc = 2.0 / (slow + 1)  # Slow EMA smoothing constant

        # KAMA initial value: use first valid price after warm-up period
        first_valid_idx = period
        if first_valid_idx >= n:
            return kama  # Return all-NaN series

        kama.iloc[first_valid_idx] = prices.iloc[first_valid_idx]

        # Calculate KAMA iteratively
        for i in range(first_valid_idx + 1, n):
            # 1. Calculate Efficiency Ratio (ER)
            # Change = abs(current price - price N periods ago)
            change = abs(prices.iloc[i] - prices.iloc[i - period])

            # Volatility = sum(abs(adjacent price changes)) over period
            volatility = 0
            for j in range(i - period + 1, i + 1):
                volatility += abs(prices.iloc[j] - prices.iloc[j - 1])

            # ER = Change / Volatility (handle division by zero)
            if volatility == 0:
                er = 0  # No price movement, use maximum smoothing
            else:
                er = change / volatility

            # 2. Calculate Smoothing Constant (SC)
            # SC = [ER * (fastest_SC - slowest_SC) + slowest_SC]^2
            sc = er * (fastest_sc - slowest_sc) + slowest_sc
            sc = sc * sc  # Square for non-linear response

            # 3. Calculate KAMA value
            # KAMA[today] = KAMA[yesterday] + SC * (Price - KAMA[yesterday])
            kama.iloc[i] = kama.iloc[i - 1] + sc * (prices.iloc[i] - kama.iloc[i - 1])

        return kama

    def calculate_efficiency_ratio(
        self,
        close: pd.Series,
        period: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate Efficiency Ratio (ER) for signal filtering

        ER measures the efficiency of price movement:
        - ER → 1: Strong directional movement (trend)
        - ER → 0: Choppy movement (consolidation)

        Args:
            close: Close price series
            period: Calculation period (uses instance default if None)

        Returns:
            Efficiency Ratio series (values between 0 and 1)
        """
        period = period or self.kama_period
        prices = pd.Series(close)
        n = len(prices)

        efficiency_ratio = pd.Series(index=prices.index, dtype=float)

        for i in range(period, n):
            # Change = abs(current price - price N periods ago)
            change = abs(prices.iloc[i] - prices.iloc[i - period])

            # Volatility = sum(abs(adjacent price changes))
            volatility = 0
            for j in range(i - period + 1, i + 1):
                volatility += abs(prices.iloc[j] - prices.iloc[j - 1])

            # ER = Change / Volatility
            if volatility == 0:
                er = 0
            else:
                er = change / volatility

            efficiency_ratio.iloc[i] = er

        return efficiency_ratio

    def calculate_slope(
        self,
        series: pd.Series,
        lookback: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate slope (linear trend direction) of a series

        Uses least squares method to calculate slope.

        Args:
            series: Data series (e.g., KAMA or price)
            lookback: Lookback period (uses instance default if None)

        Returns:
            Slope series (positive = uptrend, negative = downtrend)
        """
        lookback = lookback or self.min_slope_periods
        series = pd.Series(series)
        slopes = pd.Series(index=series.index, dtype=float)

        for i in range(lookback, len(series)):
            # Get data window
            y = series.iloc[i - lookback + 1:i + 1].values
            x = np.arange(len(y))

            # Calculate slope using least squares
            # slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
            n = len(y)
            sum_x = np.sum(x)
            sum_y = np.sum(y)
            sum_xy = np.sum(x * y)
            sum_x2 = np.sum(x * x)

            denominator = n * sum_x2 - sum_x * sum_x
            if denominator != 0:
                slope = (n * sum_xy - sum_x * sum_y) / denominator
            else:
                slope = 0

            slopes.iloc[i] = slope

        return slopes

    def calculate_adx(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate ADX (Average Directional Index)

        ADX measures trend strength (not direction).

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
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr

        # Calculate DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # Calculate ADX (moving average of DX)
        adx = dx.rolling(window=period).mean()

        return adx

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate KAMA and all filter indicators

        Args:
            df: DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)

        Returns:
            DataFrame with added indicator columns:
                - kama: KAMA line
                - efficiency_ratio: Efficiency ratio (if efficiency filter enabled)
                - kama_slope: KAMA slope (if slope confirmation enabled)
                - price_slope: Price slope (if slope filter enabled)
                - adx: ADX (if ADX filter enabled)
                - volume_ma: Volume MA (if volume filter enabled)
        """
        result = df.copy()

        # Calculate KAMA
        result['kama'] = self.calculate_kama(df['Close'])

        # Calculate efficiency ratio if needed
        if self.enable_efficiency_filter:
            result['efficiency_ratio'] = self.calculate_efficiency_ratio(df['Close'])

        # Calculate KAMA slope if needed
        if self.enable_slope_confirmation:
            result['kama_slope'] = self.calculate_slope(
                result['kama'],
                self.min_slope_periods
            )

        # Calculate price slope if needed
        if self.enable_slope_filter:
            result['price_slope'] = self.calculate_slope(
                df['Close'],
                self.slope_lookback
            )

        # Calculate ADX if enabled
        if self.enable_adx_filter:
            result['adx'] = self.calculate_adx(df['High'], df['Low'], df['Close'])

        # Calculate volume MA if enabled
        if self.enable_volume_filter:
            result['volume_ma'] = df['Volume'].rolling(window=self.volume_period).mean()

        return result

    def _check_efficiency_filter(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if efficiency ratio filter passes"""
        if not self.enable_efficiency_filter:
            return True

        if 'efficiency_ratio' not in df.columns:
            return True

        er = df['efficiency_ratio'].iloc[idx]
        if pd.isna(er):
            return False

        return er >= self.min_efficiency_ratio

    def _check_slope_confirmation(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if KAMA slope confirmation filter passes"""
        if not self.enable_slope_confirmation:
            return True

        if 'kama_slope' not in df.columns:
            return True

        slope = df['kama_slope'].iloc[idx]
        if pd.isna(slope):
            return False

        return slope > 0

    def _check_price_slope_filter(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if price slope filter passes"""
        if not self.enable_slope_filter:
            return True

        if 'price_slope' not in df.columns:
            return True

        slope = df['price_slope'].iloc[idx]
        if pd.isna(slope):
            return False

        return slope > 0

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

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate buy/sell signals for the entire DataFrame

        Signal Logic:
        - Buy signal: Price crosses above KAMA (golden cross)
        - Sell signal: Price crosses below KAMA (death cross)
        - All enabled filters must pass for signal to be valid

        Args:
            df: DataFrame with calculated indicators (from calculate_indicators)

        Returns:
            Series with signals: 1 = buy, -1 = sell, 0 = hold/no signal
        """
        signals = pd.Series(0, index=df.index)

        # Need at least 2 bars to detect crossover
        if len(df) < 2:
            return signals

        close = df['Close']
        kama = df['kama']

        for i in range(1, len(df)):
            # Detect crossovers
            close_prev = close.iloc[i - 1]
            kama_prev = kama.iloc[i - 1]
            close_curr = close.iloc[i]
            kama_curr = kama.iloc[i]

            # Skip if any value is NaN
            if pd.isna(close_prev) or pd.isna(kama_prev) or \
               pd.isna(close_curr) or pd.isna(kama_curr):
                continue

            # Buy signal: Price crosses above KAMA
            if close_prev <= kama_prev and close_curr > kama_curr:
                # Apply all filters
                if (self._check_efficiency_filter(df, i) and
                    self._check_slope_confirmation(df, i) and
                    self._check_price_slope_filter(df, i) and
                    self._check_adx_filter(df, i) and
                    self._check_volume_filter(df, i)):
                    signals.iloc[i] = 1

            # Sell signal: Price crosses below KAMA
            elif close_prev >= kama_prev and close_curr < kama_curr:
                # No filters on sell signal (follow KAMA cross)
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
        if 'kama' not in df.columns:
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
                'close': float(df['Close'].iloc[idx]) if not pd.isna(df['Close'].iloc[idx]) else None,
                'kama': float(df['kama'].iloc[idx]) if not pd.isna(df['kama'].iloc[idx]) else None,
            }

            # Add signal strength (price distance from KAMA)
            if details['close'] is not None and details['kama'] is not None and details['kama'] != 0:
                details['signal_strength'] = ((details['close'] - details['kama']) / details['kama']) * 100

            # Add filter details if enabled
            if self.enable_efficiency_filter and 'efficiency_ratio' in df.columns:
                details['efficiency_ratio'] = float(df['efficiency_ratio'].iloc[idx]) if not pd.isna(df['efficiency_ratio'].iloc[idx]) else None

            if self.enable_slope_confirmation and 'kama_slope' in df.columns:
                details['kama_slope'] = float(df['kama_slope'].iloc[idx]) if not pd.isna(df['kama_slope'].iloc[idx]) else None

            if self.enable_slope_filter and 'price_slope' in df.columns:
                details['price_slope'] = float(df['price_slope'].iloc[idx]) if not pd.isna(df['price_slope'].iloc[idx]) else None

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
            'kama_period': self.kama_period,
            'kama_fast': self.kama_fast,
            'kama_slow': self.kama_slow,
            # KAMA-specific filters
            'enable_efficiency_filter': self.enable_efficiency_filter,
            'min_efficiency_ratio': self.min_efficiency_ratio,
            'enable_slope_confirmation': self.enable_slope_confirmation,
            'min_slope_periods': self.min_slope_periods,
            # Generic filters
            'enable_adx_filter': self.enable_adx_filter,
            'adx_period': self.adx_period,
            'adx_threshold': self.adx_threshold,
            'enable_volume_filter': self.enable_volume_filter,
            'volume_period': self.volume_period,
            'volume_ratio': self.volume_ratio,
            'enable_slope_filter': self.enable_slope_filter,
            'slope_lookback': self.slope_lookback,
        }

    def __repr__(self) -> str:
        """String representation"""
        filters_enabled = []
        if self.enable_efficiency_filter:
            filters_enabled.append('EfficiencyRatio')
        if self.enable_slope_confirmation:
            filters_enabled.append('KamaSlope')
        if self.enable_adx_filter:
            filters_enabled.append('ADX')
        if self.enable_volume_filter:
            filters_enabled.append('Volume')
        if self.enable_slope_filter:
            filters_enabled.append('PriceSlope')

        filters_str = f", filters={filters_enabled}" if filters_enabled else ""

        return (f"KAMASignalGenerator(period={self.kama_period}, fast={self.kama_fast}, "
                f"slow={self.kama_slow}{filters_str})")


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
    print("KAMA Signal Generator Test")
    print("=" * 60)
    print()

    # Test 1: Baseline (no filters)
    print("Test 1: Baseline KAMA (no filters)")
    generator = KAMASignalGenerator()
    print(f"  Generator: {generator}")

    df_with_indicators = generator.calculate_indicators(df)
    signals = generator.generate_signals(df_with_indicators)

    buy_signals = (signals == 1).sum()
    sell_signals = (signals == -1).sum()
    print(f"  Buy signals: {buy_signals}")
    print(f"  Sell signals: {sell_signals}")
    print(f"  KAMA values (first 5 valid): {df_with_indicators['kama'].dropna().head().round(4).tolist()}")
    print()

    # Test 2: With Efficiency filter
    print("Test 2: KAMA with Efficiency Ratio filter")
    generator_er = KAMASignalGenerator(
        enable_efficiency_filter=True,
        min_efficiency_ratio=0.3
    )
    print(f"  Generator: {generator_er}")

    df_with_indicators = generator_er.calculate_indicators(df)
    signals_er = generator_er.generate_signals(df_with_indicators)

    buy_signals_er = (signals_er == 1).sum()
    sell_signals_er = (signals_er == -1).sum()
    print(f"  Buy signals: {buy_signals_er}")
    print(f"  Sell signals: {sell_signals_er}")
    print()

    # Test 3: With ADX filter
    print("Test 3: KAMA with ADX filter")
    generator_adx = KAMASignalGenerator(
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

    # Test 4: Get signal for specific date
    print("Test 4: Get signal for specific date")
    test_date = dates[50]
    signal_detail = generator.get_signal_for_date(df, str(test_date), return_details=True)
    print(f"  Date: {test_date}")
    print(f"  Signal: {signal_detail['signal']}")
    print(f"  Close: {signal_detail['close']:.4f}")
    print(f"  KAMA: {signal_detail['kama']:.4f}")
    if 'signal_strength' in signal_detail:
        print(f"  Signal Strength: {signal_detail['signal_strength']:.2f}%")
    print()

    # Test 5: Configuration export
    print("Test 5: Configuration export")
    config = generator.get_config()
    print(f"  Config keys: {list(config.keys())}")
    print(f"  KAMA period: {config['kama_period']}")
    print(f"  KAMA fast: {config['kama_fast']}")
    print(f"  KAMA slow: {config['kama_slow']}")
    print()

    # Test 6: KAMA calculation verification
    print("Test 6: KAMA calculation verification")
    kama_values = df_with_indicators['kama'].dropna()
    print(f"  Total KAMA values: {len(kama_values)}")
    print(f"  KAMA min: {kama_values.min():.4f}")
    print(f"  KAMA max: {kama_values.max():.4f}")
    print(f"  KAMA mean: {kama_values.mean():.4f}")
    print()

    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
