# -*- coding: utf-8 -*-
"""
Configuration Module

Defines strategy parameters, pool file paths, and backtest settings.
Based on the fixed KAMA configuration: k3_enable-adx-filter_enable-atr-stop_enable-slope-confirmation
"""

import os
from typing import Dict, List, Optional
from pathlib import Path

# Project root (relative to this file)
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # backtesting/
EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent  # selector_score/

# Fixed KAMA strategy configuration (no --optimize, fixed kama params)
STRATEGY_CONFIG = {
    'strategy': 'kama_cross',
    # Core KAMA parameters (fixed, not optimized)
    'kama_period': 20,
    'kama_fast': 2,
    'kama_slow': 30,
    # ADX filter
    'enable_adx_filter': True,
    'adx_period': 14,
    'adx_threshold': 25.0,
    # ATR stop
    'enable_atr_stop': True,
    'atr_period': 14,
    'atr_multiplier': 2.5,
    # Slope confirmation
    'enable_slope_confirmation': True,
    'min_slope_periods': 3,
}

# Backtest time period and data directory
BACKTEST_CONFIG = {
    'start_date': '20220102',
    'end_date': '20240102',
    'data_dir': str(PROJECT_ROOT / 'data' / 'chinese_etf' / 'daily' / 'etf'),
}

# ============================================================================
# Pool Auto-Discovery System
# ============================================================================
#
# 扩展性设计：支持两种方式添加新的单维度Pool
#
# 方式1: 文件名约定自动发现（推荐，零配置）
#   - 将CSV放入 pools/scoring_YYYY_YYYY/ 目录
#   - 命名格式: single_{dimension}_pool*.csv (不含 _all_scores)
#   - 系统自动发现并注册
#
# 方式2: 显式配置（用于特殊命名或需要自定义描述）
#   - 在 DIMENSION_LABELS 中添加维度描述
#   - 或使用 register_custom_pool() 运行时注册
#
# ============================================================================

# Dimension name -> Chinese label mapping
# 用于自动发现时提供友好的维度描述
# 如果维度不在此映射中，将使用原始维度名
DIMENSION_LABELS: Dict[str, str] = {
    'adx_score': 'ADX趋势强度',
    'liquidity_score': '流动性',
    'price_efficiency': '价格效率',
    'trend_consistency': '趋势一致性',
    'momentum_3m': '3个月动量',
    'momentum_12m': '12个月动量',
    'core_trend_excess_return_20d': '20日核心趋势超额收益',
    'core_trend_excess_return_60d': '60日核心趋势超额收益',
    'idr': '日内波动比率(IDR)',
    'trend_quality': '趋势质量',
    'volume': '成交量',
}

# Legacy static config (kept for backward compatibility)
# 新pool建议使用自动发现机制，无需在此添加
_STATIC_POOL_CONFIGS: Dict[str, Dict[str, str]] = {
    'single_adx_score': {
        'file': 'single_adx_score_pool_2019_2021.csv',
        'dimension': 'ADX趋势强度',
    },
    'single_liquidity_score': {
        'file': 'single_liquidity_score_pool_2019_2021.csv',
        'dimension': '流动性',
    },
    'single_price_efficiency': {
        'file': 'single_price_efficiency_pool_2019_2021.csv',
        'dimension': '价格效率',
    },
    'single_trend_consistency': {
        'file': 'single_trend_consistency_pool_2019_2021.csv',
        'dimension': '趋势一致性',
    },
    'single_momentum_3m': {
        'file': 'single_momentum_3m_pool_2019_2021.csv',
        'dimension': '3个月动量',
    },
    'single_momentum_12m': {
        'file': 'single_momentum_12m_pool_2019_2021.csv',
        'dimension': '12个月动量',
    },
}

# Baseline pool configuration (for comparison reference)
# Uses composite scoring from etf_selector module
BASELINE_POOL_CONFIG = {
    'baseline_composite': {
        'file': str(PROJECT_ROOT / 'results' / 'trend_etf_pool_2019_2021.csv'),
        'dimension': '综合评分基准(Baseline)',
        'is_absolute_path': True,  # Flag to indicate this is an absolute path
    },
}

# Pool directory for relative paths
POOL_DIR = EXPERIMENT_ROOT / 'pool'


# Runtime pool registry (can be extended via CLI)
_RUNTIME_POOLS: Dict[str, Dict[str, str]] = {}

# Cache for discovered pools
_DISCOVERED_POOLS: Optional[Dict[str, Dict[str, str]]] = None


