# Scoring Module Documentation

## Overview

The `scoring.py` module implements multi-period volatility-weighted momentum scoring for ETF trend following strategies. It provides functionality for:

- **Momentum Score Calculation**: Multi-period returns normalized by volatility
- **Hysteresis Mechanism**: Buffer zones to reduce trading frequency (buy top N, hold until rank M)
- **Score Inertia**: Bonus for existing holdings to prevent unnecessary turnover
- **Historical Score Tracking**: Rolling calculation for backtesting without look-ahead bias

## Key Concepts

### 1. Multi-Period Volatility-Weighted Momentum

The scoring system uses multiple lookback periods to capture different momentum time scales:

```
Score = Σ(weight_i × return_i / volatility_i)
```

**Default Configuration**:
- **Periods**: [20, 60, 120] days (roughly 1 month, 3 months, 6 months)
- **Weights**: [0.4, 0.3, 0.3] (higher weight on recent momentum)
- **Volatility**: Annualized (252 trading days) for consistent scaling

**Why Volatility Weighting?**
- Ensures risk-adjusted comparison across ETFs
- Prevents high-volatility ETFs from dominating rankings
- Provides "unit risk return" comparability

### 2. Hysteresis (Buffer Zone) Mechanism

Hysteresis prevents excessive turnover by creating different thresholds for entry and exit:

```
Buy Threshold:  Rank ≤ buy_top_n (e.g., Top 10)
Hold Threshold: Rank ≤ hold_until_rank (e.g., Top 15)
Sell Trigger:   Rank > hold_until_rank or stop loss
```

**Example**:
- `buy_top_n = 10`: Buy ETFs ranked 1-10
- `hold_until_rank = 15`: Continue holding as long as rank ≤ 15
- An ETF ranked 12 is NOT bought but IS held if already in portfolio

### 3. Score Inertia Bonus

Provides a small boost to existing holdings to account for transaction costs:

```
Final_Score = Raw_Score × (1 + inertia_bonus)  # for holdings
Final_Score = Raw_Score                         # for non-holdings
```

**Default**: 10% multiplicative bonus (configurable)

**Purpose**:
- Reduce churn from minor ranking fluctuations
- Implicitly account for round-trip transaction costs
- Improve tax efficiency (for taxable accounts)

## API Reference

### Core Functions

#### `calculate_momentum_score()`

Calculate momentum score for a single ETF.

```python
score = calculate_momentum_score(
    df=etf_dataframe,            # DataFrame with datetime index and 'close' column
    as_of_date='2023-12-31',     # Reference date (uses latest if None)
    periods=[20, 60, 120],       # Lookback periods in days
    weights=[0.4, 0.3, 0.3],     # Period weights (must sum to 1.0)
    min_periods_required=20      # Minimum data required (defaults to min(periods))
)
```

**Returns**: Float score or `np.nan` if insufficient data

#### `calculate_universe_scores()`

Calculate scores for all ETFs in a universe.

```python
scores_df = calculate_universe_scores(
    data_dict={'ETF1': df1, 'ETF2': df2, ...},
    as_of_date='2023-12-31',
    periods=[20, 60, 120],
    weights=[0.4, 0.3, 0.3]
)
```

**Returns**: DataFrame with columns `[symbol, raw_score, rank]`, sorted by rank

#### `apply_inertia_bonus()`

Apply inertia bonus to existing holdings.

```python
adjusted_scores = apply_inertia_bonus(
    scores_df=scores_df,              # Output from calculate_universe_scores()
    current_holdings=['ETF1', 'ETF3'], # List of currently held symbols
    bonus_pct=0.1,                    # 10% bonus
    bonus_mode='multiplicative'       # or 'additive'
)
```

**Returns**: DataFrame with additional columns `[has_inertia, adjusted_score, adjusted_rank]`

#### `get_trading_signals()`

Generate buy/hold/sell signals using hysteresis mechanism.

```python
signals = get_trading_signals(
    scores_df=adjusted_scores,        # Can use raw or adjusted scores
    current_holdings=['ETF1', 'ETF3'],
    buy_top_n=10,                     # Buy top 10
    hold_until_rank=15,               # Hold until rank drops below 15
    stop_loss_symbols=['ETF3'],       # Force sell (e.g., stop loss triggered)
    use_adjusted_rank=True            # Use adjusted_rank if available
)
```

