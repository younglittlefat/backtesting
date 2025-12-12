# Configuration Structure Visualization

## Hierarchical Structure

```
Config (Root)
│
├── env: EnvConfig
│   ├── root_dir (required)
│   ├── data_dir (default: "data/chinese_etf/daily")
│   ├── results_dir (default: "results")
│   ├── log_dir (default: "logs")
│   ├── timezone (default: "Asia/Shanghai")
│   └── trading_calendar (default: "SSE")
│
├── modes: ModesConfig
│   ├── run_mode (backtest|signal|live-dryrun)
│   ├── as_of_date (YYYY-MM-DD or null)
│   ├── lookback_days (default: 500)
│   └── calendar_offsets (signal_generation: -1, execution: 0)
│
├── universe: UniverseConfig
│   ├── pool_file (CSV path) OR pool_list (array)
│   ├── liquidity_threshold
│   │   ├── min_avg_volume (default: 1,000,000)
│   │   ├── min_avg_amount (default: 5,000,000)
│   │   └── min_turnover_rate (default: 0.001)
│   ├── blacklist (array)
│   └── handle_delisted (exclude|keep_until_delist|warn)
│
├── strategies: Array[StrategyConfig]
│   │
│   ├── MACDStrategyConfig
│   │   ├── type: "macd"
│   │   ├── fast_period (default: 12)
│   │   ├── slow_period (default: 26)
│   │   ├── signal_period (default: 9)
│   │   ├── enable_adx_filter (default: false)
│   │   ├── adx_period (default: 14)
│   │   ├── adx_threshold (default: 25.0)
│   │   ├── enable_volume_filter (default: false)
│   │   ├── volume_period (default: 20)
│   │   ├── volume_ratio (default: 1.2)
│   │   ├── enable_slope_filter (default: false)
│   │   ├── slope_lookback (default: 5)
│   │   ├── enable_confirm_filter (default: false)
│   │   └── confirm_bars (default: 2)
│   │
│   ├── KAMAStrategyConfig ⭐ RECOMMENDED
│   │   ├── type: "kama"
│   │   ├── kama_period (default: 20)
│   │   ├── kama_fast (default: 2)
│   │   ├── kama_slow (default: 30)
│   │   ├── enable_efficiency_filter (default: false)
│   │   ├── min_efficiency_ratio (default: 0.3)
│   │   ├── enable_slope_confirmation (default: false)
│   │   ├── min_slope_periods (default: 3)
│   │   ├── enable_adx_filter (default: false)
│   │   ├── adx_period (default: 14)
│   │   ├── adx_threshold (default: 25.0)
│   │   ├── enable_volume_filter (default: false)
│   │   ├── volume_period (default: 20)
│   │   └── volume_ratio (default: 1.2)
│   │
│   └── ComboStrategyConfig
│       ├── type: "combo"
│       ├── mode (or|and|split)
│       ├── strategies (array of MACD/KAMA configs)
│       ├── weights (optional, for split mode)
│       └── conflict_resolution (first|majority|weighted)
│
├── scoring: ScoringConfig
│   ├── momentum_weights
│   │   ├── 20d (default: 0.3)
│   │   ├── 60d (default: 0.4)
│   │   └── 120d (default: 0.3)  [must sum to 1.0]
│   ├── buffer_thresholds
│   │   ├── buy_top_n (default: 10)
│   │   └── hold_until_rank (default: 15)  [must be >= buy_top_n]
│   ├── inertia_bonus (default: 0.05)
│   └── rebalance_frequency (default: 5 days)
│
├── clustering: ClusteringConfig
│   ├── correlation_window (default: 60 days)
│   ├── distance_metric (correlation|euclidean|dtw)
│   ├── linkage_method (single|complete|average|ward)
│   ├── cut_threshold (default: 0.5, range: [0, 1])
│   ├── max_positions_per_cluster (default: 2)
│   └── update_frequency (default: 20 days)
│
├── risk: RiskConfig
│   ├── atr_window (default: 14)
│   ├── atr_multiplier (default: 2.0)
│   ├── time_stop_days (default: 60)
│   ├── time_stop_threshold (default: -0.05 = -5%)
│   ├── circuit_breaker_threshold (default: -0.10 = -10%)
│   ├── min_liquidity_threshold (default: 1,000,000)
│   └── enable_t1_restriction (default: true) ⚠️ China market
│
├── position_sizing: PositionSizingConfig
│   ├── target_risk_per_position (default: 0.02 = 2%)
│   ├── volatility_method (std|ewma|atr)
│   ├── ewma_lambda (default: 0.94)
│   ├── max_positions (default: 20)
│   ├── max_position_size (default: 0.15 = 15%)
│   ├── max_cluster_size (default: 0.30 = 30%)
│   ├── max_total_exposure (default: 0.95 = 95%)
│   ├── min_cash_reserve (default: 0.05 = 5%)
│   ├── commission_rate (default: 0.0003 = 0.03%)
│   └── slippage_bps (default: 5.0 bps)
│
├── execution: ExecutionConfig
│   ├── order_time_strategy (open|close|vwap|twap)
│   ├── matching_assumption (immediate|next_bar|realistic)
│   ├── slippage_model (fixed|volume_based|spread_based)
│   └── handle_t1_restriction (default: true) ⚠️ China market
│
└── io: IOConfig
    ├── signal_output_path (default: "signals/signals_{date}.csv")
    ├── position_snapshot_path (default: "positions/positions_{date}.json")
    ├── performance_report_path (default: "reports/performance_{date}.html")
    ├── log_level (DEBUG|INFO|WARNING|ERROR)
    ├── log_format (Python logging format)
    └── save_intermediate_results (default: true)
```

