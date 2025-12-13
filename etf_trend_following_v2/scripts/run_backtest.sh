#!/bin/bash
################################################################################
# run_backtest.sh - Batch Backtesting Script for ETF Trend Following v2
#
# Purpose:
#   Unified entry point for portfolio-level backtesting workflow:
#   1. Load configuration and ETF universe
#   2. Run day-by-day rolling signal calculation (avoid lookahead bias)
#   3. Simulate portfolio rebalancing with proper position sizing
#   4. Apply risk management (clustering, circuit breakers, ATR stops)
#   5. Calculate comprehensive performance metrics
#   6. Generate visualization and detailed reports
#
# Usage:
#   ./run_backtest.sh [OPTIONS]
#
# Options:
#   --config PATH         Path to config.json (default: ../config/example_config.json)
#   --start-date DATE     Backtest start date YYYY-MM-DD (required)
#   --end-date DATE       Backtest end date YYYY-MM-DD (required)
#   --output-dir DIR      Output directory for results (default: ../output/backtest)
#   --initial-capital NUM Initial capital (default: 1,000,000)
#   --log-level LEVEL     Logging level: DEBUG|INFO|WARNING|ERROR (default: INFO)
#   --help                Show this help message
#
# Examples:
#   # Run 2-year backtest with default config
#   ./run_backtest.sh --start-date 2023-01-01 --end-date 2024-12-31
#
#   # Custom config and output directory
#   ./run_backtest.sh --config ../config/custom_config.json \
#                     --start-date 2023-01-01 --end-date 2024-12-31 \
#                     --output-dir /mnt/d/git/backtesting/results/backtest_2024
#
#   # Backtest with different initial capital
#   ./run_backtest.sh --start-date 2023-01-01 --end-date 2024-12-31 \
#                     --initial-capital 5000000
#
# Output Files:
#   - equity_curve.csv                    # Daily portfolio value
#   - trades.csv                          # All executed trades
#   - positions.csv                       # Position history
#   - performance_summary.json            # Key metrics (Sharpe, max DD, etc.)
#   - performance_report.html             # Interactive visualization
#   - cluster_exposure.csv                # Diversification metrics
#   - logs/backtest_{start}_{end}.log     # Execution log
#
# Performance Metrics:
#   - Total Return, Annualized Return, CAGR
#   - Sharpe Ratio, Sortino Ratio, Calmar Ratio
#   - Maximum Drawdown (value and duration)
#   - Win Rate, Profit Factor, Average Trade P&L
#   - Turnover Rate, Cluster Exposure, Holding Period
#
# Author: Claude
# Date: 2025-12-11
################################################################################

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# ============================================================================
# Script Configuration
# ============================================================================

# Determine script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ETF_V2_DIR="$PROJECT_ROOT/etf_trend_following_v2"

# Conda configuration
CONDA_PATH="/home/zijunliu/miniforge3/condabin/conda"
CONDA_ENV="backtesting"

# Default parameters
DEFAULT_CONFIG="$ETF_V2_DIR/config/example_config.json"
DEFAULT_OUTPUT_DIR="$ETF_V2_DIR/output/backtest"
DEFAULT_INITIAL_CAPITAL=1000000
DEFAULT_LOG_LEVEL="INFO"

# ============================================================================
# Utility Functions
# ============================================================================

log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $*"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

show_help() {
    cat << EOF
ETF Trend Following v2 - Batch Backtesting Script

Usage: $0 [OPTIONS]

Required Options:
  --start-date DATE     Backtest start date (YYYY-MM-DD)
  --end-date DATE       Backtest end date (YYYY-MM-DD)

Optional Parameters:
  --config PATH         Path to config.json (default: ../config/example_config.json)
  --output-dir DIR      Output directory (default: ../output/backtest)
  --initial-capital NUM Initial capital (default: 1,000,000)
  --log-level LEVEL     Logging level: DEBUG|INFO|WARNING|ERROR (default: INFO)
  --help                Show this help message

Examples:
  # Basic backtest
  $0 --start-date 2023-01-01 --end-date 2024-12-31

  # Custom configuration
  $0 --config ../config/custom_config.json \\
     --start-date 2023-01-01 --end-date 2024-12-31 \\
     --output-dir ../output/custom_backtest

  # High capital backtest
  $0 --start-date 2023-01-01 --end-date 2024-12-31 \\
     --initial-capital 10000000

For more details, see: $ETF_V2_DIR/src/README_portfolio.md
EOF
}

