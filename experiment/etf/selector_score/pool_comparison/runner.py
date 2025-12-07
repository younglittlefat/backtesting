# -*- coding: utf-8 -*-
"""
Runner Module

Execute backtests for each ETF pool by calling run_backtest.sh.
Supports sequential and parallel execution with retry logic.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .config import (
    PROJECT_ROOT,
    POOL_CONFIGS,
    get_pool_path,
    get_all_pool_names,
    build_backtest_command,
)

logger = logging.getLogger(__name__)

# Shell script path
RUN_BACKTEST_SCRIPT = PROJECT_ROOT / 'run_backtest.sh'


def run_single_pool(
    pool_name: str,
    output_dir: Path,
    timeout: int = 1800,
    retry_count: int = 1,
    verbose: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """
    Run backtest for a single pool.

    Args:
        pool_name: Name of the pool (key in POOL_CONFIGS)
        output_dir: Base output directory for this experiment
        timeout: Timeout in seconds (default 30 min)
        retry_count: Number of retries on failure
        verbose: Print command output to console

    Returns:
        Tuple of (success, pool_name, error_message or None)
    """
    pool_path = get_pool_path(pool_name)
    pool_output_dir = output_dir / 'backtests' / pool_name

    # Build command
    args = build_backtest_command(
        pool_path=str(pool_path),
        output_dir=str(pool_output_dir),
    )
    cmd = [str(RUN_BACKTEST_SCRIPT)] + args

    logger.info(f"Running backtest for pool: {pool_name}")
    logger.debug(f"Command: {' '.join(cmd)}")

    last_error = None
    for attempt in range(retry_count + 1):
        try:
            if attempt > 0:
                logger.info(f"Retry {attempt}/{retry_count} for {pool_name}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(PROJECT_ROOT),
            )

            if result.returncode == 0:
                logger.info(f"[OK] Pool {pool_name} completed successfully")
                if verbose and result.stdout:
                    print(result.stdout)
                return (True, pool_name, None)
            else:
                last_error = f"Exit code {result.returncode}: {result.stderr[:500] if result.stderr else 'No stderr'}"
                logger.warning(f"Pool {pool_name} failed: {last_error}")

        except subprocess.TimeoutExpired:
            last_error = f"Timeout after {timeout}s"
            logger.warning(f"Pool {pool_name} timed out")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Pool {pool_name} exception: {e}")

    logger.error(f"[FAIL] Pool {pool_name} failed after {retry_count + 1} attempts: {last_error}")
    return (False, pool_name, last_error)


def run_all_pools(
    output_dir: Path,
    pool_names: Optional[List[str]] = None,
    max_workers: int = 1,
    timeout: int = 1800,
    retry_count: int = 1,
    skip_existing: bool = False,
    verbose: bool = False,
) -> Dict[str, Tuple[bool, Optional[str]]]:
    """
    Run backtests for all (or selected) pools.

    Args:
        output_dir: Base output directory for this experiment
        pool_names: List of pool names to run (None = all pools)
        max_workers: Number of parallel workers (1 = sequential)
        timeout: Timeout per pool in seconds
        retry_count: Number of retries on failure
        skip_existing: Skip pools that already have results
        verbose: Print command output to console

    Returns:
        Dict of pool_name -> (success, error_message or None)
    """
    if pool_names is None:
        pool_names = get_all_pool_names(include_baseline=False)

    # Filter out existing if requested
    if skip_existing:
        filtered = []
        for name in pool_names:
            summary_dir = output_dir / 'backtests' / name / 'summary'
            if summary_dir.exists() and any(summary_dir.glob('global_summary_*.csv')):
                logger.info(f"Skipping {name} (results exist)")
            else:
                filtered.append(name)
        pool_names = filtered

    if not pool_names:
        logger.warning("No pools to run")
        return {}

    logger.info(f"Running {len(pool_names)} pools with {max_workers} workers")
    results = {}

    if max_workers == 1:
        # Sequential execution
        for pool_name in pool_names:
            success, name, error = run_single_pool(
                pool_name, output_dir, timeout, retry_count, verbose
            )
            results[name] = (success, error)
    else:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    run_single_pool,
                    pool_name, output_dir, timeout, retry_count, verbose
                ): pool_name
                for pool_name in pool_names
            }

            for future in as_completed(futures):
                try:
                    success, name, error = future.result()
                    results[name] = (success, error)
                except Exception as e:
                    pool_name = futures[future]
                    logger.error(f"Unexpected error for {pool_name}: {e}")
                    results[pool_name] = (False, str(e))

    # Summary
    success_count = sum(1 for s, _ in results.values() if s)
    fail_count = len(results) - success_count
    logger.info(f"Completed: {success_count} success, {fail_count} failed")

    return results
