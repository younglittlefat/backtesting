# Strategy Signal Generators

This directory contains independent signal generators for various trading strategies. These modules are designed for efficient full-pool scanning and don't depend on backtesting.py's Strategy class.

## Available Strategies

### MACD Signal Generator (`macd.py`)

Independent MACD (Moving Average Convergence Divergence) signal generator for ETF trend following.

#### Features

- **Golden Cross (Buy)**: MACD line crosses above signal line
- **Death Cross (Sell)**: MACD line crosses below signal line
- **Optional Filters** (all disabled by default):
  - ADX trend strength filter
  - Volume confirmation filter
  - MACD slope filter
  - Continuous confirmation filter
  - Zero-axis constraint
  - Hysteresis/anti-whipsaw filter
  - Sell confirmation
  - Minimum holding period

#### Basic Usage

```python
from etf_trend_following_v2.src.strategies import MACDSignalGenerator
import pandas as pd

# Load your OHLCV data
df = pd.read_csv('your_data.csv', parse_dates=['date'])
df = df.set_index('date')

# Ensure columns are named: Open, High, Low, Close, Volume
df = df.rename(columns={
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
})

# Create baseline generator (no filters)
generator = MACDSignalGenerator()

# Calculate indicators
df_with_indicators = generator.calculate_indicators(df)

# Generate signals (1=buy, -1=sell, 0=hold)
signals = generator.generate_signals(df_with_indicators)

# Get signal for specific date
signal = generator.get_signal_for_date(df, '2025-12-01')
print(f"Signal: {signal}")  # 1, -1, or 0

# Get detailed signal information
signal_detail = generator.get_signal_for_date(df, '2025-12-01', return_details=True)
print(f"MACD: {signal_detail['macd_line']:.4f}")
print(f"Signal Line: {signal_detail['signal_line']:.4f}")
```

#### With Filters

```python
# Create generator with ADX and volume filters
generator = MACDSignalGenerator(
    fast_period=12,
    slow_period=26,
    signal_period=9,
    enable_adx_filter=True,
    adx_threshold=25,
    enable_volume_filter=True,
    volume_ratio=1.2
)

# Use the same way as baseline
df_with_indicators = generator.calculate_indicators(df)
signals = generator.generate_signals(df_with_indicators)
```

#### All Available Parameters

```python
generator = MACDSignalGenerator(
    # Core MACD parameters
    fast_period=12,           # Fast EMA period
    slow_period=26,           # Slow EMA period
    signal_period=9,          # Signal line period

    # ADX Filter
    enable_adx_filter=False,  # Enable ADX trend strength filter
    adx_period=14,            # ADX calculation period
    adx_threshold=25,         # ADX threshold

    # Volume Filter
    enable_volume_filter=False,  # Enable volume confirmation
    volume_period=20,            # Volume MA period
    volume_ratio=1.2,            # Volume amplification ratio

    # Slope Filter
    enable_slope_filter=False,   # Enable MACD slope filter
    slope_lookback=5,            # Slope lookback period

    # Confirmation Filter
    enable_confirm_filter=False, # Enable continuous confirmation
    confirm_bars=2,              # Number of bars for confirmation

    # Zero-axis Constraint
    enable_zero_axis=False,      # Enable zero-axis constraint
    zero_axis_mode='symmetric',  # Zero-axis mode

    # Hysteresis/Anti-whipsaw
    enable_hysteresis=False,     # Enable hysteresis filter
    hysteresis_mode='std',       # 'std' or 'abs'
    hysteresis_k=0.5,            # Multiplier for std mode
    hysteresis_window=20,        # Rolling window for std mode
    hysteresis_abs=0.001,        # Absolute threshold for abs mode

    # Sell-side controls
    confirm_bars_sell=0,         # Sell confirmation bars (0=disabled)
    min_hold_bars=0,             # Minimum holding period (0=disabled)
)
```

#### Configuration Export

```python
# Get current configuration
config = generator.get_config()
print(config)

# Save to JSON
import json
with open('macd_config.json', 'w') as f:
    json.dump(config, f, indent=2)

# Load from JSON and create generator
with open('macd_config.json', 'r') as f:
    config = json.load(f)
generator = MACDSignalGenerator(**config)
```

## Design Principles

1. **Independence**: No dependency on backtesting.py's Strategy class
2. **Efficiency**: Optimized for full-pool scanning of multiple ETFs
3. **Baseline First**: All filters disabled by default
4. **Configurability**: All parameters exposed and configurable
5. **Compatibility**: Python 3.9+ compatible

## Testing

Run the built-in tests:

```bash
# Test with synthetic data
python etf_trend_following_v2/src/strategies/macd.py

# Test with real ETF data
python -c "
from etf_trend_following_v2.src.strategies import MACDSignalGenerator
import pandas as pd

df = pd.read_csv('data/chinese_etf/daily/etf/510300.SH.csv', parse_dates=['trade_date'])
df = df.set_index('trade_date').sort_index()
df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})

gen = MACDSignalGenerator()
df_ind = gen.calculate_indicators(df.tail(200))
signals = gen.generate_signals(df_ind)
print(f'Buy signals: {(signals == 1).sum()}')
print(f'Sell signals: {(signals == -1).sum()}')
"
```

## Reference

Based on the existing MACD strategy implementation:
- `/mnt/d/git/backtesting/strategies/macd_cross.py`
- Adapted for standalone signal generation without backtesting.py dependency
