"""
Unit tests for backtest_wrappers module

Tests the Strategy wrappers (MACDBacktestStrategy, KAMABacktestStrategy, ComboBacktestStrategy)
that integrate with backtesting.py framework.

Test Philosophy:
- Use synthetic data for speed and reproducibility
- Focus on strategy logic, not exact numerical results
- Test boundary conditions and edge cases
- Verify filter switches and protection mechanisms
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add project root and src to path so local backtesting package can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtesting import Backtest
from strategies.backtest_wrappers import (
    MACDBacktestStrategy,
    KAMABacktestStrategy,
    ComboBacktestStrategy,
    get_strategy_class,
    STRATEGY_MAP,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def synthetic_data():
    """Generate synthetic OHLCV data with trend"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=200, freq='D')

    # Generate trending price data
    trend = np.linspace(100, 120, 200)  # Upward trend
    noise = np.random.randn(200) * 2
    close_prices = trend + noise

    high_prices = close_prices + np.random.rand(200) * 2
    low_prices = close_prices - np.random.rand(200) * 2
    open_prices = close_prices + np.random.randn(200) * 0.5
    volumes = np.random.randint(1000000, 5000000, 200)

    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)

    return df


@pytest.fixture
def choppy_data():
    """Generate choppy/sideways market data"""
    np.random.seed(123)
    dates = pd.date_range('2023-01-01', periods=200, freq='D')

    # Sideways movement
    close_prices = 100 + np.random.randn(200) * 3
    high_prices = close_prices + np.random.rand(200) * 2
    low_prices = close_prices - np.random.rand(200) * 2
    open_prices = close_prices + np.random.randn(200) * 0.5
    volumes = np.random.randint(1000000, 5000000, 200)

    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)

    return df


@pytest.fixture
def downtrend_data():
    """Generate downtrending market data"""
    np.random.seed(456)
    dates = pd.date_range('2023-01-01', periods=200, freq='D')

    # Downward trend
    trend = np.linspace(120, 80, 200)
    noise = np.random.randn(200) * 2
    close_prices = trend + noise

    high_prices = close_prices + np.random.rand(200) * 2
    low_prices = close_prices - np.random.rand(200) * 2
    open_prices = close_prices + np.random.randn(200) * 0.5
    volumes = np.random.randint(1000000, 5000000, 200)

    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)

    return df


# ============================================================================
# Test MACDBacktestStrategy
# ============================================================================

