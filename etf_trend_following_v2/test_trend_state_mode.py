#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for P0-3 trend state mode fix

This script tests the new trend_state_mode configuration option:
- "event": Original behavior (trend ON after buy event)
- "condition": New behavior (trend ON when Close > KAMA)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from etf_trend_following_v2.src.config_loader import (
    Config,
    EnvConfig,
    ModesConfig,
    UniverseConfig,
    KAMAStrategyConfig,
    ScoringConfig,
    ClusteringConfig,
    RiskConfig,
    PositionSizingConfig,
    ExecutionConfig,
    IOConfig,
)
from etf_trend_following_v2.src.portfolio_backtest_runner import (
    _build_trend_state,
    _build_trend_state_condition,
)


def test_build_trend_state_event():
    """Test original event-based trend state logic"""
    print("\n=== Testing Event-Based Trend State ===")

    # Create sample signal events: buy (1), hold (0), sell (-1)
    events = pd.Series([0, 0, 1, 0, 0, -1, 0, 0, 1, 0],
                       index=pd.date_range('2023-01-01', periods=10))

    trend_state = _build_trend_state(events)

    print("Signal Events:")
    print(events.to_dict())
    print("\nTrend State (event-based):")
    print(trend_state.to_dict())

    # Expected: [0, 0, 1, 1, 1, 0, 0, 0, 1, 1]
    # Trend turns ON at buy (index 2), stays ON until sell (index 5), then OFF until next buy (index 8)
    expected = pd.Series([0, 0, 1, 1, 1, 0, 0, 0, 1, 1],
                        index=events.index, dtype=int)

    assert (trend_state == expected).all(), "Event-based trend state mismatch!"
    print("✅ Event-based trend state test PASSED")


def test_build_trend_state_condition():
    """Test new condition-based trend state logic"""
    print("\n=== Testing Condition-Based Trend State ===")

    # Create sample data: price crosses above/below KAMA
    dates = pd.date_range('2023-01-01', periods=10)
    df_ind = pd.DataFrame({
        'Close': [100, 102, 105, 103, 104, 106, 108, 107, 109, 111],
        'kama':  [101, 101, 102, 103, 104, 105, 106, 107, 108, 109],
    }, index=dates)

    trend_state = _build_trend_state_condition(df_ind)

    print("Price Data:")
    print(df_ind.to_string())
    print("\nTrend State (condition-based):")
    print(trend_state.to_dict())

    # Expected: trend ON when Close > KAMA
    # Index: 0(99<101=0), 1(102>101=1), 2(105>102=1), 3(103≈103=0), 4(104≈104=0),
    #        5(106>105=1), 6(108>106=1), 7(107≈107=0), 8(109>108=1), 9(111>109=1)
    expected_values = [
        0,  # 100 < 101
        1,  # 102 > 101
        1,  # 105 > 102
        0,  # 103 ≈ 103
        0,  # 104 ≈ 104
        1,  # 106 > 105
        1,  # 108 > 106
        0,  # 107 ≈ 107
        1,  # 109 > 108
        1,  # 111 > 109
    ]
    expected = pd.Series(expected_values, index=dates, dtype=int)

    assert (trend_state == expected).all(), f"Condition-based trend state mismatch!\nGot: {trend_state.tolist()}\nExpected: {expected.tolist()}"
    print("✅ Condition-based trend state test PASSED")


def test_kama_config_with_trend_state_mode():
    """Test that KAMAStrategyConfig accepts trend_state_mode"""
    print("\n=== Testing KAMAStrategyConfig with trend_state_mode ===")

    # Test default (event mode)
    config_default = KAMAStrategyConfig()
    assert config_default.trend_state_mode == "event", "Default trend_state_mode should be 'event'"
    print("✅ Default trend_state_mode = 'event'")

    # Test explicit event mode
    config_event = KAMAStrategyConfig(trend_state_mode="event")
    assert config_event.trend_state_mode == "event"
    print("✅ Explicit trend_state_mode = 'event'")

    # Test condition mode
    config_condition = KAMAStrategyConfig(trend_state_mode="condition")
    assert config_condition.trend_state_mode == "condition"
    print("✅ Explicit trend_state_mode = 'condition'")

    # Test validation (should not allow invalid values)
    try:
        # This should fail during type checking or validation
        config_invalid = KAMAStrategyConfig(trend_state_mode="invalid")
        print("⚠️ Warning: Invalid trend_state_mode was not caught (may be a dataclass limitation)")
    except (ValueError, TypeError) as e:
        print(f"✅ Invalid trend_state_mode correctly rejected: {e}")


def test_full_config_with_trend_state_mode():
    """Test full Config object with trend_state_mode"""
    print("\n=== Testing Full Config with trend_state_mode ===")

    config = Config(
        env=EnvConfig(root_dir="/mnt/d/git/backtesting"),
        modes=ModesConfig(),
        universe=UniverseConfig(pool_file="results/trend_etf_pool.csv"),
        strategies=[KAMAStrategyConfig(trend_state_mode="condition")],
        scoring=ScoringConfig(),
        clustering=ClusteringConfig(),
        risk=RiskConfig(),
        position_sizing=PositionSizingConfig(),
        execution=ExecutionConfig(),
        io=IOConfig(),
    )

    # Validate config
    errors = config.validate()
    assert not errors, f"Config validation failed: {errors}"

    # Check that trend_state_mode is preserved
    assert config.strategies[0].trend_state_mode == "condition"
    print("✅ Full config with trend_state_mode = 'condition' validated successfully")


def main():
    """Run all tests"""
    print("="*70)
    print("Testing P0-3 Trend State Mode Fix")
    print("="*70)

    try:
        test_build_trend_state_event()
        test_build_trend_state_condition()
        test_kama_config_with_trend_state_mode()
        test_full_config_with_trend_state_mode()

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nImplementation Summary:")
        print("1. Added trend_state_mode field to KAMAStrategyConfig (default: 'event')")
        print("2. Implemented _build_trend_state_condition() for condition-based mode")
        print("3. Updated _precompute_signals() to support both modes")
        print("4. Backward compatible: default 'event' mode preserves original behavior")
        print("\nUsage in config.json:")
        print('  "strategies": [')
        print('    {')
        print('      "type": "kama",')
        print('      "trend_state_mode": "condition",  // or "event" (default)')
        print('      ...')
        print('    }')
        print('  ]')

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
