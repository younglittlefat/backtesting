#!/bin/bash
################################################################################
# manage_portfolio.sh - Portfolio Management Utility for ETF Trend Following v2
#
# Purpose:
#   Utility script for portfolio state management and maintenance:
#   1. Initialize new portfolio snapshots
#   2. Rollback to previous portfolio state
#   3. Inject or withdraw capital
#   4. List and inspect portfolio snapshots
#   5. Validate portfolio consistency
#
# Usage:
#   ./manage_portfolio.sh COMMAND [OPTIONS]
#
# Commands:
#   init              Initialize a new portfolio
#   rollback          Rollback to a previous snapshot
#   inject            Inject additional capital
#   withdraw          Withdraw capital
#   list              List all portfolio snapshots
#   show              Show portfolio snapshot details
#   validate          Validate portfolio consistency
#   help              Show this help message
#
# Options:
#   --portfolio PATH      Portfolio snapshot JSON path
#   --date DATE           Portfolio date (YYYY-MM-DD)
#   --capital AMOUNT      Initial capital or injection/withdrawal amount
#   --output PATH         Output path for new snapshot
#   --dir DIR             Directory for portfolio snapshots
#
# Examples:
#   # Initialize new portfolio
#   ./manage_portfolio.sh init --capital 1000000 --date 2025-01-01 \
#                              --output ../positions/portfolio_20250101.json
#
#   # Rollback to previous state
#   ./manage_portfolio.sh rollback --date 2025-12-10 \
#                                  --dir ../positions \
#                                  --output ../positions/portfolio_current.json
#
#   # Inject capital
#   ./manage_portfolio.sh inject --portfolio ../positions/portfolio_current.json \
#                                --capital 500000 \
#                                --output ../positions/portfolio_updated.json
#
#   # List all snapshots
#   ./manage_portfolio.sh list --dir ../positions
#
#   # Show snapshot details
#   ./manage_portfolio.sh show --portfolio ../positions/portfolio_20251210.json
#
#   # Validate portfolio
#   ./manage_portfolio.sh validate --portfolio ../positions/portfolio_current.json
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
DEFAULT_PORTFOLIO_DIR="$ETF_V2_DIR/output/positions"

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
ETF Trend Following v2 - Portfolio Management Utility

Usage: $0 COMMAND [OPTIONS]

Commands:
  init              Initialize a new portfolio
  rollback          Rollback to a previous snapshot
  inject            Inject additional capital
  withdraw          Withdraw capital
  list              List all portfolio snapshots
  show              Show portfolio snapshot details
  validate          Validate portfolio consistency
  help              Show this help message

Common Options:
  --portfolio PATH      Portfolio snapshot JSON path
  --date DATE           Portfolio date (YYYY-MM-DD)
  --capital AMOUNT      Initial capital or amount to inject/withdraw
  --output PATH         Output path for new snapshot
  --dir DIR             Directory for portfolio snapshots (default: ../output/positions)

Examples:
  # Initialize new portfolio
  $0 init --capital 1000000 --date 2025-01-01 \\
          --output ../positions/portfolio_20250101.json

  # Rollback to specific date
  $0 rollback --date 2025-12-10 --dir ../positions

  # Inject 500k capital
  $0 inject --portfolio ../positions/current.json --capital 500000

  # List all snapshots in directory
  $0 list --dir ../positions

  # Show snapshot details
  $0 show --portfolio ../positions/portfolio_20251210.json

For more details, see: $ETF_V2_DIR/src/README_portfolio.md
EOF
}

activate_conda_env() {
    # Source conda initialization script
    if [[ ! -f "$CONDA_PATH" ]]; then
        log_error "Conda not found at $CONDA_PATH"
        exit 1
    fi

    # Initialize conda for bash
    eval "$("$CONDA_PATH" shell.bash hook 2>/dev/null)"

    # Activate environment
    if ! conda activate "$CONDA_ENV" 2>/dev/null; then
        log_error "Failed to activate conda environment: $CONDA_ENV"
        exit 1
    fi
}

# ============================================================================
# Portfolio Commands
# ============================================================================

