"""
IO Utilities Usage Examples

This script demonstrates all major features of the io_utils module:
1. Logging configuration
2. Signal file I/O
3. Position snapshot management
4. Trade order persistence
5. Performance report generation
6. Data validation

Author: Claude
Date: 2025-12-11
"""

import sys
from pathlib import Path
import pandas as pd
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from io_utils import (
    setup_logging,
    save_signals, load_signals,
    save_positions, load_positions,
    save_trade_orders, load_trade_orders,
    save_performance_report,
    generate_summary_text,
    validate_ohlcv_df,
    ensure_dir,
    get_dated_filename,
    find_latest_snapshot,
    save_snapshot,
    load_latest_positions
)


def main():
    """Run all examples."""
    print("=" * 60)
    print("IO Utilities Module - Usage Examples")
    print("=" * 60)

    # Create temporary directory for examples
    temp_dir = tempfile.mkdtemp()
    print(f"\nUsing temporary directory: {temp_dir}\n")

    try:
        # ==================== Example 1: Logging ====================
        print("\n" + "=" * 60)
        print("Example 1: Logging Configuration")
        print("=" * 60)

        logger = setup_logging(
            log_dir=temp_dir,
            log_level='INFO',
            log_to_file=True,
            log_to_console=True
        )

        logger.info("This is an info message")
        logger.warning("This is a warning message")
        print("✓ Logging configured successfully")

        # ==================== Example 2: Signals ====================
        print("\n" + "=" * 60)
        print("Example 2: Signal File I/O")
        print("=" * 60)

        # Create sample signals
        signals = {
            '159994.SZ': 1,   # Buy signal
            '159941.SZ': -1,  # Sell signal
            '159819.SZ': 0    # Hold signal
        }

        # Save as CSV
        csv_path = Path(temp_dir) / 'signals.csv'
        save_signals(signals, str(csv_path), '2025-12-11', format='csv')
        print(f"✓ Signals saved to CSV: {csv_path}")

        # Save as JSON
        json_path = Path(temp_dir) / 'signals.json'
        save_signals(signals, str(json_path), '2025-12-11', format='json')
        print(f"✓ Signals saved to JSON: {json_path}")

        # Load signals
        loaded_signals = load_signals(str(json_path))
        print(f"✓ Loaded {len(loaded_signals)} signals from JSON")
        print(f"  Sample: 159994.SZ = {loaded_signals['159994.SZ']}")

        # ==================== Example 3: Positions ====================
        print("\n" + "=" * 60)
        print("Example 3: Position Snapshot Management")
        print("=" * 60)

        # Create sample positions
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

        # Save positions
        pos_path = Path(temp_dir) / 'positions.json'
        save_positions(positions, str(pos_path), '2025-12-11')
        print(f"✓ Positions saved: {pos_path}")

        # Load positions
        loaded_pos = load_positions(str(pos_path))
        print(f"✓ Loaded {len(loaded_pos)} positions")

        # ==================== Example 4: Snapshots ====================
        print("\n" + "=" * 60)
        print("Example 4: Dated Snapshots and History")
        print("=" * 60)

        snapshot_dir = Path(temp_dir) / 'snapshots'

        # Save multiple dated snapshots
        for date in ['2025-12-09', '2025-12-10', '2025-12-11']:
            path = save_snapshot(
                positions,
                str(snapshot_dir),
                date,
                prefix='portfolio'
            )
            print(f"✓ Saved snapshot: {Path(path).name}")

        # Find latest snapshot
        latest = find_latest_snapshot(str(snapshot_dir), prefix='portfolio')
        print(f"✓ Latest snapshot: {Path(latest).name}")

        # Load latest positions
        latest_pos = load_latest_positions(str(snapshot_dir), prefix='portfolio')
        print(f"✓ Loaded latest positions: {len(latest_pos)} holdings")

        # ==================== Example 5: Trade Orders ====================
        print("\n" + "=" * 60)
        print("Example 5: Trade Order Persistence")
        print("=" * 60)

        # Create sample trade orders
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
                'reason': 'Stop loss triggered'
            }
        ]

        # Save orders
        order_path = Path(temp_dir) / 'orders.csv'
        save_trade_orders(orders, str(order_path), '2025-12-11')
        print(f"✓ Saved {len(orders)} trade orders: {order_path}")

        # Load orders
        loaded_orders = load_trade_orders(str(order_path))
        print(f"✓ Loaded {len(loaded_orders)} orders")
        print(f"  First order: {loaded_orders[0]['action']} {loaded_orders[0]['symbol']}")

        # ==================== Example 6: Performance Report ====================
        print("\n" + "=" * 60)
        print("Example 6: Performance Report Generation")
        print("=" * 60)

        # Create sample performance data
        statistics = {
            'total_return': 0.3463,
            'annual_return': 0.18,
            'sharpe_ratio': 1.69,
            'max_drawdown': -0.0527,
            'win_rate': 0.64,
            'num_trades': 45,
            'avg_trade_return': 0.012,
            'best_trade': 0.085,
            'worst_trade': -0.032,
            'start_date': '2023-11-01',
            'end_date': '2025-12-11',
            'duration_days': 772
        }

        equity_curve = pd.DataFrame({
            'date': pd.date_range('2023-11-01', periods=10, freq='D'),
            'equity': [100000 + i*1000 for i in range(10)],
            'returns': [0] + [0.01] * 9,
            'drawdown': [0] * 10
        })

        trade_log = pd.DataFrame({
            'date': ['2023-11-02', '2023-11-03'],
            'symbol': ['159994.SZ', '159941.SZ'],
            'action': ['BUY', 'SELL'],
            'shares': [100, 100],
            'price': [1.658, 1.700],
            'pnl': [0, 4.2]
        })

        # Save performance report
        report_dir = Path(temp_dir) / 'report'
        save_performance_report(statistics, equity_curve, trade_log, str(report_dir))
        print(f"✓ Performance report saved to: {report_dir}")

        # Generate summary text
        summary = generate_summary_text(statistics)
        print("\n" + summary)

        # ==================== Example 7: Data Validation ====================
        print("\n" + "=" * 60)
        print("Example 7: OHLCV Data Validation")
        print("=" * 60)

        # Valid data
        valid_df = pd.DataFrame({
            'Open': [1.0, 1.1, 1.2],
            'High': [1.1, 1.2, 1.3],
            'Low': [0.9, 1.0, 1.1],
            'Close': [1.05, 1.15, 1.25],
            'Volume': [1000, 1100, 1200]
        }, index=pd.date_range('2025-01-01', periods=3))

        errors = validate_ohlcv_df(valid_df, symbol='159994.SZ')
        if not errors:
            print("✓ Valid OHLCV data passed validation")
        else:
            print(f"✗ Validation errors: {errors}")

        # Invalid data (High < Low)
        invalid_df = pd.DataFrame({
            'Open': [1.0],
            'High': [0.9],  # Invalid: High < Low
            'Low': [1.1],
            'Close': [1.05]
        }, index=pd.date_range('2025-01-01', periods=1))

        errors = validate_ohlcv_df(invalid_df, symbol='INVALID')
        if errors:
            print(f"✓ Invalid data detected: {len(errors)} error(s)")
            for error in errors:
                print(f"  - {error}")

        # ==================== Example 8: Path Utilities ====================
        print("\n" + "=" * 60)
        print("Example 8: Path Utilities")
        print("=" * 60)

        # Dated filename
        filename = get_dated_filename('portfolio', '2025-12-11', 'json')
        print(f"✓ Dated filename: {filename}")

        # Ensure directory
        nested_dir = Path(temp_dir) / 'nested' / 'deep' / 'path'
        ensure_dir(str(nested_dir))
        print(f"✓ Created nested directory: {nested_dir.exists()}")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print("\n" + "=" * 60)
        print("✓ All examples completed successfully!")
        print("=" * 60)


if __name__ == '__main__':
    main()