activate_conda_env() {
    log_info "Activating conda environment: $CONDA_ENV"

    # Source conda initialization script
    if [[ ! -f "$CONDA_PATH" ]]; then
        log_error "Conda not found at $CONDA_PATH"
        log_error "Please update CONDA_PATH in the script"
        exit 1
    fi

    # Initialize conda for bash
    eval "$("$CONDA_PATH" shell.bash hook 2>/dev/null)"

    # Activate environment
    if ! conda activate "$CONDA_ENV" 2>/dev/null; then
        log_error "Failed to activate conda environment: $CONDA_ENV"
        log_error "Please ensure the environment exists: conda create -n $CONDA_ENV python=3.9"
        exit 1
    fi

    log_info "Conda environment activated: $(conda info --envs | grep '*' | awk '{print $1}')"
}

verify_config_file() {
    local config_path="$1"

    if [[ ! -f "$config_path" ]]; then
        log_error "Configuration file not found: $config_path"
        log_error "Please provide a valid config file using --config option"
        exit 1
    fi

    log_info "Using configuration file: $config_path"
}

validate_date_format() {
    local date_str="$1"
    local date_name="$2"

    if [[ ! "$date_str" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        log_error "Invalid $date_name format: $date_str"
        log_error "Expected format: YYYY-MM-DD (e.g., 2023-01-01)"
        exit 1
    fi
}

# ============================================================================
# Parse Command Line Arguments
# ============================================================================

CONFIG_PATH="$DEFAULT_CONFIG"
START_DATE=""
END_DATE=""
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
INITIAL_CAPITAL="$DEFAULT_INITIAL_CAPITAL"
LOG_LEVEL="$DEFAULT_LOG_LEVEL"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --initial-capital)
            INITIAL_CAPITAL="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# ============================================================================
# Pre-flight Checks
# ============================================================================

log_info "=========================================="
log_info "ETF Trend Following v2 - Batch Backtest"
log_info "=========================================="

# Validate required parameters
if [[ -z "$START_DATE" ]]; then
    log_error "Missing required parameter: --start-date"
    show_help
    exit 1
fi

if [[ -z "$END_DATE" ]]; then
    log_error "Missing required parameter: --end-date"
    show_help
    exit 1
fi

# Validate date formats
validate_date_format "$START_DATE" "start-date"
validate_date_format "$END_DATE" "end-date"

# Verify configuration file
verify_config_file "$CONFIG_PATH"

# Create output directory
mkdir -p "$OUTPUT_DIR"
log_info "Output directory: $OUTPUT_DIR"

# Activate conda environment
activate_conda_env

# Check if Python module is accessible
if ! python -c "import sys; sys.path.insert(0, '$ETF_V2_DIR'); from src.portfolio_backtest_runner import run_portfolio_backtest" 2>/dev/null; then
    log_error "Failed to import portfolio_backtest_runner module"
    log_error "Please ensure the project is properly set up"
    exit 1
fi

# ============================================================================
# Build Python Command
# ============================================================================

PYTHON_CMD="python -c \"
import sys
sys.path.insert(0, '$ETF_V2_DIR')
from src.portfolio_backtest_runner import run_portfolio_backtest
import logging
import json
from pathlib import Path

logging.basicConfig(
    level=logging.$LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    print('Starting backtest...')
    print(f'Period: $START_DATE to $END_DATE')
    print(f'Initial Capital: {float($INITIAL_CAPITAL):,.0f}')
    print()

    results = run_portfolio_backtest(
        config_path='$CONFIG_PATH',
        start_date='$START_DATE',
        end_date='$END_DATE',
        output_dir='$OUTPUT_DIR',
        initial_capital=float($INITIAL_CAPITAL)
    )

    # Print summary
    print()
    print('=' * 80)
    print('BACKTEST RESULTS SUMMARY')
    print('=' * 80)

    stats = results.get('stats', {})

    print(f'Backtest Period: $START_DATE to $END_DATE')
    print(f'Initial Capital: {float($INITIAL_CAPITAL):,.0f}')
    print()

    print('Performance Metrics:')
    print(f'  Total Return: {stats.get(\\\"total_return\\\", 0)*100:.2f}%')
    print(f'  Annualized Return: {stats.get(\\\"annualized_return\\\", 0)*100:.2f}%')
    print(f'  Sharpe Ratio: {stats.get(\\\"sharpe_ratio\\\", 0):.2f}')
    print(f'  Sortino Ratio: {stats.get(\\\"sortino_ratio\\\", 0):.2f}')
    print(f'  Calmar Ratio: {stats.get(\\\"calmar_ratio\\\", 0):.2f}')
    print()

    print('Risk Metrics:')
    print(f'  Maximum Drawdown: {stats.get(\\\"max_drawdown\\\", 0)*100:.2f}%')
    print(f'  Drawdown Start: {stats.get(\\\"dd_start\\\", \\\"N/A\\\")}')
    print(f'  Drawdown End: {stats.get(\\\"dd_end\\\", \\\"N/A\\\")}')
    print(f'  Volatility (Annual): {stats.get(\\\"volatility\\\", 0)*100:.2f}%')
    print()

    print('Trading Statistics:')
    print(f'  Total Trades: {stats.get(\\\"num_trades\\\", 0)}')
    print(f'  Win Rate: {stats.get(\\\"win_rate\\\", 0)*100:.1f}%')
    print(f'  Profit Factor: {stats.get(\\\"profit_factor\\\", 0):.2f}')
    print(f'  Average Trade P&L: {stats.get(\\\"avg_trade_pnl\\\", 0):,.2f}')
    print(f'  Average Holding Period: {stats.get(\\\"avg_holding_period\\\", 0):.1f} days')
    print(f'  Turnover Rate: {stats.get(\\\"turnover_rate\\\", 0)*100:.1f}%')
    print()

    print('Portfolio Characteristics:')
    print(f'  Average Positions: {stats.get(\\\"avg_positions\\\", 0):.1f}')
    print(f'  Max Positions: {stats.get(\\\"max_positions\\\", 0)}')
    print(f'  Average Cluster Exposure: {stats.get(\\\"avg_cluster_exposure\\\", 0):.2f}')
    print('=' * 80)

    # List output files
    output_path = Path('$OUTPUT_DIR')
    print()
    print('Output Files:')

    files_to_check = [
        'equity_curve.csv',
        'trades.csv',
        'positions.csv',
        'performance_summary.json',
        'cluster_exposure.csv'
    ]

    for filename in files_to_check:
        filepath = output_path / filename
        if filepath.exists():
            print(f'  ✓ {filepath}')

    print()
    print('Backtest completed successfully!')
    sys.exit(0)

except Exception as e:
    print(f'ERROR: Backtest failed: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
\""

# ============================================================================
# Execute Backtest
# ============================================================================

log_info "Starting backtest execution..."
log_info "Parameters:"
log_info "  Config: $CONFIG_PATH"
log_info "  Period: $START_DATE to $END_DATE"
log_info "  Initial capital: $INITIAL_CAPITAL"
log_info "  Output dir: $OUTPUT_DIR"
log_info "  Log level: $LOG_LEVEL"
log_info ""

eval "$PYTHON_CMD"
EXIT_CODE=$?

# ============================================================================
# Exit Handling
# ============================================================================

if [[ $EXIT_CODE -eq 0 ]]; then
    log_info "Backtest completed successfully"
    log_info "Results saved to: $OUTPUT_DIR"
    exit 0
else
    log_error "Backtest failed with exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi
