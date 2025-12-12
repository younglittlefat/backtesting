"""
Unit tests for clustering module.

Tests cover:
- Correlation and distance matrix calculation
- Hierarchical clustering
- Cluster assignment and validation
- Intra-cluster competition and filtering
- Risk-adjusted momentum scoring
- Cluster exposure calculation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict

import sys
from pathlib import Path
# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from clustering import (
    calculate_returns,
    calculate_correlation_matrix,
    calculate_distance_matrix,
    perform_clustering,
    get_cluster_assignments,
    calculate_risk_adjusted_momentum,
    filter_by_cluster_limit,
    get_cluster_exposure,
    get_symbols_in_cluster,
    validate_cluster_assignments
)


@pytest.fixture
def sample_data_dict():
    """Create sample OHLCV data for testing."""
    np.random.seed(42)

    dates = pd.date_range(start='2024-01-01', periods=150, freq='D')

    # Create 5 ETFs with different correlation patterns
    # Group 1: High correlation (0.9+)
    returns_a = np.random.normal(0.001, 0.02, 150)
    returns_b = returns_a + np.random.normal(0, 0.005, 150)  # Highly correlated with A

    # Group 2: Moderate correlation (0.5-0.7)
    returns_c = np.random.normal(0.0005, 0.015, 150)
    returns_d = 0.5 * returns_c + 0.5 * np.random.normal(0, 0.015, 150)  # Moderately correlated with C

    # Group 3: Low/no correlation
    returns_e = np.random.normal(0.0008, 0.018, 150)

    def create_price_series(returns):
        prices = 100 * np.cumprod(1 + returns)
        return prices

    data_dict = {}
    for symbol, returns in [
        ('ETF_A', returns_a),
        ('ETF_B', returns_b),
        ('ETF_C', returns_c),
        ('ETF_D', returns_d),
        ('ETF_E', returns_e)
    ]:
        prices = create_price_series(returns)
        df = pd.DataFrame({
            'open': prices * 0.99,
            'high': prices * 1.01,
            'low': prices * 0.98,
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, 150)
        }, index=dates)
        data_dict[symbol] = df

    return data_dict


def test_calculate_returns_basic(sample_data_dict):
    """Test basic returns calculation."""
    returns_df = calculate_returns(sample_data_dict, lookback_days=120)

    assert isinstance(returns_df, pd.DataFrame)
    assert len(returns_df.columns) == 5  # All 5 ETFs
    assert len(returns_df) <= 120  # At most lookback_days
    assert returns_df.index.name == 'date' or isinstance(returns_df.index, pd.DatetimeIndex)

    # Check returns are reasonable
    assert (returns_df.abs() < 0.5).all().all()  # No single-day 50%+ moves


def test_calculate_returns_missing_data():
    """Test returns calculation with missing data."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # Create data with gaps
    data_dict = {
        'ETF_X': pd.DataFrame({
            'close': np.random.uniform(90, 110, 100)
        }, index=dates)
    }

    # Add NaNs
    data_dict['ETF_X']['close'].iloc[10:15] = np.nan

    returns_df = calculate_returns(data_dict, lookback_days=100)

    # Should handle forward-fill and drop remaining NaNs
    assert not returns_df.isnull().any().any()


def test_calculate_correlation_matrix(sample_data_dict):
    """Test correlation matrix calculation."""
    corr_matrix = calculate_correlation_matrix(sample_data_dict, lookback_days=120)

    assert isinstance(corr_matrix, pd.DataFrame)
    assert corr_matrix.shape == (5, 5)  # N x N
    assert (corr_matrix.index == corr_matrix.columns).all()  # Symmetric index

    # Check diagonal is 1.0
    assert np.allclose(np.diag(corr_matrix.values), 1.0)

    # Check correlation bounds [-1, 1]
    assert (corr_matrix.values >= -1.0).all()
    assert (corr_matrix.values <= 1.0).all()

    # Check symmetry
    assert np.allclose(corr_matrix.values, corr_matrix.values.T)

    # ETF_A and ETF_B should be highly correlated (by design)
    assert corr_matrix.loc['ETF_A', 'ETF_B'] > 0.7


