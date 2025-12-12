# Data Loader Module

## Overview

The `data_loader.py` module provides comprehensive functionality for loading, filtering, and preprocessing ETF OHLCV (Open, High, Low, Close, Volume) data for the ETF trend following system.

## Features

- **Single and batch ETF data loading** from CSV files
- **Adjusted price support** (uses `adj_open`, `adj_high`, `adj_low`, `adj_close` when available)
- **Date range filtering** for backtesting specific periods
- **Liquidity filtering** based on trading amount and volume
- **Data quality validation** (missing values, duplicate dates, price consistency)
- **Date alignment** across multiple ETFs (intersection or union methods)
- **Robust error handling** with skip_errors option for batch loading

## Data Format

### Input CSV Format

The module expects CSV files in the following format (from TuShare):

```csv
trade_date,instrument_name,open,high,low,close,pre_close,change,pct_chg,volume,amount,adj_factor,adj_open,adj_high,adj_low,adj_close
20200102,,1.1130,1.1500,1.1130,1.1480,1.1120,0.0360,3.2374,1691,191.79,1.032374,1.149032,1.187230,1.149032,1.185165
```

### Output DataFrame Format

All functions return pandas DataFrames with:
- **Index**: DatetimeIndex (column name: 'date')
- **Columns**: `['open', 'high', 'low', 'close', 'volume', 'amount']`
- **Prices**: Adjusted prices by default (if available)

## API Reference

### Core Functions

#### `load_single_etf()`

Load OHLCV data for a single ETF.

```python
def load_single_etf(
    symbol: str,
    data_dir: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_adj: bool = True
) -> pd.DataFrame
```

**Parameters:**
- `symbol`: ETF symbol (e.g., '159915.SZ' or '159915')
- `data_dir`: Directory containing ETF CSV files
- `start_date`: Start date in 'YYYY-MM-DD' format (inclusive)
- `end_date`: End date in 'YYYY-MM-DD' format (inclusive)
- `use_adj`: Whether to use adjusted prices (default: True)

**Returns:** DataFrame with datetime index and OHLCV columns

**Example:**
```python
df = load_single_etf(
    symbol='159915.SZ',
    data_dir='data/chinese_etf/daily',
    start_date='2020-01-01',
    end_date='2020-12-31'
)
```

#### `load_universe()`

Load OHLCV data for multiple ETFs.

```python
def load_universe(
    symbols: List[str],
    data_dir: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_adj: bool = True,
    skip_errors: bool = True
) -> Dict[str, pd.DataFrame]
```

**Parameters:**
- `symbols`: List of ETF symbols
- `data_dir`: Directory containing ETF CSV files
- `start_date`: Start date in 'YYYY-MM-DD' format
- `end_date`: End date in 'YYYY-MM-DD' format
- `use_adj`: Whether to use adjusted prices
- `skip_errors`: If True, skip symbols that fail to load; if False, raise exception

**Returns:** Dictionary mapping symbol to DataFrame

**Example:**
```python
symbols = ['159915.SZ', '159919.SZ', '510300.SH']
data_dict = load_universe(
    symbols=symbols,
    data_dir='data/chinese_etf/daily',
    start_date='2020-01-01',
    skip_errors=True
)
```

#### `load_universe_from_file()`

Load ETF universe from a pool file (CSV).

```python
def load_universe_from_file(
    pool_file: str,
    data_dir: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_adj: bool = True,
    skip_errors: bool = True,
    symbol_column: str = 'ts_code'
) -> Dict[str, pd.DataFrame]
```

**Parameters:**
- `pool_file`: Path to CSV file containing symbol list
- `data_dir`: Directory containing ETF CSV files
- `start_date`: Start date in 'YYYY-MM-DD' format
- `end_date`: End date in 'YYYY-MM-DD' format
- `use_adj`: Whether to use adjusted prices
- `skip_errors`: If True, skip symbols that fail to load
- `symbol_column`: Name of the column containing symbols (default: 'ts_code')

**Returns:** Dictionary mapping symbol to DataFrame

**Example:**
```python
data_dict = load_universe_from_file(
    pool_file='results/trend_etf_pool.csv',
    data_dir='data/chinese_etf/daily',
    start_date='2020-01-01',
    end_date='2020-12-31'
)
```

### Filtering Functions

#### `filter_by_liquidity()`

Filter ETFs by liquidity criteria.

```python
def filter_by_liquidity(
    data_dict: Dict[str, pd.DataFrame],
    min_amount: Optional[float] = None,
    min_volume: Optional[float] = None,
    lookback_days: int = 20,
    min_valid_days: int = 15
) -> Dict[str, pd.DataFrame]
```

**Parameters:**
- `data_dict`: Dictionary of symbol -> DataFrame
- `min_amount`: Minimum average daily trading amount (in yuan)
- `min_volume`: Minimum average daily trading volume (in shares)
- `lookback_days`: Number of days to calculate average (default: 20)
- `min_valid_days`: Minimum number of valid days required in lookback period

**Returns:** Filtered dictionary with only liquid ETFs

**Example:**
```python
liquid_dict = filter_by_liquidity(
    data_dict,
    min_amount=50_000_000,  # 50M yuan
    lookback_days=20
)
```

#### `validate_data_quality()`

Validate data quality and filter out problematic symbols.

```python
def validate_data_quality(
    data_dict: Dict[str, pd.DataFrame],
    min_data_points: int = 100,
    max_missing_pct: float = 0.05
) -> Dict[str, pd.DataFrame]
```

**Parameters:**
- `data_dict`: Dictionary of symbol -> DataFrame
- `min_data_points`: Minimum number of data points required
- `max_missing_pct`: Maximum percentage of missing values allowed

