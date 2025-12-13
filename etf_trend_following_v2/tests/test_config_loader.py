"""
Unit tests for config_loader module
"""

import json
import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config_loader import (
    Config,
    EnvConfig,
    ModesConfig,
    UniverseConfig,
    MACDStrategyConfig,
    KAMAStrategyConfig,
    ComboStrategyConfig,
    ScoringConfig,
    ClusteringConfig,
    RiskConfig,
    PositionSizingConfig,
    ExecutionConfig,
    IOConfig,
    RotationConfig,
    load_config,
    validate_config,
    save_config,
    create_default_config,
    load_config_from_dict,
)


class TestEnvConfig:
    """Test EnvConfig validation"""

    def test_valid_config(self):
        config = EnvConfig(root_dir="/test")
        errors = config.validate()
        assert len(errors) == 0

    def test_missing_root_dir(self):
        config = EnvConfig(root_dir="")
        errors = config.validate()
        assert any("root_dir is required" in e for e in errors)

    def test_invalid_timezone(self):
        config = EnvConfig(root_dir="/test", timezone="Invalid/Timezone")
        errors = config.validate()
        assert any("timezone" in e for e in errors)

    def test_invalid_trading_calendar(self):
        config = EnvConfig(root_dir="/test", trading_calendar="INVALID")
        errors = config.validate()
        assert any("trading_calendar" in e for e in errors)


class TestModesConfig:
    """Test ModesConfig validation"""

    def test_valid_config(self):
        config = ModesConfig(run_mode="backtest")
        errors = config.validate()
        assert len(errors) == 0

    def test_invalid_run_mode(self):
        config = ModesConfig(run_mode="invalid")
        errors = config.validate()
        assert any("run_mode" in e for e in errors)

    def test_invalid_date_format(self):
        config = ModesConfig(as_of_date="2025/12/11")
        errors = config.validate()
        assert any("as_of_date" in e for e in errors)

    def test_valid_date_format(self):
        config = ModesConfig(as_of_date="2025-12-11")
        errors = config.validate()
        assert len(errors) == 0

    def test_negative_lookback_days(self):
        config = ModesConfig(lookback_days=-10)
        errors = config.validate()
        assert any("lookback_days" in e for e in errors)


class TestUniverseConfig:
    """Test UniverseConfig validation"""

    def test_valid_with_pool_file(self):
        config = UniverseConfig(pool_file="test.csv")
        errors = config.validate()
        assert len(errors) == 0

    def test_valid_with_pool_list(self):
        config = UniverseConfig(pool_list=["510300.SH", "510500.SH"])
        errors = config.validate()
        assert len(errors) == 0

    def test_missing_pool(self):
        config = UniverseConfig()
        errors = config.validate()
        assert any("pool_file or universe.pool_list must be specified" in e for e in errors)

    def test_mutually_exclusive_pools(self):
        config = UniverseConfig(pool_file="test.csv", pool_list=["510300.SH"])
        errors = config.validate()
        assert any("mutually exclusive" in e for e in errors)

    def test_negative_liquidity_threshold(self):
        config = UniverseConfig(
            pool_file="test.csv",
            liquidity_threshold={"min_avg_volume": -1000}
        )
        errors = config.validate()
        assert any("min_avg_volume" in e for e in errors)


class TestRotationConfig:
    """Test RotationConfig validation and Config interplay"""

    def test_rotation_requires_schedule_when_enabled(self):
        config = RotationConfig(enabled=True, schedule_path=None)
        errors = config.validate()
        assert any("schedule_path" in e for e in errors)

    def test_rotation_allows_missing_universe_pool(self):
        cfg = Config(
            env=EnvConfig(root_dir="/test"),
            modes=ModesConfig(run_mode="backtest", lookback_days=10),
            universe=UniverseConfig(pool_file=None, pool_list=None),
            rotation=RotationConfig(enabled=True, schedule_path="results/rotation_schedules/rotation_5d.json"),
            strategies=[KAMAStrategyConfig()],
            scoring=ScoringConfig(),
            clustering=ClusteringConfig(),
            risk=RiskConfig(),
            position_sizing=PositionSizingConfig(),
            execution=ExecutionConfig(),
            io=IOConfig(),
        )
        errors = cfg.validate()
        assert not any("pool_file" in e for e in errors)

    def test_rotation_rejects_static_pool_when_enabled(self):
        cfg = Config(
            env=EnvConfig(root_dir="/test"),
            modes=ModesConfig(run_mode="backtest", lookback_days=10),
            universe=UniverseConfig(pool_list=["AAA"]),
            rotation=RotationConfig(enabled=True, schedule_path="results/rotation_schedules/rotation_5d.json"),
            strategies=[KAMAStrategyConfig()],
            scoring=ScoringConfig(),
            clustering=ClusteringConfig(),
            risk=RiskConfig(),
            position_sizing=PositionSizingConfig(),
            execution=ExecutionConfig(),
            io=IOConfig(),
        )
        errors = cfg.validate()
        assert any("rotation.enabled is true" in e for e in errors)


