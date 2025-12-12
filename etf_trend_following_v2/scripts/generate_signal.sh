#!/bin/bash
################################################################################
# generate_signal.sh - Daily Signal Generation Script for ETF Trend Following v2
#
# Purpose:
#   Unified entry point for daily signal generation workflow:
#   1. Load configuration
#   2. Scan full ETF pool and generate signals
#   3. Score and rank by momentum
#   4. Apply clustering diversification
#   5. Execute risk checks and circuit breakers
#   6. Calculate position sizing
#   7. Generate trade orders and update portfolio snapshot
#
# Usage:
#   ./generate_signal.sh [OPTIONS]
#
# Options:
#   --config PATH         Path to config.json (default: ../config/example_config.json)
#   --as-of-date DATE     Signal generation date YYYY-MM-DD (default: today)
#   --portfolio PATH      Portfolio snapshot JSON path (optional, for state recovery)
#   --output-dir DIR      Output directory (default: from config.json)
#   --dry-run             Generate signals without saving files (default: enabled)
#   --log-level LEVEL     Logging level: DEBUG|INFO|WARNING|ERROR (default: INFO)
#   --help                Show this help message
#
# Examples:
#   # Generate today's signals with default config
#   ./generate_signal.sh
#
#   # Generate signals for specific date with custom config
#   ./generate_signal.sh --config ../config/custom_config.json --as-of-date 2025-12-10
#
#   # Production run (save output files)
#   ./generate_signal.sh --dry-run false --output-dir /mnt/d/git/backtesting/results/signals
#
# Output Files (when not dry-run):
#   - signals/signals_{date}.csv          # Buy/sell signals with strategy indicators
#   - signals/scores_{date}.csv           # Momentum scores and rankings
#   - positions/positions_{date}.json     # Updated portfolio snapshot
#   - signals/trades_{date}.csv           # Trade orders to execute
#   - logs/signal_pipeline_{date}.log     # Execution log
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
DEFAULT_LOG_LEVEL="INFO"
DEFAULT_DRY_RUN=true

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
ETF Trend Following v2 - Daily Signal Generation Script

Usage: $0 [OPTIONS]

Options:
  --config PATH         Path to config.json (default: ../config/example_config.json)
  --as-of-date DATE     Signal generation date YYYY-MM-DD (default: today)
  --portfolio PATH      Portfolio snapshot JSON path (optional)
  --output-dir DIR      Output directory (default: from config.json)
  --dry-run [true|false] Generate without saving files (default: true)
  --log-level LEVEL     Logging level: DEBUG|INFO|WARNING|ERROR (default: INFO)
  --help                Show this help message

Examples:
  # Generate today's signals
  $0

  # Generate for specific date
  $0 --config ../config/custom_config.json --as-of-date 2025-12-10

  # Production run with output
  $0 --dry-run false --output-dir ../output/signals

For more details, see: $ETF_V2_DIR/src/SIGNAL_PIPELINE_README.md
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

# ============================================================================
# Parse Command Line Arguments
# ============================================================================

CONFIG_PATH="$DEFAULT_CONFIG"
AS_OF_DATE=""
PORTFOLIO_PATH=""
OUTPUT_DIR=""
DRY_RUN="$DEFAULT_DRY_RUN"
LOG_LEVEL="$DEFAULT_LOG_LEVEL"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --as-of-date)
            AS_OF_DATE="$2"
            shift 2
            ;;
        --portfolio)
            PORTFOLIO_PATH="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dry-run)
            if [[ "$2" == "false" || "$2" == "False" || "$2" == "0" ]]; then
                DRY_RUN=false
            else
                DRY_RUN=true
            fi
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
log_info "ETF Trend Following v2 - Signal Generator"
log_info "=========================================="

# Verify configuration file
verify_config_file "$CONFIG_PATH"

# Activate conda environment
activate_conda_env

# Check if Python module is accessible
if ! python -c "import sys; sys.path.insert(0, '$ETF_V2_DIR'); from src.signal_pipeline import run_daily_signal" 2>/dev/null; then
    log_error "Failed to import signal_pipeline module"
    log_error "Please ensure the project is properly set up"
    exit 1
fi

# ============================================================================
# Build Python Command
# ============================================================================

PYTHON_CMD="python -c \"
import sys
sys.path.insert(0, '$ETF_V2_DIR')
from src.signal_pipeline import run_daily_signal
import logging

logging.basicConfig(
    level=logging.$LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    result = run_daily_signal(
        config_path='$CONFIG_PATH',
        as_of_date='$AS_OF_DATE' if '$AS_OF_DATE' else None,
        portfolio_snapshot='$PORTFOLIO_PATH' if '$PORTFOLIO_PATH' else None,
        output_dir='$OUTPUT_DIR' if '$OUTPUT_DIR' else None,
        dry_run=$([[ "$DRY_RUN" == true ]] && echo "True" || echo "False")
    )

    # Print summary
    print()
    print('=' * 80)
    print('SIGNAL GENERATION SUMMARY')
    print('=' * 80)
    print(f'As of date: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"as_of_date\\\"]}')
    print(f'Execution time: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"execution_time\\\"]:.2f}s')
    print(f'Total symbols scanned: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"total_symbols\\\"]}')
    print(f'Buy signals: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"buy_signals\\\"]}')
    print(f'Sell signals: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"sell_signals\\\"]}')
    print(f'Buy orders: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"num_buy_orders\\\"]}')
    print(f'Sell orders: {result[\\\"result\\\"][\\\"metadata\\\"][\\\"num_sell_orders\\\"]}')
    print(f'Circuit breaker triggered: {result[\\\"result\\\"][\\\"circuit_breaker\\\"]}')
    print(f'Holdings after update: {len(result[\\\"portfolio_updated\\\"].holdings)}')
    print(f'Portfolio value: {result[\\\"portfolio_updated\\\"].total_value:,.2f}')
    print('=' * 80)

    if result['output_files']:
        print()
        print('Output files saved:')
        for key, path in result['output_files'].items():
            print(f'  {key}: {path}')
    elif $([[ "$DRY_RUN" == true ]] && echo "True" || echo "False"):
        print()
        print('Dry-run mode: No files saved. Use --dry-run false to save outputs.')

    print()
    print('Signal generation completed successfully!')
    sys.exit(0)

except Exception as e:
    print(f'ERROR: Signal generation failed: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
\""

# ============================================================================
# Execute Signal Generation
# ============================================================================

log_info "Starting signal generation..."
log_info "Parameters:"
log_info "  Config: $CONFIG_PATH"
log_info "  As-of-date: ${AS_OF_DATE:-today}"
log_info "  Portfolio: ${PORTFOLIO_PATH:-none}"
log_info "  Output dir: ${OUTPUT_DIR:-from config}"
log_info "  Dry-run: $DRY_RUN"
log_info "  Log level: $LOG_LEVEL"
log_info ""

eval "$PYTHON_CMD"
EXIT_CODE=$?

# ============================================================================
# Exit Handling
# ============================================================================

if [[ $EXIT_CODE -eq 0 ]]; then
    log_info "Signal generation completed successfully"
    exit 0
else
    log_error "Signal generation failed with exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi
