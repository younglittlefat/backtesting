# ETF Trend Following v2 - Scripts Directory

This directory contains shell script entry points for the ETF Trend Following v2 system. All scripts are designed to run in WSL (Ubuntu) on Windows-based project storage.

## Overview

The system provides three main operational modes:

1. **Signal Generation** (`generate_signal.sh`) - Daily production signal generation
2. **Backtesting** (`run_backtest.sh`) - Historical strategy performance testing
3. **Portfolio Management** (`manage_portfolio.sh`) - Portfolio state maintenance

## Prerequisites

### Environment Setup

- **OS**: WSL (Ubuntu 24.04) with Windows filesystem mount
- **Project Path**: `/mnt/d/git/backtesting`
- **Python**: 3.9+ (via conda)
- **Conda Environment**: `backtesting`

### Conda Environment Activation

All scripts automatically activate the `backtesting` conda environment. If the environment doesn't exist, create it:

```bash
# Create environment
conda create -n backtesting python=3.9

# Activate environment
conda activate backtesting

# Install dependencies
cd /mnt/d/git/backtesting
pip install -e '.[doc,test,dev]'
```

## Scripts Reference

### 1. generate_signal.sh - Daily Signal Generation

**Purpose**: Generate trading signals for a specific date using the full pipeline.

**Workflow**:
1. Load configuration from `config.json`
2. Scan full ETF pool and calculate strategy signals (MACD/KAMA)
3. Score and rank by momentum
4. Apply clustering for diversification
5. Execute risk checks and circuit breakers
6. Calculate position sizing
7. Generate trade orders and update portfolio snapshot

**Usage**:
```bash
./generate_signal.sh [OPTIONS]
```

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Configuration file path | `../config/example_config.json` |
| `--as-of-date DATE` | Signal date (YYYY-MM-DD) | Today |
| `--portfolio PATH` | Portfolio snapshot for state recovery | None |
| `--output-dir DIR` | Output directory | From config.json |
| `--dry-run [true\|false]` | Run without saving files | `true` |
| `--log-level LEVEL` | Logging level (DEBUG\|INFO\|WARNING\|ERROR) | `INFO` |
| `--help` | Show help message | - |

**Examples**:

```bash
# Generate today's signals (dry-run, no files saved)
./generate_signal.sh

# Generate signals for specific date
./generate_signal.sh --as-of-date 2025-12-10

# Production run (save output files)
./generate_signal.sh --dry-run false --output-dir ../output/signals

# Use custom configuration
./generate_signal.sh --config ../config/custom_config.json \
                     --as-of-date 2025-12-10 \
                     --dry-run false

# Resume from previous portfolio state
./generate_signal.sh --portfolio ../positions/portfolio_20251209.json \
                     --as-of-date 2025-12-10 \
                     --dry-run false
```

**Output Files** (when `--dry-run false`):
- `signals/signals_{date}.csv` - Buy/sell signals with strategy indicators
- `signals/scores_{date}.csv` - Momentum scores and rankings
- `positions/positions_{date}.json` - Updated portfolio snapshot
- `signals/trades_{date}.csv` - Trade orders to execute
- `logs/signal_pipeline_{date}.log` - Detailed execution log

---

### 2. run_backtest.sh - Portfolio Backtesting

**Purpose**: Run comprehensive portfolio-level backtesting with proper signal generation and rebalancing.

**Workflow**:
1. Load configuration and ETF universe
2. Day-by-day rolling signal calculation (avoid lookahead bias)
3. Simulate portfolio rebalancing with position sizing
4. Apply risk management (clustering, circuit breakers, ATR stops)
5. Calculate performance metrics
6. Generate reports and visualizations

**Usage**:
```bash
./run_backtest.sh [OPTIONS]
```

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Configuration file path | `../config/example_config.json` |
| `--start-date DATE` | Backtest start date (YYYY-MM-DD) | **Required** |
| `--end-date DATE` | Backtest end date (YYYY-MM-DD) | **Required** |
| `--output-dir DIR` | Output directory | `../output/backtest` |
| `--initial-capital NUM` | Initial capital | `1000000` |
| `--log-level LEVEL` | Logging level | `INFO` |
| `--help` | Show help message | - |

**Examples**:

```bash
# Basic 2-year backtest
./run_backtest.sh --start-date 2023-01-01 --end-date 2024-12-31

# Custom configuration and output directory
./run_backtest.sh --config ../config/custom_config.json \
                  --start-date 2023-01-01 \
                  --end-date 2024-12-31 \
                  --output-dir ../output/backtest_2024

# High capital backtest
./run_backtest.sh --start-date 2023-01-01 \
                  --end-date 2024-12-31 \
                  --initial-capital 10000000 \
                  --output-dir ../output/backtest_10M

# Debug mode with verbose logging
./run_backtest.sh --start-date 2023-01-01 \
                  --end-date 2024-12-31 \
                  --log-level DEBUG
```

