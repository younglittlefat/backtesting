# IO Utilities Module

**Module**: `io_utils.py`
**Author**: Claude
**Date**: 2025-12-11
**Status**: ✅ Fully Implemented & Tested

## Overview

The IO Utilities module provides comprehensive file I/O operations for the ETF Trend Following v2 system, including logging configuration, signal/position persistence, trade order management, performance reporting, and data validation.

## Features

### 1. Logging Configuration

Flexible logging system with file rotation and console output:

```python
from io_utils import setup_logging

logger = setup_logging(
    log_dir='./logs',
    log_level='INFO',
    log_to_file=True,
    log_to_console=True
)

logger.info("System started")
```

**Features**:
- Daily file rotation (keeps 30 days)
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Simultaneous file and console output
- Custom log formats

### 2. Signal File I/O

Save and load trading signals in CSV or JSON format:

```python
from io_utils import save_signals, load_signals

# Save signals
signals = {'159994.SZ': 1, '159941.SZ': -1, '159819.SZ': 0}
save_signals(signals, 'signals.json', '2025-12-11', format='json')

# Load signals
loaded_signals = load_signals('signals.json')
```

**Signal Values**:
- `1`: Buy signal
- `-1`: Sell signal
- `0`: Hold signal

### 3. Position Snapshot Management

Persist portfolio positions with dated snapshots:

```python
from io_utils import save_positions, load_positions, save_snapshot, load_latest_positions

# Save positions
positions = {
    '159994.SZ': {
        'shares': 30100,
        'entry_price': 1.658,
        'entry_date': '2025-11-26',
        'cost': 49915.78
    }
}
save_positions(positions, 'positions.json', '2025-12-11')

# Save dated snapshot
save_snapshot(positions, './snapshots', '2025-12-11', prefix='portfolio')

# Load latest snapshot
latest_pos = load_latest_positions('./snapshots', prefix='portfolio')
```

**Features**:
- Dated snapshot files (e.g., `portfolio_20251211.json`)
- Automatic latest snapshot detection
- JSON format with metadata (date, timestamp, count)

### 4. Trade Order Persistence

Save and load trade orders in CSV format:

```python
from io_utils import save_trade_orders, load_trade_orders

# Save orders
orders = [
    {
        'action': 'BUY',
        'symbol': '159994.SZ',
        'shares': 30100,
        'price': 1.658,
        'amount': -49915.78,
        'commission': 4.99,
        'reason': 'KAMA buy signal'
    }
]
save_trade_orders(orders, 'orders.csv', '2025-12-11')

# Load orders
loaded_orders = load_trade_orders('orders.csv')
```

### 5. Performance Report Generation

Generate comprehensive performance reports:

```python
from io_utils import save_performance_report, generate_summary_text

statistics = {
    'total_return': 0.3463,
    'sharpe_ratio': 1.69,
    'max_drawdown': -0.0527,
    'win_rate': 0.64,
    'num_trades': 45
}

equity_curve = pd.DataFrame({
    'date': [...],
    'equity': [...],
    'returns': [...],
    'drawdown': [...]
})

trade_log = pd.DataFrame({
    'date': [...],
    'symbol': [...],
    'action': [...],
    'shares': [...],
    'price': [...],
    'pnl': [...]
})

# Save complete report
save_performance_report(statistics, equity_curve, trade_log, './results')

# Generate text summary
summary = generate_summary_text(statistics)
print(summary)
```

**Output Files**:
- `statistics.json`: Performance metrics
- `equity_curve.csv`: Daily equity values
- `trade_log.csv`: Complete trade history

### 6. Data Validation

Validate OHLCV DataFrames and configuration paths:

```python
from io_utils import validate_ohlcv_df, validate_config_paths

# Validate OHLCV data
df = pd.DataFrame({
    'Open': [1.0, 1.1],
    'High': [1.1, 1.2],
    'Low': [0.9, 1.0],
    'Close': [1.05, 1.15],
    'Volume': [1000, 1100]
}, index=pd.date_range('2025-01-01', periods=2))

errors = validate_ohlcv_df(df, symbol='159994.SZ')
if errors:
    print("Validation errors:", errors)

# Validate config paths
config = {
    'data_dir': '/mnt/d/git/backtesting/data',
    'results_dir': './results'
}
errors = validate_config_paths(config)
```

**Validation Checks**:
- Required columns (Open, High, Low, Close)
- NaN values
- OHLC relationships (High >= Low, etc.)
- Non-positive prices
- DatetimeIndex format
- Duplicate dates

### 7. Path Utilities

Utility functions for path management:

```python
from io_utils import ensure_dir, get_dated_filename, find_latest_snapshot

# Ensure directory exists
ensure_dir('./results/backtest')

# Generate dated filename
filename = get_dated_filename('portfolio', '2025-12-11', 'json')
# Returns: 'portfolio_20251211.json'

# Find latest snapshot
latest = find_latest_snapshot('./snapshots', prefix='portfolio')
# Returns: './snapshots/portfolio_20251211.json'
```

## API Reference

### Logging Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `setup_logging(log_dir, log_level, log_format, log_to_file, log_to_console)` | Configure logging system | `logging.Logger` |

### Signal Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `save_signals(signals, output_path, date, format)` | Save signals to file | `None` |
| `load_signals(path)` | Load signals from file | `Dict[str, int]` |

