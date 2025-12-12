# Portfolio Management Module

## Overview

The `portfolio.py` module provides comprehensive portfolio management functionality for the ETF Trend Following v2 system. It handles position tracking, T+1 trading constraints, order generation, transaction costs, and portfolio analytics.

## Key Features

- **Position Management**: Track holdings with entry prices, shares, costs, and P&L
- **T+1 Constraint**: Enforces Chinese market rule (cannot sell on purchase date)
- **Trade Orders**: Generate and execute buy/sell orders with configurable execution
- **Transaction Costs**: Built-in commission and stamp duty calculations
- **Portfolio Analytics**: Equity curves, performance stats, holdings summaries
- **State Persistence**: Save/load portfolio snapshots for recovery and analysis

## Core Classes

### Position

Represents a single position in the portfolio.

```python
from portfolio import Position

pos = Position(
    symbol='159915.SZ',
    entry_date='2025-01-02',
    entry_price=1.50,
    shares=10000,
    cost=15005.0  # Including transaction costs
)

# Update with current price
pos.update(current_price=1.60, current_date='2025-01-03')

# Check T+1 constraint
can_sell = pos.can_sell('2025-01-03')  # True (next day)

# Access computed properties
print(f"Market Value: {pos.market_value}")
print(f"P&L: {pos.pnl} ({pos.pnl_pct:.2%})")
print(f"Days Held: {pos.days_held}")
```

### TradeOrder

Represents a trade order to be executed.

```python
from portfolio import TradeOrder

order = TradeOrder(
    action='buy',      # 'buy' or 'sell'
    symbol='159915.SZ',
    shares=10000,
    price=1.50,
    reason='signal_buy'  # Reason for trade
)

print(f"Order Value: {order.value}")
```

### Portfolio

Main portfolio manager class.

```python
from portfolio import Portfolio

# Initialize with cash and cost parameters
portfolio = Portfolio(
    initial_cash=1_000_000,
    commission_rate=0.0003,   # 0.03% for ETFs
    stamp_duty_rate=0.0,      # 0% for ETFs (0.1% for stocks)
    min_commission=5.0        # Minimum 5 RMB
)

# Add position
portfolio.add_position(
    symbol='159915.SZ',
    shares=10000,
    price=1.50,
    date='2025-01-02',
    include_costs=True
)

# Update positions with current prices
prices = {'159915.SZ': 1.60}
portfolio.update_positions(prices, '2025-01-03')

# Get total equity (cash + positions)
total_equity = portfolio.get_total_equity()

# View holdings
holdings_df = portfolio.get_holdings_summary()
print(holdings_df)
```

## Typical Workflows

### 1. Rebalancing Workflow

```python
# Define target positions
target_positions = {
    '159915.SZ': {'shares': 8000, 'price': 1.52},
    '512880.SH': {'shares': 5000, 'price': 2.05}
}

current_prices = {
    '159915.SZ': 1.52,
    '512880.SH': 2.05,
    '515050.SH': 1.28  # Will be closed
}

# Generate rebalancing orders (respects T+1)
orders = portfolio.generate_orders(
    target_positions=target_positions,
    current_date='2025-01-03',
    current_prices=current_prices,
    sell_reasons={'515050.SH': 'rank_out'}
)

# Execute orders
results = portfolio.apply_orders(
    orders=orders,
    execution_date='2025-01-03',
    execution_prices=current_prices  # Optional: override prices
)

# Check results
for idx, status in results.items():
    print(f"Order {idx}: {status}")
```

### 2. Position Closing with T+1

```python
# Day 1: Buy position
portfolio.add_position('159915.SZ', 10000, 1.50, '2025-01-02')

# Day 1: Cannot sell (T+1 constraint)
try:
    portfolio.close_position('159915.SZ', 1.55, '2025-01-02', 'test')
except ValueError as e:
    print(f"Expected: {e}")  # T+1 constraint

# Day 2: Can sell now
order = portfolio.close_position(
    symbol='159915.SZ',
    price=1.55,
    date='2025-01-03',
    reason='signal_sell'
)
```

### 3. Portfolio Snapshots

```python
# Save portfolio state
portfolio.save_snapshot(
    path='positions/snapshot_2025-01-03.json',
    date='2025-01-03'
)

# Load portfolio state (for recovery or analysis)
new_portfolio = Portfolio()
new_portfolio.load_snapshot('positions/snapshot_2025-01-03.json')
```

### 4. Equity Curve Tracking

```python
# Record daily equity snapshots
for date, prices in daily_data.items():
    portfolio.update_positions(prices, date)
    portfolio.record_equity(date, prices)

# Get equity curve as DataFrame
equity_df = portfolio.get_equity_history()
print(equity_df[['equity', 'cash', 'positions_value', 'num_positions']])

# Calculate performance stats
stats = portfolio.get_performance_stats()
print(f"Total Return: {stats['total_return_pct']:.2f}%")
print(f"Number of Trades: {stats['num_trades']}")
```

## T+1 Constraint Details