**Output Files**:
- `equity_curve.csv` - Daily portfolio value time series
- `trades.csv` - Complete trade log with entry/exit details
- `positions.csv` - Position history over time
- `performance_summary.json` - Key performance metrics
- `performance_report.html` - Interactive visualization dashboard
- `cluster_exposure.csv` - Diversification and cluster metrics
- `logs/backtest_{start}_{end}.log` - Execution log

**Performance Metrics**:
- **Returns**: Total Return, Annualized Return, CAGR
- **Risk-Adjusted**: Sharpe Ratio, Sortino Ratio, Calmar Ratio
- **Risk**: Maximum Drawdown, Volatility, Drawdown Duration
- **Trading**: Win Rate, Profit Factor, Avg Trade P&L, Turnover Rate
- **Portfolio**: Avg Positions, Cluster Exposure, Avg Holding Period

---

### 3. manage_portfolio.sh - Portfolio Management Utility

**Purpose**: Manage portfolio snapshots and perform maintenance operations.

**Commands**:
| Command | Description |
|---------|-------------|
| `init` | Initialize a new portfolio |
| `rollback` | Rollback to a previous snapshot |
| `inject` | Inject additional capital |
| `withdraw` | Withdraw capital (placeholder) |
| `list` | List all portfolio snapshots |
| `show` | Show portfolio snapshot details |
| `validate` | Validate portfolio consistency |
| `help` | Show help message |

**Usage**:
```bash
./manage_portfolio.sh COMMAND [OPTIONS]
```

**Common Options**:
| Option | Description |
|--------|-------------|
| `--portfolio PATH` | Portfolio snapshot JSON path |
| `--date DATE` | Portfolio date (YYYY-MM-DD) |
| `--capital AMOUNT` | Initial capital or injection/withdrawal amount |
| `--output PATH` | Output path for new snapshot |
| `--dir DIR` | Directory for portfolio snapshots (default: `../output/positions`) |

**Examples**:

```bash
# Initialize new portfolio
./manage_portfolio.sh init \
    --capital 1000000 \
    --date 2025-01-01 \
    --output ../positions/portfolio_20250101.json

# List all snapshots in directory
./manage_portfolio.sh list --dir ../positions

# Show snapshot details
./manage_portfolio.sh show --portfolio ../positions/portfolio_20251210.json

# Validate portfolio consistency
./manage_portfolio.sh validate --portfolio ../positions/portfolio_current.json

# Rollback to previous date
./manage_portfolio.sh rollback \
    --date 2025-12-10 \
    --dir ../positions \
    --output ../positions/portfolio_current.json

# Inject additional capital
./manage_portfolio.sh inject \
    --portfolio ../positions/portfolio_current.json \
    --capital 500000 \
    --output ../positions/portfolio_updated.json
```

---

## Configuration Management

### Configuration File Structure

All scripts use a unified `config.json` configuration file. See `../config/example_config.json` for the complete schema.

**Key Sections**:
- `env`: Environment paths and directories
- `modes`: Run mode and execution parameters
- `universe`: ETF pool and filtering criteria
- `strategies`: Strategy configurations (MACD/KAMA/Combo)
- `scoring`: Momentum scoring and ranking
- `clustering`: Diversification and cluster limits
- `risk`: Risk management (ATR stops, circuit breakers)
- `position_sizing`: Position sizing and constraints
- `execution`: Order execution and matching
- `io`: Input/output paths and logging

### Creating Custom Configurations

```bash
# Copy example config
cp ../config/example_config.json ../config/my_config.json

# Edit configuration
nano ../config/my_config.json

# Use custom config with scripts
./generate_signal.sh --config ../config/my_config.json
./run_backtest.sh --config ../config/my_config.json --start-date 2023-01-01 --end-date 2024-12-31
```

---

## Common Workflows

### Daily Production Signal Generation

```bash
#!/bin/bash
# Daily production workflow

# 1. Generate signals for today
./generate_signal.sh \
    --config ../config/production.json \
    --portfolio ../positions/portfolio_current.json \
    --output-dir ../output/signals \
    --dry-run false

# 2. Validate generated signals
./manage_portfolio.sh validate --portfolio ../output/positions/positions_$(date +%Y%m%d).json

# 3. Review trade orders
cat ../output/signals/trades_$(date +%Y%m%d).csv
```

### Strategy Research and Backtesting

```bash
#!/bin/bash
# Strategy research workflow

# 1. Create experiment configuration
cp ../config/example_config.json ../config/exp_kama_baseline.json

# Edit strategy parameters in exp_kama_baseline.json
# Set strategy type to "kama", disable all filters

# 2. Run backtest
./run_backtest.sh \
    --config ../config/exp_kama_baseline.json \
    --start-date 2023-01-01 \
    --end-date 2024-12-31 \
    --output-dir ../output/exp_kama_baseline

# 3. Review results
cat ../output/exp_kama_baseline/performance_summary.json
open ../output/exp_kama_baseline/performance_report.html  # On Windows: explorer.exe
```

