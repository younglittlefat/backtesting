"""
Data loading module for ETF trend following system.

This module provides functions to load OHLCV data from CSV files,
filter by liquidity, align dates, and handle missing data.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def load_single_etf(
    symbol: str,
    data_dir: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_adj: bool = True
) -> pd.DataFrame:
    """
    Load OHLCV data for a single ETF.

    Args:
        symbol: ETF symbol (e.g., '159915.SZ' or '159915')
        data_dir: Directory containing ETF CSV files
        start_date: Start date in 'YYYY-MM-DD' format (inclusive)
        end_date: End date in 'YYYY-MM-DD' format (inclusive)
        use_adj: Whether to use adjusted prices (adj_close, adj_open, etc.)

    Returns:
        DataFrame with datetime index and OHLCV columns
        Columns: open, high, low, close, volume, amount

    Raises:
        FileNotFoundError: If the data file doesn't exist
        ValueError: If the data is empty or invalid
    """
    # Normalize symbol format (ensure .SZ or .SH suffix)
    if '.' not in symbol:
        # Try to find the file with either suffix
        etf_subdir = Path(data_dir) / 'etf'
        possible_files = [
            etf_subdir / f"{symbol}.SZ.csv",
            etf_subdir / f"{symbol}.SH.csv"
        ]
        file_path = None
        for pf in possible_files:
            if pf.exists():
                file_path = pf
                break
        if file_path is None:
            raise FileNotFoundError(
                f"Could not find data file for {symbol} in {data_dir}"
            )
    else:
        # Check both direct path and etf subdirectory
        direct_path = Path(data_dir) / f"{symbol}.csv"
        etf_path = Path(data_dir) / 'etf' / f"{symbol}.csv"

        if etf_path.exists():
            file_path = etf_path
        elif direct_path.exists():
            file_path = direct_path
        else:
            raise FileNotFoundError(
                f"Data file not found for {symbol} in {data_dir}"
            )

    # Load CSV
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read {file_path}: {e}")

    if df.empty:
        raise ValueError(f"Empty data file for {symbol}")

    # Parse date column
    date_col = 'trade_date' if 'trade_date' in df.columns else 'date'
    if date_col not in df.columns:
        raise ValueError(f"No date column found in {symbol} data")

    df[date_col] = pd.to_datetime(df[date_col], format='%Y%m%d', errors='coerce')
    df = df.dropna(subset=[date_col])
    df = df.set_index(date_col)
    df.index.name = 'date'

    # Select price columns (use adjusted if available and requested)
    if use_adj and 'adj_close' in df.columns:
        adj_cols = ['adj_open', 'adj_high', 'adj_low', 'adj_close']
        # Check if all adjusted columns exist
        if all(col in df.columns for col in adj_cols):
            # Use adjusted prices - select and rename in one step
            price_mapping = {
                'adj_open': 'open',
                'adj_high': 'high',
                'adj_low': 'low',
                'adj_close': 'close',
                'volume': 'volume'
            }
            if 'amount' in df.columns:
                price_mapping['amount'] = 'amount'

            # Select only the columns we need and rename
            df = df[list(price_mapping.keys())].rename(columns=price_mapping)
        else:
            # Fall back to unadjusted
            logger.warning(
                f"{symbol}: Not all adjusted price columns found, using unadjusted"
            )
            # Select unadjusted columns
            cols_to_keep = ['open', 'high', 'low', 'close', 'volume']
            if 'amount' in df.columns:
                cols_to_keep.append('amount')
            df = df[cols_to_keep]
    else:
        # Use unadjusted prices - select only needed columns
        cols_to_keep = ['open', 'high', 'low', 'close', 'volume']
        if 'amount' in df.columns:
            cols_to_keep.append('amount')
        df = df[cols_to_keep]

    # Ensure required columns exist (should already be selected above)
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"{symbol}: Missing required columns: {missing_cols}")

    # Filter by date range
    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df.index >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df.index <= end_dt]

    if df.empty:
        raise ValueError(
            f"{symbol}: No data in date range [{start_date}, {end_date}]"
        )

    # Sort by date
    df = df.sort_index()

    # Basic data validation
    if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
        logger.warning(f"{symbol}: Found non-positive prices, filtering out")
        df = df[(df[['open', 'high', 'low', 'close']] > 0).all(axis=1)]

    # Check high >= low
    invalid_hl = df['high'] < df['low']
    if invalid_hl.any():
        logger.warning(
            f"{symbol}: Found {invalid_hl.sum()} rows where high < low, fixing"
        )
        # Swap high and low
        high_vals = df.loc[invalid_hl, 'high'].values
        low_vals = df.loc[invalid_hl, 'low'].values
        df.loc[invalid_hl, 'high'] = low_vals
        df.loc[invalid_hl, 'low'] = high_vals

    return df


def load_universe(
    symbols: List[str],
    data_dir: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_adj: bool = True,
    skip_errors: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Load OHLCV data for multiple ETFs.

    Args:
        symbols: List of ETF symbols
        data_dir: Directory containing ETF CSV files
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        use_adj: Whether to use adjusted prices
        skip_errors: If True, skip symbols that fail to load; if False, raise

    Returns:
        Dictionary mapping symbol to DataFrame
    """
    result = {}
    failed = []

    for symbol in symbols:
        try:
            df = load_single_etf(
                symbol=symbol,
                data_dir=data_dir,
                start_date=start_date,
                end_date=end_date,
                use_adj=use_adj
            )
            result[symbol] = df
        except Exception as e:
            if skip_errors:
                logger.warning(f"Failed to load {symbol}: {e}")
                failed.append(symbol)
            else:
                raise

    if failed:
        logger.info(
            f"Successfully loaded {len(result)}/{len(symbols)} symbols. "
            f"Failed: {failed}"
        )
    else:
        logger.info(f"Successfully loaded all {len(result)} symbols")

    return result


