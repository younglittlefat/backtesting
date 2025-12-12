# Risk Management Module

Comprehensive risk control module for ETF trend following system, providing ATR-based stop loss, time stops, circuit breakers, and liquidity checks.

## Features

### 1. ATR (Average True Range) Calculation
- **Methods**: Simple Moving Average (SMA) or Exponential Moving Average (EMA)
- **Purpose**: Measure market volatility for dynamic stop loss calculation
- **Usage**:
```python
from risk import calculate_atr

atr = calculate_atr(df, period=14, method='sma')
```

### 2. Chandelier Exit Stop Loss
- **Description**: Trailing stop loss that follows the highest price since entry
- **Formula**: `Stop Line = max(Highest_Price - N × ATR, Previous_Stop_Line)`
- **Key Feature**: Stop line only moves up (protecting profits), never down
- **Default**: 3× ATR multiplier

**Example**:
```python
from risk import calculate_stop_line

stop_data = calculate_stop_line(
    df=df,
    entry_date='2024-01-15',
    entry_price=10.50,
    atr_multiplier=3.0,
    atr_period=14
)

# Returns DataFrame with:
# - stop_line: calculated stop loss line
# - highest_since_entry: highest high since entry
# - atr: ATR values
```

### 3. Time-Based Stop Loss
- **Purpose**: Free up capital from stagnant "zombie" positions
- **Trigger Condition**: Position held for ≥ N days AND profit < threshold
- **Default**: 20 days, minimum 1× ATR profit

**Example**:
```python
from risk import check_time_stop

result = check_time_stop(
    df=df,
    entry_date='2024-01-01',
    entry_price=10.00,
    max_hold_days=20,
    min_profit_atr=1.0
)

if result['triggered']:
    print(f"Time stop triggered after {result['days_held']} days")
```

### 4. Circuit Breaker
- **Market-Level**: Triggered when market index drops by threshold (default: -5%)
- **Account-Level**: Triggered when account drawdown exceeds threshold (default: -3%)
- **Actions**: Prohibit new positions, recommend reducing positions

**Example**:
```python
from risk import check_circuit_breaker

result = check_circuit_breaker(
    market_df=csi300_df,
    account_equity=account_equity_series,
    as_of_date='2024-01-31',
    market_drop_threshold=-0.05,
    account_drawdown_threshold=-0.03
)

if result['triggered']:
    print(f"Circuit breaker: {result['reason']}")
    print(f"Recommendations: {result['recommendations']}")
```

### 5. Liquidity Check
- **Checks**: Daily trading amount, bid-ask spread
- **Purpose**: Ensure sufficient liquidity before trading
- **Default**: Minimum 50M yuan daily trading amount

**Example**:
```python
from risk import check_liquidity

result = check_liquidity(
    df=df,
    min_amount=50_000_000,
    max_spread_pct=0.005  # 0.5% max spread
)

if not result['sufficient']:
    print(f"Insufficient liquidity: {result['reason']}")
```

### 6. T+1 Constraint Enforcement
- **Rule**: Shares bought on day T cannot be sold until day T+1
- **Application**: Chinese A-share and ETF markets
- **Supports**: Trading calendar for accurate T+1 calculation

**Example**:
```python
from risk import check_t_plus_1

can_sell = check_t_plus_1(
    entry_date='2024-01-15',
    check_date='2024-01-16',
    trading_calendar=trading_calendar  # Optional
)
```

## Comprehensive Risk Manager

The `RiskManager` class integrates all risk controls for portfolio-level management.

### Initialization

```python
from risk import RiskManager

config = {
    'atr_multiplier': 3.0,
    'atr_period': 14,
    'time_stop_days': 20,
    'time_stop_min_profit_atr': 1.0,
    'market_drop_threshold': -0.05,
    'account_drawdown_threshold': -0.03,
    'min_liquidity_amount': 50_000_000,
    'max_spread_pct': 0.005,
    'circuit_breaker_lookback': 1,
    'enforce_t_plus_1': True
}

risk_manager = RiskManager(config)
```

### Position-Level Risk Check

```python
position = {
    'entry_date': '2024-01-10',
    'entry_price': 10.50,
    'shares': 1000
}

result = risk_manager.check_position_risk(
    symbol='159915.SZ',
    df=etf_data,
    position=position,
    as_of_date='2024-01-31'
)

print(f"ATR Stop: {result['atr_stop']}")
print(f"Time Stop: {result['time_stop']}")
print(f"Can Sell Today: {result['can_sell_today']}")
print(f"Recommended Actions: {result['actions']}")
```

### Portfolio-Level Risk Check