cmd_init() {
    local capital="$1"
    local date="$2"
    local output="$3"

    if [[ -z "$capital" || -z "$date" || -z "$output" ]]; then
        log_error "Missing required parameters for init command"
        log_error "Usage: $0 init --capital AMOUNT --date YYYY-MM-DD --output PATH"
        exit 1
    fi

    log_info "Initializing new portfolio..."
    log_info "  Initial capital: $capital"
    log_info "  Date: $date"
    log_info "  Output: $output"

    python << EOF
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '$ETF_V2_DIR')
from src.signal_pipeline import PortfolioSnapshot

# Create new portfolio snapshot
snapshot = PortfolioSnapshot(
    as_of_date='$date',
    holdings={},
    cash=float($capital),
    total_value=float($capital),
    cluster_assignments={},
    metadata={
        'created_at': datetime.now().isoformat(),
        'initial_capital': float($capital),
        'num_positions': 0
    }
)

# Save to file
output_path = Path('$output')
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w') as f:
    json.dump({
        'as_of_date': snapshot.as_of_date,
        'holdings': snapshot.holdings,
        'cash': snapshot.cash,
        'total_value': snapshot.total_value,
        'cluster_assignments': snapshot.cluster_assignments,
        'metadata': snapshot.metadata
    }, f, indent=2)

print(f'Portfolio initialized successfully: {output_path}')
EOF

    log_info "Portfolio initialization complete"
}

