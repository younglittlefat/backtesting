"""
Clustering module for ETF trend following system.

This module implements hierarchical clustering to prevent homogeneous position concentration.
It uses correlation-based distance metrics and intra-cluster competition rules.

Core Design (from Gemini discussion):
1. Correlation Matrix: Calculate pairwise correlations using past 120 days of returns
2. Distance Matrix: Distance = sqrt(2 * (1 - Correlation))
3. Hierarchical Clustering: Use Ward linkage to merge similar ETFs
4. Dendrogram Cutting: Set threshold (e.g., correlation > 0.5 → distance < 1.0)
5. Intra-Cluster Competition: Max 2 positions per cluster, select by risk-adjusted momentum

Update Frequency: Recommended weekly (e.g., Friday close) to avoid daily noise
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


def calculate_returns(
    data_dict: Dict[str, pd.DataFrame],
    lookback_days: int = 120,
    price_col: str = 'close'
) -> pd.DataFrame:
    """
    Calculate daily returns for all ETFs.

    Args:
        data_dict: {symbol: DataFrame} with OHLCV data
        lookback_days: Number of days to look back for correlation calculation
        price_col: Column name for price data (default: 'close')

    Returns:
        DataFrame with symbols as columns and returns as values
        Index: datetime, aligned across all ETFs

    Notes:
        - Only includes the most recent lookback_days
        - Handles missing data by forward-filling then dropping NaNs
    """
    returns_dict = {}

    for symbol, df in data_dict.items():
        if df.empty or price_col not in df.columns:
            logger.warning(f"Skipping {symbol}: missing {price_col} column")
            continue

        # Take most recent lookback_days
        df_recent = df.tail(lookback_days + 1)  # +1 for pct_change

        if len(df_recent) < 2:
            logger.warning(f"Skipping {symbol}: insufficient data (<2 bars)")
            continue

        # Calculate returns (fill_method=None to avoid FutureWarning)
        returns = df_recent[price_col].pct_change(fill_method=None).dropna()

        if len(returns) < lookback_days * 0.5:  # At least 50% data
            logger.warning(f"Skipping {symbol}: too many gaps ({len(returns)}/{lookback_days})")
            continue

        returns_dict[symbol] = returns

    if not returns_dict:
        raise ValueError("No valid returns data available for clustering")

    # Combine into DataFrame with aligned dates
    returns_df = pd.DataFrame(returns_dict)

    # Forward-fill missing values (max 5 days) - use ffill() for pandas 3.0 compatibility
    returns_df = returns_df.ffill(limit=5)

    # Drop rows with any remaining NaNs
    returns_df = returns_df.dropna()

    if returns_df.empty:
        raise ValueError("No overlapping date ranges found across ETFs")

    logger.info(
        f"Calculated returns for {len(returns_df.columns)} ETFs "
        f"over {len(returns_df)} days"
    )

    return returns_df


def calculate_correlation_matrix(
    data_dict: Dict[str, pd.DataFrame],
    lookback_days: int = 120,
    price_col: str = 'close'
) -> pd.DataFrame:
    """
    Calculate pairwise correlation matrix for all ETFs.

    Args:
        data_dict: {symbol: DataFrame} with OHLCV data
        lookback_days: Number of days to look back (default: 120 ≈ 6 months)
        price_col: Column name for price data (default: 'close')

    Returns:
        Correlation matrix (DataFrame) with symbols as both index and columns

    Example:
        >>> corr_matrix = calculate_correlation_matrix(data_dict, lookback_days=120)
        >>> print(corr_matrix.loc['159915.SZ', '159949.SZ'])
        0.85
    """
    returns_df = calculate_returns(data_dict, lookback_days, price_col)

    # Calculate correlation matrix
    corr_matrix = returns_df.corr(method='pearson')

    # Ensure diagonal is exactly 1.0 (for numerical stability)
    np.fill_diagonal(corr_matrix.values, 1.0)

    # Check for invalid values
    if corr_matrix.isnull().any().any():
        logger.warning("Correlation matrix contains NaNs - filling with 0")
        corr_matrix = corr_matrix.fillna(0)

    logger.info(f"Correlation matrix shape: {corr_matrix.shape}")
    logger.info(f"Mean correlation: {corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean():.3f}")

    return corr_matrix


def calculate_distance_matrix(corr_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Convert correlation matrix to distance matrix.

    Formula: d = sqrt(2 * (1 - rho))
    - rho = 1 (perfect correlation) → d = 0
    - rho = 0 (no correlation) → d = sqrt(2) ≈ 1.414
    - rho = -1 (perfect anti-correlation) → d = 2

    Args:
        corr_matrix: Correlation matrix (N x N DataFrame)

    Returns:
        Distance matrix (N x N DataFrame) with same index/columns as input

    Example:
        >>> dist_matrix = calculate_distance_matrix(corr_matrix)
        >>> print(dist_matrix.loc['159915.SZ', '159949.SZ'])
        0.547  # if correlation was 0.85
    """
    # Clip correlations to [-1, 1] to avoid sqrt of negative numbers
    corr_clipped = corr_matrix.clip(-1.0, 1.0)

    # Calculate distance: d = sqrt(2 * (1 - rho))
    distance_matrix = np.sqrt(2 * (1 - corr_clipped))

    # Ensure diagonal is exactly 0.0
    np.fill_diagonal(distance_matrix.values, 0.0)

    logger.info(f"Distance matrix stats: min={distance_matrix.values.min():.3f}, "
                f"max={distance_matrix.values.max():.3f}, "
                f"mean={distance_matrix.values[np.triu_indices_from(distance_matrix.values, k=1)].mean():.3f}")

    return distance_matrix


