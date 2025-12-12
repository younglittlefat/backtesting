#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MACD wrapper filter/风控行为测试（不再强求与旧框架完全一致）。

目的：
- 覆盖常见过滤器/风控组合，验证策略可运行且指标为有效值
- 验证过滤器/阈值变化会对交易数量产生合理影响
- 使用内置夹具数据，避免依赖外部真实行情
"""

import sys
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backtesting import Backtest  # noqa: E402
from etf_trend_following_v2.src.strategies.backtest_wrappers import MACDBacktestStrategy  # noqa: E402
from test_strategy_alignment import FIXTURE_DIR, load_fixture_data, TEST_SYMBOLS  # noqa: E402


BASE_PARAMS: Dict[str, float] = {
    "fast_period": 12,
    "slow_period": 26,
    "signal_period": 9,
    "enable_adx_filter": False,
    "enable_volume_filter": False,
    "enable_slope_filter": False,
    "enable_confirm_filter": False,
    "enable_loss_protection": False,
    "enable_trailing_stop": False,
}


def run_wrapper(df: pd.DataFrame, **params) -> pd.Series:
    """Run MACDBacktestStrategy with given params."""
    bt = Backtest(
        df,
        MACDBacktestStrategy,
        cash=1_000_000,
        commission=0.001,
        trade_on_close=True,
        exclusive_orders=True,
    )
    return bt.run(**params)


def assert_stats_valid(stats: pd.Series):
    """Basic sanity checks on backtest输出。"""
    required = ["Return [%]", "Max. Drawdown [%]", "# Trades"]
    for key in required:
        assert key in stats, f"缺少指标 {key}"
        assert not pd.isna(stats[key]), f"{key} 为 NaN"
    # Sharpe 可能在无交易时为 NaN，允许
    assert stats["# Trades"] >= 0


@pytest.fixture(scope="module")
def fixture_df():
    symbol = TEST_SYMBOLS[0]
    path = FIXTURE_DIR / f"{symbol}.csv"
    if not path.exists():
        pytest.skip(f"Fixture data missing: {path}")
    return load_fixture_data(symbol)


@pytest.mark.parametrize(
    "config",
    [
        {"name": "Baseline (no filters)", "params": {}},
        {
            "name": "With ADX Filter",
            "params": {"enable_adx_filter": True, "adx_period": 14, "adx_threshold": 30},
        },
        {
            "name": "With Volume Filter",
            "params": {"enable_volume_filter": True, "volume_period": 20, "volume_ratio": 1.5},
        },
        {
            "name": "With Slope Filter",
            "params": {"enable_slope_filter": True, "slope_lookback": 5},
        },
        {
            "name": "With Loss Protection",
            "params": {"enable_loss_protection": True, "max_consecutive_losses": 2, "pause_bars": 8},
        },
        {
            "name": "With Trailing Stop",
            "params": {"enable_trailing_stop": True, "trailing_stop_pct": 0.05},
        },
    ],
    ids=lambda c: c["name"],
)
def test_filters_smoke(config: Dict[str, Dict[str, float]], fixture_df: pd.DataFrame):
    """每个过滤/风控组合都能跑通且返回有效指标。"""
    params = {**BASE_PARAMS, **config["params"]}
    stats = run_wrapper(fixture_df, **params)
    assert_stats_valid(stats)


def test_adx_threshold_monotonic(fixture_df: pd.DataFrame):
    """更高阈值应当不会增加交易数量。"""
    thresholds = [15, 25, 40]
    trades = []
    for th in thresholds:
        params = {**BASE_PARAMS, "enable_adx_filter": True, "adx_period": 14, "adx_threshold": th}
        stats = run_wrapper(fixture_df, **params)
        trades.append(stats["# Trades"])
    assert trades == sorted(trades, reverse=True), f"阈值提高后交易数应非增加，当前 {trades}"


def test_volume_filter_blocks_low_volume(fixture_df: pd.DataFrame):
    """人为构造低成交量后，开启 volume filter 应减少交易。"""
    # 将后 30 根的成交量大幅降低，制造过滤场景
    df = fixture_df.copy()
    df.loc[df.index[-30:], "Volume"] = (df["Volume"].median() * 0.05).astype(int)

    baseline_stats = run_wrapper(df, **BASE_PARAMS)
    volume_stats = run_wrapper(
        df,
        **{
            **BASE_PARAMS,
            "enable_volume_filter": True,
            "volume_period": 20,
            "volume_ratio": 1.2,
        },
    )

    assert volume_stats["# Trades"] <= baseline_stats["# Trades"], "成交量过滤未减少交易数"


def test_loss_protection_reduces_activity(fixture_df: pd.DataFrame):
    """开启 loss protection 应降低交易频率或保持不变。"""
    baseline_stats = run_wrapper(fixture_df, **BASE_PARAMS)
    protected_stats = run_wrapper(
        fixture_df,
        **{
            **BASE_PARAMS,
            "enable_loss_protection": True,
            "max_consecutive_losses": 2,
            "pause_bars": 10,
        },
    )
    assert protected_stats["# Trades"] <= baseline_stats["# Trades"], "启用止损保护后交易数未下降"


def test_all_filters_enabled_smoke(fixture_df: pd.DataFrame):
    """开启全部过滤/风控，验证稳定性。"""
    params = {
        **BASE_PARAMS,
        "enable_adx_filter": True,
        "adx_period": 14,
        "adx_threshold": 25,
        "enable_volume_filter": True,
        "volume_period": 20,
        "volume_ratio": 1.2,
        "enable_slope_filter": True,
        "slope_lookback": 5,
        "enable_loss_protection": True,
        "max_consecutive_losses": 3,
        "pause_bars": 10,
        "enable_trailing_stop": True,
        "trailing_stop_pct": 0.05,
    }
    stats = run_wrapper(fixture_df, **params)
    assert_stats_valid(stats)
    assert stats["# Trades"] >= 0
