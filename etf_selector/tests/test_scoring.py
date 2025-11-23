import numpy as np
import pandas as pd
import pytest

from etf_selector.indicators import calculate_excess_return, calculate_trend_r2
from etf_selector.scoring import (
    ScoringWeights,
    UnbiasedScorer,
    calculate_etf_scores,
    LegacyScoringWeights,
    LegacyUnbiasedScorer,
    calculate_legacy_etf_scores,
)


def test_calculate_trend_r2_returns_high_value_for_stable_trend():
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    close = pd.Series(np.exp(np.linspace(0, 1, 60)), index=dates)

    r_squared = calculate_trend_r2(close, window=60)

    assert r_squared == pytest.approx(1.0, rel=1e-3)


def test_unbiased_scorer_final_score_combines_new_components():
    scorer = UnbiasedScorer(ScoringWeights())
    indicators = {
        'excess_return_20d_normalized': 0.5,
        'excess_return_60d_normalized': 0.9,
        'trend_quality_normalized': 0.8,
        'adx_mean_normalized': 0.6,
        'volume_trend_normalized': 0.4,
    }

    scores = scorer.calculate_final_score(indicators)

    assert scores['core_trend_score'] == pytest.approx(0.74)
    assert scores['final_score'] == pytest.approx(0.706)


def test_calculate_etf_scores_prioritizes_excess_and_quality():
    metrics_df = pd.DataFrame([
        {
            'ts_code': 'TOP',
            'excess_return_20d': 0.05,
            'excess_return_60d': 0.10,
            'trend_quality': 0.8,
            'adx_mean': 30,
            'volume_trend': 1.5,
        },
        {
            'ts_code': 'LOW',
            'excess_return_20d': 0.02,
            'excess_return_60d': 0.04,
            'trend_quality': 0.6,
            'adx_mean': 20,
            'volume_trend': 0.8,
        },
    ])

    scored = calculate_etf_scores(metrics_df, normalize_method='minmax')

    assert scored.iloc[0]['ts_code'] == 'TOP'
    assert scored.iloc[0]['final_score'] == pytest.approx(1.0)
    assert scored.iloc[-1]['final_score'] == pytest.approx(0.0)


def test_calculate_excess_return_handles_benchmark_and_fallback():
    dates = pd.date_range('2024-01-01', periods=25, freq='D')
    etf_close = pd.Series(np.linspace(100, 120, 25), index=dates)
    benchmark_close = pd.Series(np.linspace(100, 110, 25), index=dates)

    with_benchmark = calculate_excess_return(etf_close, benchmark_close, period=20)
    asset_return = etf_close.iloc[-1] / etf_close.iloc[-21] - 1
    benchmark_return = benchmark_close.iloc[-1] / benchmark_close.iloc[-21] - 1

    assert with_benchmark == pytest.approx(asset_return - benchmark_return)

    without_benchmark = calculate_excess_return(etf_close, None, period=20)
    assert without_benchmark == pytest.approx(asset_return)


def test_legacy_score_path_ranks_correctly():
    metrics_df = pd.DataFrame([
        {
            'ts_code': 'WIN',
            'adx_mean': 50,
            'trend_consistency': 0.8,
            'price_efficiency': 0.9,
            'liquidity_score': 0.8,
            'momentum_3m': 0.2,
            'momentum_12m': 0.3,
        },
        {
            'ts_code': 'LOSE',
            'adx_mean': 10,
            'trend_consistency': 0.2,
            'price_efficiency': 0.1,
            'liquidity_score': 0.3,
            'momentum_3m': -0.1,
            'momentum_12m': -0.05,
        },
    ])

    scorer = LegacyUnbiasedScorer(LegacyScoringWeights())
    scored = calculate_legacy_etf_scores(metrics_df, scorer=scorer, normalize_method='minmax')

    assert list(scored['ts_code']) == ['WIN', 'LOSE']
    assert scored.iloc[0]['final_score'] == pytest.approx(0.92)
    assert scored.iloc[-1]['final_score'] == pytest.approx(0.088)