## Validation Flow

```
1. Load JSON file
   ↓
2. Parse each section into dataclass
   ├── EnvConfig
   ├── ModesConfig
   ├── UniverseConfig
   ├── Strategy configs (MACD/KAMA/Combo)
   ├── ScoringConfig
   ├── ClusteringConfig
   ├── RiskConfig
   ├── PositionSizingConfig
   ├── ExecutionConfig
   └── IOConfig
   ↓
3. Create Config object
   ↓
4. Run validation
   ├── Field-level validation
   │   ├── Type checking (automatic)
   │   ├── Range validation
   │   └── Required field checking
   ├── Cross-field validation
   │   ├── MACD: fast_period < slow_period
   │   ├── KAMA: kama_fast < kama_slow
   │   ├── Scoring: weights sum to 1.0
   │   └── Scoring: hold_until_rank >= buy_top_n
   └── Cross-section validation
       ├── buy_top_n <= max_positions
       └── max_total_exposure + min_cash_reserve <= 1.0
   ↓
5. Return validation errors (if any)
```

## Strategy Selection Decision Tree

```
Need trading signals?
│
├─ Single strategy sufficient?
│  │
│  ├─ Want best performance? → Use KAMA (Sharpe 1.69)
│  │
│  ├─ Want customizable filters? → Use MACD (Sharpe 0.94 with stop loss)
│  │
│  └─ Want simple baseline? → Use SMA (not in config, use KAMA instead)
│
└─ Need multiple strategies?
   │
   ├─ Want signals from ANY strategy? → Use Combo mode="or"
   │
   ├─ Want signals from ALL strategies? → Use Combo mode="and"
   │
   └─ Want to split capital? → Use Combo mode="split" with weights
```

## Recommended Configurations

### Production Configuration (Recommended)
```json
{
  "strategies": [{"type": "kama"}],
  "scoring": {
    "buffer_thresholds": {"buy_top_n": 10, "hold_until_rank": 15}
  },
  "position_sizing": {
    "max_positions": 20,
    "max_position_size": 0.15,
    "max_total_exposure": 0.95,
    "min_cash_reserve": 0.05
  },
  "risk": {
    "enable_t1_restriction": true
  }
}
```
Expected: Sharpe 1.69, Annual Return 34.63%, Max Drawdown -5.27%

### Conservative Configuration
```json
{
  "strategies": [{"type": "kama", "enable_adx_filter": true}],
  "scoring": {
    "buffer_thresholds": {"buy_top_n": 8, "hold_until_rank": 12}
  },
  "position_sizing": {
    "max_positions": 15,
    "max_position_size": 0.10,
    "max_total_exposure": 0.85,
    "min_cash_reserve": 0.15
  }
}
```
Expected: Lower returns but reduced risk

### Aggressive Configuration
```json
{
  "strategies": [
    {"type": "kama"},
    {"type": "macd"}
  ],
  "scoring": {
    "buffer_thresholds": {"buy_top_n": 15, "hold_until_rank": 20}
  },
  "position_sizing": {
    "max_positions": 25,
    "max_position_size": 0.20,
    "max_total_exposure": 0.98,
    "min_cash_reserve": 0.02
  }
}
```
Expected: Higher returns but increased risk

## Key Constraints

### Hard Constraints (Will Fail Validation)
- fast_period < slow_period (MACD)
- kama_fast < kama_slow (KAMA)
- momentum_weights sum to 1.0
- hold_until_rank >= buy_top_n
- All percentages in [0, 1]
- Positive periods/windows

### Soft Constraints (Will Warn)
- buy_top_n <= max_positions
- max_total_exposure + min_cash_reserve <= 1.0

### Best Practices (Recommended)
- Use KAMA strategy (proven best)
- Set buy_top_n around 10-15
- Keep max_positions <= 20
- Reserve 5% cash minimum
- Enable T+1 restriction for China market
- Use EWMA for volatility estimation

## File Size Reference

- config_loader.py: 661 lines
- test_config_loader.py: 333 lines, 47 tests
- example_config.json: ~100 lines
- Documentation: 280+ lines

## Dependencies

```python
# Standard library only
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Literal
from datetime import datetime
```

No external dependencies required!
