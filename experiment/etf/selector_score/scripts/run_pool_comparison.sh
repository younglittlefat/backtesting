#!/bin/bash
################################################################################
# Pool Comparison Experiment Runner
#
# Compare backtest performance across different ETF pools with varying
# scoring dimensions using fixed KAMA strategy configuration.
#
# Usage:
#   ./run_pool_comparison.sh [options]
#
# Options are passed directly to the Python CLI module.
# Use --help for full option list.
#
# Examples:
#   # Run full experiment (all 6 pools)
#   ./run_pool_comparison.sh
#
#   # Run specific pools
#   ./run_pool_comparison.sh --pools single_adx_score single_liquidity_score
#
#   # Collect results only (after backtest completion)
#   ./run_pool_comparison.sh --collect-only --output-dir results/pool_comparison_xxx
#
#   # Run with parallel workers
#   ./run_pool_comparison.sh --max-workers 4
#
################################################################################

set -e

# Conda configuration
CONDA_PATH="/home/zijunliu/miniforge3/condabin/conda"
CONDA_ENV="backtesting"

# Script directory (pool_comparison module location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

################################################################################
# Environment Check
################################################################################
check_environment() {
    if [ ! -f "$CONDA_PATH" ]; then
        echo -e "${RED}Error: conda not found ($CONDA_PATH)${NC}" >&2
        exit 1
    fi

    if ! "$CONDA_PATH" env list 2>/dev/null | grep -q "^$CONDA_ENV "; then
        echo -e "${RED}Error: Conda environment '$CONDA_ENV' not found${NC}" >&2
        echo -e "${YELLOW}Create it with:${NC}" >&2
        echo "  conda create -n $CONDA_ENV python=3.9" >&2
        echo "  conda activate $CONDA_ENV" >&2
        echo "  pip install -e ." >&2
        exit 1
    fi
}

################################################################################
# Main
################################################################################
main() {
    check_environment

    # Display header (unless --help)
    if [[ ! " $* " =~ " -h " ]] && [[ ! " $* " =~ " --help " ]]; then
        echo -e "${BLUE}======================================================================${NC}"
        echo -e "${BLUE}             Pool Comparison Experiment${NC}"
        echo -e "${BLUE}======================================================================${NC}"
        echo -e "${YELLOW}Project Root:${NC} $PROJECT_ROOT"
        echo -e "${YELLOW}Conda Env:${NC} $CONDA_ENV"
        echo -e "${BLUE}======================================================================${NC}"
        echo ""
    fi

    # Run Python CLI module
    cd "$PROJECT_ROOT"
    "$CONDA_PATH" run -n "$CONDA_ENV" python -m experiment.etf.selector_score.pool_comparison.cli "$@"
    local exit_code=$?

    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}======================================================================${NC}"
        echo -e "${GREEN}                    Experiment Completed!${NC}"
        echo -e "${GREEN}======================================================================${NC}"
    else
        echo -e "${RED}======================================================================${NC}"
        echo -e "${RED}                    Experiment Failed (code: $exit_code)${NC}"
        echo -e "${RED}======================================================================${NC}"
    fi

    return $exit_code
}

main "$@"