class TestMACDStrategyConfig:
    """Test MACDStrategyConfig validation"""

    def test_valid_config(self):
        config = MACDStrategyConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_fast_period_greater_than_slow(self):
        config = MACDStrategyConfig(fast_period=26, slow_period=12)
        errors = config.validate()
        assert any("fast_period" in e and "slow_period" in e for e in errors)

    def test_negative_signal_period(self):
        config = MACDStrategyConfig(signal_period=-1)
        errors = config.validate()
        assert any("signal_period" in e for e in errors)

    def test_negative_adx_threshold(self):
        config = MACDStrategyConfig(adx_threshold=-10)
        errors = config.validate()
        assert any("adx_threshold" in e for e in errors)


class TestKAMAStrategyConfig:
    """Test KAMAStrategyConfig validation"""

    def test_valid_config(self):
        config = KAMAStrategyConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_fast_greater_than_slow(self):
        config = KAMAStrategyConfig(kama_fast=30, kama_slow=2)
        errors = config.validate()
        assert any("kama_fast" in e and "kama_slow" in e for e in errors)

    def test_invalid_efficiency_ratio(self):
        config = KAMAStrategyConfig(min_efficiency_ratio=1.5)
        errors = config.validate()
        assert any("min_efficiency_ratio" in e for e in errors)


class TestComboStrategyConfig:
    """Test ComboStrategyConfig validation"""

    def test_valid_config(self):
        config = ComboStrategyConfig(
            strategies=[MACDStrategyConfig(), KAMAStrategyConfig()]
        )
        errors = config.validate()
        assert len(errors) == 0

    def test_empty_strategies(self):
        config = ComboStrategyConfig(strategies=[])
        errors = config.validate()
        assert any("at least one sub-strategy" in e for e in errors)

    def test_split_mode_without_weights(self):
        config = ComboStrategyConfig(
            mode="split",
            strategies=[MACDStrategyConfig(), KAMAStrategyConfig()]
        )
        errors = config.validate()
        assert any("requires weights" in e for e in errors)

    def test_weights_not_sum_to_one(self):
        config = ComboStrategyConfig(
            mode="split",
            strategies=[MACDStrategyConfig(), KAMAStrategyConfig()],
            weights={"macd": 0.3, "kama": 0.5}
        )
        errors = config.validate()
        assert any("sum to 1.0" in e for e in errors)


class TestScoringConfig:
    """Test ScoringConfig validation"""

    def test_valid_config(self):
        config = ScoringConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_momentum_weights_not_sum_to_one(self):
        config = ScoringConfig(
            momentum_weights={"20d": 0.5, "60d": 0.3, "120d": 0.1}
        )
        errors = config.validate()
        assert any("sum to 1.0" in e for e in errors)

    def test_hold_until_rank_less_than_buy_top_n(self):
        config = ScoringConfig(
            buffer_thresholds={"buy_top_n": 15, "hold_until_rank": 10}
        )
        errors = config.validate()
        assert any("hold_until_rank" in e and "buy_top_n" in e for e in errors)

    def test_negative_inertia_bonus(self):
        config = ScoringConfig(inertia_bonus=-0.1)
        errors = config.validate()
        assert any("inertia_bonus" in e for e in errors)


class TestClusteringConfig:
    """Test ClusteringConfig validation"""

    def test_valid_config(self):
        config = ClusteringConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_small_correlation_window(self):
        config = ClusteringConfig(correlation_window=5)
        errors = config.validate()
        assert any("correlation_window" in e for e in errors)

    def test_invalid_cut_threshold(self):
        config = ClusteringConfig(cut_threshold=1.5)
        errors = config.validate()
        assert any("cut_threshold" in e for e in errors)