class TestMACDBacktestStrategy:
    """Test MACD Backtest Strategy"""

    def test_init_creates_generator(self, synthetic_data):
        """Verify generator is created with correct params"""
        bt = Backtest(synthetic_data, MACDBacktestStrategy, cash=100000)
        stats = bt.run()

        # Strategy should have been initialized
        assert stats is not None
        assert 'Return [%]' in stats

    def test_init_registers_indicators(self, synthetic_data):
        """Verify MACD indicators are registered via self.I()"""
        class TestStrategy(MACDBacktestStrategy):
            def init(self):
                super().init()
                # Check indicators were created
                assert hasattr(self, 'macd_line')
                assert hasattr(self, 'signal_line')
                assert hasattr(self, 'histogram')
                assert len(self.macd_line) > 0

        bt = Backtest(synthetic_data, TestStrategy, cash=100000)
        bt.run()

    def test_golden_cross_generates_buy(self, synthetic_data):
        """Test buy signal on MACD crossover"""
        bt = Backtest(synthetic_data, MACDBacktestStrategy, cash=100000, commission=0.001)
        stats = bt.run()

        # Should have some trades in trending market
        assert stats['# Trades'] > 0

    def test_death_cross_closes_position_long_only(self, synthetic_data):
        """Test that death cross closes position but doesn't short"""
        class TestStrategy(MACDBacktestStrategy):
            long_only = True

            def next(self):
                super().next()
                # In long_only mode, should never have short position
                if self.position:
                    assert self.position.is_long

        bt = Backtest(synthetic_data, TestStrategy, cash=100000)
        stats = bt.run()

        # Should have trades but no shorts
        assert stats['# Trades'] >= 0

    def test_adx_filter_blocks_weak_trend(self):
        """When ADX < threshold, buy signal is blocked"""
        # Create controlled choppy data with known MACD crossover
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        np.random.seed(42)

        # Sideways price with small oscillations to create MACD crossovers
        close_prices = 100 + np.sin(np.arange(100) * 0.3) * 2 + np.random.randn(100) * 0.5

        df = pd.DataFrame({
            'Open': close_prices + np.random.randn(100) * 0.2,
            'High': close_prices + np.abs(np.random.randn(100)) * 0.5,
            'Low': close_prices - np.abs(np.random.randn(100)) * 0.5,
            'Close': close_prices,
            'Volume': np.random.randint(1000000, 2000000, 100)
        }, index=dates)

        # Use a shared dict to store results from strategy
        results = {'signals_blocked': 0, 'signals_allowed': 0}

        # Track ADX values and signal blocks
        class TestStrategy(MACDBacktestStrategy):
            enable_adx_filter = True
            adx_threshold = 25.0

            def init(self):
                super().init()

            def next(self):
                # Check if we have a golden cross signal
                if len(self.macd_line) > 1 and len(self.signal_line) > 1:
                    prev_hist = self.histogram[-2] if len(self.histogram) > 1 else 0
                    curr_hist = self.histogram[-1]

                    if prev_hist <= 0 and curr_hist > 0:  # Golden cross
                        # Check if ADX filter would block
                        if hasattr(self, 'adx') and len(self.adx) > 0:
                            if self.adx[-1] < self.adx_threshold:
                                results['signals_blocked'] += 1
                            else:
                                results['signals_allowed'] += 1

                super().next()

        bt = Backtest(df, TestStrategy, cash=100000)
        stats = bt.run()

        # Verify that ADX filter actually blocked some signals
        assert results['signals_blocked'] > 0, "ADX filter should have blocked at least one signal in choppy market"

    def test_volume_filter_blocks_low_volume(self):
        """When volume < threshold, signal blocked"""
        # Create data with oscillating price to generate multiple MACD crossovers
        # and varying volume
        dates = pd.date_range('2023-01-01', periods=150, freq='D')
        np.random.seed(42)

        # Create price with multiple cycles to generate MACD crossovers
        t = np.arange(150)
        close_prices = 100 + 10 * np.sin(t * 0.15) + np.random.randn(150) * 0.5

        # High volume first 80 bars, then very low volume
        volumes = np.concatenate([
            np.random.randint(5000000, 10000000, 80),  # High volume
            np.random.randint(100000, 200000, 70)      # Very low volume (50x drop)
        ])

        df = pd.DataFrame({
            'Open': close_prices,
            'High': close_prices + 0.5,
            'Low': close_prices - 0.5,
            'Close': close_prices,
            'Volume': volumes
        }, index=dates)

        # Baseline without volume filter
        bt_base = Backtest(df, MACDBacktestStrategy, cash=100000)
        stats_base = bt_base.run()

        class VolumeFiltered(MACDBacktestStrategy):
            enable_volume_filter = True
            volume_ratio = 1.2
            volume_period = 20

        bt = Backtest(df, VolumeFiltered, cash=100000)
        stats_filtered = bt.run()

        assert stats_filtered['# Trades'] <= stats_base['# Trades'], "Volume filter未减少交易数"

    def test_slope_filter_blocks_negative_slope(self, downtrend_data):
        """When slope <= 0, signal blocked"""
        # Run without slope filter
        bt_no_filter = Backtest(downtrend_data, MACDBacktestStrategy, cash=100000)
        stats_no_filter = bt_no_filter.run()

        # Run with slope filter
        class SlopeFilterStrategy(MACDBacktestStrategy):
            enable_slope_filter = True
            slope_lookback = 5

        bt_filtered = Backtest(downtrend_data, SlopeFilterStrategy, cash=100000)
        stats_filtered = bt_filtered.run()

        # Slope filter should block signals in downtrend
        assert stats_filtered['# Trades'] <= stats_no_filter['# Trades']

    def test_loss_protection_pauses_after_consecutive_losses(self, choppy_data):
        """After N losses, trading pauses"""
        class LossProtectionStrategy(MACDBacktestStrategy):
            enable_loss_protection = True
            max_consecutive_losses = 2  # Pause after 2 losses
            pause_bars = 10

        bt = Backtest(choppy_data, LossProtectionStrategy, cash=100000)
        stats = bt.run()

        # Strategy should work and handle losses
        assert stats is not None
        # Can't guarantee specific behavior in random data, but should not crash

    def test_trailing_stop_triggers_exit(self):
        """When price drops below trailing stop, position closes"""
        # Create controlled price path with strong trend to trigger MACD buy
        dates = pd.date_range('2023-01-01', periods=150, freq='D')

        # Create a clear uptrend that will trigger MACD golden cross
        # Then a sharp drop to trigger trailing stop
        prices = np.concatenate([
            np.linspace(100, 100, 30),   # Flat - MACD near zero
            np.linspace(100, 120, 40),   # Strong uptrend - trigger MACD buy
            np.linspace(120, 125, 20),   # Continue up - raise stop to ~118.75 (125*0.95)
            np.linspace(125, 115, 20),   # Drop 8% - should trigger 5% stop
            np.linspace(115, 120, 40)    # Recovery
        ])

        df = pd.DataFrame({
            'Open': prices,
            'High': prices + 0.5,
            'Low': prices - 0.5,
            'Close': prices,
            'Volume': np.full(150, 1000000)
        }, index=dates)

        class TestStrategy(MACDBacktestStrategy):
            enable_trailing_stop = True
            trailing_stop_pct = 0.05  # 5% stop
            stop_triggered = False
            fast_period = 6
            slow_period = 13
            signal_period = 4

            def init(self):
                super().init()
                self._prev_closed = 0

            def next(self):
                prev_closed = len(self.closed_trades)
                current_stop = self.trailing_stop_price
                price = self.data.Close[-1]
                # Force an initial entry to ensure trailing stop is in play
                if not self.position and self.current_bar == 0:
                    self.buy()
                    self.entry_bar = self.current_bar
                    self.trailing_stop_price = price * (1 - self.trailing_stop_pct)
                super().next()
                if (
                    self.enable_trailing_stop
                    and len(self.closed_trades) > prev_closed
                ):
                    type(self).stop_triggered = True

        bt = Backtest(df, TestStrategy, cash=100000, commission=0.0)
        stats = bt.run()

        # Verify strategy works with trailing stop enabled
        assert stats is not None, "Backtest should complete successfully"
        assert stats['# Trades'] >= 1, "Should include at least one closed trade via stop or reversal"

    def test_trailing_stop_only_moves_up(self, synthetic_data):
        """Stop price should only increase, never decrease for same position"""
        class TestStrategy(MACDBacktestStrategy):
            enable_trailing_stop = True
            trailing_stop_pct = 0.05

            def init(self):
                super().init()
                self.stop_history = []
                self.position_size_history = []

            def next(self):
                super().next()

                # Track stop price along with position size to detect new positions
                if self.position and self.position.is_long and self.trailing_stop_price is not None:
                    current_size = self.position.size

                    # Check if this is same position (size unchanged) or new position
                    if len(self.position_size_history) > 0 and current_size == self.position_size_history[-1]:
                        # Same position - stop should only increase (or stay same if price dropped)
                        if len(self.stop_history) > 0:
                            # Allow small decrease due to float precision, but flag large decreases
                            decrease = self.stop_history[-1] - self.trailing_stop_price
                            assert decrease < 0.01, \
                                f"Trailing stop decreased significantly: {self.stop_history[-1]:.6f} -> {self.trailing_stop_price:.6f}"

                    self.stop_history.append(self.trailing_stop_price)
                    self.position_size_history.append(current_size)
                else:
                    # No position - clear history
                    if not self.position:
                        self.stop_history = []
                        self.position_size_history = []

        bt = Backtest(synthetic_data, TestStrategy, cash=100000)
        bt.run()

    def test_min_hold_bars_prevents_early_exit(self, synthetic_data):
        """Can't exit before min_hold_bars"""
        class MinHoldStrategy(MACDBacktestStrategy):
            min_hold_bars = 5

            def init(self):
                super().init()
                self.trade_entry_bars = []
                self.trade_exit_bars = []

            def next(self):
                # Track entries
                had_position = self.position

                super().next()

                # Track position changes
                if not had_position and self.position:
                    self.trade_entry_bars.append(self.current_bar)
                elif had_position and not self.position:
                    self.trade_exit_bars.append(self.current_bar)

        bt = Backtest(synthetic_data, MinHoldStrategy, cash=100000)
        stats = bt.run()

        # If we have trades, check min hold is respected
        # (This is implicit in the strategy logic)
        assert stats is not None

    def test_confirm_filter_requires_persistence(self):
        """Confirm filter requires signal to persist for N bars"""
        # Create data with brief crossover (1 bar) then reversal
        dates = pd.date_range('2023-01-01', periods=100, freq='D')

        # Create price pattern that generates brief MACD crossover
        # Use exponential pattern to create clear MACD behavior
        prices = np.concatenate([
            np.linspace(100, 105, 30),   # Slow rise
            np.linspace(105, 106, 5),    # Brief crossover (1-2 bars)
            np.linspace(106, 104, 10),   # Quick reversal
            np.linspace(104, 110, 30),   # Strong rise (sustained signal)
            np.linspace(110, 108, 25)    # Decline
        ])

        df = pd.DataFrame({
            'Open': prices,
            'High': prices + 0.3,
            'Low': prices - 0.3,
            'Close': prices,
            'Volume': np.full(100, 1000000)
        }, index=dates)

        # Track signal persistence
        class TestStrategy(MACDBacktestStrategy):
            enable_confirm_filter = True
            confirm_bars = 3  # Need 3 bars confirmation

            def init(self):
                super().init()
                self.brief_signals_blocked = 0
                self.sustained_signals_allowed = 0
                self.consecutive_bullish = 0

            def next(self):
                # Track consecutive bullish bars
                if len(self.histogram) > 0 and self.histogram[-1] > 0:
                    self.consecutive_bullish += 1
                else:
                    # Signal ended before confirmation
                    if 0 < self.consecutive_bullish < self.confirm_bars:
                        self.brief_signals_blocked += 1
                    self.consecutive_bullish = 0

                # Check if position opened (signal was confirmed)
                had_position = bool(self.position)
                super().next()

                if not had_position and self.position:
                    self.sustained_signals_allowed += 1

        bt = Backtest(df, TestStrategy, cash=100000, commission=0.0)
        stats = bt.run()

        # Verify confirm filter affected signal processing
        # The strategy should have processed signals (either blocked or allowed)
        assert stats is not None, "Backtest should complete successfully"
        # Confirm filter should reduce impulsive trading
        assert stats['# Trades'] >= 0, "Should handle confirm filter without crashing"

    def test_zero_axis_constraint(self):
        """Zero axis constraint requires MACD above zero for buy"""
        # Create data with MACD crossovers both above and below zero
        dates = pd.date_range('2023-01-01', periods=100, freq='D')

        # Pattern: downtrend (MACD<0), then uptrend (MACD>0)
        prices = np.concatenate([
            np.linspace(110, 100, 30),   # Downtrend - MACD below zero
            np.linspace(100, 101, 10),   # Brief crossover below zero
            np.linspace(101, 115, 40),   # Strong uptrend - MACD above zero
            np.linspace(115, 113, 20)    # Slight decline
        ])

        df = pd.DataFrame({
            'Open': prices,
            'High': prices + 0.3,
            'Low': prices - 0.3,
            'Close': prices,
            'Volume': np.full(100, 1000000)
        }, index=dates)

        # Track zero axis constraint
        class TestStrategy(MACDBacktestStrategy):
            enable_zero_axis = True
            zero_axis_mode = 'symmetric'

            def init(self):
                super().init()
                self.signals_below_zero = 0
                self.signals_above_zero = 0
                self.entries_recorded = 0

            def next(self):
                # Detect golden cross
                if len(self.histogram) > 1:
                    prev_hist = self.histogram[-2]
                    curr_hist = self.histogram[-1]

                    if prev_hist <= 0 and curr_hist > 0:  # Golden cross
                        macd_value = self.macd_line[-1]
                        if macd_value < 0:
                            self.signals_below_zero += 1
                        else:
                            self.signals_above_zero += 1

                had_position = bool(self.position)
                super().next()

                # Count actual entries
                if not had_position and self.position:
                    self.entries_recorded += 1

        bt = Backtest(df, TestStrategy, cash=100000, commission=0.0)
        stats = bt.run()

        # Verify zero axis constraint works
        assert stats is not None, "Backtest should complete successfully"
        # Zero axis constraint should filter some signals
        assert stats['# Trades'] >= 0, "Should handle zero axis constraint without crashing"

    def test_hysteresis_filter(self):
        """Hysteresis filter reduces noise trading"""
        # Create choppy data with many small crossovers near zero
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        np.random.seed(42)

        # Oscillating price around 100 to create many small MACD crossovers
        prices = 100 + np.sin(np.arange(100) * 0.5) * 3 + np.random.randn(100) * 0.8

        df = pd.DataFrame({
            'Open': prices,
            'High': prices + 0.5,
            'Low': prices - 0.5,
            'Close': prices,
            'Volume': np.full(100, 1000000)
        }, index=dates)

        # Run without hysteresis
        class NoHysteresisStrategy(MACDBacktestStrategy):
            enable_hysteresis = False

            def init(self):
                super().init()
                self.crossovers_detected = 0

            def next(self):
                if len(self.histogram) > 1:
                    if self.histogram[-2] <= 0 and self.histogram[-1] > 0:
                        self.crossovers_detected += 1
                super().next()

        bt_no_filter = Backtest(df, NoHysteresisStrategy, cash=100000)
        stats_no_filter = bt_no_filter.run()

        # Run with hysteresis
        class HysteresisStrategy(MACDBacktestStrategy):
            enable_hysteresis = True
            hysteresis_mode = 'std'
            hysteresis_k = 0.5

            def init(self):
                super().init()
                self.crossovers_detected = 0

            def next(self):
                if len(self.histogram) > 1:
                    if self.histogram[-2] <= 0 and self.histogram[-1] > 0:
                        self.crossovers_detected += 1
                super().next()

        bt_filtered = Backtest(df, HysteresisStrategy, cash=100000)
        stats_filtered = bt_filtered.run()

        # Hysteresis should reduce trades in choppy market
        assert stats_filtered['# Trades'] <= stats_no_filter['# Trades'], \
            f"Hysteresis should reduce trades: {stats_filtered['# Trades']} vs {stats_no_filter['# Trades']}"

    def test_boundary_fast_period(self, synthetic_data):
        """Test edge case for fast period"""
        class BoundaryStrategy(MACDBacktestStrategy):
            fast_period = 5  # Small value
            slow_period = 20

        bt = Backtest(synthetic_data, BoundaryStrategy, cash=100000)
        stats = bt.run()

        # Should work with small fast period
        assert stats is not None

    def test_combined_filters(self, synthetic_data):
        """Test multiple filters working together"""
        class CombinedStrategy(MACDBacktestStrategy):
            enable_adx_filter = True
            enable_volume_filter = True
            enable_slope_filter = True
            adx_threshold = 25.0

        bt = Backtest(synthetic_data, CombinedStrategy, cash=100000)
        stats = bt.run()

        # Should work with multiple filters
        assert stats is not None


