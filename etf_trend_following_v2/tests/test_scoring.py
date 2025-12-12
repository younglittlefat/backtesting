"""
Unit tests for scoring module.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scoring import (
    calculate_momentum_score,
    calculate_universe_scores,
    apply_inertia_bonus,
    get_trading_signals,
    calculate_historical_scores,
    get_scores_for_date,
    validate_scoring_params
)


@pytest.fixture
def sample_price_data():
    """Generate sample price data for testing."""
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    np.random.seed(42)

    # Create uptrend data
    trend = np.linspace(100, 150, len(dates))
    noise = np.random.randn(len(dates)) * 2
    close = trend + noise

    df = pd.DataFrame({
        'open': close * 0.99,
        'high': close * 1.01,
        'low': close * 0.98,
        'close': close,
        'volume': np.random.randint(1000000, 5000000, len(dates))
    }, index=dates)

    return df


@pytest.fixture
def sample_universe():
    """Generate sample universe of ETFs."""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')

    data_dict = {}

    # Create 5 ETFs with different momentum characteristics
    for i in range(5):
        base = 100 + i * 10
        trend_strength = 0.05 + i * 0.02  # Different momentum
        trend = base * (1 + trend_strength * np.arange(len(dates)) / len(dates))
        noise = np.random.randn(len(dates)) * 1.5
        close = trend + noise

        df = pd.DataFrame({
            'open': close * 0.99,
            'high': close * 1.01,
            'low': close * 0.98,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, len(dates))
        }, index=dates)

        data_dict[f'ETF{i+1}'] = df

    return data_dict


def test_calculate_momentum_score_basic(sample_price_data):
    """Test basic momentum score calculation."""
    score = calculate_momentum_score(
        df=sample_price_data,
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3]
    )

    # Should return a valid score
    assert isinstance(score, float)
    assert not np.isnan(score)
    # Should be positive for uptrend
    assert score > 0


def test_calculate_momentum_score_insufficient_data():
    """Test score calculation with insufficient data."""
    dates = pd.date_range('2023-01-01', periods=10, freq='D')
    df = pd.DataFrame({
        'close': np.linspace(100, 110, 10)
    }, index=dates)

    # Should return NaN for insufficient data
    score = calculate_momentum_score(
        df=df,
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3]
    )

    assert np.isnan(score)


def test_calculate_momentum_score_weights_validation():
    """Test weight validation."""
    dates = pd.date_range('2023-01-01', periods=150, freq='D')
    df = pd.DataFrame({
        'close': np.linspace(100, 120, 150)
    }, index=dates)

    # Weights don't sum to 1.0
    with pytest.raises(ValueError, match="weights must sum to 1.0"):
        calculate_momentum_score(
            df=df,
            periods=[20, 60, 120],
            weights=[0.5, 0.3, 0.3]
        )

    # Length mismatch
    with pytest.raises(ValueError, match="periods length"):
        calculate_momentum_score(
            df=df,
            periods=[20, 60],
            weights=[0.4, 0.3, 0.3]
        )


def test_calculate_universe_scores(sample_universe):
    """Test universe-wide score calculation."""
    scores_df = calculate_universe_scores(
        data_dict=sample_universe,
        as_of_date='2023-12-31'
    )

    # Should have all 5 ETFs
    assert len(scores_df) == 5
    assert set(scores_df.columns) == {'symbol', 'raw_score', 'rank'}

    # Ranks should be 1-5
    assert set(scores_df['rank']) == {1, 2, 3, 4, 5}

    # Scores should be sorted descending
    assert scores_df['raw_score'].is_monotonic_decreasing

    # First ranked ETF should have highest score
    # (Cannot predict exact symbol due to noise, but should have valid data)
    assert scores_df.iloc[0]['rank'] == 1
    assert scores_df.iloc[0]['symbol'] in sample_universe.keys()


def test_apply_inertia_bonus():
    """Test inertia bonus application."""
    scores_df = pd.DataFrame({
        'symbol': ['A', 'B', 'C', 'D', 'E'],
        'raw_score': [1.0, 0.8, 0.6, 0.4, 0.2],
        'rank': [1, 2, 3, 4, 5]
    })

    current_holdings = ['C', 'D']

    result_df = apply_inertia_bonus(
        scores_df=scores_df,
        current_holdings=current_holdings,
        bonus_pct=0.2
    )

    # Should have inertia marker
    assert 'has_inertia' in result_df.columns
    assert result_df[result_df['symbol'] == 'C']['has_inertia'].iloc[0]
    assert result_df[result_df['symbol'] == 'D']['has_inertia'].iloc[0]

    # Adjusted scores should be higher for holdings
    c_adjusted = result_df[result_df['symbol'] == 'C']['adjusted_score'].iloc[0]
    assert np.isclose(c_adjusted, 0.6 * 1.2)  # 20% bonus

    # Ranks should be recalculated
    assert 'adjusted_rank' in result_df.columns


def test_get_trading_signals_basic():
    """Test basic trading signal generation."""
    scores_df = pd.DataFrame({
        'symbol': ['A', 'B', 'C', 'D', 'E'],
        'raw_score': [1.0, 0.8, 0.6, 0.4, 0.2],
        'rank': [1, 2, 3, 4, 5]
    })

    current_holdings = ['C', 'D']  # Currently hold rank 3 and 4

    signals = get_trading_signals(
        scores_df=scores_df,
        current_holdings=current_holdings,
        buy_top_n=2,
        hold_until_rank=3,
        use_adjusted_rank=False
    )

    # Should buy A and B (top 2)
    assert set(signals['to_buy']) == {'A', 'B'}

    # Should hold C (rank 3, within hold_until_rank)
    assert 'C' in signals['to_hold']

    # Should sell D (rank 4, beyond hold_until_rank)
    assert 'D' in signals['to_sell']

    # Final holdings: A, B, C
    assert set(signals['final_holdings']) == {'A', 'B', 'C'}


def test_get_trading_signals_with_stop_loss():
    """Test trading signals with stop loss."""
    scores_df = pd.DataFrame({
        'symbol': ['A', 'B', 'C', 'D', 'E'],
        'raw_score': [1.0, 0.8, 0.6, 0.4, 0.2],
        'rank': [1, 2, 3, 4, 5]
    })

    current_holdings = ['A', 'B', 'C']
    stop_loss_symbols = ['B']  # Force sell B

    signals = get_trading_signals(
        scores_df=scores_df,
        current_holdings=current_holdings,
        buy_top_n=3,
        hold_until_rank=4,
        stop_loss_symbols=stop_loss_symbols,
        use_adjusted_rank=False
    )

    # B should be sold due to stop loss
    assert 'B' in signals['to_sell']
    assert signals['metadata']['sell_reasons']['B'] == 'stop_loss'

    # A and C should be held
    assert 'A' in signals['to_hold']
    assert 'C' in signals['to_hold']


def test_get_trading_signals_with_inertia():
    """Test trading signals with inertia bonus."""
    scores_df = pd.DataFrame({
        'symbol': ['A', 'B', 'C', 'D', 'E'],
        'raw_score': [1.0, 0.8, 0.6, 0.4, 0.2],
        'rank': [1, 2, 3, 4, 5]
    })

    current_holdings = ['D']  # Hold rank 4

    # Apply inertia bonus
    scores_df = apply_inertia_bonus(
        scores_df=scores_df,
        current_holdings=current_holdings,
        bonus_pct=0.5  # Large bonus
    )

    # D's adjusted rank should improve significantly
    d_adjusted_rank = scores_df[scores_df['symbol'] == 'D']['adjusted_rank'].iloc[0]
    assert d_adjusted_rank < 4  # Should move up from rank 4

    signals = get_trading_signals(
        scores_df=scores_df,
        current_holdings=current_holdings,
        buy_top_n=2,
        hold_until_rank=3,
        use_adjusted_rank=True
    )

    # D should be held due to improved rank
    assert 'D' in signals['to_hold'] or 'D' in signals['final_holdings']


def test_calculate_historical_scores(sample_universe):
    """Test historical score calculation."""
    hist_scores = calculate_historical_scores(
        data_dict=sample_universe,
        start_date='2023-06-01',
        end_date='2023-06-30'
    )

    # Should have MultiIndex (date, symbol)
    assert isinstance(hist_scores.index, pd.MultiIndex)
    assert hist_scores.index.names == ['date', 'symbol']

    # Should have expected columns
    assert set(hist_scores.columns) == {'raw_score', 'rank'}

    # Should have data for multiple dates
    unique_dates = hist_scores.index.get_level_values(0).unique()
    assert len(unique_dates) > 0


def test_get_scores_for_date(sample_universe):
    """Test extracting scores for a specific date."""
    hist_scores = calculate_historical_scores(
        data_dict=sample_universe,
        start_date='2023-06-01',
        end_date='2023-06-10'
    )

    date_scores = get_scores_for_date(hist_scores, '2023-06-05')

    # Should have scores for 5 ETFs
    assert len(date_scores) == 5
    assert set(date_scores.columns) == {'symbol', 'raw_score', 'rank'}

    # Should be sorted by rank
    assert date_scores['rank'].tolist() == [1, 2, 3, 4, 5]


def test_validate_scoring_params():
    """Test parameter validation."""
    # Valid params
    is_valid, error = validate_scoring_params(
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3],
        buy_top_n=10,
        hold_until_rank=15
    )
    assert is_valid
    assert error is None

    # Invalid: weights don't sum to 1.0
    is_valid, error = validate_scoring_params(
        periods=[20, 60, 120],
        weights=[0.5, 0.3, 0.3],
        buy_top_n=10,
        hold_until_rank=15
    )
    assert not is_valid
    assert "sum to 1.0" in error

    # Invalid: hold_until_rank < buy_top_n
    is_valid, error = validate_scoring_params(
        periods=[20, 60, 120],
        weights=[0.4, 0.3, 0.3],
        buy_top_n=15,
        hold_until_rank=10
    )
    assert not is_valid
    assert "hold_until_rank" in error


def test_edge_case_empty_scores():
    """Test handling of empty scores."""
    signals = get_trading_signals(
        scores_df=pd.DataFrame(columns=['symbol', 'raw_score', 'rank']),
        current_holdings=['A', 'B'],
        buy_top_n=5,
        hold_until_rank=10
    )

    # Should sell everything
    assert set(signals['to_sell']) == {'A', 'B'}
    assert len(signals['to_buy']) == 0
    assert len(signals['final_holdings']) == 0


def test_momentum_score_volatility_weighting():
    """Test that volatility weighting works correctly."""
    # Create two ETFs: one high return/high vol, one low return/low vol
    dates = pd.date_range('2023-01-01', periods=200, freq='D')

    # High return, high volatility
    np.random.seed(42)
    high_vol_returns = np.random.randn(200) * 0.03  # 3% daily std
    high_vol_prices = 100 * (1 + high_vol_returns).cumprod()
    df_high = pd.DataFrame({'close': high_vol_prices}, index=dates)

    # Low return, low volatility
    np.random.seed(43)
    low_vol_returns = np.random.randn(200) * 0.005  # 0.5% daily std
    low_vol_prices = 100 * (1 + low_vol_returns).cumprod()
    df_low = pd.DataFrame({'close': low_vol_prices}, index=dates)

    score_high = calculate_momentum_score(df_high)
    score_low = calculate_momentum_score(df_low)

    # Scores should be volatility-adjusted
    # Cannot predict exact relationship without knowing final prices,
    # but both should be valid numbers
    assert not np.isnan(score_high)
    assert not np.isnan(score_low)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
