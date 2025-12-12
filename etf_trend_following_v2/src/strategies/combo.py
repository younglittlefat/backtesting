#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Combo Signal Generator for ETF Trend Following v2

Combines MACD and KAMA signal generators with flexible combination modes.
Designed for multi-strategy portfolio management and signal aggregation.

Features:
- Three combination modes: 'or', 'and', 'split'
- Configurable conflict resolution strategies
- Support for independent sub-strategy configuration
- Capital allocation support for split mode
- Compatible with Python 3.9+

Reference:
- Integrates MACDSignalGenerator and KAMASignalGenerator
- Designed for backtesting and live trading signal generation
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from .macd import MACDSignalGenerator
from .kama import KAMASignalGenerator


class ComboSignalGenerator:
    """
    Combo Signal Generator

    Combines MACD and KAMA strategies with flexible combination modes.

    Parameters:
        mode: Combination mode
            - 'or' (default): Buy if ANY strategy signals buy, sell if ANY signals sell
            - 'and': Buy if ALL strategies signal buy, sell if ANY signals sell
            - 'split': Run strategies independently with capital allocation

        macd_config: Configuration dict for MACD generator (None = use defaults)
        kama_config: Configuration dict for KAMA generator (None = use defaults)

        weights: Capital allocation weights for 'split' mode
            - Example: {'macd': 0.6, 'kama': 0.4}
            - Default: {'macd': 0.5, 'kama': 0.5}

        conflict_resolution: How to resolve buy/sell conflicts in 'and' mode
            - 'macd_priority': MACD signal takes precedence
            - 'kama_priority': KAMA signal takes precedence
            - 'conservative': Choose the more conservative action (no trade/sell)

    Example:
        # OR mode (aggressive): Buy if either strategy signals buy
        combo_or = ComboSignalGenerator(mode='or')

        # AND mode (conservative): Buy only if both strategies agree
        combo_and = ComboSignalGenerator(mode='and')

        # Split mode: Allocate 60% to MACD, 40% to KAMA
        combo_split = ComboSignalGenerator(
            mode='split',
            weights={'macd': 0.6, 'kama': 0.4}
        )

        # Custom configurations
        combo_custom = ComboSignalGenerator(
            mode='or',
            macd_config={'enable_adx_filter': True, 'adx_threshold': 25},
            kama_config={'enable_efficiency_filter': True, 'min_efficiency_ratio': 0.3}
        )
    """

    def __init__(
        self,
        mode: str = 'or',
        macd_config: Optional[Dict[str, Any]] = None,
        kama_config: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None,
        conflict_resolution: str = 'macd_priority'
    ):
        # Validate mode
        valid_modes = ['or', 'and', 'split']
        if mode not in valid_modes:
            raise ValueError(f"mode must be one of {valid_modes}, got '{mode}'")

        self.mode = mode
        self.conflict_resolution = conflict_resolution

        # Validate conflict resolution
        valid_resolutions = ['macd_priority', 'kama_priority', 'conservative']
        if conflict_resolution not in valid_resolutions:
            raise ValueError(
                f"conflict_resolution must be one of {valid_resolutions}, "
                f"got '{conflict_resolution}'"
            )

        # Initialize sub-strategies
        macd_config = macd_config or {}
        kama_config = kama_config or {}

        self.macd_generator = MACDSignalGenerator(**macd_config)
        self.kama_generator = KAMASignalGenerator(**kama_config)

        # Handle weights for split mode
        if weights is None:
            weights = {'macd': 0.5, 'kama': 0.5}

        # Validate weights
        if not isinstance(weights, dict):
            raise ValueError(f"weights must be a dict, got {type(weights)}")

        if 'macd' not in weights or 'kama' not in weights:
            raise ValueError("weights must contain 'macd' and 'kama' keys")

        # Normalize weights to sum to 1.0
        total_weight = weights['macd'] + weights['kama']
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")

        self.weights = {
            'macd': weights['macd'] / total_weight,
            'kama': weights['kama'] / total_weight
        }

        # Validate weights are non-negative
        if self.weights['macd'] < 0 or self.weights['kama'] < 0:
            raise ValueError("Weights must be non-negative")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators for both MACD and KAMA strategies

        Args:
            df: DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)

        Returns:
            DataFrame with all indicators from both strategies
        """
        result = df.copy()

        # Calculate MACD indicators
        macd_df = self.macd_generator.calculate_indicators(df)
        for col in macd_df.columns:
            if col not in df.columns:
                result[f'macd_{col}'] = macd_df[col]

        # Calculate KAMA indicators
        kama_df = self.kama_generator.calculate_indicators(df)
        for col in kama_df.columns:
            if col not in df.columns:
                result[f'kama_{col}'] = kama_df[col]

        return result

    def _generate_sub_signals(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Generate signals from both sub-strategies

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dict with 'macd' and 'kama' signal series
        """
        # Calculate indicators for each strategy
        macd_df = self.macd_generator.calculate_indicators(df)
        kama_df = self.kama_generator.calculate_indicators(df)

        # Generate signals
        macd_signals = self.macd_generator.generate_signals(macd_df)
        kama_signals = self.kama_generator.generate_signals(kama_df)

        return {
            'macd': macd_signals,
            'kama': kama_signals
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate combined signals for the entire DataFrame

        Signal Logic by Mode:
        - 'or': Buy if ANY strategy signals buy (1), sell if ANY signals sell (-1)
        - 'and': Buy if ALL strategies signal buy (1), sell if ANY signals sell (-1)
        - 'split': Returns weighted signals for capital allocation

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Series with signals:
            - For 'or'/'and' modes: 1 = buy, -1 = sell, 0 = hold/no signal
            - For 'split' mode: Weighted combination of sub-signals
        """
        # Get sub-strategy signals
        sub_signals = self._generate_sub_signals(df)
        macd_signals = sub_signals['macd']
        kama_signals = sub_signals['kama']

        # Initialize combined signals
        signals = pd.Series(0, index=df.index)

        if self.mode == 'or':
            # OR mode: Buy if ANY signals buy, sell if ANY signals sell
            for i in range(len(df)):
                macd_sig = macd_signals.iloc[i]
                kama_sig = kama_signals.iloc[i]

                # Buy signal: Any strategy signals buy
                if macd_sig == 1 or kama_sig == 1:
                    signals.iloc[i] = 1
                # Sell signal: Any strategy signals sell
                elif macd_sig == -1 or kama_sig == -1:
                    signals.iloc[i] = -1

        elif self.mode == 'and':
            # AND mode: Buy if ALL signal buy, sell if ANY signals sell
            for i in range(len(df)):
                macd_sig = macd_signals.iloc[i]
                kama_sig = kama_signals.iloc[i]

                # Sell signal: Any strategy signals sell (exit first)
                if macd_sig == -1 or kama_sig == -1:
                    signals.iloc[i] = -1
                # Buy signal: Both strategies must signal buy
                elif macd_sig == 1 and kama_sig == 1:
                    signals.iloc[i] = 1
                # Conflict resolution: One signals buy, other signals hold
                elif (macd_sig == 1 and kama_sig == 0) or (macd_sig == 0 and kama_sig == 1):
                    # Apply conflict resolution for partial agreement
                    if self.conflict_resolution == 'conservative':
                        signals.iloc[i] = 0  # Don't trade
                    elif self.conflict_resolution == 'macd_priority':
                        signals.iloc[i] = macd_sig
                    elif self.conflict_resolution == 'kama_priority':
                        signals.iloc[i] = kama_sig

        elif self.mode == 'split':
            # Split mode: Return weighted combination for independent tracking
            # In split mode, we return the weighted sum of signals
            # This allows tracking fractional positions
            signals = (macd_signals * self.weights['macd'] +
                      kama_signals * self.weights['kama'])

        return signals

    def get_sub_signals(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Get individual signals from each sub-strategy

        Useful for analysis, debugging, and understanding signal composition.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dict with 'macd' and 'kama' signal series
        """
        return self._generate_sub_signals(df)

    def get_signal_for_date(
        self,
        df: pd.DataFrame,
        date: str,
        return_details: bool = False
    ) -> int | float | Dict[str, Any]:
        """
        Get combined signal for a specific date

        Args:
            df: DataFrame with OHLCV data
            date: Date string (format should match df.index)
            return_details: If True, return dict with signal and sub-strategy details

        Returns:
            - If return_details=False: Signal value (1=buy, -1=sell, 0=hold)
            - If return_details=True: Dict with combined signal and sub-signals
        """
        # Generate combined signals
        signals = self.generate_signals(df)

        # Get signal for the specific date
        try:
            if date in df.index:
                signal = signals.loc[date]
            else:
                # Try to parse date
                date_idx = pd.to_datetime(date)
                if date_idx in df.index:
                    signal = signals.loc[date_idx]
                else:
                    signal = 0
        except (KeyError, ValueError):
            signal = 0

        if not return_details:
            # For 'or'/'and' modes, convert to int; for 'split', return float
            if self.mode in ['or', 'and']:
                return int(signal)
            else:
                return float(signal)

        # Get sub-strategy signals and details
        sub_signals = self._generate_sub_signals(df)

        # Get MACD details
        macd_details = self.macd_generator.get_signal_for_date(
            df, date, return_details=True
        )

        # Get KAMA details
        kama_details = self.kama_generator.get_signal_for_date(
            df, date, return_details=True
        )

        # Prepare result
        result = {
            'combined_signal': float(signal) if self.mode == 'split' else int(signal),
            'mode': self.mode,
            'macd': macd_details,
            'kama': kama_details,
        }

        # Add weights for split mode
        if self.mode == 'split':
            result['weights'] = self.weights.copy()

        return result

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration as a dictionary

        Returns:
            Dictionary with mode, weights, and sub-strategy configurations
        """
        return {
            'mode': self.mode,
            'conflict_resolution': self.conflict_resolution,
            'weights': self.weights.copy(),
            'macd_config': self.macd_generator.get_config(),
            'kama_config': self.kama_generator.get_config(),
        }

    def __repr__(self) -> str:
        """String representation"""
        if self.mode == 'split':
            weight_str = f", weights=MACD:{self.weights['macd']:.1%}/KAMA:{self.weights['kama']:.1%}"
        else:
            weight_str = ""

        return (f"ComboSignalGenerator(mode='{self.mode}'{weight_str}, "
                f"macd={self.macd_generator}, kama={self.kama_generator})")


if __name__ == '__main__':
    """Test the combo signal generator with sample data"""

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
    print("Combo Signal Generator Test")
    print("=" * 60)
    print()

    # Test 1: OR Mode (aggressive)
    print("Test 1: OR Mode (buy if ANY strategy signals)")
    combo_or = ComboSignalGenerator(mode='or')
    print(f"  Generator: {combo_or}")

    signals_or = combo_or.generate_signals(df)
    buy_or = (signals_or == 1).sum()
    sell_or = (signals_or == -1).sum()
    print(f"  Buy signals: {buy_or}")
    print(f"  Sell signals: {sell_or}")
    print()

    # Test 2: AND Mode (conservative)
    print("Test 2: AND Mode (buy if ALL strategies signal)")
    combo_and = ComboSignalGenerator(mode='and')
    print(f"  Generator: {combo_and}")

    signals_and = combo_and.generate_signals(df)
    buy_and = (signals_and == 1).sum()
    sell_and = (signals_and == -1).sum()
    print(f"  Buy signals: {buy_and}")
    print(f"  Sell signals: {sell_and}")
    print()

    # Test 3: Split Mode (capital allocation)
    print("Test 3: Split Mode (60% MACD, 40% KAMA)")
    combo_split = ComboSignalGenerator(
        mode='split',
        weights={'macd': 0.6, 'kama': 0.4}
    )
    print(f"  Generator: {combo_split}")

    signals_split = combo_split.generate_signals(df)
    print(f"  Weighted signals (first 5 non-zero):")
    non_zero_signals = signals_split[signals_split != 0].head()
    for date, sig in non_zero_signals.items():
        print(f"    {date.date()}: {sig:.2f}")
    print()

    # Test 4: Compare sub-signals
    print("Test 4: Sub-strategy signal comparison")
    sub_signals = combo_or.get_sub_signals(df)
    macd_buy = (sub_signals['macd'] == 1).sum()
    macd_sell = (sub_signals['macd'] == -1).sum()
    kama_buy = (sub_signals['kama'] == 1).sum()
    kama_sell = (sub_signals['kama'] == -1).sum()

    print(f"  MACD - Buy: {macd_buy}, Sell: {macd_sell}")
    print(f"  KAMA - Buy: {kama_buy}, Sell: {kama_sell}")
    print(f"  OR Combined - Buy: {buy_or}, Sell: {sell_or}")
    print(f"  AND Combined - Buy: {buy_and}, Sell: {sell_and}")
    print()

    # Test 5: Get signal for specific date with details
    print("Test 5: Get signal for specific date (with details)")
    test_date = dates[50]
    signal_detail = combo_or.get_signal_for_date(df, str(test_date), return_details=True)
    print(f"  Date: {test_date.date()}")
    print(f"  Combined signal: {signal_detail['combined_signal']}")
    print(f"  Mode: {signal_detail['mode']}")
    print(f"  MACD signal: {signal_detail['macd']['signal']}")
    print(f"  KAMA signal: {signal_detail['kama']['signal']}")
    print()

    # Test 6: Custom configurations
    print("Test 6: Custom configurations with filters")
    combo_custom = ComboSignalGenerator(
        mode='or',
        macd_config={'enable_adx_filter': True, 'adx_threshold': 25},
        kama_config={'enable_efficiency_filter': True, 'min_efficiency_ratio': 0.3}
    )
    print(f"  Generator: {combo_custom}")

    signals_custom = combo_custom.generate_signals(df)
    buy_custom = (signals_custom == 1).sum()
    sell_custom = (signals_custom == -1).sum()
    print(f"  Buy signals (with filters): {buy_custom}")
    print(f"  Sell signals (with filters): {sell_custom}")
    print()

    # Test 7: Configuration export
    print("Test 7: Configuration export")
    config = combo_or.get_config()
    print(f"  Mode: {config['mode']}")
    print(f"  Weights: MACD={config['weights']['macd']:.1%}, KAMA={config['weights']['kama']:.1%}")
    print(f"  MACD fast_period: {config['macd_config']['fast_period']}")
    print(f"  KAMA period: {config['kama_config']['kama_period']}")
    print()

    # Test 8: Conflict resolution in AND mode
    print("Test 8: Conflict resolution comparison")
    combo_and_conservative = ComboSignalGenerator(mode='and', conflict_resolution='conservative')
    combo_and_macd = ComboSignalGenerator(mode='and', conflict_resolution='macd_priority')
    combo_and_kama = ComboSignalGenerator(mode='and', conflict_resolution='kama_priority')

    signals_conservative = combo_and_conservative.generate_signals(df)
    signals_macd_pri = combo_and_macd.generate_signals(df)
    signals_kama_pri = combo_and_kama.generate_signals(df)

    print(f"  Conservative - Buy: {(signals_conservative == 1).sum()}, Sell: {(signals_conservative == -1).sum()}")
    print(f"  MACD Priority - Buy: {(signals_macd_pri == 1).sum()}, Sell: {(signals_macd_pri == -1).sum()}")
    print(f"  KAMA Priority - Buy: {(signals_kama_pri == 1).sum()}, Sell: {(signals_kama_pri == -1).sum()}")
    print()

    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