**Returns**: Dictionary with:
```python
{
    'to_buy': ['ETF5', 'ETF7'],       # New positions to open
    'to_hold': ['ETF1'],              # Existing positions to keep
    'to_sell': ['ETF3'],              # Positions to close
    'final_holdings': ['ETF1', 'ETF5', 'ETF7'],  # Resulting portfolio
    'metadata': {
        'buy_reasons': {'ETF5': 'new_entry_rank_2', ...},
        'sell_reasons': {'ETF3': 'stop_loss', ...},
        'rank_column_used': 'adjusted_rank'
    }
}
```

#### `calculate_historical_scores()`

Calculate rolling scores for backtesting (avoids look-ahead bias).

```python
historical_scores = calculate_historical_scores(
    data_dict={'ETF1': df1, 'ETF2': df2, ...},
    start_date='2023-01-01',
    end_date='2023-12-31',
    periods=[20, 60, 120],
    weights=[0.4, 0.3, 0.3],
    frequency='daily'  # or 'weekly'
)
```

**Returns**: DataFrame with MultiIndex `(date, symbol)` and columns `[raw_score, rank]`

#### `get_scores_for_date()`

Extract scores for a specific date from historical scores.

```python
date_scores = get_scores_for_date(
    historical_scores=historical_scores,
    date='2023-06-15'
)
```

**Returns**: DataFrame with columns `[symbol, raw_score, rank]` for that date

### Utility Functions

#### `validate_scoring_params()`

Validate parameter consistency before running backtest.

```python
is_valid, error_msg = validate_scoring_params(
    periods=[20, 60, 120],
    weights=[0.4, 0.3, 0.3],
    buy_top_n=10,
    hold_until_rank=15
)
```

## Usage Examples

### Example 1: Daily Signal Generation (Live Trading)

```python
from etf_trend_following_v2.src import data_loader, scoring

# 1. Load universe
data_dict = data_loader.load_universe_from_file(
    pool_file='results/trend_etf_pool.csv',
    data_dir='data/chinese_etf/daily',
    end_date='2023-12-31'
)

# 2. Calculate scores
scores_df = scoring.calculate_universe_scores(
    data_dict=data_dict,
    as_of_date='2023-12-31'
)

# 3. Apply inertia bonus
current_holdings = ['159915.SZ', '510300.SH', '512690.SH']
adjusted_scores = scoring.apply_inertia_bonus(
    scores_df=scores_df,
    current_holdings=current_holdings,
    bonus_pct=0.1
)

# 4. Generate trading signals
signals = scoring.get_trading_signals(
    scores_df=adjusted_scores,
    current_holdings=current_holdings,
    buy_top_n=10,
    hold_until_rank=15,
    use_adjusted_rank=True
)

# 5. Execute trades
print(f"To Buy: {signals['to_buy']}")
print(f"To Hold: {signals['to_hold']}")
print(f"To Sell: {signals['to_sell']}")
```

### Example 2: Backtesting with Historical Scores

```python
from etf_trend_following_v2.src import data_loader, scoring

# 1. Load universe
data_dict = data_loader.load_universe_from_file(
    pool_file='results/trend_etf_pool.csv',
    data_dir='data/chinese_etf/daily',
    start_date='2020-01-01',
    end_date='2023-12-31'
)

# 2. Calculate historical scores (rolling, no look-ahead)
historical_scores = scoring.calculate_historical_scores(
    data_dict=data_dict,
    start_date='2020-06-01',  # Allow 5-month warmup
    end_date='2023-12-31',
    periods=[20, 60, 120],
    weights=[0.4, 0.3, 0.3]
)

# 3. Simulate trading over time
portfolio = []
for date in pd.date_range('2020-06-01', '2023-12-31', freq='M'):
    date_str = date.strftime('%Y-%m-%d')

    # Get scores for this date
    scores = scoring.get_scores_for_date(historical_scores, date_str)

    if scores.empty:
        continue

    # Apply inertia and generate signals
    adjusted = scoring.apply_inertia_bonus(scores, portfolio, bonus_pct=0.1)
    signals = scoring.get_trading_signals(
        adjusted, portfolio, buy_top_n=10, hold_until_rank=15
    )

    portfolio = signals['final_holdings']
    print(f"{date_str}: {len(portfolio)} holdings")
```

### Example 3: Parameter Validation