### Portfolio Lifecycle Management

```bash
#!/bin/bash
# Portfolio lifecycle management

# 1. Initialize new portfolio
./manage_portfolio.sh init \
    --capital 1000000 \
    --date 2025-01-01 \
    --output ../positions/portfolio_20250101.json

# 2. Run signals for several days
for date in 2025-01-02 2025-01-03 2025-01-04; do
    ./generate_signal.sh \
        --as-of-date $date \
        --portfolio ../positions/portfolio_$(date -d "$date - 1 day" +%Y%m%d).json \
        --dry-run false
done

# 3. List all snapshots
./manage_portfolio.sh list --dir ../positions

# 4. Validate latest snapshot
latest=$(ls -t ../positions/portfolio_*.json | head -1)
./manage_portfolio.sh validate --portfolio "$latest"
```

---

## Troubleshooting

### Common Issues

**1. Conda environment not found**
```bash
# Create the environment
conda create -n backtesting python=3.9
conda activate backtesting
pip install -e /mnt/d/git/backtesting
```

**2. Module import errors**
```bash
# Verify Python path
cd /mnt/d/git/backtesting/etf_trend_following_v2
python -c "import sys; sys.path.insert(0, '.'); from src.signal_pipeline import run_daily_signal"

# If fails, reinstall package
pip install -e /mnt/d/git/backtesting --force-reinstall
```

**3. Configuration file not found**
```bash
# Check config file exists
ls ../config/example_config.json

# Provide absolute path if needed
./generate_signal.sh --config /mnt/d/git/backtesting/etf_trend_following_v2/config/example_config.json
```

**4. Data files missing**
```bash
# Verify data directory from config
cat ../config/example_config.json | grep data_dir

# Ensure ETF pool file exists
ls /mnt/d/git/backtesting/results/trend_etf_pool.csv
```

**5. Permission denied**
```bash
# Make scripts executable
chmod +x *.sh
```

### Debug Mode

Run any script with `--log-level DEBUG` for detailed execution logs:

```bash
./generate_signal.sh --log-level DEBUG
./run_backtest.sh --start-date 2023-01-01 --end-date 2024-12-31 --log-level DEBUG
```

---

## Performance Tips

### 1. Optimize Data Loading

Use smaller date ranges for faster backtests:
```bash
# Fast 3-month test
./run_backtest.sh --start-date 2024-10-01 --end-date 2024-12-31
```

### 2. Parallel Backtests

Run multiple configurations in parallel:
```bash
# Terminal 1
./run_backtest.sh --config config1.json --start-date 2023-01-01 --end-date 2024-12-31 --output-dir out1 &

# Terminal 2
./run_backtest.sh --config config2.json --start-date 2023-01-01 --end-date 2024-12-31 --output-dir out2 &

# Wait for all to complete
wait
```

### 3. Use Dry-Run for Testing

Always test with `--dry-run true` before production:
```bash
# Test first
./generate_signal.sh --dry-run true

# If OK, run production
./generate_signal.sh --dry-run false
```

---

## Integration with Existing Tools

### Compatibility with backtesting.py

This system uses the `backtesting.py` library but extends it with portfolio-level features:

- **Signal Generation**: Standalone strategy generators (not `Strategy` subclasses)
- **Position Sizing**: Portfolio-level volatility weighting
- **Risk Management**: Clustering, circuit breakers, and T+1 restrictions
- **Multi-Asset**: Simultaneous multi-ETF tracking

### Using with Existing Strategies

To integrate with existing `backtesting.py` strategies:

1. **Convert Strategy to Signal Generator**: Extract `init()` and `next()` logic
2. **Add to strategies/**: Create new strategy module (e.g., `strategies/my_strategy.py`)
3. **Update config.json**: Add strategy type to `strategies` section
4. **Test**: Run with `generate_signal.sh` or `run_backtest.sh`

Example: See `src/strategies/kama.py` for reference implementation.

---

## Related Documentation

- **Configuration**: `../config/CONFIG_STRUCTURE.md`
- **Signal Pipeline**: `../src/SIGNAL_PIPELINE_README.md`
- **Portfolio Module**: `../src/README_portfolio.md`
- **Strategy Development**: `../src/strategies/README.md`
- **Risk Management**: `../src/README_risk.md`
- **Position Sizing**: `../src/README_position_sizing.md`

---

## Support and Contribution

For questions or issues:
1. Check existing documentation in `../src/` directory
2. Review example configurations in `../config/`
3. Examine test cases in `../tests/`
4. See project root `/mnt/d/git/backtesting/CLAUDE.md` for system overview

---

**Last Updated**: 2025-12-11
**Author**: Claude
**Version**: 1.0.0
