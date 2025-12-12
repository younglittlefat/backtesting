# Clustering Module Usage Guide

## Overview

The `clustering.py` module implements hierarchical clustering for ETF trend following systems to prevent homogeneous position concentration. It uses correlation-based distance metrics and intra-cluster competition rules.

## Quick Start

### Basic Usage

```python
from clustering import get_cluster_assignments, filter_by_cluster_limit

# Load your OHLCV data
data_dict = {
    '159915.SZ': df1,  # DataFrame with 'close' column
    '159949.SZ': df2,
    '512690.SH': df3,
    # ... more ETFs
}

# Step 1: Get cluster assignments
cluster_assignments, corr_matrix = get_cluster_assignments(
    data_dict,
    lookback_days=120,           # 6 months
    correlation_threshold=0.5,   # Cluster ETFs with >0.5 correlation
    method='ward'                # Hierarchical clustering method
)

print(f"Formed {len(set(cluster_assignments.values()))} clusters")
# Output: Formed 15 clusters

# Step 2: Apply cluster limits when buying
current_holdings = {
    '159915.SZ': 0,  # cluster_id
    '159949.SZ': 0
}

buy_candidates = ['512690.SH', '159845.SZ', ...]

# Calculate risk-adjusted momentum scores
from clustering import calculate_risk_adjusted_momentum
scores = calculate_risk_adjusted_momentum(
    data_dict,
    buy_candidates + list(current_holdings.keys()),
    lookback_days=60
)

# Filter by cluster limit (max 2 per cluster)
approved_buys = filter_by_cluster_limit(
    candidates=buy_candidates,
    cluster_assignments=cluster_assignments,
    current_holdings=current_holdings,
    max_per_cluster=2,
    scores=scores  # Enable smart replacement
)

print(f"Approved {len(approved_buys)} out of {len(buy_candidates)} candidates")
```

## Core Functions

### 1. Clustering Pipeline

#### `get_cluster_assignments()`

One-stop function to perform complete clustering analysis.

```python
cluster_assignments, corr_matrix = get_cluster_assignments(
    data_dict,
    lookback_days=120,           # Correlation window
    correlation_threshold=0.5,   # Cluster threshold
    method='ward',               # Linkage method
    price_col='close'            # Price column name
)
```

**Returns:**
- `cluster_assignments`: `{symbol: cluster_id}` mapping
- `corr_matrix`: Correlation matrix (DataFrame) for analysis

**Correlation Threshold Examples:**
- `0.3`: Loose clustering (more clusters)
- `0.5`: Moderate clustering (recommended)
- `0.7`: Tight clustering (fewer clusters, stricter grouping)

### 2. Individual Steps (Advanced)

If you need more control, use individual functions:

```python
from clustering import (
    calculate_correlation_matrix,
    calculate_distance_matrix,
    perform_clustering
)

# Step 1: Calculate correlation
corr_matrix = calculate_correlation_matrix(data_dict, lookback_days=120)

# Step 2: Convert to distance
dist_matrix = calculate_distance_matrix(corr_matrix)

# Step 3: Perform clustering
cluster_assignments = perform_clustering(
    dist_matrix,
    correlation_threshold=0.5,
    method='ward'  # or 'average', 'complete', 'single'
)
```

### 3. Intra-Cluster Competition

#### `filter_by_cluster_limit()`

Apply cluster position limits with smart replacement logic.

```python
approved_buys = filter_by_cluster_limit(
    candidates=['512690.SH', '159845.SZ'],
    cluster_assignments=cluster_assignments,
    current_holdings={'159915.SZ': 0, '159949.SZ': 0},
    max_per_cluster=2,
    scores={'159915.SZ': 0.5, '159949.SZ': 1.5, '512690.SH': 1.2, '159845.SZ': 0.8}
)
```

**Logic:**
1. If cluster has space → approve new candidate
2. If cluster is full:
   - **With scores**: Replace weakest holding if new candidate is stronger
   - **Without scores**: Reject new candidate

### 4. Risk-Adjusted Momentum Scoring

#### `calculate_risk_adjusted_momentum()`

Score ETFs for ranking in intra-cluster competition.

```python
scores = calculate_risk_adjusted_momentum(
    data_dict,
    symbols=['159915.SZ', '159949.SZ', '512690.SH'],
    lookback_days=60,
    price_col='close'
)
# Returns: {'159915.SZ': 1.2, '159949.SZ': 0.8, '512690.SH': 1.5}
```