def test_calculate_distance_matrix(sample_data_dict):
    """Test distance matrix calculation."""
    corr_matrix = calculate_correlation_matrix(sample_data_dict, lookback_days=120)
    dist_matrix = calculate_distance_matrix(corr_matrix)

    assert isinstance(dist_matrix, pd.DataFrame)
    assert dist_matrix.shape == corr_matrix.shape

    # Check diagonal is 0.0
    assert np.allclose(np.diag(dist_matrix.values), 0.0)

    # Check distance bounds [0, 2]
    assert (dist_matrix.values >= 0.0).all()
    assert (dist_matrix.values <= 2.0).all()

    # Check symmetry
    assert np.allclose(dist_matrix.values, dist_matrix.values.T)

    # High correlation → small distance
    # ETF_A and ETF_B have high correlation, so distance should be small
    assert dist_matrix.loc['ETF_A', 'ETF_B'] < 1.0


def test_distance_formula():
    """Test the distance formula: d = sqrt(2 * (1 - rho))."""
    # Create known correlations
    corr_data = {
        'A': [1.0, 0.5, 0.0, -1.0],
        'B': [0.5, 1.0, 0.2, -0.5],
        'C': [0.0, 0.2, 1.0, 0.3],
        'D': [-1.0, -0.5, 0.3, 1.0]
    }
    corr_matrix = pd.DataFrame(corr_data, index=['A', 'B', 'C', 'D'])

    dist_matrix = calculate_distance_matrix(corr_matrix)

    # Test specific values
    assert np.isclose(dist_matrix.loc['A', 'A'], 0.0)  # rho=1 → d=0
    assert np.isclose(dist_matrix.loc['A', 'B'], np.sqrt(2 * (1 - 0.5)))  # rho=0.5 → d=1.0
    assert np.isclose(dist_matrix.loc['A', 'C'], np.sqrt(2 * (1 - 0.0)))  # rho=0 → d=1.414
    assert np.isclose(dist_matrix.loc['A', 'D'], np.sqrt(2 * (1 - (-1.0))))  # rho=-1 → d=2.0


def test_perform_clustering_basic(sample_data_dict):
    """Test basic hierarchical clustering."""
    corr_matrix = calculate_correlation_matrix(sample_data_dict, lookback_days=120)
    dist_matrix = calculate_distance_matrix(corr_matrix)

    cluster_assignments = perform_clustering(
        dist_matrix,
        correlation_threshold=0.5,
        method='ward'
    )

    assert isinstance(cluster_assignments, dict)
    assert len(cluster_assignments) == 5  # All 5 ETFs
    assert set(cluster_assignments.keys()) == set(sample_data_dict.keys())

    # All cluster IDs should be non-negative integers
    assert all(isinstance(cid, int) and cid >= 0 for cid in cluster_assignments.values())

    # ETF_A and ETF_B should be in the same cluster (high correlation)
    assert cluster_assignments['ETF_A'] == cluster_assignments['ETF_B']


def test_perform_clustering_thresholds():
    """Test clustering with different correlation thresholds."""
    # Create highly correlated data
    dates = pd.date_range(start='2024-01-01', periods=150, freq='D')
    base_returns = np.random.normal(0.001, 0.02, 150)

    data_dict = {}
    for i in range(5):
        noise = np.random.normal(0, 0.003, 150)
        prices = 100 * np.cumprod(1 + base_returns + noise)
        data_dict[f'ETF_{i}'] = pd.DataFrame({
            'close': prices
        }, index=dates)

    corr_matrix = calculate_correlation_matrix(data_dict, lookback_days=120)
    dist_matrix = calculate_distance_matrix(corr_matrix)

    # Low threshold (0.3) → more clusters
    clusters_low = perform_clustering(dist_matrix, correlation_threshold=0.3)

    # High threshold (0.9) → fewer clusters
    clusters_high = perform_clustering(dist_matrix, correlation_threshold=0.9)

    num_clusters_low = len(set(clusters_low.values()))
    num_clusters_high = len(set(clusters_high.values()))

    # Higher correlation threshold should result in fewer clusters
    assert num_clusters_high <= num_clusters_low


def test_get_cluster_assignments_integration(sample_data_dict):
    """Test the one-stop get_cluster_assignments function."""
    cluster_assignments, corr_matrix = get_cluster_assignments(
        sample_data_dict,
        lookback_days=120,
        correlation_threshold=0.5
    )

    assert isinstance(cluster_assignments, dict)
    assert isinstance(corr_matrix, pd.DataFrame)

    assert len(cluster_assignments) == 5
    assert corr_matrix.shape == (5, 5)

    # Verify consistency
    assert set(cluster_assignments.keys()) == set(corr_matrix.index)


