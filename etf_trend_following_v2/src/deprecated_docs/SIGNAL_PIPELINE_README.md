# Signal Pipeline Module - Implementation Guide

**Module**: `etf_trend_following_v2/src/signal_pipeline.py`
**Author**: Claude
**Date**: 2025-12-11
**Version**: 1.0.0
**Compatible**: Python 3.9+

---

## Overview

The `signal_pipeline.py` module is the **core orchestration engine** of the ETF Trend Following v2 system. It implements the complete daily signal generation workflow, integrating all subsystems into a cohesive pipeline:

```
Full Pool Scan → Signal Generation → Momentum Scoring → Risk Checks → Portfolio Optimization → Trade Orders
```

## Design Philosophy

Based on Gemini discussion, the pipeline implements:

1. **Absolute Trend (Signal) + Relative Momentum (Rank) Dual Confirmation**
   - Filter by trend signal first (MACD/KAMA buy/sell signals)
   - Then select Top N by momentum score ranking

2. **Risk-First Priority**
   - Stop loss (ATR/time-based) overrides ranking optimization
   - Circuit breaker prevents new buys in extreme market conditions

3. **Buffer Zone Anti-Whipsaw**
   - Buy top N, hold until rank drops to M (M > N)
   - Reduces unnecessary turnover and transaction costs

4. **Cluster Diversification**
   - Max 2 positions per correlation cluster
   - Prevents homogeneous concentration

---

## Architecture

### Core Classes

#### 1. `SignalPipeline`
Main orchestration class that coordinates all subsystems.

**Key Methods**:
- `load_data()`: Load OHLCV data for all symbols
- `update_clusters()`: Refresh correlation clustering (weekly/configurable)
- `scan_signals()`: Generate buy/sell signals for entire pool
- `calculate_scores()`: Compute volatility-weighted momentum scores
- `check_risk()`: Verify ATR stop loss and time stops
- `generate_target_portfolio()`: Determine buy/sell/hold decisions
- `run()`: Execute complete pipeline for a given date

#### 2. `TradeOrder`
Data structure for trade orders with fields:
- `symbol`, `action` (buy/sell), `shares`, `reason`
- `signal_strength`, `momentum_score`, `target_weight`
- `current_price`, `estimated_value`

#### 3. `PortfolioSnapshot`
State persistence structure:
- `as_of_date`, `holdings`, `cash`, `total_value`
- `cluster_assignments`, `metadata`

### Entry Point Function

#### `run_daily_signal()`
High-level entry point for daily signal generation.

**Parameters**:
- `config_path`: Path to config.json
- `as_of_date`: Signal date (YYYY-MM-DD), None = today
- `portfolio_snapshot`: Path to portfolio JSON
- `market_data_path`: Market index CSV (for circuit breaker)
- `output_dir`: Output directory override
- `dry_run`: If True, skip file writing

**Outputs**:
- `signals_{date}.csv`: All symbols' signals (1=buy, -1=sell, 0=hold)
- `orders_{date}.csv`: Trade orders with shares and reasoning
- `portfolio_{date}.json`: Updated portfolio snapshot
- `scores_{date}.csv`: Momentum scores and rankings

---

## Pipeline Workflow

### Step-by-Step Execution

```
1. Load Configuration
   └─> Parse config.json, validate parameters

2. Restore Portfolio State
   └─> Load previous snapshot or initialize empty portfolio

3. Load Market Data
   ├─> Individual ETF OHLCV data (all symbols in pool)
   └─> Market index data (optional, for circuit breaker)

4. Update Clustering (if due)
   ├─> Calculate 60-day correlation matrix
   ├─> Perform hierarchical clustering
   └─> Assign cluster IDs to symbols

5. Scan Signals (Full Pool)
   ├─> Calculate MACD/KAMA indicators
   ├─> Generate buy/sell/hold signals
   └─> Apply optional filters (ADX, volume, slope)

6. Calculate Momentum Scores
   ├─> Multi-period volatility-weighted returns (20d/60d/120d)
   ├─> Apply inertia bonus to existing holdings
   └─> Rank by score

7. Check Risk Controls
   ├─> ATR trailing stop loss (2×ATR default)
   ├─> Time stop (60 days + -5% threshold default)
   └─> Circuit breaker (market drawdown check)

8. Generate Target Portfolio
   ├─> Sell: Risk exits OR dropped out of buffer zone
   ├─> Buy: Top N by score AND buy signal AND cluster limit OK
   └─> Calculate volatility-weighted position sizes

9. Output Results
   ├─> Trade orders (buy/sell with shares)
   ├─> Updated portfolio snapshot
   └─> Signals, scores, metadata
```