def perform_clustering(
    distance_matrix: pd.DataFrame,
    correlation_threshold: float = 0.5,
    method: str = 'ward'
) -> Dict[str, int]:
    """
    Perform hierarchical clustering on ETFs.

    Args:
        distance_matrix: Distance matrix (N x N DataFrame)
        correlation_threshold: Correlation threshold for cluster cutting (default: 0.5)
            - 0.5 → distance threshold = sqrt(2 * (1 - 0.5)) = 1.0
            - 0.7 → distance threshold ≈ 0.77
        method: Linkage method (default: 'ward')
            - 'ward': Minimizes within-cluster variance (recommended)
            - 'average': UPGMA, average linkage
            - 'complete': Maximum linkage
            - 'single': Minimum linkage

    Returns:
        Dictionary mapping symbol to cluster_id: {symbol: cluster_id}

    Example:
        >>> clusters = perform_clustering(dist_matrix, correlation_threshold=0.7)
        >>> print(clusters)
        {'159915.SZ': 0, '159949.SZ': 0, '512690.SH': 1, ...}
    """
    symbols = distance_matrix.index.tolist()
    n = len(symbols)

    if n < 2:
        logger.warning("Less than 2 symbols - all assigned to cluster 0")
        return {sym: 0 for sym in symbols}

    # Convert distance matrix to condensed form (upper triangle, row-wise)
    # scipy requires condensed distance vector for linkage
    condensed_dist = squareform(distance_matrix.values, checks=False)

    # Perform hierarchical clustering
    try:
        linkage_matrix = linkage(condensed_dist, method=method)
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        raise ValueError(f"Hierarchical clustering failed: {e}")

    # Convert correlation threshold to distance threshold
    # d = sqrt(2 * (1 - rho))
    distance_threshold = np.sqrt(2 * (1 - correlation_threshold))

    logger.info(f"Using {method} linkage with correlation threshold {correlation_threshold:.2f} "
                f"(distance threshold {distance_threshold:.3f})")

    # Cut dendrogram at distance threshold
    cluster_labels = fcluster(linkage_matrix, t=distance_threshold, criterion='distance')

    # Create symbol -> cluster_id mapping
    cluster_assignments = {
        symbol: int(cluster_id - 1)  # fcluster uses 1-based indexing
        for symbol, cluster_id in zip(symbols, cluster_labels)
    }

    # Log cluster statistics
    unique_clusters = set(cluster_assignments.values())
    cluster_sizes = {}
    for cluster_id in unique_clusters:
        cluster_sizes[cluster_id] = sum(1 for c in cluster_assignments.values() if c == cluster_id)

    logger.info(f"Formed {len(unique_clusters)} clusters from {n} ETFs")
    logger.info(f"Cluster sizes: {sorted(cluster_sizes.values(), reverse=True)[:10]}")  # Top 10

    return cluster_assignments


