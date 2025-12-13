import json
import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure project root is on sys.path for package imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from etf_trend_following_v2.src.dynamic_pool_runner import DynamicPoolPortfolioRunner
from etf_trend_following_v2.src import portfolio_backtest_runner as pbr
from etf_trend_following_v2.src.config_loader import (
    ClusteringConfig,
    Config,
    EnvConfig,
    ExecutionConfig,
    IOConfig,
    KAMAStrategyConfig,
    ModesConfig,
    PositionSizingConfig,
    RiskConfig,
    RotationConfig,
    ScoringConfig,
    UniverseConfig,
)


def _make_rotation_config(schedule_path: str, data_dir: str) -> Config:
    return Config(
        env=EnvConfig(root_dir="/mnt/d/git/backtesting", data_dir=data_dir),
        modes=ModesConfig(run_mode="backtest", lookback_days=10),
        universe=UniverseConfig(pool_file=None, pool_list=None),
        rotation=RotationConfig(enabled=True, schedule_path=schedule_path, period_days=3, pool_size=3),
        strategies=[KAMAStrategyConfig()],
        scoring=ScoringConfig(
            momentum_weights={"20d": 0.4, "60d": 0.3, "120d": 0.3},
            buffer_thresholds={"buy_top_n": 2, "hold_until_rank": 2},
            inertia_bonus=0.0,
            rebalance_frequency=1,
        ),
        clustering=ClusteringConfig(
            correlation_window=20,
            linkage_method="average",
            cut_threshold=0.5,
            max_positions_per_cluster=2,
            update_frequency=9999,
        ),
        risk=RiskConfig(time_stop_days=9999),
        position_sizing=PositionSizingConfig(
            target_risk_per_position=0.02,
            volatility_method="ewma",
            ewma_lambda=0.94,
            max_positions=2,
            max_position_size=0.9,
            max_cluster_size=0.9,
            max_total_exposure=0.9,
            min_cash_reserve=0.1,
            commission_rate=0.0,
            slippage_bps=0.0,
        ),
        execution=ExecutionConfig(order_time_strategy="close"),
        io=IOConfig(),
    )


def test_dynamic_runner_requires_rotation_enabled():
    config = _make_rotation_config(
        schedule_path=str(Path(__file__).parent / "fixtures" / "test_rotation_schedule.json"),
        data_dir=str(Path(__file__).parent / "fixtures" / "data"),
    )
    config.rotation.enabled = False

    with pytest.raises(ValueError):
        DynamicPoolPortfolioRunner(config)


def test_dynamic_runner_applies_rotation_schedule(monkeypatch):
    fixtures_dir = Path(__file__).parent / "fixtures"
    schedule_path = fixtures_dir / "test_rotation_schedule.json"
    data_dir = fixtures_dir / "data"

    config = _make_rotation_config(str(schedule_path), str(data_dir))
    runner = DynamicPoolPortfolioRunner(config)

    # Always-on trend state for all symbols.
    def fake_precompute(data_dict):
        runner._signal_events = {s: pd.Series(0, index=df.index) for s, df in data_dict.items()}
        runner._trend_state = {s: pd.Series(1, index=df.index) for s, df in data_dict.items()}

    monkeypatch.setattr(runner, "_precompute_signals", fake_precompute)
    monkeypatch.setattr(runner, "_update_clusters_if_needed", lambda *_args, **_kwargs: None)

    def fake_scores(eligible_dict, as_of_date, **_kwargs):
        syms = sorted(eligible_dict.keys())
        return pd.DataFrame(
            [{"symbol": sym, "raw_score": float(len(syms) - idx), "rank": idx + 1} for idx, sym in enumerate(syms)]
        )

    monkeypatch.setattr(pbr, "calculate_universe_scores", fake_scores)

    def fake_positions(data_dict, symbols, total_capital, **_kwargs):
        if not symbols:
            return {}
        weight = 1.0 / len(symbols)
        return {
            s: {"target_capital": total_capital * weight, "target_weight": weight, "volatility": 0.01, "cluster_id": 0}
            for s in symbols
        }

    monkeypatch.setattr(pbr, "calculate_portfolio_positions", fake_positions)

    results = runner.run(
        start_date="2023-01-01",
        end_date="2023-01-08",
        initial_capital=100_000,
        output_dir=None,
    )

    fills = results["fills"]
    assert not fills.empty
    assert "rotation_excluded" in set(fills["reason"])

    with open(schedule_path, "r", encoding="utf-8") as f:
        sched = json.load(f)["schedule"]
    last_pool = set(sched[max(sched.keys())])

    positions_df = results["positions"]
    assert not positions_df.empty
    last_date = positions_df["date"].max()
    last_syms = set(positions_df[positions_df["date"] == last_date]["symbol"])
    assert last_syms.issubset(last_pool)