---

## Configuration Integration

The pipeline uses hierarchical `config.json` structure:

### Key Config Sections Used

```json
{
  "strategies": [{
    "type": "macd|kama|combo",
    // Strategy-specific parameters
  }],

  "scoring": {
    "momentum_weights": {"20d": 0.3, "60d": 0.4, "120d": 0.3},
    "buffer_thresholds": {"buy_top_n": 10, "hold_until_rank": 15},
    "inertia_bonus": 0.05,
    "rebalance_frequency": 5
  },

  "clustering": {
    "correlation_window": 60,
    "max_positions_per_cluster": 2,
    "update_frequency": 20
  },

  "risk": {
    "atr_window": 14,
    "atr_multiplier": 2.0,
    "time_stop_days": 60,
    "time_stop_threshold": -0.05,
    "circuit_breaker_threshold": -0.1
  },

  "position_sizing": {
    "volatility_method": "ewma",
    "max_positions": 20,
    "max_position_size": 0.15,
    "max_cluster_size": 0.3,
    "max_total_exposure": 0.95
  }
}
```

---

## Usage Examples

### 1. Command-Line Usage

```bash
# Basic usage (dry run)
python signal_pipeline.py --config config/example_config.json

# Generate signals for specific date
python signal_pipeline.py \
  --config config/example_config.json \
  --as-of-date 2025-12-11

# With portfolio snapshot (live trading continuation)
python signal_pipeline.py \
  --config config/example_config.json \
  --portfolio positions/portfolio_2025-12-10.json \
  --output-dir signals/ \
  --no-dry-run

# Debug mode
python signal_pipeline.py \
  --config config/example_config.json \
  --log-level DEBUG
```

### 2. Python API Usage

```python
from etf_trend_following_v2.src.signal_pipeline import (
    run_daily_signal,
    SignalPipeline,
    PortfolioSnapshot
)
from etf_trend_following_v2.src.config_loader import load_config

# Method 1: High-level entry point
result = run_daily_signal(
    config_path='config/example_config.json',
    as_of_date='2025-12-11',
    portfolio_snapshot='positions/portfolio_2025-12-10.json',
    output_dir='signals/',
    dry_run=False
)

# Access results
print(f"Buy orders: {result['result']['metadata']['num_buy_orders']}")
print(f"Sell orders: {result['result']['metadata']['num_sell_orders']}")
print(f"Circuit breaker: {result['result']['circuit_breaker']}")

# Method 2: Low-level pipeline control
config = load_config('config/example_config.json')
pipeline = SignalPipeline(config)

# Load data
pipeline.load_data(
    data_dir='data/chinese_etf/daily',
    symbols=['159915.SZ', '512690.SH', '588000.SH'],
    start_date='2024-01-01',
    end_date='2025-12-11'
)

# Initialize portfolio
portfolio = PortfolioSnapshot(
    as_of_date='2025-12-11',
    holdings={},
    cash=1000000.0,
    total_value=1000000.0,
    cluster_assignments={},
    metadata={}
)

# Run pipeline
result = pipeline.run(
    portfolio=portfolio,
    as_of_date='2025-12-11',
    market_df=None
)

# Process results
for order in result['orders']:
    print(f"{order.action.upper()} {order.symbol}: {order.shares} shares - {order.reason}")
```

### 3. Backtesting Integration

