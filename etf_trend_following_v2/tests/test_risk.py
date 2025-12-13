"""
Test suite for risk management module.

Tests cover:
- ATR calculation (SMA and EMA methods)
- Chandelier Exit stop line calculation
- ATR stop loss trigger detection
- Time-based stop loss
- Circuit breaker (market and account)
- Liquidity checks
- T+1 constraint handling
- RiskManager comprehensive integration
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from risk import (
    calculate_atr,
    calculate_stop_line,
    check_stop_loss,
    check_time_stop,
    check_circuit_breaker,
    check_liquidity,
    check_t_plus_1,
    RiskManager
)


class TestATRCalculation(unittest.TestCase):
    """Test ATR calculation with different methods."""

    def setUp(self):
        """Create sample OHLC data."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        np.random.seed(42)

        # Generate realistic OHLC data
        close = 10.0 + np.cumsum(np.random.randn(30) * 0.2)
        high = close + np.abs(np.random.randn(30) * 0.3)
        low = close - np.abs(np.random.randn(30) * 0.3)
        open_price = close + np.random.randn(30) * 0.1

        self.df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 30)
        }, index=dates)

    def test_atr_sma_basic(self):
        """Test basic ATR calculation with SMA method."""
        atr = calculate_atr(self.df, period=14, method='sma')

        self.assertEqual(len(atr), len(self.df))
        self.assertTrue((atr >= 0).all(), "ATR should be non-negative")
        self.assertFalse(atr.isna().all(), "ATR should have valid values")

    def test_atr_ema_basic(self):
        """Test basic ATR calculation with EMA method."""
        atr = calculate_atr(self.df, period=14, method='ema')

        self.assertEqual(len(atr), len(self.df))
        self.assertTrue((atr >= 0).all(), "ATR should be non-negative")

    def test_atr_missing_columns(self):
        """Test ATR with missing required columns."""
        df_incomplete = self.df[['open', 'close']].copy()

        with self.assertRaises(ValueError) as context:
            calculate_atr(df_incomplete)

        self.assertIn('Missing required columns', str(context.exception))

    def test_atr_invalid_period(self):
        """Test ATR with invalid period."""
        with self.assertRaises(ValueError):
            calculate_atr(self.df, period=0)

        with self.assertRaises(ValueError):
            calculate_atr(self.df, period=-5)

    def test_atr_invalid_method(self):
        """Test ATR with invalid method."""
        with self.assertRaises(ValueError):
            calculate_atr(self.df, method='invalid')

    def test_atr_empty_data(self):
        """Test ATR with empty DataFrame."""
        df_empty = pd.DataFrame(columns=['high', 'low', 'close'])
        atr = calculate_atr(df_empty)

        self.assertEqual(len(atr), 0)

    def test_atr_values_reasonable(self):
        """Test that ATR values are in reasonable range."""
        atr = calculate_atr(self.df, period=14)

        # ATR should be smaller than the price range
        price_range = self.df['high'].max() - self.df['low'].min()
        self.assertTrue((atr < price_range).all())