The Chinese stock market enforces a T+1 trading rule:
- Stocks/ETFs bought on day T **cannot** be sold until day T+1
- The module automatically checks this constraint when:
  - Closing positions via `close_position()`
  - Generating orders via `generate_orders()`
  - Executing orders via `apply_orders()`

If a sell order violates T+1, it will:
- Raise `ValueError` in `close_position()`
- Skip the order in `generate_orders()` (retry next day)
- Mark as failed in `apply_orders()` results

## Transaction Costs

The module supports configurable transaction costs:

| Parameter | ETF Default | Stock Default | Description |
|-----------|-------------|---------------|-------------|
| `commission_rate` | 0.0003 (0.03%) | 0.0003 | Broker commission rate |
| `stamp_duty_rate` | 0.0 | 0.001 (0.1%) | Stamp duty (sell only) |
| `min_commission` | 5.0 RMB | 5.0 RMB | Minimum per trade |

**Buy cost calculation:**
```
cost = shares * price + max(shares * price * commission_rate, min_commission)
```

**Sell proceeds calculation:**
```
proceeds = shares * price
commission = max(proceeds * commission_rate, min_commission)
stamp_duty = proceeds * stamp_duty_rate  (stocks only)
net_proceeds = proceeds - commission - stamp_duty
```

## Data Structures

### Position Dict Format
```python
{
    'symbol': '159915.SZ',
    'entry_date': '2025-01-02',
    'entry_price': 1.50,
    'shares': 10000,
    'cost': 15005.0,
    'current_price': 1.60,
    'market_value': 16000.0,
    'pnl': 995.0,
    'pnl_pct': 6.63,  # Percentage
    'days_held': 10,
    'highest_price': 1.65,
    'stop_line': 1.45
}
```

### Trade Order Dict Format
```python
{
    'action': 'buy',
    'symbol': '159915.SZ',
    'shares': 10000,
    'price': 1.50,
    'reason': 'signal_buy',
    'timestamp': '2025-01-02T15:30:00',
    'value': 15000.0
}
```

### Holdings Summary DataFrame
```
      symbol  shares  entry_date  entry_price  current_price  market_value     cost     pnl  pnl_pct  days_held  highest_price  stop_line
0  159915.SZ   10000  2025-01-02         1.50           1.60       16000.0  15005.0   995.0     6.63         10           1.65       1.45
1  512880.SH    5000  2025-01-02         2.00           2.10       10500.0  10005.0   495.0     4.95         10           2.15       1.90
```

## Testing

Comprehensive unit tests are provided in `tests/test_portfolio.py`:

```bash
# Run all portfolio tests
pytest tests/test_portfolio.py -v

# Run specific test
pytest tests/test_portfolio.py::TestPortfolio::test_t1_constraint_on_close -v
```

Test coverage includes:
- Position creation, updates, and P&L calculation
- T+1 constraint enforcement
- Order generation and execution
- Transaction cost calculations
- Portfolio snapshots
- Equity curve tracking

## Examples

See `examples/portfolio_example.py` for comprehensive usage examples:

```bash
python examples/portfolio_example.py
```

Examples cover:
1. Basic portfolio operations
2. Price updates and P&L tracking
3. T+1 constraint handling
4. Order generation and rebalancing
5. Snapshot save/load
6. Equity curve tracking

## Integration with ETF Trend Following v2

The portfolio module integrates with other system components:

- **Data Loader**: Receives price data for position updates
- **Signal Pipeline**: Receives target positions from strategy signals
- **Risk Module**: Provides stop loss levels for position tracking
- **Position Sizing**: Receives optimal share allocations
- **Backtest Runner**: Uses portfolio for historical simulation

## Error Handling

Common errors and handling:

```python
# Insufficient cash
try:
    portfolio.add_position('159915.SZ', 1000000, 1.50, '2025-01-02')
except ValueError as e:
    print(f"Insufficient cash: {e}")

# T+1 violation
try:
    portfolio.close_position('159915.SZ', 1.55, '2025-01-02', 'test')
except ValueError as e:
    print(f"Cannot sell: {e}")

# Invalid position
try:
    portfolio.close_position('INVALID.SZ', 1.50, '2025-01-02', 'test')
except ValueError as e:
    print(f"Position not found: {e}")
```

## Performance Considerations

- Position updates are O(n) where n = number of positions
- Order generation is O(n + m) where m = number of target positions
- Holdings summary creates a new DataFrame (avoid in tight loops)
- Snapshot I/O is file-based (async recommended for production)

## Future Enhancements

Potential improvements:
- [ ] Async snapshot I/O
- [ ] Position-level stop loss tracking
- [ ] Partial position closing with FIFO/LIFO
- [ ] Multi-account support
- [ ] Margin trading support
- [ ] Short selling support

## References

- **Requirement Doc**: `requirement_docs/20251211_etf_trend_following_v2_requirement.md`
- **Source Code**: `src/portfolio.py`
- **Tests**: `tests/test_portfolio.py`
- **Examples**: `examples/portfolio_example.py`