def get_cluster_assignments(
    data_dict: Dict[str, pd.DataFrame],
    lookback_days: int = 120,
    correlation_threshold: float = 0.5,
    method: str = 'ward',
    price_col: str = 'close'
) -> Tuple[Dict[str, int], pd.DataFrame]:
    """
    One-stop function to get cluster assignments from raw data.

    This is the main entry point for clustering - it combines all steps:
    1. Calculate returns
    2. Calculate correlation matrix
    3. Convert to distance matrix
    4. Perform hierarchical clustering

    Args:
        data_dict: {symbol: DataFrame} with OHLCV data
        lookback_days: Number of days for correlation calculation (default: 120)
        correlation_threshold: Correlation threshold for cutting (default: 0.5)
        method: Linkage method (default: 'ward')
        price_col: Price column name (default: 'close')

    Returns:
        Tuple of (cluster_assignments, correlation_matrix)
        - cluster_assignments: {symbol: cluster_id}
        - correlation_matrix: DataFrame for further analysis

    Example:
        >>> clusters, corr = get_cluster_assignments(data_dict, lookback_days=120)
        >>> print(f"ETF 159915.SZ is in cluster {clusters['159915.SZ']}")
    """
    logger.info("Starting clustering pipeline...")

    # Step 1 & 2: Calculate correlation matrix
    corr_matrix = calculate_correlation_matrix(data_dict, lookback_days, price_col)

    # Step 3: Convert to distance matrix
    dist_matrix = calculate_distance_matrix(corr_matrix)

    # Step 4: Perform clustering
    cluster_assignments = perform_clustering(dist_matrix, correlation_threshold, method)

    logger.info("Clustering pipeline completed")

    return cluster_assignments, corr_matrix


def calculate_risk_adjusted_momentum(
    data_dict: Dict[str, pd.DataFrame],
    symbols: List[str],
    lookback_days: int = 60,
    price_col: str = 'close'
) -> Dict[str, float]:
    """
    Calculate risk-adjusted momentum score for symbol ranking.

    Score = Annualized Return / Annualized Volatility

    This is used for intra-cluster competition: when multiple ETFs in the same
    cluster send buy signals, we select the ones with highest scores.

    Args:
        data_dict: {symbol: DataFrame} with OHLCV data
        symbols: List of symbols to calculate scores for
        lookback_days: Number of days for momentum calculation (default: 60)
        price_col: Price column name (default: 'close')

    Returns:
        Dictionary {symbol: score}
        - Higher score = better risk-adjusted momentum
        - NaN/invalid scores are set to -np.inf

    Example:
        >>> scores = calculate_risk_adjusted_momentum(data_dict, ['159915.SZ', '159949.SZ'])
        >>> print(f"Best ETF: {max(scores, key=scores.get)}")
    """
    scores = {}

    for symbol in symbols:
        if symbol not in data_dict:
            logger.warning(f"Symbol {symbol} not in data_dict - score = -inf")
            scores[symbol] = -np.inf
            continue

        df = data_dict[symbol]

        if df.empty or price_col not in df.columns:
            logger.warning(f"Symbol {symbol} missing {price_col} - score = -inf")
            scores[symbol] = -np.inf
            continue

        # Get recent data
        df_recent = df.tail(lookback_days + 1)

        if len(df_recent) < lookback_days * 0.5:  # At least 50% data
            logger.warning(f"Symbol {symbol} insufficient data - score = -inf")
            scores[symbol] = -np.inf
            continue

        # Calculate returns (fill_method=None to avoid FutureWarning)
        returns = df_recent[price_col].pct_change(fill_method=None).dropna()

        if len(returns) < 2:
            scores[symbol] = -np.inf
            continue

        # Annualize (assuming 252 trading days per year)
        mean_return = returns.mean() * 252
        volatility = returns.std() * np.sqrt(252)

        if volatility < 1e-6:  # Avoid division by zero
            logger.warning(f"Symbol {symbol} zero volatility - score = -inf")
            scores[symbol] = -np.inf
            continue

        # Risk-adjusted momentum
        score = mean_return / volatility

        # Handle invalid values
        if not np.isfinite(score):
            scores[symbol] = -np.inf
        else:
            scores[symbol] = score

    logger.info(f"Calculated scores for {len([s for s in scores.values() if np.isfinite(s)])} symbols")

    return scores