```python
data_dict = {
    '159915.SZ': df1,
    '510300.SH': df2,
    # ... more symbols
}

positions = {
    '159915.SZ': {'entry_date': '2024-01-10', 'entry_price': 10.50},
    '510300.SH': {'entry_date': '2024-01-15', 'entry_price': 3.20},
    # ... more positions
}

result = risk_manager.check_portfolio_risk(
    data_dict=data_dict,
    positions=positions,
    market_df=market_index_df,
    account_equity=account_equity_series,
    as_of_date='2024-01-31'
)

summary = result['summary']
print(f"Total Positions: {summary['total_positions']}")
print(f"ATR Stops Triggered: {summary['atr_stops_triggered']}")
print(f"Time Stops Triggered: {summary['time_stops_triggered']}")
print(f"Circuit Breaker Active: {summary['circuit_breaker_active']}")

# Check individual position risks
for symbol, risk_status in result['position_risks'].items():
    if 'sell' in ' '.join(risk_status['actions']):
        print(f"{symbol}: {risk_status['actions']}")
```

## Integration with Trading System

### Daily Risk Workflow

```python
# 1. Initialize risk manager
risk_manager = RiskManager(config)

# 2. Check portfolio-level risks
portfolio_risk = risk_manager.check_portfolio_risk(
    data_dict=data_dict,
    positions=current_positions,
    market_df=market_df,
    account_equity=equity_curve
)

# 3. Process circuit breaker
if portfolio_risk['circuit_breaker']['triggered']:
    # Prohibit new positions
    allow_new_positions = False
    # Consider reducing positions
    if 'consider_reducing_positions' in portfolio_risk['portfolio_actions']:
        reduce_position_size()

# 4. Process individual position stops
for symbol, risk_status in portfolio_risk['position_risks'].items():
    actions = risk_status['actions']

    if 'sell_atr_stop' in actions:
        # ATR stop triggered, sell immediately
        if risk_status['can_sell_today']:
            execute_sell(symbol, reason='atr_stop')
        else:
            queue_sell_tomorrow(symbol, reason='atr_stop_t1')

    elif 'sell_time_stop' in actions:
        # Time stop triggered, free up capital
        if risk_status['can_sell_today']:
            execute_sell(symbol, reason='time_stop')
        else:
            queue_sell_tomorrow(symbol, reason='time_stop_t1')

    if 'warning_low_liquidity' in actions:
        # Reduce position size or avoid new buys
        reduce_target_weight(symbol)
```

## Configuration Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `atr_multiplier` | float | 3.0 | ATR multiplier for stop loss distance |
| `atr_period` | int | 14 | ATR calculation period (days) |
| `time_stop_days` | int | 20 | Maximum holding period before time stop |
| `time_stop_min_profit_atr` | float | 1.0 | Minimum profit (in ATR) to avoid time stop |
| `market_drop_threshold` | float | -0.05 | Market drop threshold for circuit breaker (-5%) |
| `account_drawdown_threshold` | float | -0.03 | Account drawdown threshold (-3%) |
| `min_liquidity_amount` | float | 50000000 | Minimum daily trading amount (50M yuan) |
| `max_spread_pct` | float | None | Maximum bid-ask spread (optional) |
| `circuit_breaker_lookback` | int | 1 | Lookback days for market drop check |
| `enforce_t_plus_1` | bool | True | Enforce T+1 trading constraint |

## Testing

Run comprehensive test suite:

```bash
cd /mnt/d/git/backtesting/etf_trend_following_v2
conda activate backtesting
python tests/test_risk.py
```

**Test Coverage**:
- ATR calculation (SMA and EMA methods)
- Chandelier Exit stop line calculation
- Stop loss trigger detection
- Time-based stop loss
- Circuit breaker (market and account level)
- Liquidity checks
- T+1 constraint handling
- RiskManager integration

All 36 tests pass with comprehensive coverage of edge cases and error handling.

## Design Principles

1. **Conservative Risk Management**: Default parameters err on the side of capital preservation
2. **Adaptive to Volatility**: ATR-based stops adjust to market conditions
3. **Capital Efficiency**: Time stops free up capital from underperforming positions
4. **Market Regime Awareness**: Circuit breakers prevent trading in adverse conditions
5. **Execution Feasibility**: T+1 constraint ensures compliance with market rules
6. **Liquidity Protection**: Prevents trading in illiquid securities

## Implementation Notes

- **Stop Line Monotonicity**: Chandelier Exit stop line only moves up, protecting accumulated profits
- **ATR Methods**:
  - SMA: Simple moving average, suitable for general use
  - EMA: Wilder's smoothing method, more responsive to recent volatility
- **Circuit Breaker Recovery**: System should provide mechanism to resume trading when conditions improve
- **Trading Calendar**: Highly recommended for production use to accurately handle T+1 and holidays

## References

- **Chandelier Exit**: Developed by Chuck LeBeau, uses ATR for trailing stop loss
- **ATR (Average True Range)**: Developed by J. Welles Wilder Jr.
- **Time Stops**: Common practice in systematic trading to manage opportunity cost

## Future Enhancements

Potential additions (not yet implemented):
- Dynamic ATR multiplier based on market regime
- Correlation-based portfolio-level circuit breaker
- Volatility-scaled time stop thresholds
- Multi-level circuit breaker severity
- Recovery conditions for automatic circuit breaker reset