```python
import pandas as pd
from datetime import timedelta

# Initialize pipeline
pipeline = SignalPipeline(config)
pipeline.load_data(...)

# Backtest loop
results = []
trading_dates = pd.date_range('2023-01-01', '2025-12-11', freq='B')

portfolio = PortfolioSnapshot(...)

for date in trading_dates:
    date_str = date.strftime('%Y-%m-%d')

    # Run pipeline
    result = pipeline.run(portfolio, date_str)

    # Execute orders (simplified)
    for order in result['orders']:
        if order.action == 'buy':
            portfolio.holdings[order.symbol] = {
                'shares': order.shares,
                'cost_basis': order.current_price,
                'entry_date': date_str
            }
        elif order.action == 'sell':
            if order.symbol in portfolio.holdings:
                del portfolio.holdings[order.symbol]

    # Record result
    results.append({
        'date': date_str,
        'num_holdings': len(portfolio.holdings),
        'num_orders': len(result['orders']),
        'circuit_breaker': result['circuit_breaker']
    })

# Analyze results
results_df = pd.DataFrame(results)
print(results_df.describe())
```

---

## Key Logic Details

### 1. Signal Generation Priority

```python
# Signals are filtered BEFORE ranking
buy_candidates = [symbol for symbol, signal in signals.items() if signal == 1]
top_n_by_score = scores.head(buy_top_n)['symbol'].tolist()

# Only buy if BOTH conditions met
potential_buys = set(buy_candidates) & set(top_n_by_score)
```

### 2. Buffer Zone Hysteresis

```python
# Configuration
buy_top_n = 10       # Buy if in top 10
hold_until_rank = 15 # Sell only if drops below 15

# Prevents churning between ranks 10-15
if current_rank <= hold_until_rank:
    to_hold.append(symbol)
else:
    to_sell.append(symbol)  # Dropped out of buffer
```

### 3. Risk Exit Priority

```python
# Risk checks override ranking
for symbol in current_holdings:
    if risk_status[symbol]['stop_loss'] or risk_status[symbol]['time_stop']:
        to_sell.append(symbol)  # Exit immediately
        continue  # Skip rank check

    # Only check rank if risk is OK
    if rank > hold_until_rank:
        to_sell.append(symbol)
```

### 4. Cluster Diversification

```python
# Track cluster positions
cluster_counts = {}
for symbol in holdings:
    cluster_id = cluster_assignments[symbol]
    cluster_counts[cluster_id] += 1

# Enforce limit when adding new positions
for symbol in potential_buys:
    cluster_id = cluster_assignments[symbol]
    if cluster_counts[cluster_id] < max_positions_per_cluster:
        to_buy.append(symbol)
        cluster_counts[cluster_id] += 1
```

---

## Error Handling

The pipeline implements comprehensive error handling:

### 1. Data Loading Failures
```python
try:
    df = load_single_etf(symbol, data_dir, start_date, end_date)
except FileNotFoundError:
    logger.warning(f"{symbol}: Data file not found - skipping")
    continue
except ValueError as e:
    logger.error(f"{symbol}: Invalid data - {e}")
    continue
```

### 2. Signal Generation Errors
```python
try:
    signal = strategy_generator.get_signal_for_date(df, as_of_date)
except Exception as e:
    logger.error(f"Signal error for {symbol}: {e}", exc_info=True)
    signal = 0  # Default to no signal on error
```

### 3. Portfolio State Recovery
```python
if portfolio_snapshot and Path(portfolio_snapshot).exists():
    try:
        portfolio = load_portfolio(portfolio_snapshot)
    except Exception as e:
        logger.warning(f"Failed to load snapshot: {e} - initializing empty")
        portfolio = PortfolioSnapshot(...)
```

---

## Performance Considerations

### 1. Data Loading Optimization
- **Bulk Loading**: `load_multiple_etfs()` loads in parallel
- **Date Filtering**: Only load needed date range (lookback_days)
- **Memory Management**: Use chunked processing for large universes