**Formula:** `Score = Annualized Return / Annualized Volatility`

Higher score = better risk-adjusted performance.

### 5. Monitoring & Reporting

#### `get_cluster_exposure()`

Monitor cluster diversification in current portfolio.

```python
from clustering import get_cluster_exposure

exposure = get_cluster_exposure(
    holdings=['159915.SZ', '159949.SZ', '512690.SH'],
    cluster_assignments=cluster_assignments,
    weights={'159915.SZ': 0.3, '159949.SZ': 0.3, '512690.SH': 0.4}
)

for cluster_id, info in exposure.items():
    print(f"Cluster {cluster_id}: {info['count']} positions, "
          f"{info['weight']:.1%} weight, symbols={info['symbols']}")
```

**Output:**
```
Cluster 0: 2 positions, 60.0% weight, symbols=['159915.SZ', '159949.SZ']
Cluster 1: 1 positions, 40.0% weight, symbols=['512690.SH']
```

#### `get_symbols_in_cluster()`

Get all ETFs in a specific cluster.

```python
from clustering import get_symbols_in_cluster

cluster_0_etfs = get_symbols_in_cluster(0, cluster_assignments)
print(f"Cluster 0 contains: {cluster_0_etfs}")
```

#### `validate_cluster_assignments()`

Validate that all symbols have cluster assignments.

```python
from clustering import validate_cluster_assignments

is_valid, missing = validate_cluster_assignments(cluster_assignments, data_dict)

if not is_valid:
    print(f"Warning: {len(missing)} symbols missing cluster assignment")
    print(f"Missing: {missing}")
```

## Complete Workflow Example

### Weekly Clustering Update (Recommended)

```python
import pandas as pd
from pathlib import Path
from clustering import (
    get_cluster_assignments,
    validate_cluster_assignments,
    get_cluster_exposure
)

# 1. Load ETF data
data_dir = Path("data/chinese_etf/daily")
etf_list = ['159915.SZ', '159949.SZ', '512690.SH', ...]  # Your ETF pool

data_dict = {}
for symbol in etf_list:
    df = pd.read_csv(data_dir / f"{symbol}.csv")
    df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('date')
    data_dict[symbol] = df

# 2. Perform clustering (weekly, e.g., every Friday)
cluster_assignments, corr_matrix = get_cluster_assignments(
    data_dict,
    lookback_days=120,
    correlation_threshold=0.5
)

# 3. Validate
is_valid, missing = validate_cluster_assignments(cluster_assignments, data_dict)
assert is_valid, f"Missing assignments: {missing}"

# 4. Save for use during the week
import json
with open('cluster_assignments.json', 'w') as f:
    json.dump(cluster_assignments, f, indent=2)

print(f"Clustering complete: {len(set(cluster_assignments.values()))} clusters")
```

### Daily Trade Signal Processing

```python
import json
from clustering import (
    filter_by_cluster_limit,
    calculate_risk_adjusted_momentum
)

# 1. Load cluster assignments (from weekly update)
with open('cluster_assignments.json', 'r') as f:
    cluster_assignments = json.load(f)

# 2. Current portfolio
current_holdings = {
    '159915.SZ': cluster_assignments['159915.SZ'],
    '159949.SZ': cluster_assignments['159949.SZ']
}

# 3. New buy signals from strategy
buy_signals = ['512690.SH', '159845.SZ', '512660.SH']

# 4. Calculate scores for all relevant symbols
all_symbols = list(current_holdings.keys()) + buy_signals
scores = calculate_risk_adjusted_momentum(
    data_dict,
    all_symbols,
    lookback_days=60
)

# 5. Filter by cluster limits
approved_buys = filter_by_cluster_limit(
    candidates=buy_signals,
    cluster_assignments=cluster_assignments,
    current_holdings=current_holdings,
    max_per_cluster=2,
    scores=scores
)

# 6. Execute approved trades
for symbol in approved_buys:
    print(f"BUY {symbol} (cluster {cluster_assignments[symbol]}, score {scores[symbol]:.3f})")
```

### Portfolio Monitoring

```python
from clustering import get_cluster_exposure

# Monitor cluster exposure
exposure = get_cluster_exposure(
    holdings=list(current_holdings.keys()),
    cluster_assignments=cluster_assignments,
    weights=None  # Equal weight
)

# Check if over-concentrated
for cluster_id, info in exposure.items():
    if info['count'] > 2:
        print(f"WARNING: Cluster {cluster_id} has {info['count']} positions (limit: 2)")
        print(f"  Symbols: {info['symbols']}")

# Diversification score
diversification = len(exposure) / len(current_holdings)
print(f"Diversification: {diversification:.1%} (higher is better)")
```

