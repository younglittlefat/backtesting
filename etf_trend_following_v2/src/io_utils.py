"""
IO Utilities Module for ETF Trend Following v2 System

This module handles file I/O operations including:
- Logging configuration with file rotation
- Signal file reading/writing (CSV/JSON)
- Position snapshot management
- Trade order persistence
- Performance report generation
- Data validation

Author: Claude
Date: 2025-12-11
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import json
import csv
import pandas as pd
import numpy as np
import re


# ==================== Logging Configuration ====================

def setup_logging(
    log_dir: Optional[str] = None,
    log_level: str = 'INFO',
    log_format: Optional[str] = None,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Configure logging system with file rotation and console output.

    Parameters
    ----------
    log_dir : str, optional
        Directory for log files. If None, logs to './logs'
    log_level : str, default 'INFO'
        Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_format : str, optional
        Custom log format. If None, uses default format
    log_to_file : bool, default True
        Enable logging to rotating daily files
    log_to_console : bool, default True
        Enable logging to console

    Returns
    -------
    logging.Logger
        Configured root logger

    Examples
    --------
    >>> logger = setup_logging(log_dir='./logs', log_level='DEBUG')
    >>> logger.info("System started")
    """
    # Default format with timestamp, level, module, and message
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with daily rotation
    if log_to_file:
        if log_dir is None:
            log_dir = './logs'

        log_path = Path(log_dir)
        ensure_dir(str(log_path))

        log_file = log_path / 'etf_trend_following.log'

        # Rotate at midnight, keep 30 days
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        file_handler.suffix = '%Y%m%d'  # Date suffix for rotated files
        root_logger.addHandler(file_handler)

    root_logger.info(f"Logging configured: level={log_level}, file={log_to_file}, console={log_to_console}")

    return root_logger


# ==================== Signal Files ====================

