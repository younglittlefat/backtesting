"""
Unit tests for portfolio management module.

Tests cover:
- Position creation and updates
- T+1 constraint handling
- Trade order generation and execution
- Portfolio state management
- Snapshot save/load functionality
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from portfolio import Position, TradeOrder, Portfolio


class TestPosition(unittest.TestCase):
    """Test Position class functionality."""

    def test_position_creation(self):
        """Test basic position creation."""
        pos = Position(
            symbol='159915.SZ',
            entry_date='2025-01-01',
            entry_price=1.5,
            shares=1000,
            cost=1505.0  # Including 5 RMB commission
        )

        self.assertEqual(pos.symbol, '159915.SZ')
        self.assertEqual(pos.shares, 1000)
        self.assertEqual(pos.entry_price, 1.5)
        self.assertEqual(pos.highest_price, 1.5)  # Initialized to entry price

    def test_position_update(self):
        """Test position price update."""
        pos = Position(
            symbol='159915.SZ',
            entry_date='2025-01-01',
            entry_price=1.5,
            shares=1000,
            cost=1500.0
        )

        # Update with higher price
        pos.update(1.6, '2025-01-02')
        self.assertEqual(pos.highest_price, 1.6)

        # Update with lower price (highest should not change)
        pos.update(1.4, '2025-01-03')
        self.assertEqual(pos.highest_price, 1.6)

    def test_t1_constraint(self):
        """Test T+1 selling constraint."""
        pos = Position(
            symbol='159915.SZ',
            entry_date='2025-01-01',
            entry_price=1.5,
            shares=1000,
            cost=1500.0
        )

        # Cannot sell on same day
        self.assertFalse(pos.can_sell('2025-01-01'))

        # Can sell on next day
        self.assertTrue(pos.can_sell('2025-01-02'))

        # Can sell on later days
        self.assertTrue(pos.can_sell('2025-01-10'))

    def test_pnl_calculation(self):
        """Test P&L calculation."""
        pos = Position(
            symbol='159915.SZ',
            entry_date='2025-01-01',
            entry_price=1.5,
            shares=1000,
            cost=1500.0
        )

        # Set current price
        pos.current_price = 1.6

        # Check P&L
        self.assertEqual(pos.market_value, 1600.0)
        self.assertEqual(pos.pnl, 100.0)
        self.assertAlmostEqual(pos.pnl_pct, 100.0 / 1500.0, places=4)

    def test_position_validation(self):
        """Test position data validation."""
        # Invalid shares (non-positive)
        with self.assertRaises(ValueError):
            Position(
                symbol='159915.SZ',
                entry_date='2025-01-01',
                entry_price=1.5,
                shares=-100,
                cost=1500.0
            )

        # Invalid price (non-positive)
        with self.assertRaises(ValueError):
            Position(
                symbol='159915.SZ',
                entry_date='2025-01-01',
                entry_price=-1.5,
                shares=1000,
                cost=1500.0
            )


class TestTradeOrder(unittest.TestCase):
    """Test TradeOrder class functionality."""

    def test_order_creation(self):
        """Test basic order creation."""
        order = TradeOrder(
            action='buy',
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            reason='signal_buy'
        )

        self.assertEqual(order.action, 'buy')
        self.assertEqual(order.symbol, '159915.SZ')
        self.assertEqual(order.shares, 1000)
        self.assertEqual(order.value, 1500.0)

    def test_order_validation(self):
        """Test order data validation."""
        # Invalid action
        with self.assertRaises(ValueError):
            TradeOrder(
                action='hold',
                symbol='159915.SZ',
                shares=1000,
                price=1.5,
                reason='test'
            )

        # Invalid shares
        with self.assertRaises(ValueError):
            TradeOrder(
                action='buy',
                symbol='159915.SZ',
                shares=-100,
                price=1.5,
                reason='test'
            )


class TestPortfolio(unittest.TestCase):
    """Test Portfolio class functionality."""

    def setUp(self):
        """Set up test portfolio."""
        self.portfolio = Portfolio(initial_cash=100000.0)

    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        self.assertEqual(self.portfolio.cash, 100000.0)
        self.assertEqual(len(self.portfolio.positions), 0)
        self.assertEqual(len(self.portfolio.trade_history), 0)

    def test_add_position(self):
        """Test adding a position."""
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        self.assertEqual(len(self.portfolio.positions), 1)
        self.assertEqual(self.portfolio.cash, 98500.0)  # 100000 - 1500

        pos = self.portfolio.get_position('159915.SZ')
        self.assertIsNotNone(pos)
        self.assertEqual(pos.shares, 1000)

    def test_add_position_with_costs(self):
        """Test adding position with transaction costs."""
        portfolio = Portfolio(
            initial_cash=100000.0,
            commission_rate=0.0003,
            min_commission=5.0
        )

        portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=True
        )

        # Cost = 1000 * 1.5 + max(1500 * 0.0003, 5) = 1500 + 5 = 1505
        expected_cash = 100000.0 - 1505.0
        self.assertAlmostEqual(portfolio.cash, expected_cash, places=2)

    def test_close_position(self):
        """Test closing a position."""
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        # Close position next day at higher price
        order = self.portfolio.close_position(
            symbol='159915.SZ',
            price=1.6,
            date='2025-01-02',
            reason='signal_sell',
            include_costs=False
        )

        self.assertEqual(order.action, 'sell')
        self.assertEqual(order.shares, 1000)
        self.assertEqual(len(self.portfolio.positions), 0)
        self.assertEqual(self.portfolio.cash, 100100.0)  # 98500 + 1600

    def test_t1_constraint_on_close(self):
        """Test T+1 constraint when closing position."""
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        # Try to close on same day (should fail)
        with self.assertRaises(ValueError):
            self.portfolio.close_position(
                symbol='159915.SZ',
                price=1.6,
                date='2025-01-01',
                reason='test',
                include_costs=False
            )

    def test_update_positions(self):
        """Test updating positions with current prices."""
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        self.portfolio.add_position(
            symbol='159916.SZ',
            shares=500,
            price=2.0,
            date='2025-01-01',
            include_costs=False
        )

        # Update prices
        prices = {
            '159915.SZ': 1.6,
            '159916.SZ': 2.1
        }
        self.portfolio.update_positions(prices, '2025-01-02')

        pos1 = self.portfolio.get_position('159915.SZ')
        pos2 = self.portfolio.get_position('159916.SZ')

        self.assertEqual(pos1.current_price, 1.6)
        self.assertEqual(pos2.current_price, 2.1)

    def test_get_total_equity(self):
        """Test total equity calculation."""
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        # Update price
        self.portfolio.update_positions({'159915.SZ': 1.6}, '2025-01-02')

        # Total equity = cash + positions value
        # Cash = 100000 - 1500 = 98500
        # Positions = 1000 * 1.6 = 1600
        # Total = 100100
        self.assertEqual(self.portfolio.get_total_equity(), 100100.0)

    def test_generate_orders_new_positions(self):
        """Test order generation for new positions."""
        target_positions = {
            '159915.SZ': {'shares': 1000, 'price': 1.5},
            '159916.SZ': {'shares': 500, 'price': 2.0}
        }

        current_prices = {
            '159915.SZ': 1.5,
            '159916.SZ': 2.0
        }

        orders = self.portfolio.generate_orders(
            target_positions=target_positions,
            current_date='2025-01-01',
            current_prices=current_prices
        )

        # Should generate 2 buy orders
        self.assertEqual(len(orders), 2)
        self.assertTrue(all(o.action == 'buy' for o in orders))

    def test_generate_orders_close_positions(self):
        """Test order generation for closing positions."""
        # Add positions
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        self.portfolio.add_position(
            symbol='159916.SZ',
            shares=500,
            price=2.0,
            date='2025-01-01',
            include_costs=False
        )

        # Target: keep only 159915.SZ
        target_positions = {
            '159915.SZ': {'shares': 1000, 'price': 1.5}
        }

        current_prices = {
            '159915.SZ': 1.5,
            '159916.SZ': 2.0
        }

        orders = self.portfolio.generate_orders(
            target_positions=target_positions,
            current_date='2025-01-02',  # Next day to satisfy T+1
            current_prices=current_prices
        )

        # Should generate 1 sell order for 159916.SZ
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].action, 'sell')
        self.assertEqual(orders[0].symbol, '159916.SZ')

    def test_apply_orders(self):
        """Test applying trade orders."""
        orders = [
            TradeOrder(
                action='buy',
                symbol='159915.SZ',
                shares=1000,
                price=1.5,
                reason='signal_buy'
            ),
            TradeOrder(
                action='buy',
                symbol='159916.SZ',
                shares=500,
                price=2.0,
                reason='signal_buy'
            )
        ]

        results = self.portfolio.apply_orders(
            orders=orders,
            execution_date='2025-01-01',
            include_costs=False
        )

        # Check all orders executed
        self.assertTrue(all(v == 'executed' for v in results.values()))
        self.assertEqual(len(self.portfolio.positions), 2)
        self.assertEqual(self.portfolio.cash, 97500.0)  # 100000 - 1500 - 1000

    def test_snapshot_save_load(self):
        """Test saving and loading portfolio snapshots."""
        # Create portfolio with positions
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        # Save snapshot
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            snapshot_path = f.name

        try:
            self.portfolio.save_snapshot(snapshot_path, '2025-01-01')

            # Create new portfolio and load snapshot
            new_portfolio = Portfolio()
            new_portfolio.load_snapshot(snapshot_path)

            # Verify state restored
            self.assertEqual(new_portfolio.cash, self.portfolio.cash)
            self.assertEqual(len(new_portfolio.positions), len(self.portfolio.positions))

            pos = new_portfolio.get_position('159915.SZ')
            self.assertIsNotNone(pos)
            self.assertEqual(pos.shares, 1000)
            self.assertEqual(pos.entry_price, 1.5)

        finally:
            # Cleanup
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)

    def test_equity_curve(self):
        """Test equity curve tracking."""
        # Add position and record equity
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        prices = {'159915.SZ': 1.5}
        self.portfolio.record_equity('2025-01-01', prices)

        # Update price and record
        prices = {'159915.SZ': 1.6}
        self.portfolio.record_equity('2025-01-02', prices)

        # Get equity history
        equity_df = self.portfolio.get_equity_history()

        self.assertEqual(len(equity_df), 2)
        self.assertIn('equity', equity_df.columns)
        self.assertIn('cash', equity_df.columns)

    def test_performance_stats(self):
        """Test performance statistics calculation."""
        # Add position with profit
        self.portfolio.add_position(
            symbol='159915.SZ',
            shares=1000,
            price=1.5,
            date='2025-01-01',
            include_costs=False
        )

        # Update to higher price
        self.portfolio.update_positions({'159915.SZ': 1.6}, '2025-01-02')

        stats = self.portfolio.get_performance_stats()

        self.assertIn('total_return_pct', stats)
        self.assertIn('total_equity', stats)
        self.assertIn('num_positions', stats)
        self.assertEqual(stats['num_positions'], 1)


if __name__ == '__main__':
    unittest.main()