## Parameter Tuning Guide

### `lookback_days`

Controls correlation calculation window.

- **60 days**: Short-term clustering, responds quickly to regime changes
- **120 days** (recommended): Medium-term, balances stability and adaptability
- **252 days**: Long-term, very stable but may miss recent correlation changes

### `correlation_threshold`

Controls cluster tightness.

- **0.3**: Loose grouping (e.g., 30 clusters for 50 ETFs)
- **0.5** (recommended): Moderate grouping (e.g., 15-20 clusters)
- **0.7**: Tight grouping (e.g., 8-12 clusters)

**Rule of thumb:** Lower threshold → more clusters → stricter diversification

### `max_per_cluster`

Maximum positions per cluster.

- **1**: Maximum diversification, but may reject good opportunities
- **2** (recommended): Balanced approach from Gemini discussion
- **3**: More flexible, suitable for large portfolios (20+ positions)

### `method` (Linkage)

Hierarchical clustering method.

- **'ward'** (recommended): Minimizes within-cluster variance, most popular
- **'average'**: UPGMA, good for balanced clusters
- **'complete'**: Maximum linkage, sensitive to outliers
- **'single'**: Minimum linkage, can create uneven clusters

## Edge Cases & Handling

### Insufficient Data

```python
try:
    cluster_assignments, _ = get_cluster_assignments(data_dict, lookback_days=120)
except ValueError as e:
    print(f"Clustering failed: {e}")
    # Fallback: treat each ETF as separate cluster
    cluster_assignments = {symbol: i for i, symbol in enumerate(data_dict.keys())}
```

### Missing Symbols in Assignments

```python
is_valid, missing = validate_cluster_assignments(cluster_assignments, data_dict)

if not is_valid:
    # Assign missing symbols to new clusters
    max_cluster = max(cluster_assignments.values())
    for i, symbol in enumerate(missing, start=1):
        cluster_assignments[symbol] = max_cluster + i
```

### Zero/Low Volatility Symbols

Risk-adjusted momentum will return `-np.inf` for zero-volatility symbols. These will always be rejected in `filter_by_cluster_limit()`.

```python
scores = calculate_risk_adjusted_momentum(data_dict, symbols, lookback_days=60)

# Filter out invalid scores
valid_scores = {k: v for k, v in scores.items() if np.isfinite(v)}
```

## Performance Considerations

### Memory Usage

For N ETFs with M days:
- Correlation matrix: O(N²)
- Returns DataFrame: O(N × M)

**Recommendation:** For 100+ ETFs, use `lookback_days=120` (not 252) to reduce memory.

### Update Frequency

- **Weekly update** (recommended): Balances stability and computation cost
- **Daily update**: Unnecessary noise, clusters are relatively stable
- **Monthly update**: Too infrequent, may miss important correlation changes

### Caching

```python
import pickle
from datetime import datetime

# Cache cluster results
cache_file = f"clusters_{datetime.now().strftime('%Y%m%d')}.pkl"

if Path(cache_file).exists():
    with open(cache_file, 'rb') as f:
        cluster_assignments, corr_matrix = pickle.load(f)
else:
    cluster_assignments, corr_matrix = get_cluster_assignments(data_dict)
    with open(cache_file, 'wb') as f:
        pickle.dump((cluster_assignments, corr_matrix), f)
```

## Troubleshooting

### Issue: All ETFs in one cluster

**Cause:** Correlation threshold too high (e.g., 0.9) or highly correlated ETFs.

**Solution:** Lower `correlation_threshold` to 0.5 or 0.3.

### Issue: Each ETF in separate cluster

**Cause:** Correlation threshold too low (e.g., 0.1) or uncorrelated ETFs.

**Solution:** Increase `correlation_threshold` to 0.5 or review ETF selection.

### Issue: RuntimeWarning about empty slice

**Cause:** Single ETF or very small dataset.

**Solution:** This is expected for N=1, can be safely ignored.

## References

- **Design Discussion:** Based on Gemini conversation about correlation-based clustering
- **Formula:** Distance = sqrt(2 × (1 - Correlation))
- **Method:** Ward linkage hierarchical clustering (minimizes within-cluster variance)
- **Update Frequency:** Weekly (recommended by Gemini to avoid daily noise)
