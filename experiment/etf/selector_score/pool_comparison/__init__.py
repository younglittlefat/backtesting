# -*- coding: utf-8 -*-
"""
Pool Comparison Module

Compare backtest performance across different ETF pools
with varying scoring dimensions.

Extensibility:
- Auto-discovery: Place CSV files in pool/ directory with naming convention
  single_{dimension}_pool*.csv (excluding _all_scores)
- Manual registration: Use register_custom_pool() at runtime
- Dimension labels: Add to DIMENSION_LABELS in config.py
"""

from .config import (
    STRATEGY_CONFIG,
    POOL_CONFIGS,
    BASELINE_POOL_CONFIG,
    BACKTEST_CONFIG,
    DIMENSION_LABELS,
    get_pool_path,
    get_pool_config,
    get_pool_configs,
    get_all_pool_names,
    discover_pools,
    register_custom_pool,
    validate_config,
)
from .runner import run_single_pool, run_all_pools
from .collector import collect_pool_results, collect_all_results
from .analyzer import compute_pool_stats, compare_pools, generate_reports

__all__ = [
    # Config
    'STRATEGY_CONFIG',
    'POOL_CONFIGS',
    'BASELINE_POOL_CONFIG',
    'BACKTEST_CONFIG',
    'DIMENSION_LABELS',
    'get_pool_path',
    'get_pool_config',
    'get_pool_configs',
    'get_all_pool_names',
    'discover_pools',
    'register_custom_pool',
    'validate_config',
    # Runner
    'run_single_pool',
    'run_all_pools',
    # Collector
    'collect_pool_results',
    'collect_all_results',
    # Analyzer
    'compute_pool_stats',
    'compare_pools',
    'generate_reports',
]