def filter_by_cluster_limit(
    candidates: List[str],
    cluster_assignments: Dict[str, int],
    current_holdings: Dict[str, int],
    max_per_cluster: int = 2,
    scores: Optional[Dict[str, float]] = None
) -> List[str]:
    """
    Filter candidate buy signals by cluster position limits.

    Intra-cluster competition rules:
    1. Each cluster can hold at most max_per_cluster positions (default: 2)
    2. If a cluster is full and a new candidate arrives:
       - If scores provided: replace the weakest holding if new candidate is stronger
       - If scores not provided: reject the new candidate
    3. Candidates without cluster assignment are rejected (data quality issue)

    Args:
        candidates: List of symbols with buy signals
        cluster_assignments: {symbol: cluster_id} mapping
        current_holdings: {symbol: cluster_id} of current positions
        max_per_cluster: Max positions per cluster (default: 2)
        scores: Optional {symbol: score} for ranking (higher = better)
            If not provided, new candidates won't replace existing holdings

    Returns:
        Filtered list of symbols to buy (subset of candidates)

    Example:
        >>> # Cluster 0 has 2 holdings, cluster 1 has 1
        >>> current = {'159915.SZ': 0, '159949.SZ': 0, '512690.SH': 1}
        >>> candidates = ['159845.SZ', '512660.SH']  # Both in cluster 0
        >>> clusters = {'159845.SZ': 0, '512660.SH': 0, ...}
        >>> scores = {'159845.SZ': 1.5, '512660.SH': 1.2, '159915.SZ': 0.8, ...}
        >>> # Result: ['159845.SZ'] - replaces weakest holding 159915.SZ
        >>> filtered = filter_by_cluster_limit(candidates, clusters, current, 2, scores)
    """
    # Count current cluster occupancy
    cluster_counts = {}
    cluster_holdings = {}  # {cluster_id: [symbols]}

    for symbol, cluster_id in current_holdings.items():
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
        if cluster_id not in cluster_holdings:
            cluster_holdings[cluster_id] = []
        cluster_holdings[cluster_id].append(symbol)

    approved_buys = []
    replacements = []  # Track what we're replacing

    for candidate in candidates:
        # Check if candidate has cluster assignment
        if candidate not in cluster_assignments:
            logger.warning(f"Candidate {candidate} not in cluster assignments - rejected")
            continue

        candidate_cluster = cluster_assignments[candidate]
        current_count = cluster_counts.get(candidate_cluster, 0)

        # Case 1: Cluster has space
        if current_count < max_per_cluster:
            approved_buys.append(candidate)
            cluster_counts[candidate_cluster] = current_count + 1
            if candidate_cluster not in cluster_holdings:
                cluster_holdings[candidate_cluster] = []
            cluster_holdings[candidate_cluster].append(candidate)
            logger.debug(f"Approved {candidate} for cluster {candidate_cluster} ({current_count + 1}/{max_per_cluster})")
            continue

        # Case 2: Cluster is full
        if scores is None:
            logger.info(f"Rejected {candidate}: cluster {candidate_cluster} is full ({current_count}/{max_per_cluster}), no scores for replacement")
            continue

        # Check if candidate can replace weakest holding
        holdings_in_cluster = cluster_holdings.get(candidate_cluster, [])

        if not holdings_in_cluster:
            # Should not happen, but handle gracefully
            logger.warning(f"Cluster {candidate_cluster} count={current_count} but no holdings found")
            continue

        # Find weakest holding in this cluster
        weakest_symbol = None
        weakest_score = np.inf

        for holding in holdings_in_cluster:
            if holding in scores:
                if scores[holding] < weakest_score:
                    weakest_score = scores[holding]
                    weakest_symbol = holding

        # Get candidate score
        candidate_score = scores.get(candidate, -np.inf)

        # Replace if candidate is stronger
        if weakest_symbol and candidate_score > weakest_score:
            approved_buys.append(candidate)
            replacements.append((candidate, weakest_symbol, candidate_score, weakest_score))
            logger.info(
                f"Approved {candidate} (score={candidate_score:.3f}) "
                f"to replace {weakest_symbol} (score={weakest_score:.3f}) "
                f"in cluster {candidate_cluster}"
            )
            # Update internal tracking (for subsequent candidates in same loop)
            cluster_holdings[candidate_cluster].remove(weakest_symbol)
            cluster_holdings[candidate_cluster].append(candidate)
        else:
            logger.info(
                f"Rejected {candidate} (score={candidate_score:.3f}): "
                f"weaker than weakest holding in cluster {candidate_cluster} "
                f"(score={weakest_score:.3f})"
            )

    logger.info(f"Cluster filtering: {len(candidates)} candidates → {len(approved_buys)} approved ({len(replacements)} replacements)")

    return approved_buys