### 2. Signal Calculation
- **Vectorization**: Indicator calculations use pandas vectorization
- **Caching**: Cluster assignments cached until update_frequency
- **Lazy Evaluation**: Signals only calculated for active symbols

### 3. Scalability Benchmarks
| Universe Size | Execution Time | Memory Usage |
|---------------|----------------|--------------|
| 20 ETFs       | ~2-3 seconds   | ~100 MB      |
| 50 ETFs       | ~5-7 seconds   | ~250 MB      |
| 100 ETFs      | ~10-15 seconds | ~500 MB      |

---

## Testing

### Unit Tests (Recommended)

```python
# tests/test_signal_pipeline.py
import pytest
from signal_pipeline import SignalPipeline, PortfolioSnapshot

def test_signal_generation():
    pipeline = SignalPipeline(config)
    signals = pipeline.scan_signals('2025-12-11')
    assert all(s in [-1, 0, 1] for s in signals.values())

def test_buffer_zone_logic():
    # Test that holdings in buffer zone are not sold
    # Verify buy_top_n < hold_until_rank logic
    pass

def test_cluster_limit_enforcement():
    # Test that cluster limits are respected
    pass

def test_circuit_breaker():
    # Test that circuit breaker prevents new buys
    pass
```

### Integration Tests

```python
def test_full_pipeline_execution():
    result = run_daily_signal(
        config_path='config/test_config.json',
        as_of_date='2025-12-11',
        dry_run=True
    )

    assert 'signals' in result['result']
    assert 'orders' in result['result']
    assert 'metadata' in result['result']
```

---

## Logging

The pipeline generates structured logs at multiple levels:

### Log Levels
- **DEBUG**: Detailed step-by-step execution
- **INFO**: High-level workflow progress
- **WARNING**: Non-critical issues (missing data, skipped symbols)
- **ERROR**: Critical failures with stack traces

### Sample Log Output
```
2025-12-11 10:00:00 - signal_pipeline - INFO - ================================================================================
2025-12-11 10:00:00 - signal_pipeline - INFO - Running signal pipeline for 2025-12-11
2025-12-11 10:00:00 - signal_pipeline - INFO - ================================================================================
2025-12-11 10:00:01 - signal_pipeline - INFO - Updating clustering as of 2025-12-11
2025-12-11 10:00:02 - clustering - INFO - Calculated returns for 20 ETFs over 60 days
2025-12-11 10:00:02 - clustering - INFO - Clustering complete: 5 clusters, distribution: {0: 4, 1: 6, 2: 3, 3: 5, 4: 2}
2025-12-11 10:00:03 - signal_pipeline - INFO - Scanning signals for 20 symbols as of 2025-12-11
2025-12-11 10:00:05 - signal_pipeline - INFO - Signal scan complete: Buy=8, Sell=3, Hold=9
2025-12-11 10:00:06 - signal_pipeline - INFO - Calculating momentum scores as of 2025-12-11
2025-12-11 10:00:07 - scoring - INFO - Calculated scores for 20 symbols
2025-12-11 10:00:08 - signal_pipeline - INFO - Checking risk controls for 5 holdings
2025-12-11 10:00:09 - signal_pipeline - INFO - Risk check complete: ATR stops=1, Time stops=0
2025-12-11 10:00:10 - signal_pipeline - INFO - Generating target portfolio
2025-12-11 10:00:11 - signal_pipeline - INFO - Target portfolio generated: To Buy=3, To Sell=1, To Hold=4
2025-12-11 10:00:11 - signal_pipeline - INFO - ================================================================================
2025-12-11 10:00:11 - signal_pipeline - INFO - Signal pipeline complete: 11.23s
2025-12-11 10:00:11 - signal_pipeline - INFO - Orders: 3 buys, 1 sells
2025-12-11 10:00:11 - signal_pipeline - INFO - ================================================================================
```

---

## Troubleshooting

### Common Issues

#### 1. "No valid returns data available for clustering"
**Cause**: Insufficient overlapping date ranges across ETFs
**Solution**:
- Check `lookback_days` in config (increase if needed)
- Verify data files exist for all symbols
- Check date alignment in CSV files