```python
from etf_trend_following_v2.src import scoring

# Validate before running expensive backtest
is_valid, error = scoring.validate_scoring_params(
    periods=[20, 60, 120],
    weights=[0.4, 0.3, 0.3],
    buy_top_n=10,
    hold_until_rank=15
)

if not is_valid:
    raise ValueError(f"Invalid parameters: {error}")
```

## Design Rationale

### Why Multi-Period?

Single-period momentum can be noisy and regime-dependent:
- Short periods (20d): Capture recent trend changes, but noisy
- Medium periods (60d): Balance trend and stability
- Long periods (120d): Capture sustained trends, but slower to react

Combining multiple periods with declining weights provides robustness.

### Why Volatility Weighting?

Without volatility adjustment:
- High-volatility ETFs would dominate rankings even with mediocre risk-adjusted returns
- Low-volatility ETFs with steady returns would be undervalued
- Portfolio would be implicitly biased toward volatility clustering

Volatility weighting ensures we rank by **Sharpe-like ratio** (return per unit risk).

### Why Hysteresis?

Without buffer zones:
- Minor ranking fluctuations (rank 9 ↔ 11) would trigger trades
- Transaction costs would erode alpha
- Tax inefficiency (frequent capital gains realizations)

Hysteresis creates a "stability zone" where holdings persist despite small ranking changes.

### Why Inertia Bonus?

Even with hysteresis, holdings near the boundary (rank 13-15) might churn:
- Rank 14 → 13 → 15 → 14 (held entire time but unstable)
- Small boost (10%) stabilizes marginal holdings
- Accounts for round-trip costs (~0.1-0.2% in Chinese ETF market)

## Performance Considerations

### Computational Complexity

- `calculate_momentum_score()`: O(periods × lookback) per symbol
- `calculate_universe_scores()`: O(N × periods × lookback) for N symbols
- `calculate_historical_scores()`: O(D × N × periods × lookback) for D dates

**Optimization**: For daily production, use `calculate_universe_scores()`. For backtesting, pre-calculate with `calculate_historical_scores()` once, then query dates as needed.

### Memory Usage

- Historical scores: ~8 bytes/float × 3 columns × N symbols × D dates
- Example: 50 ETFs × 250 days × 3 columns = ~300 KB (negligible)

## Integration with Other Modules

```
data_loader → scoring → clustering → position_sizing → portfolio
              ↓
         (rankings)     (correlation)    (weights)     (orders)
```

1. **data_loader**: Provides OHLCV data → **scoring**
2. **scoring**: Generates rankings → **clustering** (correlation analysis)
3. **clustering**: Assigns cluster limits → **position_sizing**
4. **position_sizing**: Calculates target weights → **portfolio**
5. **portfolio**: Generates orders considering T+1 constraints

## Testing

Run the test suite:

```bash
conda activate backtesting
python -m pytest etf_trend_following_v2/tests/test_scoring.py -v
```

**Test Coverage**:
- ✅ Basic momentum calculation
- ✅ Insufficient data handling
- ✅ Parameter validation
- ✅ Universe-wide scoring
- ✅ Inertia bonus (multiplicative/additive)
- ✅ Trading signals with hysteresis
- ✅ Stop loss integration
- ✅ Historical score calculation
- ✅ Date-specific score extraction
- ✅ Edge cases (empty scores, NaN handling)

## Configuration Example

Typical parameters in `config.json`:

```json
{
  "scoring": {
    "periods": [20, 60, 120],
    "weights": [0.4, 0.3, 0.3],
    "min_periods_required": 20,
    "buy_top_n": 10,
    "hold_until_rank": 15,
    "inertia_bonus_pct": 0.1,
    "inertia_bonus_mode": "multiplicative",
    "rebalance_frequency": "daily"
  }
}
```

## Limitations & Future Enhancements

**Current Limitations**:
1. Assumes price-based momentum (doesn't consider fundamentals)
2. Equal treatment of upside/downside volatility
3. Fixed period weights (not adaptive)

**Potential Enhancements**:
- [ ] Adaptive period weights based on market regime
- [ ] Downside deviation instead of total volatility
- [ ] Momentum quality filters (consistency, drawdown)
- [ ] Sector-neutral ranking within clusters

## References

- Jegadeesh & Titman (1993): "Returns to Buying Winners and Selling Losers"
- Asness, Moskowitz & Pedersen (2013): "Value and Momentum Everywhere"
- Hysteresis in trading: Reduces turnover by 30-50% vs. fixed threshold