def save_signals(
    signals: Dict[str, int],
    output_path: str,
    date: str,
    format: str = 'csv'
) -> None:
    """
    Save trading signals to file.

    Parameters
    ----------
    signals : Dict[str, int]
        Signal dictionary {symbol: signal}, where signal is 1 (buy), -1 (sell), or 0 (hold)
    output_path : str
        Output file path
    date : str
        Signal generation date (YYYY-MM-DD or YYYYMMDD)
    format : str, default 'csv'
        Output format: 'csv' or 'json'

    Examples
    --------
    >>> signals = {'159994.SZ': 1, '159941.SZ': -1, '159819.SZ': 0}
    >>> save_signals(signals, 'signals.csv', '2025-12-11')
    """
    ensure_dir(str(Path(output_path).parent))

    # Normalize date format
    clean_date = date.replace('-', '')

    if format == 'csv':
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['symbol', 'signal', 'date'])
            for symbol, signal in sorted(signals.items()):
                writer.writerow([symbol, signal, clean_date])
    elif format == 'json':
        data = {
            'date': clean_date,
            'signals': signals,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'json'")

    logging.info(f"Saved {len(signals)} signals to {output_path} (format={format})")


def load_signals(path: str) -> Dict[str, int]:
    """
    Load trading signals from file.

    Parameters
    ----------
    path : str
        Input file path (.csv or .json)

    Returns
    -------
    Dict[str, int]
        Signal dictionary {symbol: signal}

    Examples
    --------
    >>> signals = load_signals('signals.json')
    >>> print(signals['159994.SZ'])
    1
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Signal file not found: {path}")

    if path_obj.suffix == '.csv':
        signals = {}
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                signals[row['symbol']] = int(row['signal'])
        return signals

    elif path_obj.suffix == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('signals', {})

    else:
        raise ValueError(f"Unsupported file format: {path_obj.suffix}. Use .csv or .json")


# ==================== Position Files ====================

def save_positions(
    positions: Dict[str, dict],
    output_path: str,
    date: str
) -> None:
    """
    Save position snapshot to JSON file.

    Parameters
    ----------
    positions : Dict[str, dict]
        Position dictionary {symbol: position_data}
    output_path : str
        Output JSON file path
    date : str
        Snapshot date (YYYY-MM-DD or YYYYMMDD)

    Examples
    --------
    >>> positions = {
    ...     '159994.SZ': {'shares': 30100, 'entry_price': 1.658, 'cost': 49915.78}
    ... }
    >>> save_positions(positions, 'positions.json', '2025-12-11')
    """
    ensure_dir(str(Path(output_path).parent))

    # Normalize date format
    clean_date = date.replace('-', '')

    data = {
        'date': clean_date,
        'positions': positions,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(positions)
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logging.info(f"Saved {len(positions)} positions to {output_path}")


def load_positions(path: str) -> Dict[str, dict]:
    """
    Load position snapshot from JSON file.

    Parameters
    ----------
    path : str
        Input JSON file path

    Returns
    -------
    Dict[str, dict]
        Position dictionary {symbol: position_data}

    Examples
    --------
    >>> positions = load_positions('positions.json')
    >>> print(positions['159994.SZ']['shares'])
    30100
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Position file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('positions', {})


# ==================== Trade Orders ====================

def save_trade_orders(
    orders: List[dict],
    output_path: str,
    date: str
) -> None:
    """
    Save trade orders to CSV file.

    Parameters
    ----------
    orders : List[dict]
        List of trade orders with keys: action, symbol, shares, price, reason
    output_path : str
        Output CSV file path
    date : str
        Trade date (YYYY-MM-DD or YYYYMMDD)

    Examples
    --------
    >>> orders = [
    ...     {'action': 'BUY', 'symbol': '159994.SZ', 'shares': 100, 'price': 1.658, 'reason': 'Signal'}
    ... ]
    >>> save_trade_orders(orders, 'trades.csv', '2025-12-11')
    """
    ensure_dir(str(Path(output_path).parent))

    # Normalize date format
    clean_date = date.replace('-', '')

    if not orders:
        logging.warning(f"No trade orders to save for {clean_date}")
        return

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        # Determine fieldnames from first order, ensure standard fields exist
        fieldnames = ['date', 'action', 'symbol', 'shares', 'price', 'amount', 'commission', 'reason']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')

        writer.writeheader()
        for order in orders:
            row = {'date': clean_date}
            row.update(order)
            writer.writerow(row)

    logging.info(f"Saved {len(orders)} trade orders to {output_path}")


def load_trade_orders(path: str) -> List[dict]:
    """
    Load trade orders from CSV file.

    Parameters
    ----------
    path : str
        Input CSV file path

    Returns
    -------
    List[dict]
        List of trade orders

    Examples
    --------
    >>> orders = load_trade_orders('trades.csv')
    >>> print(orders[0]['action'])
    'BUY'
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Trade order file not found: {path}")

    orders = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            if 'shares' in row:
                row['shares'] = int(row['shares'])
            if 'price' in row:
                row['price'] = float(row['price'])
            if 'amount' in row:
                row['amount'] = float(row['amount'])
            if 'commission' in row:
                row['commission'] = float(row['commission'])
            orders.append(row)

    return orders


# ==================== Performance Reports ====================

def save_performance_report(
    statistics: dict,
    equity_curve: pd.DataFrame,
    trade_log: pd.DataFrame,
    output_dir: str
) -> None:
    """
    Save comprehensive performance report.

    Generates three files:
    - statistics.json: Performance metrics
    - equity_curve.csv: Daily equity values
    - trade_log.csv: Complete trade history

    Parameters
    ----------
    statistics : dict
        Performance statistics dictionary
    equity_curve : pd.DataFrame
        Daily equity curve with columns: date, equity, returns, drawdown
    trade_log : pd.DataFrame
        Trade log with columns: date, symbol, action, shares, price, pnl
    output_dir : str
        Output directory path

    Examples
    --------
    >>> stats = {'total_return': 0.35, 'sharpe_ratio': 1.69, 'max_drawdown': -0.05}
    >>> equity_df = pd.DataFrame({'date': [...], 'equity': [...]})
    >>> trades_df = pd.DataFrame({'date': [...], 'symbol': [...], 'action': [...]})
    >>> save_performance_report(stats, equity_df, trades_df, './results')
    """
    ensure_dir(output_dir)
    output_path = Path(output_dir)

    # Save statistics as JSON
    stats_file = output_path / 'statistics.json'
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(statistics, f, indent=2, ensure_ascii=False, default=str)

    # Save equity curve as CSV
    equity_file = output_path / 'equity_curve.csv'
    equity_curve.to_csv(equity_file, index=False, encoding='utf-8')

    # Save trade log as CSV
    trades_file = output_path / 'trade_log.csv'
    trade_log.to_csv(trades_file, index=False, encoding='utf-8')

    logging.info(f"Performance report saved to {output_dir}")
    logging.info(f"  - Statistics: {stats_file}")
    logging.info(f"  - Equity curve: {equity_file}")
    logging.info(f"  - Trade log: {trades_file}")


def generate_summary_text(statistics: dict) -> str:
    """
    Generate human-readable performance summary text.

    Parameters
    ----------
    statistics : dict
        Performance statistics dictionary

    Returns
    -------
    str
        Formatted summary text

    Examples
    --------
    >>> stats = {'total_return': 0.3463, 'sharpe_ratio': 1.69, 'max_drawdown': -0.0527}
    >>> print(generate_summary_text(stats))
    Performance Summary
    ===================
    Total Return:    34.63%
    Sharpe Ratio:     1.69
    Max Drawdown:    -5.27%
    ...
    """
    lines = []
    lines.append("Performance Summary")
    lines.append("=" * 50)

    # Key metrics
    if 'total_return' in statistics:
        lines.append(f"Total Return:    {statistics['total_return']*100:>8.2f}%")
    if 'annual_return' in statistics:
        lines.append(f"Annual Return:   {statistics['annual_return']*100:>8.2f}%")
    if 'sharpe_ratio' in statistics:
        lines.append(f"Sharpe Ratio:    {statistics['sharpe_ratio']:>8.2f}")
    if 'max_drawdown' in statistics:
        lines.append(f"Max Drawdown:    {statistics['max_drawdown']*100:>8.2f}%")
    if 'win_rate' in statistics:
        lines.append(f"Win Rate:        {statistics['win_rate']*100:>8.2f}%")

    lines.append("")

    # Trade statistics
    if 'num_trades' in statistics:
        lines.append(f"Total Trades:    {statistics['num_trades']:>8}")
    if 'avg_trade_return' in statistics:
        lines.append(f"Avg Trade:       {statistics['avg_trade_return']*100:>8.2f}%")
    if 'best_trade' in statistics:
        lines.append(f"Best Trade:      {statistics['best_trade']*100:>8.2f}%")
    if 'worst_trade' in statistics:
        lines.append(f"Worst Trade:     {statistics['worst_trade']*100:>8.2f}%")

    lines.append("")

    # Period info
    if 'start_date' in statistics:
        lines.append(f"Start Date:      {statistics['start_date']}")
    if 'end_date' in statistics:
        lines.append(f"End Date:        {statistics['end_date']}")
    if 'duration_days' in statistics:
        lines.append(f"Duration:        {statistics['duration_days']} days")

    lines.append("=" * 50)

    return "\n".join(lines)


# ==================== Data Validation ====================

def validate_ohlcv_df(df: pd.DataFrame, symbol: Optional[str] = None) -> List[str]:
    """
    Validate OHLCV DataFrame format and data quality.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate
    symbol : str, optional
        Symbol name for error messages

    Returns
    -------
    List[str]
        List of error messages (empty if valid)

    Examples
    --------
    >>> df = pd.DataFrame({'Open': [1.0], 'High': [1.1], 'Low': [0.9], 'Close': [1.05]})
    >>> errors = validate_ohlcv_df(df, symbol='159994.SZ')
    >>> if errors:
    ...     print("Validation failed:", errors)
    """
    errors = []
    prefix = f"[{symbol}] " if symbol else ""

    # Check required columns
    required_cols = ['Open', 'High', 'Low', 'Close']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"{prefix}Missing required columns: {missing_cols}")
        return errors  # Cannot proceed with further checks

    # Check for empty DataFrame
    if df.empty:
        errors.append(f"{prefix}DataFrame is empty")
        return errors

    # Check for NaN values
    for col in required_cols:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            errors.append(f"{prefix}Column '{col}' has {nan_count} NaN values")

    # Check OHLC relationships
    invalid_high = (df['High'] < df['Low']).sum()
    if invalid_high > 0:
        errors.append(f"{prefix}High < Low in {invalid_high} rows")

    invalid_range_open = ((df['Open'] > df['High']) | (df['Open'] < df['Low'])).sum()
    if invalid_range_open > 0:
        errors.append(f"{prefix}Open outside [Low, High] in {invalid_range_open} rows")

    invalid_range_close = ((df['Close'] > df['High']) | (df['Close'] < df['Low'])).sum()
    if invalid_range_close > 0:
        errors.append(f"{prefix}Close outside [Low, High] in {invalid_range_close} rows")

    # Check for negative prices
    for col in required_cols:
        negative_count = (df[col] <= 0).sum()
        if negative_count > 0:
            errors.append(f"{prefix}Column '{col}' has {negative_count} non-positive values")

    # Check Volume if present
    if 'Volume' in df.columns:
        negative_vol = (df['Volume'] < 0).sum()
        if negative_vol > 0:
            errors.append(f"{prefix}Volume has {negative_vol} negative values")

    # Check index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        errors.append(f"{prefix}Index is not DatetimeIndex (type: {type(df.index).__name__})")
    else:
        # Check for duplicate dates
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            errors.append(f"{prefix}Index has {duplicates} duplicate dates")

    return errors


def validate_config_paths(config: dict) -> List[str]:
    """
    Validate that paths in configuration exist.

    Parameters
    ----------
    config : dict
        Configuration dictionary

    Returns
    -------
    List[str]
        List of error messages (empty if all paths valid)

    Examples
    --------
    >>> config = {'data_dir': '/mnt/d/git/backtesting/data', 'results_dir': './results'}
    >>> errors = validate_config_paths(config)
    >>> if errors:
    ...     print("Invalid paths:", errors)
    """
    errors = []

    # Common path keys to check
    path_keys = [
        'data_dir', 'results_dir', 'log_dir', 'output_dir',
        'position_file', 'signal_file', 'universe_file'
    ]

    for key in path_keys:
        if key in config:
            path = config[key]
            if path and not Path(path).exists():
                errors.append(f"Path for '{key}' does not exist: {path}")

    return errors


# ==================== Path Utilities ====================

def ensure_dir(path: str) -> None:
    """
    Ensure directory exists, create if not.

    Parameters
    ----------
    path : str
        Directory path to ensure

    Examples
    --------
    >>> ensure_dir('./results/backtest')
    """
    path_obj = Path(path)
    if not path_obj.exists():
        path_obj.mkdir(parents=True, exist_ok=True)
        logging.debug(f"Created directory: {path}")


def get_dated_filename(base_name: str, date: str, ext: str) -> str:
    """
    Generate filename with date suffix.

    Parameters
    ----------
    base_name : str
        Base filename without extension
    date : str
        Date string (YYYY-MM-DD or YYYYMMDD)
    ext : str
        File extension (with or without leading dot)

    Returns
    -------
    str
        Filename in format: base_name_YYYYMMDD.ext

    Examples
    --------
    >>> get_dated_filename('portfolio', '2025-12-11', 'json')
    'portfolio_20251211.json'
    >>> get_dated_filename('signals', '20251211', '.csv')
    'signals_20251211.csv'
    """
    # Normalize date to YYYYMMDD
    clean_date = date.replace('-', '')

    # Normalize extension
    if not ext.startswith('.'):
        ext = '.' + ext

    return f"{base_name}_{clean_date}{ext}"


def find_latest_snapshot(snapshot_dir: str, prefix: str = 'portfolio') -> str:
    """
    Find the latest snapshot file in directory by date suffix.

    Parameters
    ----------
    snapshot_dir : str
        Directory containing snapshot files
    prefix : str, default 'portfolio'
        Filename prefix to search for

    Returns
    -------
    str
        Path to latest snapshot file

    Raises
    ------
    FileNotFoundError
        If no matching snapshot files found

    Examples
    --------
    >>> latest = find_latest_snapshot('./positions/history', prefix='snapshot_etf_kama')
    >>> print(latest)
    './positions/history/snapshot_etf_kama_cross_portfolio_20251211.json'
    """
    snapshot_path = Path(snapshot_dir)

    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot directory not found: {snapshot_dir}")

    # Pattern: prefix*_YYYYMMDD.json
    pattern = re.compile(rf'{re.escape(prefix)}.*_(\d{{8}})\.json$')

    matching_files = []
    for file_path in snapshot_path.glob(f'{prefix}*.json'):
        match = pattern.search(file_path.name)
        if match:
            date_str = match.group(1)
            matching_files.append((date_str, file_path))

    if not matching_files:
        raise FileNotFoundError(f"No snapshot files found with prefix '{prefix}' in {snapshot_dir}")

    # Sort by date string (YYYYMMDD) and get latest
    matching_files.sort(key=lambda x: x[0], reverse=True)
    latest_file = matching_files[0][1]

    logging.info(f"Found latest snapshot: {latest_file} (date={matching_files[0][0]})")

    return str(latest_file)


# ==================== Convenience Functions ====================

def load_latest_positions(snapshot_dir: str, prefix: str = 'portfolio') -> Dict[str, dict]:
    """
    Load positions from latest snapshot file.

    Parameters
    ----------
    snapshot_dir : str
        Directory containing snapshot files
    prefix : str, default 'portfolio'
        Filename prefix

    Returns
    -------
    Dict[str, dict]
        Position dictionary

    Examples
    --------
    >>> positions = load_latest_positions('./positions/history', prefix='snapshot_etf_kama')
    """
    latest_file = find_latest_snapshot(snapshot_dir, prefix)
    return load_positions(latest_file)


def save_snapshot(
    positions: Dict[str, dict],
    snapshot_dir: str,
    date: str,
    prefix: str = 'portfolio'
) -> str:
    """
    Save position snapshot with dated filename.

    Parameters
    ----------
    positions : Dict[str, dict]
        Position dictionary
    snapshot_dir : str
        Snapshot directory
    date : str
        Snapshot date (YYYY-MM-DD or YYYYMMDD)
    prefix : str, default 'portfolio'
        Filename prefix

    Returns
    -------
    str
        Path to saved snapshot file

    Examples
    --------
    >>> path = save_snapshot(positions, './positions/history', '2025-12-11', 'snapshot_etf_kama')
    """
    ensure_dir(snapshot_dir)
    filename = get_dated_filename(prefix, date, 'json')
    output_path = Path(snapshot_dir) / filename
    save_positions(positions, str(output_path), date)
    return str(output_path)