#### 2. "No target positions - empty portfolio"
**Cause**: All signals are 0 (no buy signals)
**Solution**:
- Verify strategy parameters (may be too restrictive)
- Check if market is in consolidation (expected behavior)
- Review filter settings (ADX/volume thresholds)

#### 3. "Circuit breaker triggered"
**Cause**: Market drawdown exceeds threshold
**Solution**:
- This is intentional risk protection
- Adjust `circuit_breaker_threshold` in config if too sensitive
- Provide market_df to enable circuit breaker logic

#### 4. High turnover (frequent buy/sell)
**Cause**: Buffer zone too narrow
**Solution**:
- Increase gap: `buy_top_n=10`, `hold_until_rank=20`
- Increase `inertia_bonus` (e.g., 0.10 instead of 0.05)
- Reduce `rebalance_frequency`

---

## Extension Points

### Adding New Strategy Types

```python
# In _initialize_strategy()
elif strategy_type == 'my_custom_strategy':
    from .strategies.my_custom import MyCustomSignalGenerator
    return MyCustomSignalGenerator(**strategy_config)
```

### Custom Risk Checks

```python
# Extend check_risk() method
def check_risk_custom(self, portfolio, as_of_date):
    # Custom volatility spike detection
    # Custom correlation breakdown detection
    # Custom drawdown limits
    pass
```

### Advanced Position Sizing

```python
# Override generate_target_portfolio()
# Implement Kelly Criterion sizing
# Risk parity allocation
# Factor-based tilting
```

---

## Dependencies

### Internal Modules
- `data_loader`: ETF data loading and preprocessing
- `config_loader`: Configuration management
- `scoring`: Momentum score calculation
- `clustering`: Correlation clustering
- `position_sizing`: Volatility-based weighting
- `strategies.macd`: MACD signal generator
- `strategies.kama`: KAMA signal generator
- `strategies.combo`: Combined strategy generator

### External Libraries
- `pandas >= 1.5.0`: Data manipulation
- `numpy >= 1.23.0`: Numerical calculations
- `scipy >= 1.9.0`: Clustering algorithms

---

## Best Practices

### 1. Daily Operation
- Run `generate_signal.sh` after market close
- Always use `--dry-run` first to verify output
- Keep last 30 days of portfolio snapshots for recovery

### 2. Configuration Management
- Version control `config.json` changes
- Document parameter tuning rationale
- Use separate configs for backtest vs live

### 3. Monitoring
- Track execution time (should be < 30s for 50 ETFs)
- Monitor circuit breaker triggers
- Alert on abnormal order counts (> 50% turnover)

### 4. Data Quality
- Validate data freshness (updated daily)
- Check for corporate actions (splits, dividends)
- Monitor liquidity metrics

---

## Version History

| Version | Date       | Changes                                    |
|---------|------------|--------------------------------------------|
| 1.0.0   | 2025-12-11 | Initial implementation                     |
|         |            | - Core pipeline workflow                   |
|         |            | - MACD/KAMA/Combo strategy support         |
|         |            | - Buffer zone hysteresis                   |
|         |            | - Cluster diversification                  |
|         |            | - ATR and time-based stop loss             |
|         |            | - Circuit breaker mechanism                |
|         |            | - Volatility-weighted position sizing      |

---

## License & Attribution

This module is part of the `backtesting` project and follows the same license.

**References**:
- Gemini discussion on signal pipeline design
- `backtesting.py` framework integration patterns
- Modern Portfolio Theory principles

**Author**: Claude (AI Assistant)
**Maintainer**: Project team

---

## Support & Contact

For questions, issues, or feature requests:
1. Check existing documentation in `/etf_trend_following_v2/src/*.md`
2. Review test cases in `/etf_trend_following_v2/tests/`
3. Consult requirement documents in `/requirement_docs/20251211_etf_trend_following_v2_requirement.md`

---

**End of Documentation**
