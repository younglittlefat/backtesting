#!/usr/bin/env python3
"""
Example script demonstrating clustering module usage.

This script shows a complete workflow:
1. Load ETF data
2. Perform clustering
3. Calculate risk-adjusted momentum
4. Apply cluster limits to buy signals
5. Monitor cluster exposure
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from clustering import (
    get_cluster_assignments,
    calculate_risk_adjusted_momentum,
    filter_by_cluster_limit,
    get_cluster_exposure,
    validate_cluster_assignments,
    get_symbols_in_cluster
)


def load_sample_data(num_etfs=10, num_days=150):
    """
    Create synthetic ETF data for demonstration.

    In production, replace this with actual data loading from CSV files.
    """
    print(f"Generating {num_etfs} synthetic ETFs with {num_days} days of data...")

    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=num_days, freq='D')

    data_dict = {}

    # Create 3 groups with different correlations
    group_1_base = np.random.normal(0.001, 0.02, num_days)  # High correlation group
    group_2_base = np.random.normal(0.0005, 0.015, num_days)  # Medium correlation group
    group_3_base = np.random.normal(0.0008, 0.018, num_days)  # Low correlation group

    for i in range(num_etfs):
        # Assign to group
        if i < num_etfs // 3:
            base_returns = group_1_base + np.random.normal(0, 0.003, num_days)
        elif i < 2 * num_etfs // 3:
            base_returns = group_2_base + np.random.normal(0, 0.005, num_days)
        else:
            base_returns = group_3_base + np.random.normal(0, 0.008, num_days)

        # Create price series
        prices = 100 * np.cumprod(1 + base_returns)

        # Create OHLCV DataFrame
        df = pd.DataFrame({
            'open': prices * np.random.uniform(0.99, 1.00, num_days),
            'high': prices * np.random.uniform(1.00, 1.02, num_days),
            'low': prices * np.random.uniform(0.98, 0.99, num_days),
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, num_days)
        }, index=dates)

        data_dict[f'ETF_{i:03d}'] = df

    return data_dict


def main():
    print("=" * 70)
    print("Clustering Module - Example Usage")
    print("=" * 70)
    print()

    # Step 1: Load data
    print("Step 1: Loading ETF Data")
    print("-" * 70)

    data_dict = load_sample_data(num_etfs=15, num_days=150)

    print(f"Loaded {len(data_dict)} ETFs")
    print(f"Date range: {data_dict['ETF_000'].index[0]} to {data_dict['ETF_000'].index[-1]}")
    print()

    # Step 2: Perform clustering
    print("Step 2: Performing Hierarchical Clustering")
    print("-" * 70)

    cluster_assignments, corr_matrix = get_cluster_assignments(
        data_dict,
        lookback_days=120,
        correlation_threshold=0.5,
        method='ward'
    )

    num_clusters = len(set(cluster_assignments.values()))
    print(f"Formed {num_clusters} clusters from {len(data_dict)} ETFs")
    print()

    # Show cluster composition
    print("Cluster Composition:")
    for cluster_id in sorted(set(cluster_assignments.values())):
        symbols = get_symbols_in_cluster(cluster_id, cluster_assignments)
        print(f"  Cluster {cluster_id}: {len(symbols)} ETFs - {symbols}")
    print()

    # Validate
    is_valid, missing = validate_cluster_assignments(cluster_assignments, data_dict)
    if is_valid:
        print("✓ All symbols successfully assigned to clusters")
    else:
        print(f"✗ Warning: {len(missing)} symbols missing assignments")
    print()

    # Step 3: Calculate risk-adjusted momentum scores
    print("Step 3: Calculating Risk-Adjusted Momentum Scores")
    print("-" * 70)

    all_symbols = list(data_dict.keys())
    scores = calculate_risk_adjusted_momentum(
        data_dict,
        all_symbols,
        lookback_days=60
    )

    # Show top 5 and bottom 5
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    print("Top 5 ETFs by risk-adjusted momentum:")
    for symbol, score in sorted_scores[:5]:
        if np.isfinite(score):
            print(f"  {symbol}: {score:.3f}")

    print("\nBottom 5 ETFs by risk-adjusted momentum:")
    for symbol, score in sorted_scores[-5:]:
        if np.isfinite(score):
            print(f"  {symbol}: {score:.3f}")
        else:
            print(f"  {symbol}: invalid")
    print()

    # Step 4: Simulate portfolio construction with cluster limits
    print("Step 4: Simulating Portfolio Construction with Cluster Limits")
    print("-" * 70)

    # Current holdings (first 4 symbols)
    current_holdings = {
        sym: cluster_assignments[sym]
        for sym in list(data_dict.keys())[:4]
    }

    print(f"Current holdings: {list(current_holdings.keys())}")
    for sym, cid in current_holdings.items():
        print(f"  {sym} -> Cluster {cid}")
    print()

    # New buy signals (next 6 symbols)
    buy_candidates = list(data_dict.keys())[4:10]
    print(f"Buy candidates: {buy_candidates}")
    for sym in buy_candidates:
        print(f"  {sym} -> Cluster {cluster_assignments[sym]}, Score: {scores[sym]:.3f}")
    print()

    # Apply cluster limit filter
    max_per_cluster = 2
    approved_buys = filter_by_cluster_limit(
        candidates=buy_candidates,
        cluster_assignments=cluster_assignments,
        current_holdings=current_holdings,
        max_per_cluster=max_per_cluster,
        scores=scores
    )

    print(f"Approved buys (max {max_per_cluster} per cluster): {approved_buys}")
    print(f"  Approved: {len(approved_buys)} / {len(buy_candidates)}")
    print()

    # Step 5: Monitor cluster exposure
    print("Step 5: Monitoring Cluster Exposure")
    print("-" * 70)

    # Simulated portfolio after buys
    final_holdings = list(current_holdings.keys()) + approved_buys

    exposure = get_cluster_exposure(
        holdings=final_holdings,
        cluster_assignments=cluster_assignments,
        weights=None  # Equal weight
    )

    print(f"Final portfolio: {len(final_holdings)} positions across {len(exposure)} clusters")
    print()

    for cluster_id in sorted(exposure.keys()):
        info = exposure[cluster_id]
        print(f"Cluster {cluster_id}:")
        print(f"  Positions: {info['count']}/{max_per_cluster}")
        print(f"  Weight: {info['weight']:.1%}")
        print(f"  Symbols: {info['symbols']}")

        # Check if over-limit (shouldn't happen)
        if info['count'] > max_per_cluster:
            print(f"  ⚠️  WARNING: Exceeds limit!")
    print()

    # Step 6: Save results
    print("Step 6: Saving Results")
    print("-" * 70)

    output_dir = Path(__file__).parent.parent / 'output'
    output_dir.mkdir(exist_ok=True)

    # Save cluster assignments
    cluster_file = output_dir / 'cluster_assignments.json'
    with open(cluster_file, 'w') as f:
        json.dump(cluster_assignments, f, indent=2)
    print(f"✓ Saved cluster assignments to {cluster_file}")

    # Save correlation matrix
    corr_file = output_dir / 'correlation_matrix.csv'
    corr_matrix.to_csv(corr_file)
    print(f"✓ Saved correlation matrix to {corr_file}")

    # Save scores
    scores_file = output_dir / 'momentum_scores.json'
    # Filter out -inf values for cleaner JSON
    valid_scores = {k: v for k, v in scores.items() if np.isfinite(v)}
    with open(scores_file, 'w') as f:
        json.dump(valid_scores, f, indent=2)
    print(f"✓ Saved momentum scores to {scores_file}")

    print()
    print("=" * 70)
    print("Example completed successfully!")
    print("=" * 70)


if __name__ == '__main__':
    main()