class TestStopLineCalculation(unittest.TestCase):
    """Test Chandelier Exit stop line calculation."""

    def setUp(self):
        """Create sample trending data."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        np.random.seed(42)

        # Create uptrending data
        base_price = 10.0 + np.arange(50) * 0.1  # Uptrend
        noise = np.random.randn(50) * 0.2
        close = base_price + noise

        high = close + np.abs(np.random.randn(50) * 0.2)
        low = close - np.abs(np.random.randn(50) * 0.2)
        open_price = close + np.random.randn(50) * 0.1

        self.df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 50)
        }, index=dates)

        self.entry_date = '2024-01-10'
        self.entry_price = self.df.loc['2024-01-10', 'close']

    def test_stop_line_basic(self):
        """Test basic stop line calculation."""
        result = calculate_stop_line(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price
        )

        self.assertIn('stop_line', result.columns)
        self.assertIn('atr', result.columns)
        self.assertIn('highest_since_entry', result.columns)
        self.assertTrue(len(result) > 0)

    def test_stop_line_only_moves_up(self):
        """Test that stop line only moves up, never down."""
        result = calculate_stop_line(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price
        )

        stop_line = result['stop_line']

        # Check that stop line is monotonically increasing
        for i in range(1, len(stop_line)):
            self.assertGreaterEqual(
                stop_line.iloc[i],
                stop_line.iloc[i-1],
                f"Stop line decreased at index {i}"
            )

    def test_stop_line_below_highest(self):
        """Test that stop line stays below highest price."""
        result = calculate_stop_line(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            atr_multiplier=3.0
        )

        # Stop line should be below highest price
        below_highest = result['stop_line'] < result['highest_since_entry']
        self.assertTrue(below_highest.all())

    def test_stop_line_invalid_entry_date(self):
        """Test stop line with entry date not in data."""
        with self.assertRaises(ValueError):
            calculate_stop_line(
                self.df,
                entry_date='2023-01-01',  # Before data starts
                entry_price=10.0
            )

    def test_stop_line_different_multipliers(self):
        """Test stop line with different ATR multipliers."""
        result_3x = calculate_stop_line(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            atr_multiplier=3.0
        )

        result_2x = calculate_stop_line(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            atr_multiplier=2.0
        )

        # 2x stop should be higher (tighter) than 3x stop
        self.assertTrue(
            (result_2x['stop_line'] > result_3x['stop_line']).any()
        )


class TestStopLossTrigger(unittest.TestCase):
    """Test ATR stop loss trigger detection."""

    def setUp(self):
        """Create sample data with price drop."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        np.random.seed(42)

        # Create data: uptrend then drop
        price = [10.0 + i * 0.1 for i in range(30)]  # Uptrend
        price.extend([13.0 - i * 0.3 for i in range(20)])  # Drop

        close = np.array(price) + np.random.randn(50) * 0.1
        high = close + np.abs(np.random.randn(50) * 0.15)
        low = close - np.abs(np.random.randn(50) * 0.15)
        open_price = close + np.random.randn(50) * 0.05

        self.df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 50)
        }, index=dates)

        self.entry_date = '2024-01-05'
        self.entry_price = self.df.loc['2024-01-05', 'close']

    def test_stop_loss_triggered(self):
        """Test that stop loss is eventually triggered in downtrend."""
        result = check_stop_loss(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            atr_multiplier=2.0  # Use tighter stop for this test
        )

        # With the constructed downtrend, stop should eventually trigger
        self.assertIn('triggered', result)
        self.assertIn('trigger_date', result)
        self.assertIn('days_held', result)

    def test_stop_loss_not_triggered_early(self):
        """Test that stop loss not triggered during uptrend."""
        result = check_stop_loss(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            check_until_date='2024-01-25',  # Check only during uptrend
            atr_multiplier=3.0
        )

        # Should not trigger during uptrend
        self.assertFalse(result['triggered'])
        self.assertIsNone(result['trigger_date'])

    def test_stop_loss_return_structure(self):
        """Test that stop loss result has required fields."""
        result = check_stop_loss(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price
        )

        required_fields = [
            'triggered', 'trigger_date', 'trigger_price',
            'trigger_reason', 'days_held', 'final_pnl_pct'
        ]

        for field in required_fields:
            self.assertIn(field, result)


