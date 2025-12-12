# Scoring Module - Quick Start Guide

## Installation & Testing

```bash
# Activate environment
conda activate backtesting

# Run tests
python -m pytest etf_trend_following_v2/tests/test_scoring.py -v

# Run examples
python etf_trend_following_v2/examples/scoring_example.py
```

## Quick Example

```python
from etf_trend_following_v2.src import scoring

# 1. Calculate scores for your ETF universe
scores_df = scoring.calculate_universe_scores(
    data_dict={'ETF1': df1, 'ETF2': df2, ...},
    as_of_date='2023-12-31'
)

# 2. Apply inertia bonus to existing holdings
adjusted = scoring.apply_inertia_bonus(
    scores_df=scores_df,
    current_holdings=['ETF1'],
    bonus_pct=0.1  # 10% boost
)

# 3. Generate trading signals
signals = scoring.get_trading_signals(
    scores_df=adjusted,
    current_holdings=['ETF1'],
    buy_top_n=10,        # Buy top 10
    hold_until_rank=15   # Hold until rank drops below 15
)

# 4. Execute trades
print(f"Buy: {signals['to_buy']}")
print(f"Hold: {signals['to_hold']}")
print(f"Sell: {signals['to_sell']}")
```

## Key Parameters

### Momentum Calculation
- `periods`: [20, 60, 120] - Lookback periods in days
- `weights`: [0.4, 0.3, 0.3] - Period weights (must sum to 1.0)

### Hysteresis (Buffer Zone)
- `buy_top_n`: 10 - Buy symbols ranked 1-10
- `hold_until_rank`: 15 - Hold as long as rank ≤ 15

### Inertia Bonus
- `bonus_pct`: 0.1 - 10% boost for existing holdings
- `bonus_mode`: 'multiplicative' - Score × (1 + 0.1)

## Output Format

### Scores DataFrame
```
  symbol  raw_score  rank
0   ETF1   0.125000     1
1   ETF2   0.098000     2
2   ETF3   0.067000     3
```

### Trading Signals
```python
{
    'to_buy': ['ETF5', 'ETF7'],      # New positions
    'to_hold': ['ETF1', 'ETF3'],     # Keep existing
    'to_sell': ['ETF2'],             # Close positions
    'final_holdings': ['ETF1', 'ETF3', 'ETF5', 'ETF7']
}
```

## Common Use Cases

### Daily Signal Generation (Live Trading)
```python
# Generate signals for today
scores = scoring.calculate_universe_scores(data_dict, as_of_date='2024-01-15')
adjusted = scoring.apply_inertia_bonus(scores, current_holdings, bonus_pct=0.1)
signals = scoring.get_trading_signals(adjusted, current_holdings, buy_top_n=10, hold_until_rank=15)
```

### Backtesting with Historical Data
```python
# Pre-calculate all historical scores (efficient)
hist_scores = scoring.calculate_historical_scores(
    data_dict, start_date='2020-01-01', end_date='2023-12-31'
)

# Then query for specific dates
for date in rebalance_dates:
    scores = scoring.get_scores_for_date(hist_scores, date)
    # ... generate signals and simulate trades
```

### Parameter Validation
```python
# Validate before expensive backtest
is_valid, error = scoring.validate_scoring_params(
    periods=[20, 60, 120],
    weights=[0.4, 0.3, 0.3],
    buy_top_n=10,
    hold_until_rank=15
)
if not is_valid:
    raise ValueError(f"Invalid params: {error}")
```

## Performance Tips

1. **Pre-calculate historical scores** for backtesting (call `calculate_historical_scores()` once)
2. **Use weekly rebalancing** to reduce computation (set `frequency='weekly'`)
3. **Filter by liquidity** before scoring to reduce universe size
4. **Cache results** if running multiple strategy variants on same data

## See Also

- Full documentation: `etf_trend_following_v2/src/README_scoring.md`
- Example scripts: `etf_trend_following_v2/examples/scoring_example.py`
- Unit tests: `etf_trend_following_v2/tests/test_scoring.py`