def load_universe_from_file(
    pool_file: str,
    data_dir: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_adj: bool = True,
    skip_errors: bool = True,
    symbol_column: str = 'ts_code'
) -> Dict[str, pd.DataFrame]:
    """
    Load ETF universe from a pool file (CSV).

    Args:
        pool_file: Path to CSV file containing symbol list
        data_dir: Directory containing ETF CSV files
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        use_adj: Whether to use adjusted prices
        skip_errors: If True, skip symbols that fail to load
        symbol_column: Name of the column containing symbols (default: 'ts_code')

    Returns:
        Dictionary mapping symbol to DataFrame

    Raises:
        FileNotFoundError: If pool_file doesn't exist
        ValueError: If pool_file is invalid or empty
    """
    if not os.path.exists(pool_file):
        raise FileNotFoundError(f"Pool file not found: {pool_file}")

    try:
        pool_df = pd.read_csv(pool_file)
    except Exception as e:
        raise ValueError(f"Failed to read pool file {pool_file}: {e}")

    if pool_df.empty:
        raise ValueError(f"Pool file is empty: {pool_file}")

    # Try to find symbol column
    if symbol_column not in pool_df.columns:
        # Try alternative column names
        alternatives = ['symbol', 'code', 'ts_code', 'stock_code']
        for alt in alternatives:
            if alt in pool_df.columns:
                symbol_column = alt
                break
        else:
            # Use first column
            symbol_column = pool_df.columns[0]
            logger.warning(
                f"Symbol column not found, using first column: {symbol_column}"
            )

    symbols = pool_df[symbol_column].dropna().unique().tolist()

    if not symbols:
        raise ValueError(f"No symbols found in pool file: {pool_file}")

    logger.info(f"Loading {len(symbols)} symbols from {pool_file}")

    return load_universe(
        symbols=symbols,
        data_dir=data_dir,
        start_date=start_date,
        end_date=end_date,
        use_adj=use_adj,
        skip_errors=skip_errors
    )


def filter_by_liquidity(
    data_dict: Dict[str, pd.DataFrame],
    min_amount: Optional[float] = None,
    min_volume: Optional[float] = None,
    lookback_days: int = 20,
    min_valid_days: int = 15
) -> Dict[str, pd.DataFrame]:
    """
    Filter ETFs by liquidity criteria.

    Args:
        data_dict: Dictionary of symbol -> DataFrame
        min_amount: Minimum average daily trading amount (in yuan)
        min_volume: Minimum average daily trading volume (in shares)
        lookback_days: Number of days to calculate average (default: 20)
        min_valid_days: Minimum number of valid days required in lookback period

    Returns:
        Filtered dictionary with only liquid ETFs
    """
    if min_amount is None and min_volume is None:
        logger.info("No liquidity filters specified, returning all symbols")
        return data_dict

    result = {}
    filtered_out = []

    for symbol, df in data_dict.items():
        if len(df) < min_valid_days:
            logger.debug(
                f"{symbol}: Insufficient data ({len(df)} < {min_valid_days} days)"
            )
            filtered_out.append((symbol, 'insufficient_data'))
            continue

        # Calculate rolling average for recent period
        recent_df = df.tail(lookback_days)

        # Check amount filter
        if min_amount is not None:
            if 'amount' not in df.columns:
                logger.warning(
                    f"{symbol}: No 'amount' column, cannot apply amount filter"
                )
                filtered_out.append((symbol, 'no_amount_column'))
                continue

            avg_amount = recent_df['amount'].mean()
            if pd.isna(avg_amount) or avg_amount < min_amount:
                logger.debug(
                    f"{symbol}: Low liquidity (avg_amount={avg_amount:.0f} "
                    f"< {min_amount:.0f})"
                )
                filtered_out.append((symbol, 'low_amount'))
                continue

        # Check volume filter
        if min_volume is not None:
            avg_volume = recent_df['volume'].mean()
            if pd.isna(avg_volume) or avg_volume < min_volume:
                logger.debug(
                    f"{symbol}: Low volume (avg_volume={avg_volume:.0f} "
                    f"< {min_volume:.0f})"
                )
                filtered_out.append((symbol, 'low_volume'))
                continue

        result[symbol] = df

    logger.info(
        f"Liquidity filter: {len(result)}/{len(data_dict)} symbols passed. "
        f"Filtered out: {len(filtered_out)}"
    )

    return result