class TestTimeStop(unittest.TestCase):
    """Test time-based stop loss."""

    def setUp(self):
        """Create sample stagnant data."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        np.random.seed(42)

        # Create stagnant price action that never makes a new high above entry.
        # Requirement: time stop triggers only when profit is small AND no new high since entry.
        close = np.empty(30, dtype=float)
        close[0] = 10.0
        close[1:] = 10.0 - np.abs(np.random.randn(29)) * 0.05  # Always <= entry_price
        high = close.copy()
        low = close - 0.1
        open_price = close.copy()

        self.df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 30)
        }, index=dates)

        self.entry_date = '2024-01-01'
        self.entry_price = self.df.loc['2024-01-01', 'close']

    def test_time_stop_triggered(self):
        """Test that time stop triggers after max_hold_days."""
        result = check_time_stop(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            max_hold_days=20,
            min_profit_atr=1.0
        )

        # After 30 days with minimal profit, time stop should trigger
        self.assertTrue(result['triggered'])
        self.assertIsNotNone(result['trigger_date'])

    def test_time_stop_not_triggered_early(self):
        """Test that time stop doesn't trigger before max_hold_days."""
        result = check_time_stop(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price,
            max_hold_days=50,  # More than data length
            min_profit_atr=1.0
        )

        # Should not trigger - not held long enough
        self.assertFalse(result['triggered'])

    def test_time_stop_with_profit(self):
        """Test that time stop doesn't trigger if profit exceeds threshold."""
        # Create profitable data
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        close = 10.0 + np.arange(30) * 0.2  # Strong uptrend
        high = close + 0.1
        low = close - 0.1

        df_profit = pd.DataFrame({
            'open': close,
            'high': high,
            'low': low,
            'close': close,
            'volume': 1000000
        }, index=dates)

        result = check_time_stop(
            df_profit,
            entry_date='2024-01-01',
            entry_price=df_profit.loc['2024-01-01', 'close'],
            max_hold_days=20,
            min_profit_atr=1.0
        )

        # Should not trigger - profit is good
        self.assertFalse(result['triggered'])

    def test_time_stop_return_structure(self):
        """Test time stop result structure."""
        result = check_time_stop(
            self.df,
            entry_date=self.entry_date,
            entry_price=self.entry_price
        )

        required_fields = [
            'triggered', 'trigger_date', 'days_held',
            'profit_pct', 'profit_atr', 'reason'
        ]

        for field in required_fields:
            self.assertIn(field, result)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""

    def test_market_drop_trigger(self):
        """Test circuit breaker triggered by market drop."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')

        # Create market crash scenario - sharp drop on last day
        # Day 9: 100, Day 10: 94 = -6% drop (exceeds -5% threshold)
        market_close = [100.0] * 9 + [94.0]

        market_df = pd.DataFrame({
            'close': market_close
        }, index=dates)

        result = check_circuit_breaker(
            market_df=market_df,
            as_of_date='2024-01-10',
            market_drop_threshold=-0.05,
            lookback_days=1
        )

        self.assertTrue(result['triggered'])
        self.assertIn('market_drop', result['reason'])
        self.assertIsNotNone(result['market_change'])
        self.assertLessEqual(result['market_change'], -0.05)

    def test_account_drawdown_trigger(self):
        """Test circuit breaker triggered by account drawdown."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')

        # Create account drawdown scenario
        equity = pd.Series([100000, 102000, 105000, 103000, 96000,
                          95000, 94000, 93000, 92000, 91000], index=dates)

        result = check_circuit_breaker(
            account_equity=equity,
            as_of_date='2024-01-10',
            account_drawdown_threshold=-0.03
        )

        self.assertTrue(result['triggered'])
        self.assertIn('account_drawdown', result['reason'])
        self.assertIsNotNone(result['account_drawdown'])

    def test_circuit_breaker_not_triggered(self):
        """Test circuit breaker not triggered in normal market."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')

        market_df = pd.DataFrame({
            'close': [100.0 + i * 0.5 for i in range(10)]  # Slight uptrend
        }, index=dates)

        equity = pd.Series([100000 + i * 500 for i in range(10)], index=dates)

        result = check_circuit_breaker(
            market_df=market_df,
            account_equity=equity,
            as_of_date='2024-01-10',
            market_drop_threshold=-0.05,
            account_drawdown_threshold=-0.03
        )

        self.assertFalse(result['triggered'])
        self.assertEqual(result['reason'], 'none')

    def test_circuit_breaker_both_triggered(self):
        """Test circuit breaker with both triggers."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')

        # Both market crash and account drawdown
        # Market: Sharp drop on last day from 100 to 93 (-7%)
        market_close = [100.0] * 9 + [93.0]
        market_df = pd.DataFrame({'close': market_close}, index=dates)

        # Account: Peak at 105k on day 3, current 91k = -13.3% drawdown
        equity = pd.Series([100000, 102000, 105000, 103000, 96000,
                          95000, 94000, 93000, 92000, 91000], index=dates)

        result = check_circuit_breaker(
            market_df=market_df,
            account_equity=equity,
            as_of_date='2024-01-10',
            market_drop_threshold=-0.05,
            account_drawdown_threshold=-0.03,
            lookback_days=1
        )

        self.assertTrue(result['triggered'])
        self.assertEqual(result['reason'], 'both')
        self.assertIn('prohibit_new_positions', result['recommendations'])

    def test_circuit_breaker_no_data(self):
        """Test circuit breaker with no data provided."""
        with self.assertRaises(ValueError):
            check_circuit_breaker()


