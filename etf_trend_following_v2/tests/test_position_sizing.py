"""
Unit tests for position_sizing module

Tests cover:
- Volatility calculation (STD and EWMA methods)
- Position sizing with various constraints
- Portfolio construction with cluster limits
- Rebalancing calculations
- Constraint validation

Run tests:
    python -m pytest etf_trend_following_v2/tests/test_position_sizing.py -v
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from position_sizing import (
    calculate_volatility,
    calculate_position_size,
    calculate_portfolio_positions,
    normalize_positions,
    apply_cluster_limits,
    calculate_rebalance_trades,
    validate_portfolio_constraints,
    get_position_summary
)


@pytest.fixture
def sample_price_data():
    """Generate synthetic price data for testing"""
    dates = pd.date_range('2023-01-01', '2024-12-31', freq='D')

    # Low volatility asset (treasury-like)
    np.random.seed(42)
    low_vol_returns = np.random.normal(0.0001, 0.001, len(dates))
    low_vol_prices = 100 * np.exp(np.cumsum(low_vol_returns))

    # High volatility asset (equity-like)
    high_vol_returns = np.random.normal(0.001, 0.02, len(dates))
    high_vol_prices = 50 * np.exp(np.cumsum(high_vol_returns))

    return {
        'low_vol': pd.DataFrame({'close': low_vol_prices}, index=dates),
        'high_vol': pd.DataFrame({'close': high_vol_prices}, index=dates)
    }


class TestVolatilityCalculation:
    """Test volatility calculation methods"""

    def test_std_method(self, sample_price_data):
        """Test rolling standard deviation method"""
        vol = calculate_volatility(
            sample_price_data['low_vol'],
            method='std',
            window=60
        )
        assert vol > 0
        assert vol < 0.01  # Low vol asset should have <1% daily vol

    def test_ewma_method(self, sample_price_data):
        """Test EWMA method"""
        vol = calculate_volatility(
            sample_price_data['high_vol'],
            method='ewma',
            ewma_lambda=0.94
        )
        assert vol > 0.01  # High vol asset should have >1% daily vol

    def test_minimum_volatility_floor(self):
        """Test that minimum volatility floor is applied"""
        # Create zero-volatility data
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
        constant_prices = pd.Series([100] * len(dates), index=dates)
        df = pd.DataFrame({'close': constant_prices})

        vol = calculate_volatility(df, method='ewma')
        assert vol == 0.0001  # Should equal min_volatility floor

    def test_invalid_method_raises_error(self, sample_price_data):
        """Test that invalid method raises ValueError"""
        with pytest.raises(ValueError):
            calculate_volatility(sample_price_data['low_vol'], method='invalid')

    def test_empty_dataframe_returns_nan(self):
        """Test that empty dataframe returns NaN"""
        df = pd.DataFrame({'close': []})
        vol = calculate_volatility(df)
        assert pd.isna(vol)


class TestPositionSizing:
    """Test position size calculation"""

    def test_basic_position_sizing(self):
        """Test basic inverse volatility weighting"""
        total_capital = 1_000_000
        vol = 0.02  # 2% daily vol
        target_risk = 0.005  # 0.5% target risk

        capital, weight = calculate_position_size(vol, total_capital, target_risk, max_position_pct=0.5)

        # Expected: 1M * 0.005 / 0.02 = 250,000
        assert capital == pytest.approx(250_000, rel=0.01)
        assert weight == pytest.approx(0.25, rel=0.01)

    def test_max_position_cap(self):
        """Test that max position cap is enforced"""
        total_capital = 1_000_000
        vol = 0.001  # Very low vol
        target_risk = 0.005
        max_pct = 0.2  # 20% cap

        capital, weight = calculate_position_size(vol, total_capital, target_risk, max_pct)

        # Without cap: 1M * 0.005 / 0.001 = 5M
        # With cap: capped at 20% = 200k
        assert capital == pytest.approx(200_000, rel=0.01)
        assert weight == pytest.approx(0.2, rel=0.01)

    def test_zero_volatility_returns_zero_position(self):
        """Test that zero volatility returns zero position"""
        capital, weight = calculate_position_size(0.0, 1_000_000, 0.005, 0.2)
        assert capital == 0.0
        assert weight == 0.0


class TestPortfolioConstruction:
    """Test portfolio-level position calculation"""

    def test_basic_portfolio(self, sample_price_data):
        """Test basic portfolio construction"""
        total_capital = 1_000_000
        symbols = list(sample_price_data.keys())

        positions = calculate_portfolio_positions(
            sample_price_data,
            symbols,
            total_capital,
            max_position_pct=0.3,
            max_cluster_pct=None,  # Disable cluster limits
            volatility_method='ewma'
        )

        assert len(positions) == 2
        assert 'low_vol' in positions
        assert 'high_vol' in positions

        # Check that all positions have required fields
        for pos in positions.values():
            assert 'target_capital' in pos
            assert 'target_weight' in pos
            assert 'volatility' in pos

    def test_cluster_limits(self, sample_price_data):
        """Test that cluster limits are enforced"""
        total_capital = 1_000_000
        symbols = list(sample_price_data.keys())

        # Assign both to same cluster
        cluster_map = {'low_vol': 0, 'high_vol': 0}

        positions = calculate_portfolio_positions(
            sample_price_data,
            symbols,
            total_capital,
            max_position_pct=0.3,
            max_cluster_pct=0.4,  # 40% max per cluster
            cluster_assignments=cluster_map
        )

        # Total cluster weight should not exceed 40%
        total_cluster_weight = sum(pos['target_weight'] for pos in positions.values())
        assert total_cluster_weight <= 0.4 * 1.01  # 1% tolerance

    def test_total_portfolio_limit(self, sample_price_data):
        """Test that total portfolio limit is enforced"""
        total_capital = 1_000_000
        symbols = list(sample_price_data.keys())

        positions = calculate_portfolio_positions(
            sample_price_data,
            symbols,
            total_capital,
            max_position_pct=0.8,  # Allow large positions
            max_cluster_pct=None,
            max_total_pct=0.5  # But limit total to 50%
        )

        total_weight = sum(pos['target_weight'] for pos in positions.values())
        assert total_weight <= 0.5 * 1.01


class TestNormalization:
    """Test position normalization"""

    def test_normalize_over_limit(self):
        """Test normalization when total exceeds limit"""
        positions = {
            'A': {'target_weight': 0.6, 'target_capital': 600_000},
            'B': {'target_weight': 0.5, 'target_capital': 500_000}
        }
        total_capital = 1_000_000

        normalized = normalize_positions(positions, max_total_pct=1.0, total_capital=total_capital)

        total_weight = sum(pos['target_weight'] for pos in normalized.values())
        assert total_weight == pytest.approx(1.0, rel=0.01)

        # Check proportional scaling
        assert normalized['A']['target_weight'] / normalized['B']['target_weight'] == pytest.approx(0.6 / 0.5, rel=0.01)

    def test_normalize_under_limit_no_change(self):
        """Test that positions under limit are not changed"""
        positions = {
            'A': {'target_weight': 0.3, 'target_capital': 300_000},
            'B': {'target_weight': 0.2, 'target_capital': 200_000}
        }

        normalized = normalize_positions(positions, max_total_pct=1.0)

        # Should be unchanged
        assert normalized['A']['target_weight'] == 0.3
        assert normalized['B']['target_weight'] == 0.2


class TestClusterLimits:
    """Test cluster limit application"""

    def test_single_cluster_over_limit(self):
        """Test scaling when single cluster exceeds limit"""
        positions = {
            'A': {'target_weight': 0.2, 'target_capital': 200_000},
            'B': {'target_weight': 0.15, 'target_capital': 150_000},
            'C': {'target_weight': 0.1, 'target_capital': 100_000}
        }
        cluster_map = {'A': 0, 'B': 0, 'C': 1}  # A,B in cluster 0

        adjusted = apply_cluster_limits(
            positions,
            cluster_map,
            max_cluster_pct=0.25,
            total_capital=1_000_000
        )

        # Cluster 0 (A+B) should be scaled from 0.35 to 0.25
        cluster_0_weight = adjusted['A']['target_weight'] + adjusted['B']['target_weight']
        assert cluster_0_weight == pytest.approx(0.25, rel=0.01)

        # Cluster 1 (C) should be unchanged
        assert adjusted['C']['target_weight'] == pytest.approx(0.1, rel=0.01)


class TestRebalancing:
    """Test rebalancing trade calculation"""

    def test_buy_trade(self):
        """Test buy trade generation"""
        current = {'A': 50_000}
        target = {'A': 100_000}
        prices = {'A': 10.0}

        trades = calculate_rebalance_trades(current, target, prices, min_trade_amount=1000)

        assert 'A' in trades
        assert trades['A']['action'] == 'buy'
        # Expected: (100k - 50k) / 10 = 5000 shares, rounded to 5000 (50 lots)
        assert trades['A']['shares'] == 5000

    def test_sell_trade(self):
        """Test sell trade generation"""
        current = {'A': 100_000}
        target = {'A': 50_000}
        prices = {'A': 10.0}

        trades = calculate_rebalance_trades(current, target, prices)

        assert 'A' in trades
        assert trades['A']['action'] == 'sell'

    def test_new_position(self):
        """Test new position (not in current holdings)"""
        current = {}
        target = {'A': 50_000}
        prices = {'A': 10.0}

        trades = calculate_rebalance_trades(current, target, prices)

        assert 'A' in trades
        assert trades['A']['action'] == 'buy'

    def test_exit_position(self):
        """Test exiting position (not in target)"""
        current = {'A': 50_000}
        target = {}
        prices = {'A': 10.0}

        trades = calculate_rebalance_trades(current, target, prices)

        assert 'A' in trades
        assert trades['A']['action'] == 'sell'

    def test_lot_size_rounding(self):
        """Test that shares are rounded to lot size (100)"""
        current = {}
        target = {'A': 15_000}  # 15k at 10 CNY/share = 1500 shares = 15 lots
        prices = {'A': 10.0}

        trades = calculate_rebalance_trades(current, target, prices, lot_size=100)

        # Should be rounded to 1500 (15 lots of 100)
        assert trades['A']['shares'] % 100 == 0

    def test_minimum_trade_filter(self):
        """Test that trades below minimum are filtered"""
        current = {'A': 50_000}
        target = {'A': 50_500}  # Only 500 CNY difference
        prices = {'A': 10.0}

        trades = calculate_rebalance_trades(current, target, prices, min_trade_amount=1000)

        # Should be filtered out
        assert len(trades) == 0


class TestConstraintValidation:
    """Test portfolio constraint validation"""

    def test_valid_portfolio(self):
        """Test validation of valid portfolio"""
        positions = {
            'A': {'target_weight': 0.15},
            'B': {'target_weight': 0.10}
        }

        is_valid, errors = validate_portfolio_constraints(
            positions,
            max_position_pct=0.2,
            max_total_pct=1.0
        )

        assert is_valid
        assert len(errors) == 0

    def test_position_limit_violation(self):
        """Test detection of position limit violation"""
        positions = {
            'A': {'target_weight': 0.25}  # Exceeds 20% limit
        }

        is_valid, errors = validate_portfolio_constraints(
            positions,
            max_position_pct=0.2
        )

        assert not is_valid
        assert len(errors) > 0

    def test_total_limit_violation(self):
        """Test detection of total portfolio limit violation"""
        positions = {
            'A': {'target_weight': 0.6},
            'B': {'target_weight': 0.5}
        }

        is_valid, errors = validate_portfolio_constraints(
            positions,
            max_position_pct=0.8,
            max_total_pct=1.0
        )

        assert not is_valid
        assert 'Total portfolio' in errors[0]


class TestSummaryGeneration:
    """Test position summary generation"""

    def test_summary_table(self):
        """Test that summary table is generated correctly"""
        positions = {
            'A': {
                'target_capital': 200_000,
                'target_weight': 0.2,
                'volatility': 0.01,
                'cluster_id': 0
            },
            'B': {
                'target_capital': 150_000,
                'target_weight': 0.15,
                'volatility': 0.02,
                'cluster_id': 1
            }
        }

        summary = get_position_summary(positions, 1_000_000)

        assert len(summary) == 3  # 2 positions + 1 TOTAL row
        assert summary.iloc[-1]['symbol'] == 'TOTAL'
        assert summary.iloc[-1]['target_capital'] == 350_000
        assert summary.iloc[-1]['target_weight'] == pytest.approx(35.0, rel=0.01)

    def test_empty_positions(self):
        """Test summary with empty positions"""
        summary = get_position_summary({}, 1_000_000)
        assert len(summary) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