class TestRiskConfig:
    """Test RiskConfig validation"""

    def test_valid_config(self):
        config = RiskConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_negative_atr_window(self):
        config = RiskConfig(atr_window=-10)
        errors = config.validate()
        assert any("atr_window" in e for e in errors)

    def test_positive_time_stop_threshold(self):
        config = RiskConfig(time_stop_threshold=0.05)
        errors = config.validate()
        assert any("time_stop_threshold" in e for e in errors)


class TestPositionSizingConfig:
    """Test PositionSizingConfig validation"""

    def test_valid_config(self):
        config = PositionSizingConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_invalid_target_risk(self):
        config = PositionSizingConfig(target_risk_per_position=0.15)
        errors = config.validate()
        assert any("target_risk_per_position" in e for e in errors)

    def test_invalid_ewma_lambda(self):
        config = PositionSizingConfig(ewma_lambda=1.5)
        errors = config.validate()
        assert any("ewma_lambda" in e for e in errors)

    def test_exposure_plus_reserve_exceeds_one(self):
        config = PositionSizingConfig(
            max_total_exposure=0.98,
            min_cash_reserve=0.05
        )
        errors = config.validate()
        assert any("max_total_exposure + min_cash_reserve" in e for e in errors)


class TestConfigLoading:
    """Test configuration loading and saving"""

    def test_create_default_config(self):
        config = create_default_config(root_dir="/test")
        assert config.env.root_dir == "/test"
        assert len(config.strategies) > 0
        errors = validate_config(config)
        assert len(errors) == 0

    def test_load_and_save_config(self, tmp_path):
        # Create a config
        config = create_default_config(root_dir="/test")

        # Save it
        config_path = tmp_path / "test_config.json"
        save_config(config, config_path)

        # Load it back
        loaded_config = load_config(config_path)

        # Verify
        assert loaded_config.env.root_dir == config.env.root_dir
        assert len(loaded_config.strategies) == len(config.strategies)

    def test_load_config_from_dict(self):
        config_dict = {
            "env": {"root_dir": "/test"},
            "modes": {"run_mode": "backtest"},
            "universe": {"pool_file": "test.csv"},
            "strategies": [{"type": "kama"}],
            "scoring": {},
            "clustering": {},
            "risk": {},
            "position_sizing": {},
            "execution": {},
            "io": {}
        }

        config = load_config_from_dict(config_dict)
        errors = validate_config(config)
        assert len(errors) == 0

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.json")

    def test_load_invalid_json(self, tmp_path):
        config_path = tmp_path / "invalid.json"
        config_path.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            load_config(config_path)


class TestFullConfig:
    """Test full configuration validation"""

    def test_valid_full_config(self):
        config = Config(
            env=EnvConfig(root_dir="/test"),
            modes=ModesConfig(),
            universe=UniverseConfig(pool_file="test.csv"),
            strategies=[KAMAStrategyConfig()],
            scoring=ScoringConfig(),
            clustering=ClusteringConfig(),
            risk=RiskConfig(),
            position_sizing=PositionSizingConfig(),
            execution=ExecutionConfig(),
            io=IOConfig()
        )

        errors = validate_config(config)
        assert len(errors) == 0

    def test_buy_top_n_exceeds_max_positions(self):
        config = Config(
            env=EnvConfig(root_dir="/test"),
            modes=ModesConfig(),
            universe=UniverseConfig(pool_file="test.csv"),
            strategies=[KAMAStrategyConfig()],
            scoring=ScoringConfig(buffer_thresholds={"buy_top_n": 30, "hold_until_rank": 35}),
            clustering=ClusteringConfig(),
            risk=RiskConfig(),
            position_sizing=PositionSizingConfig(max_positions=20),
            execution=ExecutionConfig(),
            io=IOConfig()
        )

        errors = validate_config(config)
        assert any("buy_top_n" in e and "max_positions" in e for e in errors)

    def test_config_to_dict(self):
        config = create_default_config(root_dir="/test")
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert "env" in config_dict
        assert "strategies" in config_dict
        assert config_dict["env"]["root_dir"] == "/test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