def align_dates(
    data_dict: Dict[str, pd.DataFrame],
    method: str = 'intersection',
    fill_method: Optional[str] = 'ffill',
    max_fill_days: int = 5
) -> Dict[str, pd.DataFrame]:
    """
    Align dates across all ETFs in the universe.

    Args:
        data_dict: Dictionary of symbol -> DataFrame
        method: 'intersection' (only common dates) or 'union' (all dates)
        fill_method: How to fill missing values ('ffill', 'bfill', None)
        max_fill_days: Maximum number of days to forward/backward fill

    Returns:
        Dictionary with aligned DataFrames
    """
    if not data_dict:
        return {}

    # Get all unique dates
    all_dates = set()
    for df in data_dict.values():
        all_dates.update(df.index)

    if method == 'intersection':
        # Find common dates across all symbols
        common_dates = set(list(data_dict.values())[0].index)
        for df in list(data_dict.values())[1:]:
            common_dates &= set(df.index)

        if not common_dates:
            logger.warning("No common dates found across all symbols")
            return {}

        target_dates = sorted(common_dates)
        logger.info(
            f"Aligning to {len(target_dates)} common dates "
            f"({min(target_dates)} to {max(target_dates)})"
        )

        # Filter each DataFrame to common dates
        result = {}
        for symbol, df in data_dict.items():
            aligned_df = df.loc[df.index.isin(target_dates)].sort_index()
            result[symbol] = aligned_df

        return result

    elif method == 'union':
        # Use all dates, fill missing values
        target_dates = sorted(all_dates)
        logger.info(
            f"Aligning to {len(target_dates)} union dates "
            f"({min(target_dates)} to {max(target_dates)})"
        )

        result = {}
        for symbol, df in data_dict.items():
            # Reindex to target dates
            aligned_df = df.reindex(target_dates)

            # Fill missing values if requested
            if fill_method == 'ffill':
                aligned_df = aligned_df.fillna(method='ffill', limit=max_fill_days)
            elif fill_method == 'bfill':
                aligned_df = aligned_df.fillna(method='bfill', limit=max_fill_days)

            # Drop rows that still have NaN after filling
            initial_len = len(aligned_df)
            aligned_df = aligned_df.dropna()
            dropped = initial_len - len(aligned_df)

            if dropped > 0:
                logger.debug(
                    f"{symbol}: Dropped {dropped} rows with missing data "
                    f"after filling"
                )

            result[symbol] = aligned_df

        return result

    else:
        raise ValueError(f"Invalid method: {method}. Use 'intersection' or 'union'")


def get_data_date_range(data_dict: Dict[str, pd.DataFrame]) -> tuple:
    """
    Get the overall date range covered by the data.

    Args:
        data_dict: Dictionary of symbol -> DataFrame

    Returns:
        Tuple of (min_date, max_date)
    """
    if not data_dict:
        return None, None

    min_date = min(df.index.min() for df in data_dict.values())
    max_date = max(df.index.max() for df in data_dict.values())

    return min_date, max_date


def validate_data_quality(
    data_dict: Dict[str, pd.DataFrame],
    min_data_points: int = 100,
    max_missing_pct: float = 0.05
) -> Dict[str, pd.DataFrame]:
    """
    Validate data quality and filter out problematic symbols.

    Args:
        data_dict: Dictionary of symbol -> DataFrame
        min_data_points: Minimum number of data points required
        max_missing_pct: Maximum percentage of missing values allowed

    Returns:
        Dictionary with only valid symbols
    """
    result = {}
    issues = []

    for symbol, df in data_dict.items():
        # Check minimum data points
        if len(df) < min_data_points:
            issues.append((symbol, f'insufficient_data_{len(df)}'))
            continue

        # Check for excessive missing values
        missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns))
        if missing_pct > max_missing_pct:
            issues.append((symbol, f'high_missing_{missing_pct:.2%}'))
            continue

        # Check for duplicate dates
        if df.index.duplicated().any():
            logger.warning(f"{symbol}: Found duplicate dates, removing")
            df = df[~df.index.duplicated(keep='first')]

        result[symbol] = df

    if issues:
        logger.info(
            f"Data quality validation: {len(result)}/{len(data_dict)} passed. "
            f"Issues: {len(issues)}"
        )

    return result
