#!/usr/bin/env python
"""
Example script demonstrating config_loader usage

This script shows various ways to use the config_loader module
for the ETF Trend Following V2 system.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config_loader import (
    load_config,
    validate_config,
    save_config,
    create_default_config,
    MACDStrategyConfig,
    KAMAStrategyConfig,
)


def example_1_load_existing_config():
    """Example 1: Load and validate existing configuration"""
    print("=" * 60)
    print("Example 1: Load and validate existing configuration")
    print("=" * 60)

    config_path = Path(__file__).parent.parent / "config" / "example_config.json"

    # Load configuration
    config = load_config(config_path)
    print(f"Loaded configuration from: {config_path}")

    # Validate
    errors = validate_config(config)
    if errors:
        print("\nValidation errors found:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\nConfiguration is valid!")

    # Display key settings
    print(f"\nKey Settings:")
    print(f"  Root directory: {config.env.root_dir}")
    print(f"  Run mode: {config.modes.run_mode}")
    print(f"  Strategy: {config.strategies[0].type}")
    print(f"  Max positions: {config.position_sizing.max_positions}")
    print(f"  Buy top N: {config.scoring.buffer_thresholds['buy_top_n']}")
    print()


def example_2_create_default_config():
    """Example 2: Create default configuration"""
    print("=" * 60)
    print("Example 2: Create default configuration")
    print("=" * 60)

    # Create default config
    config = create_default_config(root_dir="/mnt/d/git/backtesting")
    print("Created default configuration")

    # Validate
    errors = validate_config(config)
    print(f"Validation result: {'Valid' if not errors else 'Invalid'}")

    # Display strategy info
    strategy = config.strategies[0]
    print(f"\nDefault strategy: {strategy.type}")
    if strategy.type == "kama":
        print(f"  KAMA period: {strategy.kama_period}")
        print(f"  KAMA fast: {strategy.kama_fast}")
        print(f"  KAMA slow: {strategy.kama_slow}")

    print()


def example_3_customize_and_save():
    """Example 3: Customize configuration and save"""
    print("=" * 60)
    print("Example 3: Customize configuration and save")
    print("=" * 60)

    # Create default config
    config = create_default_config(root_dir="/mnt/d/git/backtesting")

    # Customize settings
    config.modes.run_mode = "signal"
    config.modes.as_of_date = "2025-12-11"
    config.position_sizing.max_positions = 15
    config.scoring.buffer_thresholds["buy_top_n"] = 8
    config.scoring.buffer_thresholds["hold_until_rank"] = 12

    print("Customized configuration:")
    print(f"  Run mode: {config.modes.run_mode}")
    print(f"  As of date: {config.modes.as_of_date}")
    print(f"  Max positions: {config.position_sizing.max_positions}")
    print(f"  Buy top N: {config.scoring.buffer_thresholds['buy_top_n']}")

    # Validate
    errors = validate_config(config)
    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\nConfiguration is valid!")

        # Save to file
        output_path = Path(__file__).parent.parent / "config" / "custom_config.json"
        save_config(config, output_path)
        print(f"\nSaved to: {output_path}")

    print()


def example_4_multiple_strategies():
    """Example 4: Configuration with multiple strategies"""
    print("=" * 60)
    print("Example 4: Configuration with multiple strategies")
    print("=" * 60)

    # Create default config
    config = create_default_config(root_dir="/mnt/d/git/backtesting")

    # Add multiple strategies
    config.strategies = [
        KAMAStrategyConfig(
            kama_period=20,
            kama_fast=2,
            kama_slow=30,
            enable_adx_filter=True,
            adx_threshold=25.0
        ),
        MACDStrategyConfig(
            fast_period=12,
            slow_period=26,
            signal_period=9,
            enable_volume_filter=True,
            volume_ratio=1.2
        )
    ]

    print(f"Number of strategies: {len(config.strategies)}")
    for i, strategy in enumerate(config.strategies):
        print(f"\nStrategy {i+1}: {strategy.type}")
        if strategy.type == "kama":
            print(f"  KAMA period: {strategy.kama_period}")
            print(f"  ADX filter: {strategy.enable_adx_filter}")
        elif strategy.type == "macd":
            print(f"  Fast period: {strategy.fast_period}")
            print(f"  Slow period: {strategy.slow_period}")
            print(f"  Volume filter: {strategy.enable_volume_filter}")

    # Validate
    errors = validate_config(config)
    print(f"\nValidation result: {'Valid' if not errors else 'Invalid'}")

    print()


def example_5_validation_errors():
    """Example 5: Demonstrate validation errors"""
    print("=" * 60)
    print("Example 5: Demonstrate validation errors")
    print("=" * 60)

    # Create config with intentional errors
    config = create_default_config(root_dir="/mnt/d/git/backtesting")

    # Introduce errors
    config.position_sizing.max_positions = 5  # Too small
    config.scoring.buffer_thresholds["buy_top_n"] = 10  # Exceeds max_positions
    config.scoring.momentum_weights = {"20d": 0.5, "60d": 0.3, "120d": 0.1}  # Doesn't sum to 1.0

    # Validate
    errors = validate_config(config)

    print("Intentional validation errors:")
    for error in errors:
        print(f"  - {error}")

    print("\nThese errors demonstrate the validation system working correctly.")
    print()


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("Config Loader Usage Examples")
    print("=" * 60 + "\n")

    example_1_load_existing_config()
    example_2_create_default_config()
    example_3_customize_and_save()
    example_4_multiple_strategies()
    example_5_validation_errors()

    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