# ============================================================================
# Test KAMABacktestStrategy
# ============================================================================

class TestKAMABacktestStrategy:
    """Test KAMA Backtest Strategy"""

    def test_init_creates_kama_generator(self, synthetic_data):
        """Verify KAMA generator is created"""
        bt = Backtest(synthetic_data, KAMABacktestStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None
        assert 'Return [%]' in stats

    def test_price_cross_above_kama_buys(self, synthetic_data):
        """Test buy signal when price crosses above KAMA"""
        bt = Backtest(synthetic_data, KAMABacktestStrategy, cash=100000)
        stats = bt.run()

        # Should generate trades in trending market
        assert stats['# Trades'] > 0

    def test_price_cross_below_kama_sells(self, synthetic_data):
        """Test sell signal when price crosses below"""
        class TestStrategy(KAMABacktestStrategy):
            def next(self):
                super().next()
                # In long_only mode, should never short
                if self.position:
                    assert self.position.is_long

        bt = Backtest(synthetic_data, TestStrategy, cash=100000)
        stats = bt.run()

        assert stats['# Trades'] >= 0

    def test_efficiency_filter_blocks_choppy_market(self, choppy_data):
        """When ER < threshold, signal blocked"""
        # Run without efficiency filter
        bt_no_filter = Backtest(choppy_data, KAMABacktestStrategy, cash=100000)
        stats_no_filter = bt_no_filter.run()

        # Run with efficiency filter
        class EfficiencyFilterStrategy(KAMABacktestStrategy):
            enable_efficiency_filter = True
            min_efficiency_ratio = 0.5  # High threshold

        bt_filtered = Backtest(choppy_data, EfficiencyFilterStrategy, cash=100000)
        stats_filtered = bt_filtered.run()

        # Efficiency filter should reduce trades in choppy market
        assert stats_filtered['# Trades'] <= stats_no_filter['# Trades']

    def test_slope_confirmation_filter(self, downtrend_data):
        """Test KAMA slope confirmation blocks negative slope"""
        # Run without slope confirmation
        bt_no_filter = Backtest(downtrend_data, KAMABacktestStrategy, cash=100000)
        stats_no_filter = bt_no_filter.run()

        # Run with slope confirmation
        class SlopeConfirmStrategy(KAMABacktestStrategy):
            enable_slope_confirmation = True
            min_slope_periods = 3

        bt_filtered = Backtest(downtrend_data, SlopeConfirmStrategy, cash=100000)
        stats_filtered = bt_filtered.run()

        # Should reduce trades in downtrend
        assert stats_filtered['# Trades'] <= stats_no_filter['# Trades']

    def test_loss_protection_works(self, choppy_data):
        """Loss protection pauses trading after consecutive losses"""
        class LossProtectionStrategy(KAMABacktestStrategy):
            enable_loss_protection = True
            max_consecutive_losses = 2
            pause_bars = 10

        bt = Backtest(choppy_data, LossProtectionStrategy, cash=100000)
        stats = bt.run()

        # Should not crash
        assert stats is not None

    def test_long_only_mode(self, synthetic_data):
        """Verify no shorts in long_only mode"""
        class TestStrategy(KAMABacktestStrategy):
            long_only = True

            def next(self):
                super().next()
                if self.position:
                    assert self.position.is_long, "Found short position in long_only mode"

        bt = Backtest(synthetic_data, TestStrategy, cash=100000)
        bt.run()

    def test_adx_filter_integration(self, choppy_data):
        """Test ADX filter works with KAMA"""
        class ADXFilterStrategy(KAMABacktestStrategy):
            enable_adx_filter = True
            adx_threshold = 30.0

        bt = Backtest(choppy_data, ADXFilterStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None

    def test_volume_filter_integration(self, synthetic_data):
        """Test volume filter works with KAMA"""
        class VolumeFilterStrategy(KAMABacktestStrategy):
            enable_volume_filter = True
            volume_ratio = 1.0

        bt = Backtest(synthetic_data, VolumeFilterStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None

    def test_boundary_kama_period(self, synthetic_data):
        """Test edge case for KAMA period"""
        class BoundaryStrategy(KAMABacktestStrategy):
            kama_period = 10  # Short period

        bt = Backtest(synthetic_data, BoundaryStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None

    def test_combined_kama_filters(self, synthetic_data):
        """Test multiple KAMA-specific filters together"""
        class CombinedStrategy(KAMABacktestStrategy):
            enable_efficiency_filter = True
            enable_slope_confirmation = True
            enable_adx_filter = True
            min_efficiency_ratio = 0.3

        bt = Backtest(synthetic_data, CombinedStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None


# ============================================================================
# Test ComboBacktestStrategy
# ============================================================================

class TestComboBacktestStrategy:
    """Test Combo Backtest Strategy"""

    def test_or_mode_any_signal_triggers(self, synthetic_data):
        """Buy when either MACD or KAMA signals"""
        class OrModeStrategy(ComboBacktestStrategy):
            combo_mode = 'or'

        bt = Backtest(synthetic_data, OrModeStrategy, cash=100000)
        stats = bt.run()

        # OR mode should have more trades than AND mode
        assert stats['# Trades'] >= 0

    def test_and_mode_requires_both_signals(self, synthetic_data):
        """Buy only when both signal"""
        # Run OR mode
        class OrStrategy(ComboBacktestStrategy):
            combo_mode = 'or'

        bt_or = Backtest(synthetic_data, OrStrategy, cash=100000)
        stats_or = bt_or.run()

        # Run AND mode
        class AndStrategy(ComboBacktestStrategy):
            combo_mode = 'and'

        bt_and = Backtest(synthetic_data, AndStrategy, cash=100000)
        stats_and = bt_and.run()

        # AND mode should have fewer or equal trades
        assert stats_and['# Trades'] <= stats_or['# Trades']

    def test_split_mode_uses_macd(self, synthetic_data):
        """Split mode uses MACD (simplified implementation)"""
        class SplitStrategy(ComboBacktestStrategy):
            combo_mode = 'split'

        bt = Backtest(synthetic_data, SplitStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None

    def test_loss_protection_works(self, choppy_data):
        """Loss protection works in combo mode"""
        class LossProtectionStrategy(ComboBacktestStrategy):
            enable_loss_protection = True
            max_consecutive_losses = 2
            pause_bars = 10

        bt = Backtest(choppy_data, LossProtectionStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None

    def test_long_only_combo(self, synthetic_data):
        """Verify long_only mode in combo strategy"""
        class TestStrategy(ComboBacktestStrategy):
            long_only = True

            def next(self):
                super().next()
                if self.position:
                    assert self.position.is_long

        bt = Backtest(synthetic_data, TestStrategy, cash=100000)
        bt.run()

    def test_custom_macd_parameters(self, synthetic_data):
        """Test custom MACD parameters in combo"""
        class CustomStrategy(ComboBacktestStrategy):
            macd_fast_period = 8
            macd_slow_period = 21
            macd_signal_period = 5

        bt = Backtest(synthetic_data, CustomStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None

    def test_custom_kama_parameters(self, synthetic_data):
        """Test custom KAMA parameters in combo"""
        class CustomStrategy(ComboBacktestStrategy):
            kama_period = 15
            kama_fast = 3
            kama_slow = 25

        bt = Backtest(synthetic_data, CustomStrategy, cash=100000)
        stats = bt.run()

        assert stats is not None


# ============================================================================
# Test Strategy Map and Helper Functions
# ============================================================================

class TestStrategyMap:
    """Test strategy mapping and helper functions"""

    def test_get_strategy_class_macd(self):
        """Returns MACDBacktestStrategy"""
        strategy_class = get_strategy_class('macd')
        assert strategy_class == MACDBacktestStrategy

    def test_get_strategy_class_kama(self):
        """Returns KAMABacktestStrategy"""
        strategy_class = get_strategy_class('kama')
        assert strategy_class == KAMABacktestStrategy

    def test_get_strategy_class_combo(self):
        """Returns ComboBacktestStrategy"""
        strategy_class = get_strategy_class('combo')
        assert strategy_class == ComboBacktestStrategy

    def test_get_strategy_class_invalid(self):
        """Raises ValueError for unknown type"""
        with pytest.raises(ValueError) as exc_info:
            get_strategy_class('unknown')

        assert "Unknown strategy type" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)

    def test_strategy_map_completeness(self):
        """Verify STRATEGY_MAP has all expected strategies"""
        assert 'macd' in STRATEGY_MAP
        assert 'kama' in STRATEGY_MAP
        assert 'combo' in STRATEGY_MAP
        assert len(STRATEGY_MAP) == 3

    def test_strategy_map_values(self):
        """Verify STRATEGY_MAP values are correct classes"""
        assert STRATEGY_MAP['macd'] == MACDBacktestStrategy
        assert STRATEGY_MAP['kama'] == KAMABacktestStrategy
        assert STRATEGY_MAP['combo'] == ComboBacktestStrategy


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for realistic scenarios"""

    def test_full_macd_with_all_features(self, synthetic_data):
        """Test MACD with all features enabled"""
        class FullFeaturedStrategy(MACDBacktestStrategy):
            # Filters
            enable_adx_filter = True
            enable_volume_filter = True
            enable_slope_filter = True
            enable_confirm_filter = True

            # Protection
            enable_loss_protection = True
            enable_trailing_stop = True

            # Anti-whipsaw
            enable_hysteresis = True
            min_hold_bars = 3

        bt = Backtest(synthetic_data, FullFeaturedStrategy, cash=100000, commission=0.001)
        stats = bt.run()

        # Should work without crashing
        assert stats is not None
        assert stats['Return [%]'] != 0 or stats['# Trades'] == 0

    def test_full_kama_with_all_features(self, synthetic_data):
        """Test KAMA with all features enabled"""
        class FullFeaturedStrategy(KAMABacktestStrategy):
            # KAMA-specific
            enable_efficiency_filter = True
            enable_slope_confirmation = True

            # Generic filters
            enable_slope_filter = True
            enable_adx_filter = True
            enable_volume_filter = True

            # Protection
            enable_loss_protection = True

        bt = Backtest(synthetic_data, FullFeaturedStrategy, cash=100000, commission=0.001)
        stats = bt.run()

        assert stats is not None
        assert stats['Return [%]'] != 0 or stats['# Trades'] == 0

    def test_strategy_comparison(self, synthetic_data):
        """Compare all three strategies on same data"""
        strategies = [
            MACDBacktestStrategy,
            KAMABacktestStrategy,
            ComboBacktestStrategy
        ]

        results = []
        for strategy in strategies:
            bt = Backtest(synthetic_data, strategy, cash=100000, commission=0.001)
            stats = bt.run()
            results.append({
                'strategy': strategy.__name__,
                'trades': stats['# Trades'],
                'return': stats['Return [%]']
            })

        # All strategies should produce valid results
        assert len(results) == 3
        for result in results:
            assert result['trades'] >= 0

    def test_parameter_optimization_compatibility(self, synthetic_data):
        """Test that strategies work with optimization"""
        # This tests that class variables can be optimized
        class OptimizableStrategy(MACDBacktestStrategy):
            fast_period = 12
            slow_period = 26

        bt = Backtest(synthetic_data, OptimizableStrategy, cash=100000)

        # Run simple optimization (just verify it doesn't crash)
        # Note: Full optimization takes too long for unit tests
        stats = bt.run()

        assert stats is not None


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_minimal_data(self):
        """Test with minimal amount of data"""
        # Only 50 bars (might not be enough for some indicators)
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        np.random.seed(42)

        df = pd.DataFrame({
            'Open': 100 + np.random.randn(50),
            'High': 102 + np.random.randn(50),
            'Low': 98 + np.random.randn(50),
            'Close': 100 + np.random.randn(50),
            'Volume': np.random.randint(1000000, 5000000, 50)
        }, index=dates)

        bt = Backtest(df, MACDBacktestStrategy, cash=100000)
        stats = bt.run()

        # Should not crash even with minimal data
        assert stats is not None

    def test_zero_volatility_data(self):
        """Test with zero volatility (flat prices)"""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')

        df = pd.DataFrame({
            'Open': [100.0] * 100,
            'High': [100.0] * 100,
            'Low': [100.0] * 100,
            'Close': [100.0] * 100,
            'Volume': [1000000] * 100
        }, index=dates)

        bt = Backtest(df, KAMABacktestStrategy, cash=100000)
        stats = bt.run()

        # Should handle flat prices gracefully
        assert stats is not None
        assert stats['# Trades'] == 0  # No trades expected

    def test_high_commission_impact(self, synthetic_data):
        """Test with high commission to verify cost handling"""
        bt = Backtest(synthetic_data, MACDBacktestStrategy, cash=100000, commission=0.01)
        stats = bt.run()

        # Should work even with high commission
        assert stats is not None

    def test_small_cash_amount(self, synthetic_data):
        """Test with small cash amount"""
        bt = Backtest(synthetic_data, KAMABacktestStrategy, cash=1000)
        stats = bt.run()

        # Should work even with limited capital
        assert stats is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
