# Configuration Loader Module

## Overview

The `config_loader.py` module provides a comprehensive configuration management system for the ETF Trend Following V2 system. It supports hierarchical JSON configuration files with full validation and type safety.

## Features

- **Type-safe configuration** using Python dataclasses
- **Comprehensive validation** with detailed error messages
- **Default values** for all optional parameters
- **Hierarchical structure** supporting 10 configuration sections
- **Multiple strategy types** (MACD, KAMA, Combo)
- **JSON serialization** for easy persistence
- **Python 3.9+ compatible**

## Configuration Structure

The configuration is organized into 10 main sections:

### 1. Environment (`env`)
Defines paths and environment settings:
- `root_dir`: Project root directory (required)
- `data_dir`: Data directory (default: "data/chinese_etf/daily")
- `results_dir`: Results output directory
- `log_dir`: Log file directory
- `timezone`: Timezone for trading (default: "Asia/Shanghai")
- `trading_calendar`: Trading calendar (default: "SSE")

### 2. Modes (`modes`)
Operating mode configuration:
- `run_mode`: "backtest", "signal", or "live-dryrun"
- `as_of_date`: Date for signal generation (YYYY-MM-DD format, null = today)
- `lookback_days`: Historical data lookback period
- `calendar_offsets`: Signal generation and execution timing offsets

### 3. Universe (`universe`)
Trading universe definition:
- `pool_file`: Path to CSV file with stock list
- `pool_list`: Direct list of stock codes (mutually exclusive with pool_file)
- `liquidity_threshold`: Minimum volume, amount, and turnover requirements
- `blacklist`: List of excluded stocks
- `handle_delisted`: How to handle delisted stocks

### 4. Strategies (`strategies`)
Array of strategy configurations. Supports three types:

#### MACD Strategy
```json
{
  "type": "macd",
  "fast_period": 12,
  "slow_period": 26,
  "signal_period": 9,
  "enable_adx_filter": false,
  "enable_volume_filter": false,
  "enable_slope_filter": false,
  "enable_confirm_filter": false
}
```

#### KAMA Strategy (Recommended)
```json
{
  "type": "kama",
  "kama_period": 20,
  "kama_fast": 2,
  "kama_slow": 30,
  "enable_efficiency_filter": false,
  "enable_slope_confirmation": false,
  "enable_adx_filter": false,
  "enable_volume_filter": false
}
```

#### Combo Strategy
```json
{
  "type": "combo",
  "mode": "or",
  "strategies": [
    {"type": "macd"},
    {"type": "kama"}
  ],
  "conflict_resolution": "majority"
}
```

### 5. Scoring (`scoring`)
Multi-period momentum scoring:
- `momentum_weights`: Weights for 20d, 60d, 120d momentum (must sum to 1.0)
- `buffer_thresholds`: Buy top N and hold until rank thresholds
- `inertia_bonus`: Bonus coefficient for existing positions
- `rebalance_frequency`: Days between rebalancing

### 6. Clustering (`clustering`)
Correlation-based clustering:
- `correlation_window`: Days for correlation calculation
- `distance_metric`: "correlation", "euclidean", or "dtw"
- `linkage_method`: "single", "complete", "average", or "ward"
- `cut_threshold`: Distance threshold for cutting dendrogram
- `max_positions_per_cluster`: Maximum positions per cluster
- `update_frequency`: Days between cluster updates

### 7. Risk (`risk`)
Risk management parameters:
- `atr_window`: ATR calculation window
- `atr_multiplier`: ATR multiplier for stop loss
- `time_stop_days`: Maximum holding period
- `time_stop_threshold`: Loss threshold for time stop
- `circuit_breaker_threshold`: Daily loss threshold for circuit breaker
- `min_liquidity_threshold`: Minimum daily volume
- `enable_t1_restriction`: Enable T+1 trading restriction

### 8. Position Sizing (`position_sizing`)
Portfolio constraints and sizing:
- `target_risk_per_position`: Target risk per position (e.g., 0.02 = 2%)
- `volatility_method`: "std", "ewma", or "atr"
- `ewma_lambda`: Lambda for EWMA volatility (default: 0.94)
- `max_positions`: Maximum number of positions
- `max_position_size`: Maximum size per position (e.g., 0.15 = 15%)
- `max_cluster_size`: Maximum size per cluster (e.g., 0.30 = 30%)
- `max_total_exposure`: Maximum total exposure (e.g., 0.95 = 95%)
- `min_cash_reserve`: Minimum cash reserve (e.g., 0.05 = 5%)
- `commission_rate`: Commission rate (e.g., 0.0003 = 0.03%)
- `slippage_bps`: Slippage in basis points

### 9. Execution (`execution`)
Order execution settings:
- `order_time_strategy`: "open", "close", "vwap", or "twap"
- `matching_assumption`: "immediate", "next_bar", or "realistic"
- `slippage_model`: "fixed", "volume_based", or "spread_based"
- `handle_t1_restriction`: Handle T+1 restriction

