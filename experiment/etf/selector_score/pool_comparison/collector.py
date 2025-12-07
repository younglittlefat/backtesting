# -*- coding: utf-8 -*-
"""
Collector Module

Extract backtest results from summary CSV files.
Reuses greedy_search.metrics_extractor for parsing logic.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

# Import from greedy_search module for consistent metric extraction
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from greedy_search.metrics_extractor import (
    find_global_summary,
    extract_metrics_from_csv,
    DETAIL_COL_MAPPING,
)

from .config import POOL_CONFIGS, BASELINE_POOL_CONFIG, get_pool_config, get_all_pool_names

logger = logging.getLogger(__name__)


def collect_pool_results(
    backtest_dir: Path,
    pool_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Collect results from a single pool's backtest directory.

    Args:
        backtest_dir: Path to the pool's backtest output directory
                      (e.g., results/pool_comparison_xxx/backtests/single_adx_score)
        pool_name: Name of the pool for metadata

    Returns:
        Dict with pool results including:
        - pool_name: str
        - scoring_dimension: str
        - metrics: Dict of mean/median values
        - summary_path: str
        - num_stocks: int
        - detail_records: List[Dict] (individual ETF records, if available)
        Or None if no results found
    """
    summary_path = find_global_summary(str(backtest_dir))

    if not summary_path:
        logger.warning(f"No global_summary found for pool: {pool_name} in {backtest_dir}")
        return None

    logger.info(f"Collecting results from: {summary_path}")

    # Extract metrics using greedy_search utility
    metrics = extract_metrics_from_csv(summary_path)

    # Get pool config for dimension info
    try:
        pool_config = get_pool_config(pool_name)
        dimension = pool_config.get('dimension', 'Unknown')
    except ValueError:
        dimension = 'Unknown'

    # Try to get detail records from backtest_summary file
    detail_records = []
    num_stocks = 0

    # Find the corresponding backtest_summary file
    summary_dir = Path(summary_path).parent
    backtest_summaries = list(summary_dir.glob('backtest_summary_*.csv'))

    if backtest_summaries:
        detail_path = backtest_summaries[0]
        try:
            df = pd.read_csv(detail_path, encoding='utf-8-sig')
            num_stocks = len(df)

            # Extract per-ETF records
            for _, row in df.iterrows():
                record = {}
                # Try to get ts_code and name
                if '标的代码' in df.columns:
                    record['ts_code'] = row['标的代码']
                elif 'ts_code' in df.columns:
                    record['ts_code'] = row['ts_code']

                if '标的名称' in df.columns:
                    record['name'] = row['标的名称']
                elif 'name' in df.columns:
                    record['name'] = row['name']

                # Extract metrics using column mapping
                col_map = {
                    'return': ['年化收益率(%)', 'Return [%]'],
                    'sharpe': ['夏普比率', 'Sharpe Ratio'],
                    'max_dd': ['最大回撤(%)', 'Max. Drawdown [%]'],
                    'win_rate': ['胜率(%)', 'Win Rate [%]'],
                    'pl_ratio': ['盈亏比', 'Profit/Loss Ratio'],
                    'trades': ['交易次数', '# Trades'],
                }

                for key, possible_cols in col_map.items():
                    for col in possible_cols:
                        if col in df.columns:
                            record[key] = row[col]
                            break

                if record.get('ts_code'):
                    detail_records.append(record)

        except Exception as e:
            logger.warning(f"Could not read detail file {detail_path}: {e}")

    # If no detail file, try to get num_stocks from global summary
    if num_stocks == 0:
        try:
            gs_df = pd.read_csv(summary_path, encoding='utf-8-sig')
            if '标的数量' in gs_df.columns:
                num_stocks = int(gs_df['标的数量'].iloc[0])
            elif 'num_stocks' in gs_df.columns:
                num_stocks = int(gs_df['num_stocks'].iloc[0])
        except Exception:
            pass

    return {
        'pool_name': pool_name,
        'scoring_dimension': dimension,
        'metrics': metrics,
        'summary_path': summary_path,
        'num_stocks': num_stocks,
        'detail_records': detail_records,
    }


def collect_all_results(
    experiment_dir: Path,
    pool_names: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Collect results from all pools in an experiment directory.

    Args:
        experiment_dir: Root experiment directory containing backtests/ subdirectory
        pool_names: List of pool names to collect (None = all standard pools)

    Returns:
        Dict of pool_name -> result dict (from collect_pool_results)
    """
    if pool_names is None:
        pool_names = get_all_pool_names(include_baseline=False)

    backtests_dir = experiment_dir / 'backtests'
    results = {}

    for pool_name in pool_names:
        pool_dir = backtests_dir / pool_name
        if not pool_dir.exists():
            logger.warning(f"Pool directory not found: {pool_dir}")
            continue

        result = collect_pool_results(pool_dir, pool_name)
        if result:
            results[pool_name] = result

    logger.info(f"Collected results for {len(results)}/{len(pool_names)} pools")
    return results
