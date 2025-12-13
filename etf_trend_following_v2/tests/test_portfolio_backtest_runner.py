import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

# Ensure project root is on sys.path for package imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _make_min_config(pool_list):
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

    return Config(
        env=EnvConfig(root_dir="/mnt/d/git/backtesting", data_dir="data/chinese_etf/daily"),
        modes=ModesConfig(run_mode="backtest", lookback_days=10),
        universe=UniverseConfig(pool_list=pool_list),
        strategies=[KAMAStrategyConfig()],
        scoring=ScoringConfig(
            momentum_weights={"20d": 0.4, "60d": 0.3, "120d": 0.3},
            buffer_thresholds={"buy_top_n": 2, "hold_until_rank": 3},
            inertia_bonus=0.0,
            rebalance_frequency=1,
        ),
        clustering=ClusteringConfig(
            correlation_window=20,
            linkage_method="average",
            cut_threshold=0.5,
            max_positions_per_cluster=1,
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


def test_select_symbols_respects_cluster_limit():
    from etf_trend_following_v2.src.portfolio_backtest_runner import PortfolioBacktestRunner

    config = _make_min_config(["A", "B", "C"])
    runner = PortfolioBacktestRunner(config)

    # Two symbols in the same cluster, limit=1.
    runner._cluster_assignments = {"A": 0, "B": 0, "C": 1}

    scores_df = pd.DataFrame(
        [
            {"symbol": "A", "raw_score": 2.0, "rank": 1},
            {"symbol": "B", "raw_score": 1.0, "rank": 2},
            {"symbol": "C", "raw_score": 0.5, "rank": 3},
        ]
    )
    scores_df["adjusted_score"] = scores_df["raw_score"]
    scores_df["adjusted_rank"] = scores_df["rank"]

    final_syms, sell_reasons = runner._select_symbols(
        scores_df=scores_df,
        current_holdings=["B"],
        forced_sells=[],
    )

    # Only one of A/B can be selected; A wins by score.
    assert "A" in final_syms
    assert "B" not in final_syms
    assert len(final_syms) == 2
    assert sell_reasons.get("B") in {"cluster_limit", "rank_out_2", "max_positions", "dropped_from_universe"}


def test_portfolio_backtest_runner_smoke(monkeypatch):
    from etf_trend_following_v2.src import portfolio_backtest_runner as pbr

    dates = pd.date_range("2024-01-01", periods=6, freq="D")

    def make_df(close_start: float) -> pd.DataFrame:
        close = close_start + np.arange(len(dates), dtype=float)
        return pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 2_000_000,
                "amount": close * 2_000_000,
            },
            index=dates,
        )

    data_dict = {"AAA": make_df(10.0), "BBB": make_df(8.0), "CCC": make_df(6.0)}

    config = _make_min_config(list(data_dict.keys()))
    runner = pbr.PortfolioBacktestRunner(config)

    monkeypatch.setattr(runner, "_load_data", lambda *_args, **_kwargs: data_dict)

    def fake_precompute(_data_dict):
        runner._signal_events = {s: pd.Series(0, index=dates) for s in data_dict}
        runner._trend_state = {s: pd.Series(1, index=dates) for s in data_dict}

    monkeypatch.setattr(runner, "_precompute_signals", fake_precompute)
    monkeypatch.setattr(runner, "_update_clusters_if_needed", lambda *_args, **_kwargs: None)

    def fake_scores(_eligible_dict, as_of_date, **_kwargs):
        # Always prefer AAA > BBB > CCC
        return pd.DataFrame(
            [
                {"symbol": "AAA", "raw_score": 3.0, "rank": 1},
                {"symbol": "BBB", "raw_score": 2.0, "rank": 2},
                {"symbol": "CCC", "raw_score": 1.0, "rank": 3},
            ]
        )

    monkeypatch.setattr(pbr, "calculate_universe_scores", fake_scores)

    def fake_positions(data_dict, symbols, total_capital, **_kwargs):
        # Equal-weight across selected symbols.
        w = 1.0 / len(symbols)
        return {
            s: {"target_capital": total_capital * w, "target_weight": w, "volatility": 0.01, "cluster_id": 0}
            for s in symbols
        }

    monkeypatch.setattr(pbr, "calculate_portfolio_positions", fake_positions)

    results = runner.run(
        start_date="2024-01-01",
        end_date="2024-01-06",
        initial_capital=100_000,
        output_dir=None,
    )

    assert "equity_curve" in results
    assert "fills" in results
    assert "stats" in results

    equity = results["equity_curve"]["equity"].astype(float)
    assert len(equity) == 6
    assert np.isfinite(equity).all()

    # Should have at least some executed orders when rebalancing daily.
    assert len(results["fills"]) > 0
    assert results["stats"]["num_orders"] == len(results["fills"])