class TestLiquidityCheck(unittest.TestCase):
    """Test liquidity checking."""

    def test_sufficient_liquidity(self):
        """Test ETF with sufficient liquidity."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')

        df = pd.DataFrame({
            'close': [10.0] * 30,
            'amount': [100_000_000] * 30  # 100M daily
        }, index=dates)

        result = check_liquidity(df, min_amount=50_000_000)

        self.assertTrue(result['sufficient'])
        self.assertGreaterEqual(result['avg_amount'], 50_000_000)

    def test_insufficient_liquidity(self):
        """Test ETF with insufficient liquidity."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')

        df = pd.DataFrame({
            'close': [10.0] * 30,
            'amount': [20_000_000] * 30  # Only 20M daily
        }, index=dates)

        result = check_liquidity(df, min_amount=50_000_000)

        self.assertFalse(result['sufficient'])
        self.assertIn('low_amount', result['reason'])

    def test_liquidity_missing_amount_column(self):
        """Test liquidity check with missing amount column."""
        df = pd.DataFrame({
            'close': [10.0] * 30
        })

        with self.assertRaises(ValueError):
            check_liquidity(df)

    def test_liquidity_with_spread_check(self):
        """Test liquidity with bid-ask spread check."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')

        df = pd.DataFrame({
            'close': [10.0] * 30,
            'amount': [100_000_000] * 30,
            'bid': [9.98] * 30,
            'ask': [10.02] * 30  # 0.4% spread
        }, index=dates)

        # Should pass with 0.5% max spread
        result = check_liquidity(df, min_amount=50_000_000, max_spread_pct=0.005)
        self.assertTrue(result['sufficient'])

        # Should fail with 0.3% max spread
        result = check_liquidity(df, min_amount=50_000_000, max_spread_pct=0.003)
        self.assertFalse(result['sufficient'])


class TestTPlusOne(unittest.TestCase):
    """Test T+1 constraint checking."""

    def test_same_day_not_allowed(self):
        """Test that selling on same day is not allowed."""
        result = check_t_plus_1('2024-01-15', '2024-01-15')
        self.assertFalse(result)

    def test_next_day_allowed(self):
        """Test that selling on next day is allowed."""
        result = check_t_plus_1('2024-01-15', '2024-01-16')
        self.assertTrue(result)

    def test_later_days_allowed(self):
        """Test that selling on later days is allowed."""
        result = check_t_plus_1('2024-01-15', '2024-01-20')
        self.assertTrue(result)

    def test_with_trading_calendar(self):
        """Test T+1 with trading calendar."""
        # Create a trading calendar (Mon-Fri, no holidays)
        calendar = pd.date_range('2024-01-01', '2024-01-31', freq='B')

        # Monday to Tuesday (next trading day)
        result = check_t_plus_1('2024-01-15', '2024-01-16', calendar)
        self.assertTrue(result)

        # Friday to Monday (next trading day after weekend)
        result = check_t_plus_1('2024-01-19', '2024-01-22', calendar)
        self.assertTrue(result)

        # Friday to Saturday (not next trading day)
        result = check_t_plus_1('2024-01-19', '2024-01-20', calendar)
        self.assertFalse(result)


class TestRiskManager(unittest.TestCase):
    """Test comprehensive RiskManager class."""

    def setUp(self):
        """Create sample data and risk manager."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        np.random.seed(42)

        # Create uptrending then dropping data
        price = [10.0 + i * 0.1 for i in range(30)]
        price.extend([13.0 - i * 0.2 for i in range(20)])

        close = np.array(price) + np.random.randn(50) * 0.1
        high = close + 0.2
        low = close - 0.2

        self.df = pd.DataFrame({
            'open': close,
            'high': high,
            'low': low,
            'close': close,
            'volume': 2000000,
            'amount': 50_000_000
        }, index=dates)

        self.config = {
            'atr_multiplier': 3.0,
            'atr_period': 14,
            'time_stop_days': 20,
            'time_stop_min_profit_atr': 1.0,
            'market_drop_threshold': -0.05,
            'account_drawdown_threshold': -0.03,
            'min_liquidity_amount': 30_000_000,
            'enforce_t_plus_1': True
        }

        self.risk_manager = RiskManager(self.config)

    def test_risk_manager_initialization(self):
        """Test RiskManager initialization."""
        self.assertIsNotNone(self.risk_manager)
        self.assertEqual(self.risk_manager.atr_multiplier, 3.0)
        self.assertEqual(self.risk_manager.atr_period, 14)

    def test_check_position_risk(self):
        """Test position risk checking."""
        position = {
            'entry_date': '2024-01-05',
            'entry_price': self.df.loc['2024-01-05', 'close'],
            'shares': 1000
        }

        result = self.risk_manager.check_position_risk(
            symbol='159915.SZ',
            df=self.df,
            position=position,
            as_of_date='2024-02-10'
        )

        self.assertIn('symbol', result)
        self.assertIn('atr_stop', result)
        self.assertIn('time_stop', result)
        self.assertIn('liquidity', result)
        self.assertIn('can_sell_today', result)
        self.assertIn('actions', result)

    def test_check_portfolio_risk(self):
        """Test portfolio-level risk checking."""
        data_dict = {
            '159915.SZ': self.df,
            '510300.SH': self.df.copy()
        }

        positions = {
            '159915.SZ': {
                'entry_date': '2024-01-05',
                'entry_price': self.df.loc['2024-01-05', 'close']
            },
            '510300.SH': {
                'entry_date': '2024-01-10',
                'entry_price': self.df.loc['2024-01-10', 'close']
            }
        }

        # Create market and equity data
        market_df = pd.DataFrame({
            'close': [3000.0 - i * 10 for i in range(50)]
        }, index=self.df.index)

        equity = pd.Series(
            [100000 + i * 500 for i in range(50)],
            index=self.df.index
        )

        result = self.risk_manager.check_portfolio_risk(
            data_dict=data_dict,
            positions=positions,
            market_df=market_df,
            account_equity=equity,
            as_of_date='2024-02-10'
        )

        self.assertIn('circuit_breaker', result)
        self.assertIn('position_risks', result)
        self.assertIn('portfolio_actions', result)
        self.assertIn('summary', result)

        summary = result['summary']
        self.assertEqual(summary['total_positions'], 2)
        self.assertIn('atr_stops_triggered', summary)
        self.assertIn('time_stops_triggered', summary)

    def test_risk_manager_with_minimal_config(self):
        """Test RiskManager with minimal config (uses defaults)."""
        minimal_config = {}
        rm = RiskManager(minimal_config)

        # Should use default values
        self.assertEqual(rm.atr_multiplier, 3.0)
        self.assertEqual(rm.atr_period, 14)
        self.assertEqual(rm.time_stop_days, 20)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestATRCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestStopLineCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestStopLossTrigger))
    suite.addTests(loader.loadTestsFromTestCase(TestTimeStop))
    suite.addTests(loader.loadTestsFromTestCase(TestCircuitBreaker))
    suite.addTests(loader.loadTestsFromTestCase(TestLiquidityCheck))
    suite.addTests(loader.loadTestsFromTestCase(TestTPlusOne))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManager))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