def _parse_pool_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse pool filename to extract pool name and dimension.

    Expected format: single_{dimension}_pool*.csv (excluding _all_scores files)

    Args:
        filename: Pool CSV filename

    Returns:
        Dict with 'name', 'file', 'dimension' or None if not matching pattern
    """
    import re

    # Skip _all_scores files
    if '_all_scores' in filename:
        return None

    # Pattern: single_{dimension}_pool{optional_suffix}.csv
    # Examples:
    #   single_adx_score_pool_2019_2021.csv -> dimension = adx_score
    #   single_idr_pool.csv -> dimension = idr
    pattern = r'^single_(.+?)_pool(?:_.+)?\.csv$'
    match = re.match(pattern, filename)

    if not match:
        return None

    dimension_key = match.group(1)

    # Generate pool name from filename (without .csv)
    pool_name = filename.rsplit('.csv', 1)[0]
    # Normalize: single_adx_score_pool_2019_2021 -> single_adx_score
    # Keep it simple for now: use the part before _pool
    name_match = re.match(r'^(single_.+?)_pool', filename)
    if name_match:
        pool_name = name_match.group(1)

    # Get dimension label
    dimension_label = DIMENSION_LABELS.get(dimension_key, dimension_key)

    return {
        'name': pool_name,
        'file': filename,
        'dimension': dimension_label,
    }


def discover_pools(force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
    """
    Auto-discover pool files in POOL_DIR based on naming convention.

    Naming convention: single_{dimension}_pool*.csv (excluding _all_scores)

    Args:
        force_refresh: Force re-scan even if cache exists

    Returns:
        Dict of pool_name -> {'file': str, 'dimension': str}
    """
    global _DISCOVERED_POOLS

    if _DISCOVERED_POOLS is not None and not force_refresh:
        return _DISCOVERED_POOLS

    discovered = {}

    if not POOL_DIR.exists():
        _DISCOVERED_POOLS = discovered
        return discovered

    for csv_file in POOL_DIR.glob('single_*_pool*.csv'):
        parsed = _parse_pool_filename(csv_file.name)
        if parsed:
            pool_name = parsed['name']
            # Avoid duplicates (keep first found, typically the one without suffix)
            if pool_name not in discovered:
                discovered[pool_name] = {
                    'file': parsed['file'],
                    'dimension': parsed['dimension'],
                }

    _DISCOVERED_POOLS = discovered
    return discovered


def get_pool_configs() -> Dict[str, Dict[str, str]]:
    """
    Get all pool configurations (static + discovered + runtime).

    Priority: runtime > static > discovered

    Returns:
        Merged dict of all pool configurations
    """
    # Start with discovered pools (lowest priority)
    result = dict(discover_pools())

    # Override with static configs
    result.update(_STATIC_POOL_CONFIGS)

    # Override with runtime pools (highest priority)
    result.update(_RUNTIME_POOLS)

    return result


# Backward compatibility: POOL_CONFIGS as a dynamic getter
# Note: Direct access to POOL_CONFIGS will get static config only
# Use get_pool_configs() for full dynamic pool list
POOL_CONFIGS = _STATIC_POOL_CONFIGS  # For backward compatibility with existing imports


def get_pool_path(pool_name: str) -> Path:
    """Get the absolute path to a pool CSV file."""
    # Check runtime pools first (highest priority)
    if pool_name in _RUNTIME_POOLS:
        config = _RUNTIME_POOLS[pool_name]
        if config.get('is_absolute_path'):
            return Path(config['file'])
        return POOL_DIR / config['file']

    # Check baseline pool
    if pool_name in BASELINE_POOL_CONFIG:
        config = BASELINE_POOL_CONFIG[pool_name]
        if config.get('is_absolute_path'):
            return Path(config['file'])
        return POOL_DIR / config['file']

    # Check static pools
    if pool_name in _STATIC_POOL_CONFIGS:
        return POOL_DIR / _STATIC_POOL_CONFIGS[pool_name]['file']

    # Check discovered pools (auto-discovery)
    discovered = discover_pools()
    if pool_name in discovered:
        return POOL_DIR / discovered[pool_name]['file']

    raise ValueError(f"Unknown pool: {pool_name}. Available: {get_all_pool_names()}")


def get_pool_config(pool_name: str) -> Dict[str, str]:
    """Get the configuration dict for a pool."""
    if pool_name in _RUNTIME_POOLS:
        return _RUNTIME_POOLS[pool_name]
    if pool_name in BASELINE_POOL_CONFIG:
        return BASELINE_POOL_CONFIG[pool_name]
    if pool_name in _STATIC_POOL_CONFIGS:
        return _STATIC_POOL_CONFIGS[pool_name]
    # Check discovered pools
    discovered = discover_pools()
    if pool_name in discovered:
        return discovered[pool_name]
    raise ValueError(f"Unknown pool: {pool_name}")


def get_all_pool_names(
    include_baseline: bool = False,
    include_discovered: bool = True,
) -> List[str]:
    """
    Get list of all configured pool names.

    Args:
        include_baseline: Include baseline composite pool
        include_discovered: Include auto-discovered pools (default True)

    Returns:
        List of pool names
    """
    names = list(_STATIC_POOL_CONFIGS.keys())

    if include_discovered:
        discovered = discover_pools()
        for name in discovered:
            if name not in names:
                names.append(name)

    if include_baseline:
        names.extend(BASELINE_POOL_CONFIG.keys())

    names.extend(_RUNTIME_POOLS.keys())
    return names


def register_custom_pool(name: str, file_path: str, dimension: str) -> None:
    """
    Register a custom pool at runtime.

    Args:
        name: Pool name (must be unique)
        file_path: Path to pool CSV file (absolute or relative to POOL_DIR)
        dimension: Description of the scoring dimension
    """
    path = Path(file_path)
    is_absolute = path.is_absolute()

    _RUNTIME_POOLS[name] = {
        'file': str(path) if is_absolute else file_path,
        'dimension': dimension,
        'is_absolute_path': is_absolute,
    }


def validate_config(pool_names: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """
    Validate configuration: check file existence and data directory.

    Args:
        pool_names: List of pool names to validate (None = all standard pools)

    Returns:
        Dict with 'errors' and 'warnings' lists
    """
    import pandas as pd

    errors = []
    warnings = []

    # Check data directory
    data_dir = Path(BACKTEST_CONFIG['data_dir'])
    if not data_dir.exists():
        errors.append(f"Data directory not found: {data_dir}")
    elif not any(data_dir.glob('*.csv')):
        warnings.append(f"No CSV files found in data directory: {data_dir}")

    # Determine which pools to validate
    if pool_names is None:
        pools_to_check = list(_STATIC_POOL_CONFIGS.keys())
    else:
        pools_to_check = pool_names

    # Check pool files
    for pool_name in pools_to_check:
        try:
            pool_path = get_pool_path(pool_name)
        except ValueError as e:
            errors.append(str(e))
            continue

        if not pool_path.exists():
            errors.append(f"Pool file not found: {pool_path}")
        else:
            # Check for ts_code column and BOM handling
            try:
                df = pd.read_csv(pool_path, encoding='utf-8-sig', nrows=1)
                if 'ts_code' not in df.columns:
                    errors.append(f"Pool {pool_name} missing 'ts_code' column")
            except Exception as e:
                warnings.append(f"Could not validate pool {pool_name}: {e}")

    # Also validate baseline pool if it exists
    for pool_name, config in BASELINE_POOL_CONFIG.items():
        if config.get('is_absolute_path'):
            pool_path = Path(config['file'])
        else:
            pool_path = POOL_DIR / config['file']

        if not pool_path.exists():
            warnings.append(f"Baseline pool file not found: {pool_path}")

    return {'errors': errors, 'warnings': warnings}


def build_backtest_command(
    pool_path: str,
    output_dir: str,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """
    Build the run_backtest.sh command arguments.

    Args:
        pool_path: Path to the pool CSV file
        output_dir: Output directory for backtest results
        extra_args: Additional command line arguments

    Returns:
        List of command line arguments (excluding the script itself)
    """
    args = [
        '--stock-list', str(pool_path),
        '--strategy', STRATEGY_CONFIG['strategy'],
        '--data-dir', BACKTEST_CONFIG['data_dir'],
        '--output-dir', str(output_dir),
        '--start-date', BACKTEST_CONFIG['start_date'],
        '--end-date', BACKTEST_CONFIG['end_date'],
        # Fixed KAMA parameters
        '--kama-period', str(STRATEGY_CONFIG['kama_period']),
        '--kama-fast', str(STRATEGY_CONFIG['kama_fast']),
        '--kama-slow', str(STRATEGY_CONFIG['kama_slow']),
    ]

    # ADX filter
    if STRATEGY_CONFIG['enable_adx_filter']:
        args.extend([
            '--enable-adx-filter',
            '--adx-period', str(STRATEGY_CONFIG['adx_period']),
            '--adx-threshold', str(STRATEGY_CONFIG['adx_threshold']),
        ])

    # ATR stop
    if STRATEGY_CONFIG['enable_atr_stop']:
        args.extend([
            '--enable-atr-stop',
            '--atr-period', str(STRATEGY_CONFIG['atr_period']),
            '--atr-multiplier', str(STRATEGY_CONFIG['atr_multiplier']),
        ])

    # Slope confirmation
    if STRATEGY_CONFIG['enable_slope_confirmation']:
        args.extend([
            '--enable-slope-confirmation',
            '--min-slope-periods', str(STRATEGY_CONFIG['min_slope_periods']),
        ])

    if extra_args:
        args.extend(extra_args)

    return args