### 10. I/O (`io`)
Input/output configuration:
- `signal_output_path`: Path template for signal output
- `position_snapshot_path`: Path template for position snapshots
- `performance_report_path`: Path template for performance reports
- `log_level`: "DEBUG", "INFO", "WARNING", or "ERROR"
- `log_format`: Python logging format string
- `save_intermediate_results`: Whether to save intermediate results

## Usage Examples

### Basic Usage

```python
from config_loader import load_config, validate_config

# Load configuration from file
config = load_config("config/my_config.json")

# Validate configuration
errors = validate_config(config)
if errors:
    for error in errors:
        print(f"Error: {error}")
else:
    print("Configuration is valid!")

# Access configuration values
print(f"Root directory: {config.env.root_dir}")
print(f"Run mode: {config.modes.run_mode}")
print(f"Number of strategies: {len(config.strategies)}")
```

### Creating Default Configuration

```python
from config_loader import create_default_config, save_config

# Create default configuration
config = create_default_config(root_dir="/mnt/d/git/backtesting")

# Customize as needed
config.modes.run_mode = "signal"
config.modes.as_of_date = "2025-12-11"

# Save to file
save_config(config, "config/my_config.json")
```

### Loading from Dictionary

```python
from config_loader import load_config_from_dict

config_dict = {
    "env": {"root_dir": "/test"},
    "modes": {"run_mode": "backtest"},
    "universe": {"pool_file": "results/trend_etf_pool.csv"},
    "strategies": [{"type": "kama"}],
    # ... other sections with defaults
}

config = load_config_from_dict(config_dict)
```

### Accessing Strategy Configuration

```python
# Access first strategy
strategy = config.strategies[0]

if strategy.type == "kama":
    print(f"KAMA period: {strategy.kama_period}")
    print(f"KAMA fast: {strategy.kama_fast}")
    print(f"KAMA slow: {strategy.kama_slow}")
elif strategy.type == "macd":
    print(f"MACD fast: {strategy.fast_period}")
    print(f"MACD slow: {strategy.slow_period}")
```

### Converting to Dictionary

```python
# Convert config to dictionary (useful for serialization)
config_dict = config.to_dict()

# Access nested values
print(config_dict["env"]["root_dir"])
print(config_dict["strategies"][0]["type"])
```

## Validation

The module provides comprehensive validation at multiple levels:

### Field-level Validation
- Type checking (automatic via dataclasses)
- Range validation (e.g., percentages in [0, 1])
- Required field checking

### Cross-field Validation
- MACD fast_period < slow_period
- KAMA kama_fast < kama_slow
- Weights sum to 1.0
- hold_until_rank >= buy_top_n

### Cross-section Validation
- buy_top_n <= max_positions
- max_total_exposure + min_cash_reserve <= 1.0

### Example Validation Output

```python
errors = validate_config(config)
# Example errors:
# [
#   "env: env.root_dir is required",
#   "strategies[0]: MACD fast_period (26) must be < slow_period (12)",
#   "scoring: scoring.momentum_weights must sum to 1.0, got 0.8",
#   "scoring.buy_top_n (30) should not exceed position_sizing.max_positions (20)"
# ]
```

## Best Practices

1. **Always validate** after loading or creating configuration
2. **Use KAMA strategy** as default (best performance based on experiments)
3. **Set appropriate buffer thresholds** (buy_top_n=10, hold_until_rank=15)
4. **Enable T+1 restriction** for China market
5. **Use EWMA volatility** for position sizing (more responsive)
6. **Keep max_positions <= 20** for diversification
7. **Reserve 5% cash** for liquidity and rebalancing

## Example Configuration File

See `/mnt/d/git/backtesting/etf_trend_following_v2/config/example_config.json` for a complete example configuration file with all sections properly configured.

## Testing

Run the comprehensive test suite:

```bash
cd /mnt/d/git/backtesting/etf_trend_following_v2
python -m pytest tests/test_config_loader.py -v
```

All 47 tests should pass, covering:
- Individual section validation
- Strategy configuration validation
- Full configuration validation
- Loading and saving
- Error handling

## Error Handling

The module provides clear error messages for common issues:

```python
try:
    config = load_config("config/my_config.json")
except FileNotFoundError:
    print("Configuration file not found")
except json.JSONDecodeError:
    print("Invalid JSON format")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Integration with ETF Trend Following V2

This configuration loader is designed to integrate seamlessly with the ETF Trend Following V2 system:

1. **Signal Generation**: Use `modes.run_mode = "signal"` with `as_of_date`
2. **Backtesting**: Use `modes.run_mode = "backtest"` with historical data
3. **Live Trading**: Use `modes.run_mode = "live-dryrun"` for paper trading

The configuration structure aligns with the system architecture described in the requirement document.
