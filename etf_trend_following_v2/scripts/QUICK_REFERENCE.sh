#!/bin/bash
# QUICK REFERENCE - ETF Trend Following v2 Scripts
# Copy-paste these commands for common operations

# ============================================================================
# 1. DAILY SIGNAL GENERATION
# ============================================================================

# Test run (dry-run, no files saved)
./generate_signal.sh

# Production run for today
./generate_signal.sh --dry-run false

# Specific date with portfolio recovery
./generate_signal.sh --as-of-date 2025-12-10 \
                     --portfolio ../positions/portfolio_20251209.json \
                     --dry-run false

# Custom configuration
./generate_signal.sh --config ../config/production.json \
                     --dry-run false \
                     --output-dir ../output/signals

# ============================================================================
# 2. BACKTESTING
# ============================================================================

# Basic 2-year backtest
./run_backtest.sh --start-date 2023-01-01 --end-date 2024-12-31

# Experiment with custom config
./run_backtest.sh --config ../config/exp_kama_baseline.json \
                  --start-date 2023-01-01 \
                  --end-date 2024-12-31 \
                  --output-dir ../output/exp_kama_baseline

# Quick 3-month test
./run_backtest.sh --start-date 2024-10-01 --end-date 2024-12-31

# High capital backtest
./run_backtest.sh --start-date 2023-01-01 \
                  --end-date 2024-12-31 \
                  --initial-capital 10000000

# Debug mode
./run_backtest.sh --start-date 2023-01-01 \
                  --end-date 2024-12-31 \
                  --log-level DEBUG

# ============================================================================
# 3. PORTFOLIO MANAGEMENT
# ============================================================================

# Initialize new portfolio
./manage_portfolio.sh init \
    --capital 1000000 \
    --date 2025-01-01 \
    --output ../positions/portfolio_20250101.json

# List all snapshots
./manage_portfolio.sh list --dir ../positions

# Show snapshot details
./manage_portfolio.sh show --portfolio ../positions/portfolio_20251210.json

# Validate portfolio
./manage_portfolio.sh validate --portfolio ../positions/portfolio_current.json

# Rollback to previous state
./manage_portfolio.sh rollback \
    --date 2025-12-10 \
    --dir ../positions \
    --output ../positions/portfolio_restored.json

# Inject capital
./manage_portfolio.sh inject \
    --portfolio ../positions/portfolio_current.json \
    --capital 500000 \
    --output ../positions/portfolio_updated.json

# ============================================================================
# 4. COMMON WORKFLOWS
# ============================================================================

# Daily production workflow
./generate_signal.sh --config ../config/production.json \
                     --portfolio ../positions/portfolio_current.json \
                     --dry-run false
./manage_portfolio.sh validate --portfolio ../output/positions/positions_$(date +%Y%m%d).json

# Strategy research workflow
cp ../config/example_config.json ../config/exp_new_strategy.json
# Edit exp_new_strategy.json
./run_backtest.sh --config ../config/exp_new_strategy.json \
                  --start-date 2023-01-01 --end-date 2024-12-31 \
                  --output-dir ../output/exp_new_strategy

# Multi-day signal generation
for date in 2025-01-02 2025-01-03 2025-01-04; do
    ./generate_signal.sh --as-of-date $date --dry-run false
done

# ============================================================================
# 5. HELP COMMANDS
# ============================================================================

./generate_signal.sh --help
./run_backtest.sh --help
./manage_portfolio.sh help

# ============================================================================
# 6. DEBUGGING
# ============================================================================

# Check conda environment
conda activate backtesting
python -c "import sys; print(sys.version)"

# Test Python module imports
python -c "import sys; sys.path.insert(0, '/mnt/d/git/backtesting/etf_trend_following_v2'); from src.signal_pipeline import run_daily_signal"

# Verify configuration
cat ../config/example_config.json | python -m json.tool

# Check data files
ls /mnt/d/git/backtesting/results/trend_etf_pool.csv
ls /mnt/d/git/backtesting/data/chinese_etf/daily/

# ============================================================================
# 7. FILE LOCATIONS
# ============================================================================

# Configuration files
cd ../config
ls -lh *.json

# Output files
cd ../output
ls -lh signals/ positions/ backtest/

# Logs
cd ../output/logs
tail -f signal_pipeline_*.log

# ============================================================================
# END OF QUICK REFERENCE
# ============================================================================