### Position Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `save_positions(positions, output_path, date)` | Save position snapshot | `None` |
| `load_positions(path)` | Load position snapshot | `Dict[str, dict]` |
| `save_snapshot(positions, snapshot_dir, date, prefix)` | Save dated snapshot | `str` (path) |
| `load_latest_positions(snapshot_dir, prefix)` | Load latest snapshot | `Dict[str, dict]` |

### Trade Order Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `save_trade_orders(orders, output_path, date)` | Save trade orders | `None` |
| `load_trade_orders(path)` | Load trade orders | `List[dict]` |

### Performance Report Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `save_performance_report(statistics, equity_curve, trade_log, output_dir)` | Save full report | `None` |
| `generate_summary_text(statistics)` | Generate text summary | `str` |

### Validation Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `validate_ohlcv_df(df, symbol)` | Validate OHLCV DataFrame | `List[str]` (errors) |
| `validate_config_paths(config)` | Validate config paths | `List[str]` (errors) |

### Path Utility Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `ensure_dir(path)` | Create directory if not exists | `None` |
| `get_dated_filename(base_name, date, ext)` | Generate dated filename | `str` |
| `find_latest_snapshot(snapshot_dir, prefix)` | Find latest snapshot file | `str` (path) |

## File Formats

### Signal CSV Format

```csv
symbol,signal,date
159994.SZ,1,20251211
159941.SZ,-1,20251211
159819.SZ,0,20251211
```

### Signal JSON Format

```json
{
  "date": "20251211",
  "signals": {
    "159994.SZ": 1,
    "159941.SZ": -1,
    "159819.SZ": 0
  },
  "timestamp": "2025-12-11 10:00:00"
}
```

### Position JSON Format

```json
{
  "date": "20251211",
  "positions": {
    "159994.SZ": {
      "shares": 30100,
      "entry_price": 1.658,
      "entry_date": "2025-11-26",
      "cost": 49915.78
    }
  },
  "timestamp": "2025-12-11 10:00:00",
  "count": 1
}
```

### Trade Order CSV Format

```csv
date,action,symbol,shares,price,amount,commission,reason
20251211,BUY,159994.SZ,30100,1.658,-49915.78,4.99,KAMA buy signal
20251211,SELL,159941.SZ,34600,1.500,51900.00,5.19,Stop loss triggered
```

## Testing

The module includes comprehensive unit tests covering all functionality:

```bash
# Run tests
conda activate backtesting
python -m pytest etf_trend_following_v2/tests/test_io_utils.py -v

# Run with coverage
python -m pytest etf_trend_following_v2/tests/test_io_utils.py --cov=io_utils --cov-report=html
```

**Test Coverage**: 23 tests, 100% pass rate

Test categories:
- Logging configuration (2 tests)
- Signal I/O (3 tests)
- Position I/O (2 tests)
- Trade orders (2 tests)
- Performance reports (2 tests)
- Data validation (5 tests)
- Path utilities (6 tests)
- Integration workflow (1 test)

## Examples

See comprehensive usage examples in:
- `examples/io_utils_example.py`: Demonstrates all features

Run examples:
```bash
conda activate backtesting
python etf_trend_following_v2/examples/io_utils_example.py
```

## Error Handling

The module provides clear error messages and logging:

```python
# File not found
try:
    signals = load_signals('nonexistent.json')
except FileNotFoundError as e:
    print(f"Error: {e}")

# Invalid format
try:
    save_signals(signals, 'output.csv', '2025-12-11', format='invalid')
except ValueError as e:
    print(f"Error: {e}")

# Validation errors
errors = validate_ohlcv_df(df, symbol='TEST')
if errors:
    for error in errors:
        logging.error(error)
```

## Best Practices

1. **Logging**: Configure logging once at application startup
2. **Snapshots**: Use dated snapshots for historical tracking
3. **Validation**: Always validate OHLCV data before processing
4. **Paths**: Use absolute paths to avoid WSL/Windows compatibility issues
5. **Error Handling**: Check validation errors before proceeding

## Dependencies

- Python 3.9+
- pandas
- numpy
- Standard library: logging, json, csv, pathlib, re

## Implementation Notes

- All JSON files use UTF-8 encoding with indent=2 for readability
- CSV files use UTF-8 encoding
- Log files rotate daily and keep 30 days of history
- Date formats are normalized to YYYYMMDD for filenames
- Supports POSIX paths (compatible with WSL)
- Type hints for all public functions

## Integration with Other Modules

The io_utils module is designed to integrate seamlessly with other system components:

- **config_loader**: Validate configuration paths
- **data_loader**: Validate OHLCV DataFrames
- **portfolio**: Save/load position snapshots
- **signal_pipeline**: Save/load signals and trade orders
- **backtest_runner**: Generate performance reports

## Future Enhancements

Potential future features (not in current scope):
- Binary serialization (pickle/joblib) for large data
- Compression support (gzip/bz2)
- Database backend (SQLite/PostgreSQL)
- Cloud storage integration (S3/GCS)
- Real-time streaming logs

## Support

For issues or questions:
1. Check test cases for usage examples
2. Run `examples/io_utils_example.py` for demonstrations
3. Review validation error messages
4. Check log files for detailed information

---

**Status**: Production Ready ✅
**Test Coverage**: 23/23 tests passing
**Documentation**: Complete
**Last Updated**: 2025-12-11
