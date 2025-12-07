# -*- coding: utf-8 -*-
"""
Analyzer Module

Compute statistics and generate comparison reports across pools.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Metrics to include in summary (aligned with mega_test_greedy_summary.csv)
SUMMARY_METRICS = [
    'return_mean', 'return_median',
    'sharpe_mean', 'sharpe_median',
    'max_dd_mean', 'max_dd_median',
    'win_rate_mean', 'win_rate_median',
    'pl_ratio_mean', 'pl_ratio_median',
    'trades_mean', 'trades_median',
]


def compute_pool_stats(pool_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute summary statistics for a single pool.

    If detailed records are available, computes statistics from them.
    Otherwise uses the pre-computed metrics from global_summary.

    Args:
        pool_result: Result dict from collector.collect_pool_results()

    Returns:
        Dict with computed statistics
    """
    stats = {
        'pool_name': pool_result['pool_name'],
        'scoring_dimension': pool_result['scoring_dimension'],
        'num_stocks': pool_result['num_stocks'],
        'summary_path': pool_result['summary_path'],
    }

    # Use metrics directly from collector (already computed mean/median)
    metrics = pool_result.get('metrics', {})
    for key in SUMMARY_METRICS:
        stats[key] = metrics.get(key)

    # If we have detail records, we could compute additional stats like p25
    detail_records = pool_result.get('detail_records', [])
    if detail_records:
        df = pd.DataFrame(detail_records)

        # Compute p25 (25th percentile) for key metrics
        for metric in ['sharpe', 'return', 'max_dd', 'win_rate']:
            if metric in df.columns:
                series = pd.to_numeric(df[metric], errors='coerce').dropna()
                if len(series) > 0:
                    stats[f'{metric}_p25'] = float(series.quantile(0.25))
                    stats[f'{metric}_min'] = float(series.min())
                    stats[f'{metric}_max'] = float(series.max())

    return stats


def compare_pools(
    all_results: Dict[str, Dict[str, Any]],
    sort_by: str = 'sharpe_median',
    ascending: bool = False,
) -> pd.DataFrame:
    """
    Compare all pools and generate a ranking DataFrame.

    Args:
        all_results: Dict from collector.collect_all_results()
        sort_by: Metric to sort by
        ascending: Sort order

    Returns:
        DataFrame with one row per pool, sorted by specified metric
    """
    rows = []
    for pool_name, result in all_results.items():
        stats = compute_pool_stats(result)
        rows.append(stats)

    if not rows:
        logger.warning("No results to compare")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Sort by specified metric
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending)
    else:
        logger.warning(f"Sort column {sort_by} not found, using default order")

    # Add rank column
    df.insert(0, 'rank', range(1, len(df) + 1))

    return df


def generate_reports(
    all_results: Dict[str, Dict[str, Any]],
    output_dir: Path,
) -> Dict[str, Path]:
    """
    Generate summary and detail CSV reports.

    Args:
        all_results: Dict from collector.collect_all_results()
        output_dir: Directory to save reports

    Returns:
        Dict with paths to generated reports
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = {}

    # 1. Generate summary report (one row per pool)
    summary_df = compare_pools(all_results)
    if not summary_df.empty:
        # Reorder columns for better readability
        cols_order = [
            'rank', 'pool_name', 'scoring_dimension',
            'return_mean', 'return_median',
            'sharpe_mean', 'sharpe_median',
            'max_dd_mean', 'max_dd_median',
            'win_rate_mean', 'win_rate_median',
            'pl_ratio_mean', 'pl_ratio_median',
            'trades_mean', 'trades_median',
            'num_stocks', 'summary_path',
        ]
        # Only include columns that exist
        cols_order = [c for c in cols_order if c in summary_df.columns]
        summary_df = summary_df[cols_order]

        summary_path = output_dir / 'pool_comparison_summary.csv'
        summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
        logger.info(f"Summary report saved to: {summary_path}")
        reports['summary'] = summary_path

    # 2. Generate detail report (one row per ETF)
    detail_rows = []
    for pool_name, result in all_results.items():
        for record in result.get('detail_records', []):
            row = {'pool_name': pool_name}
            row.update(record)
            detail_rows.append(row)

    if detail_rows:
        detail_df = pd.DataFrame(detail_rows)

        # Reorder columns
        cols_order = [
            'pool_name', 'ts_code', 'name',
            'return', 'sharpe', 'max_dd',
            'win_rate', 'pl_ratio', 'trades',
        ]
        cols_order = [c for c in cols_order if c in detail_df.columns]
        detail_df = detail_df[cols_order]

        detail_path = output_dir / 'pool_comparison_detail.csv'
        detail_df.to_csv(detail_path, index=False, encoding='utf-8-sig')
        logger.info(f"Detail report saved to: {detail_path}")
        reports['detail'] = detail_path

    return reports


def print_comparison_summary(summary_df: pd.DataFrame) -> None:
    """Print a human-readable summary comparison to console."""
    if summary_df.empty:
        print("No results to display")
        return

    print("\n" + "=" * 80)
    print("Pool Comparison Summary (sorted by sharpe_median)")
    print("=" * 80)

    # Print header
    headers = ['Rank', 'Pool Name', 'Dimension', 'Sharpe(med)', 'Return(med)', 'MaxDD(med)', 'N']
    print(f"{'Rank':<6}{'Pool Name':<25}{'Dimension':<15}{'Sharpe':<10}{'Return':<10}{'MaxDD':<10}{'N':<5}")
    print("-" * 80)

    for _, row in summary_df.iterrows():
        sharpe = f"{row.get('sharpe_median', 'N/A'):.2f}" if pd.notna(row.get('sharpe_median')) else 'N/A'
        ret = f"{row.get('return_median', 'N/A'):.1f}%" if pd.notna(row.get('return_median')) else 'N/A'
        dd = f"{row.get('max_dd_median', 'N/A'):.1f}%" if pd.notna(row.get('max_dd_median')) else 'N/A'

        print(f"{row.get('rank', '-'):<6}"
              f"{row.get('pool_name', 'Unknown'):<25}"
              f"{row.get('scoring_dimension', 'Unknown')[:14]:<15}"
              f"{sharpe:<10}"
              f"{ret:<10}"
              f"{dd:<10}"
              f"{row.get('num_stocks', 0):<5}")

    print("=" * 80)

    # Best pool recommendation
    if len(summary_df) > 0:
        best = summary_df.iloc[0]
        print(f"\nBest Pool: {best.get('pool_name')} ({best.get('scoring_dimension')})")
        print(f"  Sharpe: {best.get('sharpe_median', 'N/A'):.3f}")
        print(f"  Return: {best.get('return_median', 'N/A'):.2f}%")
        print(f"  Max DD: {best.get('max_dd_median', 'N/A'):.2f}%")
