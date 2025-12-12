"""
Position Sizing Module for ETF Trend Following System

This module implements volatility-based position sizing using inverse volatility weighting.
The core principle is to allocate more capital to low-volatility assets and less to high-volatility
assets, ensuring each position contributes equally to portfolio risk.

Key Features:
- EWMA and rolling standard deviation volatility estimation
- Inverse volatility weighting for position sizing
- Multi-level constraints: single position, cluster, and total portfolio limits
- Rebalancing calculation with lot size constraints (A-share 100 shares/lot)

Author: Claude
Date: 2025-12-11
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from collections import defaultdict


def calculate_volatility(
    df: pd.DataFrame,
    method: str = 'ewma',
    window: int = 60,
    ewma_lambda: float = 0.94,
    min_volatility: float = 0.0001  # 0.01% minimum to prevent division by zero
) -> float:
    """
    Calculate daily volatility for a single asset.

    Parameters
    ----------
    df : pd.DataFrame
        Price data with 'close' column and datetime index
    method : str, default 'ewma'
        Volatility calculation method: 'std' (rolling standard deviation) or 'ewma' (exponentially weighted)
    window : int, default 60
        Rolling window size for volatility calculation (60 days ~3 months)
    ewma_lambda : float, default 0.94
        Decay factor for EWMA, higher values give more weight to recent data
        RiskMetrics standard: 0.94 for daily data
    min_volatility : float, default 0.0001
        Minimum volatility floor to prevent division by zero (0.01%)

    Returns
    -------
    float
        Annualized daily volatility (standard deviation of daily returns)

    Notes
    -----
    - EWMA is more responsive to recent market changes than rolling std
    - For low-volatility assets (e.g., treasury ETFs), the min_volatility floor applies
    - Returns NaN if insufficient data (less than window size for 'std' method)

    Examples
    --------
    >>> vol_std = calculate_volatility(df, method='std', window=60)
    >>> vol_ewma = calculate_volatility(df, method='ewma', ewma_lambda=0.94)
    """
    if df is None or len(df) == 0:
        return np.nan

    # Calculate daily returns
    returns = df['close'].pct_change().dropna()

    if len(returns) == 0:
        return np.nan

    # Calculate volatility based on method
    if method == 'std':
        if len(returns) < window:
            return np.nan
        volatility = returns.rolling(window=window).std().iloc[-1]

    elif method == 'ewma':
        # EWMA volatility: more weight to recent data
        # ewm(alpha=1-lambda) is equivalent to ewm(span=2/(1-lambda)-1)
        volatility = returns.ewm(alpha=1-ewma_lambda, adjust=False).std().iloc[-1]

    else:
        raise ValueError(f"Unknown volatility method: {method}. Use 'std' or 'ewma'.")

    # Apply minimum volatility floor
    if pd.isna(volatility) or volatility < min_volatility:
        volatility = min_volatility

    return volatility


def calculate_position_size(
    volatility: float,
    total_capital: float,
    target_risk_pct: float = 0.005,
    max_position_pct: float = 0.2
) -> Tuple[float, float]:
    """
    Calculate target position size for a single asset using inverse volatility weighting.

    The formula is:
        Position_Capital = Total_Capital × Target_Risk / Volatility

    This ensures each position contributes the same absolute risk (in dollars) to the portfolio.

    Parameters
    ----------
    volatility : float
        Daily volatility (standard deviation of daily returns)
    total_capital : float
        Total account capital (in CNY for A-shares)
    target_risk_pct : float, default 0.005
        Target daily risk per position (0.5% = 0.005)
        Derivation: If portfolio target is 20% annual vol, with 10 positions:
            Daily vol = 20% / sqrt(252) ≈ 1.25%
            Per-position vol = 1.25% / sqrt(10) ≈ 0.4% → rounded to 0.5%
    max_position_pct : float, default 0.2
        Maximum position size as fraction of total capital (20%)

    Returns
    -------
    tuple of (float, float)
        (target_capital, target_weight)
        - target_capital: Position size in dollars (capped by max_position_pct)
        - target_weight: Position weight as fraction of total capital

    Examples
    --------
    >>> # Treasury ETF: 0.1% volatility, 1M capital, 0.5% target risk
    >>> capital, weight = calculate_position_size(0.001, 1_000_000, 0.005, 0.2)
    >>> # Result: capital=200,000 (capped at 20%), weight=0.2

    >>> # Broker ETF: 2% volatility, 1M capital, 0.5% target risk
    >>> capital, weight = calculate_position_size(0.02, 1_000_000, 0.005, 0.2)
    >>> # Result: capital=25,000, weight=0.025
    """
    if pd.isna(volatility) or volatility <= 0:
        return 0.0, 0.0

    # Inverse volatility weighting: PositionCapital = TotalCapital × TargetRisk / Volatility
    target_capital = total_capital * target_risk_pct / volatility

    # Apply maximum position size constraint
    max_capital = total_capital * max_position_pct
    target_capital = min(target_capital, max_capital)

    # Calculate weight
    target_weight = target_capital / total_capital if total_capital > 0 else 0.0

    return target_capital, target_weight


def calculate_portfolio_positions(
    data_dict: Dict[str, pd.DataFrame],
    symbols: List[str],
    total_capital: float,
    target_risk_pct: float = 0.005,
    max_position_pct: float = 0.2,
    max_cluster_pct: Optional[float] = 0.2,
    cluster_assignments: Optional[Dict[str, int]] = None,
    max_total_pct: float = 1.0,
    volatility_method: str = 'ewma',
    volatility_window: int = 60,
    ewma_lambda: float = 0.94
) -> Dict[str, dict]:
    """
    Calculate position sizes for entire portfolio with multi-level constraints.

    This is the main entry point for portfolio construction. It applies:
    1. Individual position limits (max_position_pct)
    2. Cluster limits (max_cluster_pct, if clusters provided)
    3. Total portfolio limit (max_total_pct)

    Parameters
    ----------
    data_dict : Dict[str, pd.DataFrame]
        Dictionary mapping symbols to OHLCV dataframes
    symbols : List[str]
        List of symbols to include in portfolio
    total_capital : float
        Total account capital
    target_risk_pct : float, default 0.005
        Target daily risk per position (0.5%)
    max_position_pct : float, default 0.2
        Maximum single position size (20%)
    max_cluster_pct : float or None, default 0.2
        Maximum total allocation per cluster (20%). Set to None to disable.
    cluster_assignments : Dict[str, int] or None
        Mapping of symbol to cluster ID. Required if max_cluster_pct is set.
    max_total_pct : float, default 1.0
        Maximum total portfolio allocation (100% = fully invested, no leverage)
    volatility_method : str, default 'ewma'
        Volatility calculation method ('std' or 'ewma')
    volatility_window : int, default 60
        Window for rolling std (ignored for ewma)
    ewma_lambda : float, default 0.94
        Decay factor for EWMA

    Returns
    -------
    Dict[str, dict]
        Mapping of symbol to position details:
        {
            'symbol': {
                'target_capital': float,  # Target position size in dollars
                'target_weight': float,   # Position weight (0-1)
                'volatility': float,      # Daily volatility
                'cluster_id': int or None # Cluster assignment
            }
        }

    Notes
    -----
    The function applies constraints in the following order:
    1. Calculate inverse-volatility weighted positions with individual caps
    2. Apply cluster limits (if applicable)
    3. Apply total portfolio limit

    If total allocation < max_total_pct, the remainder is held as cash.

    Examples
    --------
    >>> positions = calculate_portfolio_positions(
    ...     data_dict,
    ...     symbols=['159915.SZ', '512880.SH'],
    ...     total_capital=1_000_000,
    ...     max_cluster_pct=0.2,
    ...     cluster_assignments={'159915.SZ': 0, '512880.SH': 1}
    ... )
    """
    positions = {}

    # Step 1: Calculate initial positions with individual caps
    for symbol in symbols:
        if symbol not in data_dict:
            continue

        df = data_dict[symbol]

        # Calculate volatility
        vol = calculate_volatility(
            df,
            method=volatility_method,
            window=volatility_window,
            ewma_lambda=ewma_lambda
        )

        # Calculate position size
        target_capital, target_weight = calculate_position_size(
            vol,
            total_capital,
            target_risk_pct,
            max_position_pct
        )

        # Store position details
        cluster_id = cluster_assignments.get(symbol) if cluster_assignments else None
        positions[symbol] = {
            'target_capital': target_capital,
            'target_weight': target_weight,
            'volatility': vol,
            'cluster_id': cluster_id
        }

    # Step 2: Apply cluster limits (if applicable)
    if max_cluster_pct is not None and cluster_assignments is not None:
        positions = apply_cluster_limits(
            positions,
            cluster_assignments,
            max_cluster_pct,
            total_capital
        )

    # Step 3: Apply total portfolio limit
    positions = normalize_positions(
        positions,
        max_total_pct,
        total_capital
    )

    return positions


def normalize_positions(
    positions: Dict[str, dict],
    max_total_pct: float = 1.0,
    total_capital: Optional[float] = None
) -> Dict[str, dict]:
    """
    Normalize positions to ensure total allocation does not exceed limit.

    If total_weight <= max_total_pct: keep positions as-is (hold cash)
    If total_weight > max_total_pct: scale down proportionally

    Parameters
    ----------
    positions : Dict[str, dict]
        Position dictionary from calculate_portfolio_positions
    max_total_pct : float, default 1.0
        Maximum total allocation (1.0 = 100%, no leverage)
    total_capital : float or None
        Total capital (used to recalculate target_capital after scaling)

    Returns
    -------
    Dict[str, dict]
        Normalized positions with updated target_weight and target_capital

    Examples
    --------
    >>> # Total weight = 120%, scale down to 100%
    >>> positions = normalize_positions(positions, max_total_pct=1.0, total_capital=1_000_000)
    """
    # Calculate current total weight
    total_weight = sum(pos['target_weight'] for pos in positions.values())

    if total_weight <= max_total_pct:
        # No scaling needed
        return positions

    # Scale down proportionally
    scale_factor = max_total_pct / total_weight

    for symbol in positions:
        positions[symbol]['target_weight'] *= scale_factor
        if total_capital is not None:
            positions[symbol]['target_capital'] = positions[symbol]['target_weight'] * total_capital

    return positions


def apply_cluster_limits(
    positions: Dict[str, dict],
    cluster_assignments: Dict[str, int],
    max_cluster_pct: float = 0.2,
    total_capital: Optional[float] = None
) -> Dict[str, dict]:
    """
    Apply cluster-level allocation limits.

    For each cluster, if total weight > max_cluster_pct, scale down positions
    within that cluster proportionally.

    Parameters
    ----------
    positions : Dict[str, dict]
        Position dictionary from calculate_portfolio_positions
    cluster_assignments : Dict[str, int]
        Mapping of symbol to cluster ID
    max_cluster_pct : float, default 0.2
        Maximum allocation per cluster (20%)
    total_capital : float or None
        Total capital (used to recalculate target_capital after scaling)

    Returns
    -------
    Dict[str, dict]
        Positions with cluster limits applied

    Examples
    --------
    >>> # If broker cluster (cluster_id=2) has 30% total weight, scale down to 20%
    >>> positions = apply_cluster_limits(positions, cluster_map, max_cluster_pct=0.2)
    """
    # Group positions by cluster
    cluster_weights = defaultdict(float)
    cluster_symbols = defaultdict(list)

    for symbol, pos in positions.items():
        cluster_id = cluster_assignments.get(symbol)
        if cluster_id is not None:
            cluster_weights[cluster_id] += pos['target_weight']
            cluster_symbols[cluster_id].append(symbol)

    # Check each cluster and scale if necessary
    for cluster_id, total_weight in cluster_weights.items():
        if total_weight > max_cluster_pct:
            # Scale down this cluster
            scale_factor = max_cluster_pct / total_weight

            for symbol in cluster_symbols[cluster_id]:
                positions[symbol]['target_weight'] *= scale_factor
                if total_capital is not None:
                    positions[symbol]['target_capital'] = positions[symbol]['target_weight'] * total_capital

    return positions


def calculate_rebalance_trades(
    current_positions: Dict[str, float],
    target_positions: Dict[str, float],
    current_prices: Dict[str, float],
    min_trade_amount: float = 1000,
    lot_size: int = 100
) -> Dict[str, dict]:
    """
    Calculate rebalancing trades from current to target positions.

    This function determines buy/sell orders needed to move from current holdings
    to target allocations, respecting A-share lot size constraints (100 shares/lot).

    Parameters
    ----------
    current_positions : Dict[str, float]
        Current holdings: {symbol: capital_amount}
    target_positions : Dict[str, float]
        Target holdings: {symbol: capital_amount}
    current_prices : Dict[str, float]
        Current prices: {symbol: price}
    min_trade_amount : float, default 1000
        Minimum trade size to avoid trivial trades (1000 CNY)
    lot_size : int, default 100
        Minimum trading unit for A-shares (100 shares per lot)

    Returns
    -------
    Dict[str, dict]
        Rebalancing trades:
        {
            'symbol': {
                'action': 'buy' or 'sell',
                'amount': float,        # Trade amount in dollars
                'shares': int,          # Number of shares (rounded to lot_size)
                'delta_pct': float      # Change as % of target position
            }
        }

    Notes
    -----
    - Shares are rounded down to nearest lot for buys, up for sells
    - Trades below min_trade_amount are filtered out
    - New positions (not in current) generate 'buy' orders
    - Positions to exit (not in target) generate 'sell' orders

    Examples
    --------
    >>> current = {'159915.SZ': 50000}  # Current: 50k CNY
    >>> target = {'159915.SZ': 80000}   # Target: 80k CNY
    >>> prices = {'159915.SZ': 2.5}     # Price: 2.5 CNY/share
    >>> trades = calculate_rebalance_trades(current, target, prices)
    >>> # Result: {'159915.SZ': {'action': 'buy', 'amount': 30000, 'shares': 12000}}
    """
    trades = {}

    # Combine all symbols from current and target
    all_symbols = set(current_positions.keys()) | set(target_positions.keys())

    for symbol in all_symbols:
        current_value = current_positions.get(symbol, 0.0)
        target_value = target_positions.get(symbol, 0.0)

        # Calculate trade delta
        delta = target_value - current_value

        # Skip if delta is too small
        if abs(delta) < min_trade_amount:
            continue

        # Get current price
        price = current_prices.get(symbol)
        if price is None or price <= 0:
            continue

        # Determine action
        action = 'buy' if delta > 0 else 'sell'

        # Calculate shares (must be multiple of lot_size)
        shares_float = abs(delta) / price

        if action == 'buy':
            # Round down for buys (avoid over-buying)
            shares = int(shares_float // lot_size) * lot_size
        else:
            # Round up for sells (ensure full liquidation)
            shares = int(np.ceil(shares_float / lot_size)) * lot_size

        # Skip if rounded to zero
        if shares == 0:
            continue

        # Calculate actual trade amount
        trade_amount = shares * price

        # Calculate delta as percentage of target position (for monitoring)
        delta_pct = (trade_amount / target_value * 100) if target_value > 0 else 0

        trades[symbol] = {
            'action': action,
            'amount': trade_amount,
            'shares': shares,
            'delta_pct': delta_pct
        }

    return trades


def get_position_summary(
    positions: Dict[str, dict],
    total_capital: float
) -> pd.DataFrame:
    """
    Generate a summary table of portfolio positions for reporting.

    Parameters
    ----------
    positions : Dict[str, dict]
        Position dictionary from calculate_portfolio_positions
    total_capital : float
        Total account capital

    Returns
    -------
    pd.DataFrame
        Summary table with columns:
        - symbol: ETF code
        - target_capital: Position size (CNY)
        - target_weight: Weight (%)
        - volatility: Daily volatility (%)
        - cluster_id: Cluster assignment

        Sorted by target_weight descending.

    Examples
    --------
    >>> summary = get_position_summary(positions, 1_000_000)
    >>> print(summary.to_string())
    """
    if not positions:
        return pd.DataFrame()

    # Convert to list of dicts
    rows = []
    for symbol, pos in positions.items():
        rows.append({
            'symbol': symbol,
            'target_capital': pos['target_capital'],
            'target_weight': pos['target_weight'] * 100,  # Convert to percentage
            'volatility': pos['volatility'] * 100,  # Convert to percentage
            'cluster_id': pos.get('cluster_id', None)
        })

    df = pd.DataFrame(rows)

    # Sort by weight descending
    df = df.sort_values('target_weight', ascending=False).reset_index(drop=True)

    # Add total row
    total_row = pd.DataFrame([{
        'symbol': 'TOTAL',
        'target_capital': df['target_capital'].sum(),
        'target_weight': df['target_weight'].sum(),
        'volatility': np.nan,
        'cluster_id': None
    }])

    df = pd.concat([df, total_row], ignore_index=True)

    return df


def validate_portfolio_constraints(
    positions: Dict[str, dict],
    max_position_pct: float = 0.2,
    max_cluster_pct: Optional[float] = 0.2,
    max_total_pct: float = 1.0,
    cluster_assignments: Optional[Dict[str, int]] = None
) -> Tuple[bool, List[str]]:
    """
    Validate that portfolio positions satisfy all constraints.

    This is a safety check to ensure calculate_portfolio_positions worked correctly.

    Parameters
    ----------
    positions : Dict[str, dict]
        Position dictionary to validate
    max_position_pct : float
        Maximum single position weight
    max_cluster_pct : float or None
        Maximum cluster weight
    max_total_pct : float
        Maximum total portfolio weight
    cluster_assignments : Dict[str, int] or None
        Cluster mapping (required if max_cluster_pct is set)

    Returns
    -------
    tuple of (bool, List[str])
        (is_valid, error_messages)
        - is_valid: True if all constraints satisfied
        - error_messages: List of constraint violations (empty if valid)

    Examples
    --------
    >>> is_valid, errors = validate_portfolio_constraints(positions, 0.2, 0.2, 1.0)
    >>> if not is_valid:
    ...     print("Constraint violations:", errors)
    """
    errors = []

    # Check individual position limits
    for symbol, pos in positions.items():
        weight = pos['target_weight']
        if weight > max_position_pct * 1.001:  # 0.1% tolerance for rounding
            errors.append(f"{symbol}: weight {weight:.2%} exceeds max {max_position_pct:.2%}")

    # Check cluster limits
    if max_cluster_pct is not None and cluster_assignments is not None:
        cluster_weights = defaultdict(float)
        for symbol, pos in positions.items():
            cluster_id = cluster_assignments.get(symbol)
            if cluster_id is not None:
                cluster_weights[cluster_id] += pos['target_weight']

        for cluster_id, weight in cluster_weights.items():
            if weight > max_cluster_pct * 1.001:
                errors.append(f"Cluster {cluster_id}: weight {weight:.2%} exceeds max {max_cluster_pct:.2%}")

    # Check total portfolio limit
    total_weight = sum(pos['target_weight'] for pos in positions.values())
    if total_weight > max_total_pct * 1.001:
        errors.append(f"Total portfolio: weight {total_weight:.2%} exceeds max {max_total_pct:.2%}")

    is_valid = len(errors) == 0
    return is_valid, errors


# Example usage and testing
if __name__ == '__main__':
    # Example: Create synthetic data for testing
    print("=== Position Sizing Module Test ===\n")

    # Synthetic price data
    dates = pd.date_range('2023-01-01', '2025-11-30', freq='D')

    # Treasury ETF: low volatility
    np.random.seed(42)
    treasury_returns = np.random.normal(0.0001, 0.001, len(dates))
    treasury_prices = 100 * np.exp(np.cumsum(treasury_returns))

    # Broker ETF: high volatility
    broker_returns = np.random.normal(0.001, 0.02, len(dates))
    broker_prices = 50 * np.exp(np.cumsum(broker_returns))

    data_dict = {
        '511010.SH': pd.DataFrame({'close': treasury_prices}, index=dates),
        '512880.SH': pd.DataFrame({'close': broker_prices}, index=dates)
    }

    # Test volatility calculation
    print("1. Volatility Calculation:")
    for symbol, df in data_dict.items():
        vol_std = calculate_volatility(df, method='std', window=60)
        vol_ewma = calculate_volatility(df, method='ewma', ewma_lambda=0.94)
        print(f"   {symbol}: STD={vol_std*100:.3f}%, EWMA={vol_ewma*100:.3f}%")

    # Test position sizing
    print("\n2. Position Sizing (1M capital, 0.5% target risk):")
    total_capital = 1_000_000
    for symbol, df in data_dict.items():
        vol = calculate_volatility(df, method='ewma')
        capital, weight = calculate_position_size(vol, total_capital, 0.005, 0.2)
        print(f"   {symbol}: Capital={capital:,.0f} CNY ({weight*100:.1f}%)")

    # Test portfolio construction
    print("\n3. Portfolio Construction:")
    cluster_map = {'511010.SH': 0, '512880.SH': 1}  # Different clusters

    positions = calculate_portfolio_positions(
        data_dict,
        list(data_dict.keys()),
        total_capital,
        target_risk_pct=0.005,
        max_position_pct=0.2,
        max_cluster_pct=0.3,
        cluster_assignments=cluster_map,
        volatility_method='ewma'
    )

    summary = get_position_summary(positions, total_capital)
    print(summary.to_string(index=False))

    # Test constraint validation
    print("\n4. Constraint Validation:")
    is_valid, errors = validate_portfolio_constraints(
        positions, 0.2, 0.3, 1.0, cluster_map
    )
    print(f"   Valid: {is_valid}")
    if errors:
        for error in errors:
            print(f"   - {error}")

    # Test rebalancing
    print("\n5. Rebalancing (from 50% current to full target):")
    current = {symbol: pos['target_capital'] * 0.5 for symbol, pos in positions.items()}
    target = {symbol: pos['target_capital'] for symbol, pos in positions.items()}
    prices = {symbol: df['close'].iloc[-1] for symbol, df in data_dict.items()}

    trades = calculate_rebalance_trades(current, target, prices, min_trade_amount=1000)
    for symbol, trade in trades.items():
        print(f"   {symbol}: {trade['action'].upper()} {trade['shares']:,} shares "
              f"({trade['amount']:,.0f} CNY)")

    print("\n=== Test Complete ===")