def get_cluster_exposure(
    holdings: List[str],
    cluster_assignments: Dict[str, int],
    weights: Optional[Dict[str, float]] = None
) -> Dict[int, dict]:
    """
    Calculate current portfolio's cluster exposure.

    This is useful for monitoring and reporting cluster diversification.

    Args:
        holdings: List of currently held symbols
        cluster_assignments: {symbol: cluster_id} mapping
        weights: Optional {symbol: weight} for weighted exposure
            If None, assumes equal weight

    Returns:
        Dictionary {cluster_id: {'count': n, 'weight': w, 'symbols': [...]}}
        - count: Number of positions in this cluster
        - weight: Total weight in this cluster (sum of position weights)
        - symbols: List of symbols in this cluster

    Example:
        >>> holdings = ['159915.SZ', '159949.SZ', '512690.SH']
        >>> weights = {'159915.SZ': 0.3, '159949.SZ': 0.3, '512690.SH': 0.4}
        >>> exposure = get_cluster_exposure(holdings, clusters, weights)
        >>> print(exposure)
        {0: {'count': 2, 'weight': 0.6, 'symbols': ['159915.SZ', '159949.SZ']},
         1: {'count': 1, 'weight': 0.4, 'symbols': ['512690.SH']}}
    """
    if weights is None:
        # Equal weight
        equal_weight = 1.0 / len(holdings) if holdings else 0.0
        weights = {symbol: equal_weight for symbol in holdings}

    cluster_exposure = {}

    for symbol in holdings:
        if symbol not in cluster_assignments:
            logger.warning(f"Holding {symbol} not in cluster assignments - skipped")
            continue

        cluster_id = cluster_assignments[symbol]
        weight = weights.get(symbol, 0.0)

        if cluster_id not in cluster_exposure:
            cluster_exposure[cluster_id] = {
                'count': 0,
                'weight': 0.0,
                'symbols': []
            }

        cluster_exposure[cluster_id]['count'] += 1
        cluster_exposure[cluster_id]['weight'] += weight
        cluster_exposure[cluster_id]['symbols'].append(symbol)

    # Log summary
    logger.info(f"Cluster exposure: {len(cluster_exposure)} clusters across {len(holdings)} holdings")
    for cluster_id in sorted(cluster_exposure.keys()):
        info = cluster_exposure[cluster_id]
        logger.debug(
            f"  Cluster {cluster_id}: {info['count']} positions, "
            f"{info['weight']:.1%} weight, symbols={info['symbols']}"
        )

    return cluster_exposure


def get_symbols_in_cluster(
    cluster_id: int,
    cluster_assignments: Dict[str, int]
) -> List[str]:
    """
    Get all symbols belonging to a specific cluster.

    Args:
        cluster_id: Target cluster ID
        cluster_assignments: {symbol: cluster_id} mapping

    Returns:
        List of symbols in the cluster

    Example:
        >>> symbols = get_symbols_in_cluster(0, cluster_assignments)
        >>> print(f"Cluster 0 contains {len(symbols)} ETFs: {symbols[:5]}")
    """
    return [
        symbol for symbol, cid in cluster_assignments.items()
        if cid == cluster_id
    ]


def validate_cluster_assignments(
    cluster_assignments: Dict[str, int],
    data_dict: Dict[str, pd.DataFrame]
) -> Tuple[bool, List[str]]:
    """
    Validate that all symbols in data_dict have cluster assignments.

    Args:
        cluster_assignments: {symbol: cluster_id} mapping
        data_dict: {symbol: DataFrame} original data

    Returns:
        Tuple of (is_valid, missing_symbols)
        - is_valid: True if all symbols are assigned
        - missing_symbols: List of symbols without assignments

    Example:
        >>> is_valid, missing = validate_cluster_assignments(clusters, data_dict)
        >>> if not is_valid:
        >>>     print(f"Warning: {len(missing)} symbols missing cluster assignment")
    """
    all_symbols = set(data_dict.keys())
    assigned_symbols = set(cluster_assignments.keys())

    missing_symbols = list(all_symbols - assigned_symbols)

    is_valid = len(missing_symbols) == 0

    if not is_valid:
        logger.warning(
            f"Cluster validation failed: {len(missing_symbols)} symbols "
            f"missing assignments out of {len(all_symbols)}"
        )
        logger.debug(f"Missing symbols: {missing_symbols[:10]}")  # Show first 10
    else:
        logger.info(f"Cluster validation passed: all {len(all_symbols)} symbols assigned")

    return is_valid, missing_symbols