def test_calculate_risk_adjusted_momentum(sample_data_dict):
    """Test risk-adjusted momentum calculation."""
    symbols = list(sample_data_dict.keys())

    scores = calculate_risk_adjusted_momentum(
        sample_data_dict,
        symbols,
        lookback_days=60
    )

    assert isinstance(scores, dict)
    assert len(scores) == 5

    # All symbols should have scores
    for symbol in symbols:
        assert symbol in scores
        assert isinstance(scores[symbol], (int, float))

    # Scores should be finite or -inf (for invalid data)
    for score in scores.values():
        assert np.isfinite(score) or score == -np.inf


def test_calculate_risk_adjusted_momentum_missing_symbol():
    """Test momentum calculation with missing symbols."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data_dict = {
        'ETF_A': pd.DataFrame({'close': np.random.uniform(95, 105, 100)}, index=dates)
    }

    scores = calculate_risk_adjusted_momentum(
        data_dict,
        ['ETF_A', 'ETF_MISSING'],
        lookback_days=60
    )

    assert scores['ETF_A'] != -np.inf  # Valid score
    assert scores['ETF_MISSING'] == -np.inf  # Missing symbol


def test_filter_by_cluster_limit_basic(sample_data_dict):
    """Test cluster filtering with basic scenarios."""
    # Setup: Create cluster assignments
    cluster_assignments, _ = get_cluster_assignments(sample_data_dict, lookback_days=120)

    # Assume ETF_A and ETF_B are in same cluster (cluster 0)
    # Force them to be in same cluster for this test
    cluster_assignments['ETF_A'] = 0
    cluster_assignments['ETF_B'] = 0
    cluster_assignments['ETF_C'] = 1
    cluster_assignments['ETF_D'] = 1
    cluster_assignments['ETF_E'] = 2

    # Current holdings: 2 in cluster 0 (full)
    current_holdings = {
        'ETF_A': 0,
        'ETF_B': 0
    }

    # Candidates: 1 new in cluster 0, 1 in cluster 1
    candidates = ['ETF_C', 'ETF_D']  # Different clusters

    # Without scores: both should be approved (cluster 1 has space)
    filtered = filter_by_cluster_limit(
        candidates,
        cluster_assignments,
        current_holdings,
        max_per_cluster=2,
        scores=None
    )

    assert 'ETF_C' in filtered
    assert 'ETF_D' in filtered


def test_filter_by_cluster_limit_replacement(sample_data_dict):
    """Test cluster filtering with replacement logic."""
    cluster_assignments = {
        'ETF_A': 0, 'ETF_B': 0, 'ETF_C': 0,
        'ETF_D': 1, 'ETF_E': 1
    }

    # Current holdings: 2 in cluster 0
    current_holdings = {
        'ETF_A': 0,  # Weak
        'ETF_B': 0   # Strong
    }

    # Candidate: ETF_C wants to join cluster 0
    candidates = ['ETF_C']

    # Scores: ETF_C is stronger than ETF_A
    scores = {
        'ETF_A': 0.5,  # Weakest
        'ETF_B': 1.5,  # Strongest
        'ETF_C': 1.2   # Stronger than A
    }

    filtered = filter_by_cluster_limit(
        candidates,
        cluster_assignments,
        current_holdings,
        max_per_cluster=2,
        scores=scores
    )

    # ETF_C should be approved (replaces ETF_A)
    assert 'ETF_C' in filtered


def test_filter_by_cluster_limit_no_replacement(sample_data_dict):
    """Test cluster filtering when candidate is weaker than all holdings."""
    cluster_assignments = {
        'ETF_A': 0, 'ETF_B': 0, 'ETF_C': 0
    }

    current_holdings = {
        'ETF_A': 0,  # Medium
        'ETF_B': 0   # Strong
    }

    candidates = ['ETF_C']

    # ETF_C is weaker than all current holdings
    scores = {
        'ETF_A': 1.0,
        'ETF_B': 1.5,
        'ETF_C': 0.3  # Weakest
    }

    filtered = filter_by_cluster_limit(
        candidates,
        cluster_assignments,
        current_holdings,
        max_per_cluster=2,
        scores=scores
    )

    # ETF_C should be rejected
    assert 'ETF_C' not in filtered


def test_get_cluster_exposure_equal_weight(sample_data_dict):
    """Test cluster exposure with equal weighting."""
    cluster_assignments = {
        'ETF_A': 0, 'ETF_B': 0,
        'ETF_C': 1,
        'ETF_D': 2, 'ETF_E': 2
    }

    holdings = ['ETF_A', 'ETF_B', 'ETF_C']

    exposure = get_cluster_exposure(holdings, cluster_assignments)

    assert len(exposure) == 2  # Clusters 0 and 1

    assert exposure[0]['count'] == 2
    assert exposure[1]['count'] == 1

    # Equal weight: 1/3 each
    assert np.isclose(exposure[0]['weight'], 2/3)
    assert np.isclose(exposure[1]['weight'], 1/3)

    assert set(exposure[0]['symbols']) == {'ETF_A', 'ETF_B'}
    assert exposure[1]['symbols'] == ['ETF_C']


def test_get_cluster_exposure_custom_weights():
    """Test cluster exposure with custom weights."""
    cluster_assignments = {
        'ETF_A': 0, 'ETF_B': 0, 'ETF_C': 1
    }

    holdings = ['ETF_A', 'ETF_B', 'ETF_C']

    weights = {
        'ETF_A': 0.3,
        'ETF_B': 0.2,
        'ETF_C': 0.5
    }

    exposure = get_cluster_exposure(holdings, cluster_assignments, weights)

    assert np.isclose(exposure[0]['weight'], 0.5)  # 0.3 + 0.2
    assert np.isclose(exposure[1]['weight'], 0.5)  # 0.5


def test_get_symbols_in_cluster():
    """Test getting symbols in a specific cluster."""
    cluster_assignments = {
        'ETF_A': 0, 'ETF_B': 0, 'ETF_C': 0,
        'ETF_D': 1, 'ETF_E': 2
    }

    symbols_0 = get_symbols_in_cluster(0, cluster_assignments)
    symbols_1 = get_symbols_in_cluster(1, cluster_assignments)
    symbols_2 = get_symbols_in_cluster(2, cluster_assignments)

    assert set(symbols_0) == {'ETF_A', 'ETF_B', 'ETF_C'}
    assert symbols_1 == ['ETF_D']
    assert symbols_2 == ['ETF_E']


def test_validate_cluster_assignments_valid(sample_data_dict):
    """Test cluster validation with valid assignments."""
    cluster_assignments, _ = get_cluster_assignments(sample_data_dict, lookback_days=120)

    is_valid, missing = validate_cluster_assignments(cluster_assignments, sample_data_dict)

    assert is_valid is True
    assert len(missing) == 0


def test_validate_cluster_assignments_invalid():
    """Test cluster validation with missing assignments."""
    data_dict = {
        'ETF_A': pd.DataFrame({'close': [100, 101, 102]}),
        'ETF_B': pd.DataFrame({'close': [100, 101, 102]}),
        'ETF_C': pd.DataFrame({'close': [100, 101, 102]})
    }

    # Missing ETF_C
    cluster_assignments = {
        'ETF_A': 0,
        'ETF_B': 0
    }

    is_valid, missing = validate_cluster_assignments(cluster_assignments, data_dict)

    assert is_valid is False
    assert 'ETF_C' in missing
    assert len(missing) == 1


def test_edge_case_single_etf():
    """Test clustering with only 1 ETF."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data_dict = {
        'ETF_SOLO': pd.DataFrame({'close': np.random.uniform(95, 105, 100)}, index=dates)
    }

    cluster_assignments, corr_matrix = get_cluster_assignments(data_dict, lookback_days=50)

    # Should handle gracefully
    assert len(cluster_assignments) == 1
    assert cluster_assignments['ETF_SOLO'] == 0


def test_edge_case_zero_volatility():
    """Test momentum calculation with zero volatility."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data_dict = {
        'ETF_FLAT': pd.DataFrame({'close': np.full(100, 100.0)}, index=dates)  # Constant price
    }

    scores = calculate_risk_adjusted_momentum(data_dict, ['ETF_FLAT'], lookback_days=60)

    # Zero volatility should result in -inf
    assert scores['ETF_FLAT'] == -np.inf


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
