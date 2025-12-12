"""
Portfolio Management Module - Usage Examples

This example demonstrates the key features of the portfolio management module.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from portfolio import Position, TradeOrder, Portfolio
import pandas as pd


def example_basic_portfolio_operations():
    """Example 1: Basic portfolio operations."""
    print("=" * 60)
    print("Example 1: Basic Portfolio Operations")
    print("=" * 60)

    # Initialize portfolio with 1 million RMB
    portfolio = Portfolio(
        initial_cash=1_000_000,
        commission_rate=0.0003,  # 0.03% commission for ETFs
        stamp_duty_rate=0.0,     # No stamp duty for ETFs
        min_commission=5.0       # Minimum 5 RMB per trade
    )

    print(f"\nInitial state: {portfolio}")

    # Buy first ETF
    portfolio.add_position(
        symbol='159915.SZ',  # 创业板ETF
        shares=10000,
        price=1.50,
        date='2025-01-02',
        include_costs=True
    )

    print(f"\nAfter buying 159915.SZ: {portfolio}")
    print(f"Cash remaining: {portfolio.cash:.2f}")

    # Buy second ETF
    portfolio.add_position(
        symbol='512880.SH',  # 证券ETF
        shares=5000,
        price=2.00,
        date='2025-01-02',
        include_costs=True
    )

    print(f"\nAfter buying 512880.SH: {portfolio}")

    # Display holdings summary
    print("\nCurrent Holdings:")
    print(portfolio.get_holdings_summary().to_string())


def example_price_updates_and_pnl():
    """Example 2: Price updates and P&L tracking."""
    print("\n" + "=" * 60)
    print("Example 2: Price Updates and P&L Tracking")
    print("=" * 60)

    portfolio = Portfolio(initial_cash=1_000_000)

    # Open positions
    portfolio.add_position('159915.SZ', 10000, 1.50, '2025-01-02', include_costs=False)
    portfolio.add_position('512880.SH', 5000, 2.00, '2025-01-02', include_costs=False)

    print("\nDay 1 - Entry:")
    print(portfolio.get_holdings_summary()[['symbol', 'shares', 'entry_price', 'market_value', 'pnl']].to_string())

    # Day 2: Prices go up
    prices_day2 = {
        '159915.SZ': 1.55,
        '512880.SH': 2.10
    }
    portfolio.update_positions(prices_day2, '2025-01-03')
    portfolio.record_equity('2025-01-03', prices_day2)

    print("\nDay 2 - Prices up:")
    print(portfolio.get_holdings_summary()[['symbol', 'current_price', 'market_value', 'pnl', 'pnl_pct']].to_string())

    # Day 3: Prices mixed
    prices_day3 = {
        '159915.SZ': 1.60,
        '512880.SH': 1.95
    }
    portfolio.update_positions(prices_day3, '2025-01-04')
    portfolio.record_equity('2025-01-04', prices_day3)

    print("\nDay 3 - Prices mixed:")
    print(portfolio.get_holdings_summary()[['symbol', 'current_price', 'market_value', 'pnl', 'pnl_pct']].to_string())

    # Show performance stats
    print("\nPerformance Summary:")
    stats = portfolio.get_performance_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def example_t1_constraint_and_trading():
    """Example 3: T+1 constraint and order execution."""
    print("\n" + "=" * 60)
    print("Example 3: T+1 Constraint and Trading")
    print("=" * 60)

    portfolio = Portfolio(initial_cash=1_000_000)

    # Day 1: Buy position
    portfolio.add_position('159915.SZ', 10000, 1.50, '2025-01-02', include_costs=False)
    print(f"\nDay 1 (2025-01-02): Bought 159915.SZ")
    print(f"Cash: {portfolio.cash:.2f}")

    # Day 1: Try to sell same day (will fail)
    try:
        portfolio.close_position('159915.SZ', 1.55, '2025-01-02', 'test_sell', include_costs=False)
        print("ERROR: Should not be able to sell on same day!")
    except ValueError as e:
        print(f"✓ T+1 constraint enforced: {e}")

    # Day 2: Can sell now
    order = portfolio.close_position('159915.SZ', 1.55, '2025-01-03', 'signal_sell', include_costs=False)
    print(f"\nDay 2 (2025-01-03): Sold 159915.SZ")
    print(f"Sell order: {order.action} {order.shares} shares @ {order.price}")
    print(f"Cash after sell: {portfolio.cash:.2f}")
    print(f"Profit: {portfolio.cash - 1_000_000:.2f}")


def example_order_generation_and_rebalancing():
    """Example 4: Order generation for rebalancing."""
    print("\n" + "=" * 60)
    print("Example 4: Order Generation and Rebalancing")
    print("=" * 60)

    portfolio = Portfolio(initial_cash=1_000_000)

    # Initial positions
    portfolio.add_position('159915.SZ', 10000, 1.50, '2025-01-02', include_costs=False)
    portfolio.add_position('512880.SH', 5000, 2.00, '2025-01-02', include_costs=False)
    portfolio.add_position('515050.SH', 8000, 1.25, '2025-01-02', include_costs=False)

    print("\nInitial Holdings:")
    print(portfolio.get_holdings_summary()[['symbol', 'shares', 'market_value']].to_string())

    # Define new target positions (next day)
    # - Keep 159915.SZ but reduce shares
    # - Close 512880.SH
    # - Increase 515050.SH
    # - Add new 159949.SZ
    target_positions = {
        '159915.SZ': {'shares': 8000, 'price': 1.52},
        '515050.SH': {'shares': 10000, 'price': 1.28},
        '159949.SZ': {'shares': 6000, 'price': 1.80}
    }

    current_prices = {
        '159915.SZ': 1.52,
        '512880.SH': 2.05,
        '515050.SH': 1.28,
        '159949.SZ': 1.80
    }

    # Generate rebalancing orders
    orders = portfolio.generate_orders(
        target_positions=target_positions,
        current_date='2025-01-03',  # Next day for T+1
        current_prices=current_prices,
        sell_reasons={'512880.SH': 'rank_out'}
    )

    print("\nRebalancing Orders Generated:")
    for i, order in enumerate(orders, 1):
        print(f"  {i}. {order.action.upper()} {order.shares} shares of {order.symbol} @ {order.price:.2f} ({order.reason})")

    # Execute orders
    results = portfolio.apply_orders(orders, '2025-01-03', current_prices, include_costs=False)

    print("\nOrder Execution Results:")
    for idx, status in results.items():
        order = orders[idx]
        print(f"  Order {idx}: {order.symbol} - {status}")

    print("\nFinal Holdings:")
    print(portfolio.get_holdings_summary()[['symbol', 'shares', 'market_value']].to_string())


def example_snapshot_persistence():
    """Example 5: Portfolio snapshot save/load."""
    print("\n" + "=" * 60)
    print("Example 5: Portfolio Snapshot Save/Load")
    print("=" * 60)

    # Create portfolio with positions
    portfolio = Portfolio(initial_cash=1_000_000)
    portfolio.add_position('159915.SZ', 10000, 1.50, '2025-01-02', include_costs=False)
    portfolio.add_position('512880.SH', 5000, 2.00, '2025-01-02', include_costs=False)

    print("\nOriginal Portfolio:")
    print(f"  Cash: {portfolio.cash:.2f}")
    print(f"  Positions: {len(portfolio.positions)}")
    print(f"  Total Equity: {portfolio.get_total_equity():.2f}")

    # Save snapshot
    snapshot_path = '/tmp/portfolio_snapshot.json'
    portfolio.save_snapshot(snapshot_path, '2025-01-02')
    print(f"\n✓ Snapshot saved to: {snapshot_path}")

    # Create new portfolio and load snapshot
    new_portfolio = Portfolio()
    new_portfolio.load_snapshot(snapshot_path)

    print("\nRestored Portfolio:")
    print(f"  Cash: {new_portfolio.cash:.2f}")
    print(f"  Positions: {len(new_portfolio.positions)}")
    print(f"  Total Equity: {new_portfolio.get_total_equity():.2f}")

    print("\nRestored Holdings:")
    print(new_portfolio.get_holdings_summary()[['symbol', 'shares', 'entry_price', 'cost']].to_string())


def example_equity_curve_tracking():
    """Example 6: Equity curve and performance tracking."""
    print("\n" + "=" * 60)
    print("Example 6: Equity Curve Tracking")
    print("=" * 60)

    portfolio = Portfolio(initial_cash=1_000_000)

    # Simulate a trading period
    trades = [
        # Day 1: Buy positions
        ('2025-01-02', {'159915.SZ': (10000, 1.50), '512880.SH': (5000, 2.00)}, 'buy'),
        # Day 2: Prices change
        ('2025-01-03', {'159915.SZ': 1.55, '512880.SH': 2.10}, 'update'),
        # Day 3: More price changes
        ('2025-01-04', {'159915.SZ': 1.60, '512880.SH': 2.05}, 'update'),
        # Day 4: Sell one position
        ('2025-01-05', {'159915.SZ': 1.58}, 'sell_512880'),
    ]

    for date, data, action in trades:
        if action == 'buy':
            for symbol, (shares, price) in data.items():
                portfolio.add_position(symbol, shares, price, date, include_costs=False)
            prices = {k: v[1] for k, v in data.items()}
            portfolio.record_equity(date, prices)

        elif action == 'update':
            portfolio.update_positions(data, date)
            portfolio.record_equity(date, data)

        elif action == 'sell_512880':
            portfolio.close_position('512880.SH', 2.05, date, 'signal_sell', include_costs=False)
            portfolio.update_positions(data, date)
            portfolio.record_equity(date, {**data, '512880.SH': 2.05})

    # Show equity curve
    print("\nEquity Curve:")
    equity_df = portfolio.get_equity_history()
    print(equity_df[['equity', 'cash', 'positions_value', 'num_positions']].to_string())

    # Show trade history
    print("\nTrade History:")
    trades_df = portfolio.get_trade_history()
    if not trades_df.empty:
        print(trades_df[['action', 'symbol', 'shares', 'price', 'value', 'reason']].to_string())


def main():
    """Run all examples."""
    examples = [
        example_basic_portfolio_operations,
        example_price_updates_and_pnl,
        example_t1_constraint_and_trading,
        example_order_generation_and_rebalancing,
        example_snapshot_persistence,
        example_equity_curve_tracking,
    ]

    for example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\nError in {example_func.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
