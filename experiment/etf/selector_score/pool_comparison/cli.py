# -*- coding: utf-8 -*-
"""
CLI Module

Command-line interface for pool comparison experiment.
"""

import argparse
import logging
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from .config import (
    PROJECT_ROOT,
    EXPERIMENT_ROOT,
    POOL_CONFIGS,
    BASELINE_POOL_CONFIG,
    BACKTEST_CONFIG,
    STRATEGY_CONFIG,
    validate_config,
    get_all_pool_names,
    get_pool_path,
    get_pool_config,
    POOL_DIR,
)
from .runner import run_all_pools
from .collector import collect_all_results
from .analyzer import compare_pools, generate_reports, print_comparison_summary

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def get_git_commit() -> Optional[str]:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0:
            return result.stdout.strip()[:8]
    except Exception:
        pass
    return None


def compute_file_md5(filepath: Path) -> Optional[str]:
    """Compute MD5 hash of a file."""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:12]
    except Exception:
        return None


def save_experiment_metadata(output_dir: Path, args: argparse.Namespace, pool_names: List[str]) -> None:
    """Save experiment metadata to JSON file."""
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'git_commit': get_git_commit(),
        'strategy_config': STRATEGY_CONFIG,
        'backtest_config': BACKTEST_CONFIG,
        'pools': {},
        'cli_args': {
            'collect_only': args.collect_only,
            'max_workers': args.max_workers,
            'pools': args.pools,
            'include_baseline': args.include_baseline,
        },
    }

    # Add pool file MD5 hashes
    for pool_name in pool_names:
        try:
            pool_path = get_pool_path(pool_name)
            pool_config = get_pool_config(pool_name)
            if pool_path.exists():
                metadata['pools'][pool_name] = {
                    'file': str(pool_path),
                    'md5': compute_file_md5(pool_path),
                    'dimension': pool_config.get('dimension', 'Unknown'),
                }
        except ValueError:
            continue

    metadata_path = output_dir / '.experiment_metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Metadata saved to: {metadata_path}")


def create_output_dir(base_name: str = 'pool_comparison') -> Path:
    """Create timestamped output directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = EXPERIMENT_ROOT / 'results' / f'{base_name}_{timestamp}'
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for CLI.

    Args:
        args: Command line arguments (None = use sys.argv)

    Returns:
        Exit code (0 = success)
    """
    parser = argparse.ArgumentParser(
        description='Compare backtest performance across different ETF pools.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full experiment (all 6 pools)
  python -m pool_comparison.cli

  # Run specific pools only
  python -m pool_comparison.cli --pools single_adx_score single_liquidity_score

  # Include baseline composite pool for comparison
  python -m pool_comparison.cli --include-baseline

  # Collect results only (skip backtest execution)
  python -m pool_comparison.cli --collect-only --output-dir results/pool_comparison_xxx

  # Run with parallel execution
  python -m pool_comparison.cli --max-workers 4
        """,
    )

    # Get available pool choices (without baseline by default for the choices)
    available_pools = get_all_pool_names(include_baseline=True)

    parser.add_argument(
        '--pools',
        nargs='+',
        choices=available_pools,
        help=f'Pool names to test (default: all single-dimension pools). Choices: {available_pools}',
    )
    parser.add_argument(
        '--include-baseline',
        action='store_true',
        help='Include baseline composite pool (trend_etf_pool_2019_2021.csv) for comparison',
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory (default: auto-generated with timestamp)',
    )
    parser.add_argument(
        '--collect-only',
        action='store_true',
        help='Skip backtest execution, only collect results from existing output-dir',
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=1,
        help='Number of parallel workers (default: 1 = sequential)',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=1800,
        help='Timeout per pool in seconds (default: 1800 = 30min)',
    )
    parser.add_argument(
        '--retry',
        type=int,
        default=1,
        help='Number of retries on failure (default: 1)',
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip pools that already have results',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output',
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate configuration, do not run',
    )

    parsed_args = parser.parse_args(args)
    setup_logging(parsed_args.verbose)

    # Determine pool names to process
    if parsed_args.pools:
        pool_names = parsed_args.pools
    else:
        # Default: all single-dimension pools
        pool_names = get_all_pool_names(include_baseline=False)

    # Add baseline if requested
    if parsed_args.include_baseline:
        baseline_pools = list(BASELINE_POOL_CONFIG.keys())
        for bp in baseline_pools:
            if bp not in pool_names:
                pool_names.append(bp)

    # Validate configuration for selected pools
    validation = validate_config(pool_names)
    if validation['errors']:
        for err in validation['errors']:
            logger.error(f"Config error: {err}")
        return 1
    if validation['warnings']:
        for warn in validation['warnings']:
            logger.warning(f"Config warning: {warn}")

    if parsed_args.validate_only:
        logger.info("Configuration validated successfully")
        return 0

    # Determine output directory
    if parsed_args.output_dir:
        output_dir = Path(parsed_args.output_dir)
        if not output_dir.exists() and not parsed_args.collect_only:
            output_dir.mkdir(parents=True, exist_ok=True)
    else:
        if parsed_args.collect_only:
            logger.error("--output-dir is required when using --collect-only")
            return 1
        output_dir = create_output_dir()

    logger.info(f"Output directory: {output_dir}")

    # Save metadata (unless collect-only with existing metadata)
    if not parsed_args.collect_only:
        save_experiment_metadata(output_dir, parsed_args, pool_names)

    logger.info(f"Pools to process: {pool_names}")

    # Run backtests (unless collect-only)
    if not parsed_args.collect_only:
        logger.info("Starting backtest execution...")
        run_results = run_all_pools(
            output_dir=output_dir,
            pool_names=pool_names,
            max_workers=parsed_args.max_workers,
            timeout=parsed_args.timeout,
            retry_count=parsed_args.retry,
            skip_existing=parsed_args.skip_existing,
            verbose=parsed_args.verbose,
        )

        # Check for failures
        failures = [(name, err) for name, (success, err) in run_results.items() if not success]
        if failures:
            logger.warning(f"{len(failures)} pools failed:")
            for name, err in failures:
                logger.warning(f"  - {name}: {err}")

    # Collect results
    logger.info("Collecting results...")
    all_results = collect_all_results(output_dir, pool_names)

    if not all_results:
        logger.error("No results collected!")
        return 1

    # Generate reports
    logger.info("Generating reports...")
    reports = generate_reports(all_results, output_dir)

    # Print summary to console
    summary_df = compare_pools(all_results)
    print_comparison_summary(summary_df)

    # Final summary
    print(f"\nReports saved to: {output_dir}")
    for name, path in reports.items():
        print(f"  - {name}: {path}")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