cmd_list() {
    local dir="$1"

    if [[ -z "$dir" ]]; then
        dir="$DEFAULT_PORTFOLIO_DIR"
    fi

    log_info "Listing portfolio snapshots in: $dir"

    if [[ ! -d "$dir" ]]; then
        log_error "Directory not found: $dir"
        exit 1
    fi

    python << EOF
import sys
import json
from pathlib import Path
from datetime import datetime

dir_path = Path('$dir')
json_files = sorted(dir_path.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)

if not json_files:
    print(f'No portfolio snapshots found in {dir_path}')
    sys.exit(0)

print('=' * 80)
print(f'Portfolio Snapshots in {dir_path}')
print('=' * 80)
print()

for i, filepath in enumerate(json_files, 1):
    try:
        with open(filepath) as f:
            data = json.load(f)

        as_of_date = data.get('as_of_date', 'N/A')
        total_value = data.get('total_value', 0)
        cash = data.get('cash', 0)
        num_holdings = len(data.get('holdings', {}))
        modified = datetime.fromtimestamp(filepath.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        print(f'{i}. {filepath.name}')
        print(f'   Date: {as_of_date}')
        print(f'   Total Value: ¥{total_value:,.2f}')
        print(f'   Cash: ¥{cash:,.2f}')
        print(f'   Positions: {num_holdings}')
        print(f'   Modified: {modified}')
        print()

    except Exception as e:
        print(f'{i}. {filepath.name} (Error: {e})')
        print()

print('=' * 80)
EOF
}

cmd_show() {
    local portfolio="$1"

    if [[ -z "$portfolio" ]]; then
        log_error "Missing required parameter: --portfolio"
        exit 1
    fi

    if [[ ! -f "$portfolio" ]]; then
        log_error "Portfolio file not found: $portfolio"
        exit 1
    fi

    log_info "Displaying portfolio snapshot: $portfolio"

    python << EOF
import sys
import json
from pathlib import Path

with open('$portfolio') as f:
    data = json.load(f)

print('=' * 80)
print('PORTFOLIO SNAPSHOT DETAILS')
print('=' * 80)
print()

print(f'As of Date: {data.get("as_of_date", "N/A")}')
print(f'Total Value: ¥{data.get("total_value", 0):,.2f}')
print(f'Cash: ¥{data.get("cash", 0):,.2f}')
print(f'Invested: ¥{data.get("total_value", 0) - data.get("cash", 0):,.2f}')
print()

holdings = data.get('holdings', {})
if holdings:
    print(f'Holdings ({len(holdings)} positions):')
    print('-' * 80)

    for symbol, position in holdings.items():
        shares = position.get('shares', 0)
        cost_basis = position.get('cost_basis', 0)
        entry_date = position.get('entry_date', 'N/A')
        value = shares * cost_basis

        print(f'  {symbol}:')
        print(f'    Shares: {shares:,}')
        print(f'    Cost Basis: ¥{cost_basis:.3f}')
        print(f'    Position Value: ¥{value:,.2f}')
        print(f'    Entry Date: {entry_date}')
        print()
else:
    print('Holdings: None (all cash)')
    print()

clusters = data.get('cluster_assignments', {})
if clusters:
    print(f'Cluster Assignments: {len(clusters)} symbols')
    cluster_counts = {}
    for symbol, cluster_id in clusters.items():
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

    for cluster_id, count in sorted(cluster_counts.items()):
        print(f'  Cluster {cluster_id}: {count} positions')
    print()

metadata = data.get('metadata', {})
if metadata:
    print('Metadata:')
    for key, value in metadata.items():
        print(f'  {key}: {value}')
    print()

print('=' * 80)
EOF
}

cmd_validate() {
    local portfolio="$1"

    if [[ -z "$portfolio" ]]; then
        log_error "Missing required parameter: --portfolio"
        exit 1
    fi

    if [[ ! -f "$portfolio" ]]; then
        log_error "Portfolio file not found: $portfolio"
        exit 1
    fi

    log_info "Validating portfolio snapshot: $portfolio"

    python << EOF
import sys
import json
from pathlib import Path

with open('$portfolio') as f:
    data = json.load(f)

errors = []
warnings = []

# Check required fields
required_fields = ['as_of_date', 'holdings', 'cash', 'total_value']
for field in required_fields:
    if field not in data:
        errors.append(f'Missing required field: {field}')

# Check cash is non-negative
if data.get('cash', -1) < 0:
    errors.append(f'Cash cannot be negative: {data.get("cash")}')

# Check total value consistency
holdings = data.get('holdings', {})
cash = data.get('cash', 0)
total_value = data.get('total_value', 0)

holdings_value = sum(
    pos.get('shares', 0) * pos.get('cost_basis', 0)
    for pos in holdings.values()
)

calculated_total = cash + holdings_value
if abs(calculated_total - total_value) > 0.01:
    errors.append(
        f'Total value mismatch: reported={total_value:.2f}, '
        f'calculated={calculated_total:.2f} (diff={abs(total_value - calculated_total):.2f})'
    )

# Check position validity
for symbol, position in holdings.items():
    if position.get('shares', 0) <= 0:
        warnings.append(f'{symbol}: Zero or negative shares ({position.get("shares")})')

    if position.get('cost_basis', 0) <= 0:
        warnings.append(f'{symbol}: Zero or negative cost basis ({position.get("cost_basis")})')

# Print results
print('=' * 80)
print('PORTFOLIO VALIDATION RESULTS')
print('=' * 80)
print()

if errors:
    print(f'❌ ERRORS FOUND ({len(errors)}):')
    for error in errors:
        print(f'  - {error}')
    print()
    sys.exit(1)
else:
    print('✓ No errors found')
    print()

if warnings:
    print(f'⚠ WARNINGS ({len(warnings)}):')
    for warning in warnings:
        print(f'  - {warning}')
    print()

print('Summary:')
print(f'  As of date: {data.get("as_of_date")}')
print(f'  Total value: ¥{total_value:,.2f}')
print(f'  Cash: ¥{cash:,.2f}')
print(f'  Holdings value: ¥{holdings_value:,.2f}')
print(f'  Number of positions: {len(holdings)}')
print()
print('=' * 80)

if not warnings:
    print('✓ Portfolio is valid')
else:
    print('⚠ Portfolio is valid with warnings')
EOF
}

cmd_inject() {
    local portfolio="$1"
    local amount="$2"
    local output="$3"

    if [[ -z "$portfolio" || -z "$amount" ]]; then
        log_error "Missing required parameters for inject command"
        log_error "Usage: $0 inject --portfolio PATH --capital AMOUNT [--output PATH]"
        exit 1
    fi

    if [[ -z "$output" ]]; then
        output="$portfolio"
    fi

    log_info "Injecting capital into portfolio..."
    log_info "  Portfolio: $portfolio"
    log_info "  Amount: $amount"
    log_info "  Output: $output"

    python << EOF
import sys
import json
from pathlib import Path
from datetime import datetime

with open('$portfolio') as f:
    data = json.load(f)

# Inject capital
amount = float($amount)
data['cash'] += amount
data['total_value'] += amount

# Update metadata
if 'metadata' not in data:
    data['metadata'] = {}

data['metadata']['last_capital_injection'] = {
    'amount': amount,
    'timestamp': datetime.now().isoformat()
}

# Save
output_path = Path('$output')
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w') as f:
    json.dump(data, f, indent=2)

print(f'Capital injection successful')
print(f'New cash balance: ¥{data["cash"]:,.2f}')
print(f'New total value: ¥{data["total_value"]:,.2f}')
print(f'Updated portfolio saved to: {output_path}')
EOF

    log_info "Capital injection complete"
}

cmd_rollback() {
    local date="$1"
    local dir="$2"
    local output="$3"

    if [[ -z "$date" || -z "$dir" ]]; then
        log_error "Missing required parameters for rollback command"
        log_error "Usage: $0 rollback --date YYYY-MM-DD --dir PATH [--output PATH]"
        exit 1
    fi

    log_info "Rolling back to snapshot date: $date"

    python << EOF
import sys
import json
from pathlib import Path
import shutil

dir_path = Path('$dir')
target_date = '$date'.replace('-', '')

# Find snapshot file
candidates = list(dir_path.glob(f'*{target_date}*.json'))

if not candidates:
    print(f'No snapshot found for date: $date', file=sys.stderr)
    sys.exit(1)

if len(candidates) > 1:
    print(f'Multiple snapshots found for date {$date}:', file=sys.stderr)
    for c in candidates:
        print(f'  - {c}', file=sys.stderr)
    print('Please specify exact file path with --portfolio', file=sys.stderr)
    sys.exit(1)

source_file = candidates[0]
print(f'Found snapshot: {source_file}')

# Copy to output if specified, otherwise just show info
output = '$output'
if output:
    shutil.copy2(source_file, output)
    print(f'Rollback successful: {output}')
else:
    # Just display the snapshot
    with open(source_file) as f:
        data = json.load(f)

    print()
    print(f'Snapshot Details:')
    print(f'  Date: {data.get("as_of_date")}')
    print(f'  Total Value: ¥{data.get("total_value", 0):,.2f}')
    print(f'  Cash: ¥{data.get("cash", 0):,.2f}')
    print(f'  Positions: {len(data.get("holdings", {}))}')
    print()
    print(f'To restore this snapshot, run:')
    print(f'  $0 rollback --date $date --dir $dir --output <target_path>')
EOF
}

# ============================================================================
# Main Entry Point
# ============================================================================

# Check for command
if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

COMMAND="$1"
shift

# Parse command-specific options
PORTFOLIO=""
DATE=""
CAPITAL=""
OUTPUT=""
DIR="$DEFAULT_PORTFOLIO_DIR"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --portfolio)
            PORTFOLIO="$2"
            shift 2
            ;;
        --date)
            DATE="$2"
            shift 2
            ;;
        --capital)
            CAPITAL="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --dir)
            DIR="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Activate conda environment for Python commands
if [[ "$COMMAND" != "help" ]]; then
    activate_conda_env
fi

# Execute command
case "$COMMAND" in
    init)
        cmd_init "$CAPITAL" "$DATE" "$OUTPUT"
        ;;
    list)
        cmd_list "$DIR"
        ;;
    show)
        cmd_show "$PORTFOLIO"
        ;;
    validate)
        cmd_validate "$PORTFOLIO"
        ;;
    inject)
        cmd_inject "$PORTFOLIO" "$CAPITAL" "$OUTPUT"
        ;;
    rollback)
        cmd_rollback "$DATE" "$DIR" "$OUTPUT"
        ;;
    help)
        show_help
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac

exit 0
