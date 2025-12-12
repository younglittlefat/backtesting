"""
Unit tests for io_utils module

Tests cover:
- Logging configuration
- Signal file I/O (CSV/JSON)
- Position snapshot management
- Trade order persistence
- Performance report generation
- Data validation
- Path utilities

Author: Claude
Date: 2025-12-11
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import pandas as pd
import json
import csv
import logging
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from io_utils import (
    setup_logging,
    save_signals, load_signals,
    save_positions, load_positions,
    save_trade_orders, load_trade_orders,
    save_performance_report,
    generate_summary_text,
    validate_ohlcv_df,
    validate_config_paths,
    ensure_dir,
    get_dated_filename,
    find_latest_snapshot,
    load_latest_positions,
    save_snapshot
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


# ==================== Logging Tests ====================

def test_setup_logging_console_only(temp_dir):
    """Test logging setup with console output only."""
    logger = setup_logging(
        log_dir=temp_dir,
        log_level='INFO',
        log_to_file=False,
        log_to_console=True
    )

    assert logger is not None
    assert logger.level == logging.INFO

    # Should have only console handler
    console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(console_handlers) > 0


def test_setup_logging_file_rotation(temp_dir):
    """Test logging setup with file rotation."""
    logger = setup_logging(
        log_dir=temp_dir,
        log_level='DEBUG',
        log_to_file=True,
        log_to_console=False
    )

    assert logger.level == logging.DEBUG

    # Write a log message
    logger.info("Test message")

    # Check log file exists
    log_files = list(Path(temp_dir).glob('*.log'))
    assert len(log_files) > 0


# ==================== Signal I/O Tests ====================

def test_save_load_signals_csv(temp_dir):
    """Test signal saving and loading in CSV format."""
    signals = {
        '159994.SZ': 1,
        '159941.SZ': -1,
        '159819.SZ': 0
    }

    output_path = Path(temp_dir) / 'signals.csv'
    save_signals(signals, str(output_path), '2025-12-11', format='csv')

    # Verify file exists
    assert output_path.exists()

    # Load and verify
    loaded_signals = load_signals(str(output_path))
    assert loaded_signals == signals


def test_save_load_signals_json(temp_dir):
    """Test signal saving and loading in JSON format."""
    signals = {
        '159994.SZ': 1,
        '159941.SZ': -1,
        '159819.SZ': 0
    }

    output_path = Path(temp_dir) / 'signals.json'
    save_signals(signals, str(output_path), '20251211', format='json')

    # Verify file exists
    assert output_path.exists()

    # Load and verify
    loaded_signals = load_signals(str(output_path))
    assert loaded_signals == signals


def test_load_signals_file_not_found():
    """Test loading signals from non-existent file."""
    with pytest.raises(FileNotFoundError):
        load_signals('/nonexistent/signals.csv')


# ==================== Position I/O Tests ====================

def test_save_load_positions(temp_dir):
    """Test position snapshot saving and loading."""
    positions = {
        '159994.SZ': {
            'shares': 30100,
            'entry_price': 1.658,
            'entry_date': '2025-11-26',
            'cost': 49915.78
        },
        '159941.SZ': {
            'shares': 34600,
            'entry_price': 1.443,
            'entry_date': '2025-11-26',
            'cost': 49937.79
        }
    }

    output_path = Path(temp_dir) / 'positions.json'
    save_positions(positions, str(output_path), '2025-12-11')

    # Verify file exists
    assert output_path.exists()

    # Load and verify
    loaded_positions = load_positions(str(output_path))
    assert loaded_positions == positions


def test_load_positions_file_not_found():
    """Test loading positions from non-existent file."""
    with pytest.raises(FileNotFoundError):
        load_positions('/nonexistent/positions.json')


# ==================== Trade Order Tests ====================

def test_save_load_trade_orders(temp_dir):
    """Test trade order saving and loading."""
    orders = [
        {
            'action': 'BUY',
            'symbol': '159994.SZ',
            'shares': 30100,
            'price': 1.658,
            'amount': -49915.78,
            'commission': 4.99,
            'reason': 'KAMA buy signal'
        },
        {
            'action': 'SELL',
            'symbol': '159941.SZ',
            'shares': 34600,
            'price': 1.500,
            'amount': 51900.00,
            'commission': 5.19,
            'reason': 'Stop loss'
        }
    ]

    output_path = Path(temp_dir) / 'trades.csv'
    save_trade_orders(orders, str(output_path), '2025-12-11')

    # Verify file exists
    assert output_path.exists()

    # Load and verify
    loaded_orders = load_trade_orders(str(output_path))
    assert len(loaded_orders) == 2
    assert loaded_orders[0]['symbol'] == '159994.SZ'
    assert loaded_orders[0]['shares'] == 30100
    assert loaded_orders[1]['action'] == 'SELL'


def test_save_empty_trade_orders(temp_dir):
    """Test saving empty trade orders list."""
    output_path = Path(temp_dir) / 'trades.csv'
    save_trade_orders([], str(output_path), '2025-12-11')

    # File should not be created for empty orders
    # (function logs warning and returns early)


# ==================== Performance Report Tests ====================

def test_save_performance_report(temp_dir):
    """Test saving comprehensive performance report."""
    statistics = {
        'total_return': 0.3463,
        'annual_return': 0.18,
        'sharpe_ratio': 1.69,
        'max_drawdown': -0.0527,
        'win_rate': 0.64,
        'num_trades': 45
    }

    equity_curve = pd.DataFrame({
        'date': ['2025-01-01', '2025-01-02', '2025-01-03'],
        'equity': [100000, 101000, 102000],
        'returns': [0, 0.01, 0.0099],
        'drawdown': [0, 0, 0]
    })

    trade_log = pd.DataFrame({
        'date': ['2025-01-02', '2025-01-03'],
        'symbol': ['159994.SZ', '159941.SZ'],
        'action': ['BUY', 'SELL'],
        'shares': [100, 100],
        'price': [1.658, 1.700],
        'pnl': [0, 4.2]
    })

    save_performance_report(statistics, equity_curve, trade_log, temp_dir)

    # Verify all three files exist
    assert (Path(temp_dir) / 'statistics.json').exists()
    assert (Path(temp_dir) / 'equity_curve.csv').exists()
    assert (Path(temp_dir) / 'trade_log.csv').exists()


def test_generate_summary_text():
    """Test performance summary text generation."""
    statistics = {
        'total_return': 0.3463,
        'sharpe_ratio': 1.69,
        'max_drawdown': -0.0527,
        'win_rate': 0.64,
        'num_trades': 45,
        'start_date': '2025-01-01',
        'end_date': '2025-12-11'
    }

    summary = generate_summary_text(statistics)

    assert 'Performance Summary' in summary
    assert '34.63%' in summary  # Total return
    assert '1.69' in summary    # Sharpe ratio
    assert '-5.27%' in summary  # Max drawdown
    assert '45' in summary      # Num trades


# ==================== Data Validation Tests ====================

def test_validate_ohlcv_df_valid():
    """Test OHLCV validation with valid data."""
    df = pd.DataFrame({
        'Open': [1.0, 1.1, 1.2],
        'High': [1.1, 1.2, 1.3],
        'Low': [0.9, 1.0, 1.1],
        'Close': [1.05, 1.15, 1.25],
        'Volume': [1000, 1100, 1200]
    }, index=pd.date_range('2025-01-01', periods=3))

    errors = validate_ohlcv_df(df, symbol='TEST')
    assert len(errors) == 0


def test_validate_ohlcv_df_missing_columns():
    """Test OHLCV validation with missing columns."""
    df = pd.DataFrame({
        'Open': [1.0, 1.1],
        'High': [1.1, 1.2]
    })

    errors = validate_ohlcv_df(df, symbol='TEST')
    assert len(errors) > 0
    assert any('Missing required columns' in e for e in errors)


def test_validate_ohlcv_df_invalid_relationships():
    """Test OHLCV validation with invalid OHLC relationships."""
    df = pd.DataFrame({
        'Open': [1.0, 1.1],
        'High': [1.1, 1.0],  # High < Low
        'Low': [0.9, 1.2],
        'Close': [1.05, 1.15]
    }, index=pd.date_range('2025-01-01', periods=2))

    errors = validate_ohlcv_df(df, symbol='TEST')
    assert len(errors) > 0
    assert any('High < Low' in e for e in errors)


def test_validate_ohlcv_df_negative_prices():
    """Test OHLCV validation with negative prices."""
    df = pd.DataFrame({
        'Open': [1.0, -1.1],  # Negative price
        'High': [1.1, 1.2],
        'Low': [0.9, 1.0],
        'Close': [1.05, 1.15]
    }, index=pd.date_range('2025-01-01', periods=2))

    errors = validate_ohlcv_df(df, symbol='TEST')
    assert len(errors) > 0
    assert any('non-positive values' in e for e in errors)


def test_validate_config_paths(temp_dir):
    """Test configuration path validation."""
    # Create a valid directory
    valid_dir = Path(temp_dir) / 'valid'
    valid_dir.mkdir()

    config = {
        'data_dir': str(valid_dir),
        'results_dir': '/nonexistent/path'
    }

    errors = validate_config_paths(config)
    assert len(errors) > 0
    assert any('results_dir' in e for e in errors)


# ==================== Path Utilities Tests ====================

def test_ensure_dir(temp_dir):
    """Test directory creation."""
    test_path = Path(temp_dir) / 'nested' / 'deep' / 'path'
    ensure_dir(str(test_path))

    assert test_path.exists()
    assert test_path.is_dir()


def test_get_dated_filename():
    """Test dated filename generation."""
    filename = get_dated_filename('portfolio', '2025-12-11', 'json')
    assert filename == 'portfolio_20251211.json'

    filename = get_dated_filename('signals', '20251211', '.csv')
    assert filename == 'signals_20251211.csv'


def test_find_latest_snapshot(temp_dir):
    """Test finding latest snapshot file."""
    # Create multiple snapshot files
    snapshot_dir = Path(temp_dir) / 'snapshots'
    snapshot_dir.mkdir()

    (snapshot_dir / 'snapshot_etf_kama_cross_portfolio_20251209.json').touch()
    (snapshot_dir / 'snapshot_etf_kama_cross_portfolio_20251210.json').touch()
    (snapshot_dir / 'snapshot_etf_kama_cross_portfolio_20251211.json').touch()

    latest = find_latest_snapshot(str(snapshot_dir), prefix='snapshot_etf_kama')

    assert '20251211' in latest


def test_find_latest_snapshot_not_found(temp_dir):
    """Test finding latest snapshot when no files exist."""
    snapshot_dir = Path(temp_dir) / 'empty'
    snapshot_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        find_latest_snapshot(str(snapshot_dir), prefix='nonexistent')


def test_save_snapshot(temp_dir):
    """Test saving position snapshot with dated filename."""
    positions = {
        '159994.SZ': {'shares': 100, 'entry_price': 1.658}
    }

    snapshot_dir = Path(temp_dir) / 'snapshots'
    saved_path = save_snapshot(positions, str(snapshot_dir), '2025-12-11', prefix='test_portfolio')

    assert Path(saved_path).exists()
    assert '20251211' in saved_path
    assert 'test_portfolio' in saved_path


def test_load_latest_positions(temp_dir):
    """Test loading latest position snapshot."""
    snapshot_dir = Path(temp_dir) / 'snapshots'
    snapshot_dir.mkdir()

    # Create multiple snapshots
    positions1 = {'SYM1': {'shares': 100}}
    positions2 = {'SYM2': {'shares': 200}}

    save_snapshot(positions1, str(snapshot_dir), '2025-12-10', prefix='portfolio')
    save_snapshot(positions2, str(snapshot_dir), '2025-12-11', prefix='portfolio')

    # Load latest
    loaded = load_latest_positions(str(snapshot_dir), prefix='portfolio')

    # Should load the newer snapshot (positions2)
    assert 'SYM2' in loaded
    assert loaded['SYM2']['shares'] == 200


# ==================== Integration Tests ====================

def test_full_workflow(temp_dir):
    """Test complete workflow: signals -> orders -> positions -> report."""
    # Step 1: Generate and save signals
    signals = {'159994.SZ': 1, '159941.SZ': -1}
    signal_file = Path(temp_dir) / 'signals.json'
    save_signals(signals, str(signal_file), '2025-12-11', format='json')

    # Step 2: Save trade orders
    orders = [
        {'action': 'BUY', 'symbol': '159994.SZ', 'shares': 100, 'price': 1.658, 'amount': -165.8, 'commission': 0.17, 'reason': 'Signal'},
        {'action': 'SELL', 'symbol': '159941.SZ', 'shares': 100, 'price': 1.500, 'amount': 150.0, 'commission': 0.15, 'reason': 'Signal'}
    ]
    order_file = Path(temp_dir) / 'orders.csv'
    save_trade_orders(orders, str(order_file), '2025-12-11')

    # Step 3: Save positions
    positions = {
        '159994.SZ': {'shares': 100, 'entry_price': 1.658, 'entry_date': '2025-12-11', 'cost': 165.8}
    }
    position_file = Path(temp_dir) / 'positions.json'
    save_positions(positions, str(position_file), '2025-12-11')

    # Step 4: Generate performance report
    stats = {'total_return': 0.10, 'sharpe_ratio': 1.5}
    equity = pd.DataFrame({'date': ['2025-12-11'], 'equity': [110000]})
    trades = pd.DataFrame({'date': ['2025-12-11'], 'symbol': ['159994.SZ'], 'action': ['BUY']})

    report_dir = Path(temp_dir) / 'report'
    save_performance_report(stats, equity, trades, str(report_dir))

    # Verify all files exist
    assert signal_file.exists()
    assert order_file.exists()
    assert position_file.exists()
    assert (report_dir / 'statistics.json').exists()
    assert (report_dir / 'equity_curve.csv').exists()
    assert (report_dir / 'trade_log.csv').exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