**Returns:** Dictionary with only valid symbols

**Example:**
```python
valid_dict = validate_data_quality(
    data_dict,
    min_data_points=100,
    max_missing_pct=0.05
)
```

### Alignment Functions

#### `align_dates()`

Align dates across all ETFs in the universe.

```python
def align_dates(
    data_dict: Dict[str, pd.DataFrame],
    method: str = 'intersection',
    fill_method: Optional[str] = 'ffill',
    max_fill_days: int = 5
) -> Dict[str, pd.DataFrame]
```

**Parameters:**
- `data_dict`: Dictionary of symbol -> DataFrame
- `method`: 'intersection' (only common dates) or 'union' (all dates)
- `fill_method`: How to fill missing values ('ffill', 'bfill', None)
- `max_fill_days`: Maximum number of days to forward/backward fill

**Returns:** Dictionary with aligned DataFrames

**Example:**
```python
# Use intersection method (recommended for backtesting)
aligned_dict = align_dates(data_dict, method='intersection')

# Use union method with forward fill
aligned_dict = align_dates(
    data_dict,
    method='union',
    fill_method='ffill',
    max_fill_days=5
)
```

### Utility Functions

#### `get_data_date_range()`

Get the overall date range covered by the data.

```python
def get_data_date_range(
    data_dict: Dict[str, pd.DataFrame]
) -> tuple
```

**Returns:** Tuple of (min_date, max_date)

**Example:**
```python
min_date, max_date = get_data_date_range(data_dict)
print(f"Date range: {min_date} to {max_date}")
```

## Complete Pipeline Example

Here's a complete example of loading and preprocessing ETF data:

```python
from data_loader import (
    load_universe_from_file,
    filter_by_liquidity,
    validate_data_quality,
    align_dates,
    get_data_date_range
)

# Step 1: Load from pool file
data_dict = load_universe_from_file(
    pool_file='results/trend_etf_pool.csv',
    data_dir='data/chinese_etf/daily',
    start_date='2020-01-01',
    end_date='2020-12-31',
    skip_errors=True
)
print(f"Loaded {len(data_dict)} symbols")

# Step 2: Filter by liquidity
liquid_dict = filter_by_liquidity(
    data_dict,
    min_amount=50_000_000,  # 50M yuan
    lookback_days=20
)
print(f"After liquidity filter: {len(liquid_dict)} symbols")

# Step 3: Validate data quality
valid_dict = validate_data_quality(
    liquid_dict,
    min_data_points=150,
    max_missing_pct=0.05
)
print(f"After quality validation: {len(valid_dict)} symbols")

# Step 4: Align dates
aligned_dict = align_dates(valid_dict, method='intersection')
print(f"After date alignment: {len(aligned_dict)} symbols")

# Get final statistics
min_date, max_date = get_data_date_range(aligned_dict)
num_days = len(list(aligned_dict.values())[0])
print(f"Final dataset: {len(aligned_dict)} symbols, {num_days} trading days")
print(f"Date range: {min_date} to {max_date}")
```

## Data Validation

The module performs several data validation checks:

1. **Price Validation**: Ensures all prices are positive
2. **High/Low Consistency**: Verifies high >= low, swaps if necessary
3. **Date Sorting**: Ensures data is sorted by date
4. **Duplicate Dates**: Removes duplicate date entries
5. **Missing Values**: Checks for excessive missing data

## Error Handling

- **FileNotFoundError**: Raised when data file or pool file doesn't exist
- **ValueError**: Raised for invalid data or empty datasets
- **skip_errors parameter**: When True, logs warnings and continues; when False, raises exceptions

## Performance Considerations

- **Batch Loading**: Use `load_universe()` or `load_universe_from_file()` for efficient batch loading
- **Date Filtering**: Apply date filters early to reduce memory usage
- **Liquidity Filtering**: Filter by liquidity before alignment to reduce computation
- **Intersection Method**: Recommended for backtesting to ensure all symbols have data on same dates

## File Path Handling

The module handles both direct paths and the 'etf' subdirectory structure:

```
data/chinese_etf/daily/
├── etf/
│   ├── 159915.SZ.csv
│   ├── 159919.SZ.csv
│   └── ...
```

Symbol format flexibility:
- `'159915.SZ'` - Full format with exchange suffix
- `'159915'` - Short format (will search for .SZ or .SH)

## Logging

The module uses Python's logging framework. Configure logging level to control verbosity:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Log levels:
- **INFO**: Summary statistics and progress
- **WARNING**: Data issues and fallbacks
- **DEBUG**: Detailed processing information

## Testing

Run the test suite:

```bash
# Using pytest
pytest etf_trend_following_v2/tests/test_data_loader.py -v

# Using manual test script
python etf_trend_following_v2/test_manual.py
```

Run examples:

```bash
python etf_trend_following_v2/examples/data_loader_example.py
```

## Dependencies

- pandas >= 1.3.0
- numpy >= 1.20.0
- Python >= 3.9

## Notes

- **Adjusted Prices**: By default, the module uses adjusted prices (adj_close, adj_open, etc.) when available. This accounts for splits and dividends.
- **T+1 Constraint**: The module loads historical data; T+1 trading constraints should be handled in the strategy/execution layer.
- **Future Function Avoidance**: All filtering and validation use only historical data up to each point in time.
- **WSL Compatibility**: File paths use POSIX format, compatible with WSL mounted drives.

## Future Enhancements

Potential future additions:
- Support for intraday data (minute/tick level)
- Real-time data streaming integration
- Caching mechanism for frequently accessed data
- Parallel loading for large universes
- Support for additional data sources beyond TuShare
