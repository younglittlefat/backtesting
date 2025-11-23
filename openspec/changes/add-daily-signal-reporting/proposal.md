# Change: Daily signal summary reporting

## Why
Daily ETF signal runs output orders and portfolio updates but lack a reviewable summary. Analysts need
context on parameters, inputs, and decisions to audit results and debug automation.

## What Changes
- Add optional summary export to `generate_daily_signals` for analyze/execute runs (Markdown by default,
  JSON optional)
- Capture run metadata (strategy, parameters, stock list, date window) plus generated orders and
  portfolio deltas in a human-readable artifact
- Support configurable output directory/filename pattern under `results/` for daily automation

## Impact
- Affected specs: signal-reporting
- Affected code: generate_daily_signals.sh, signal generation helpers, results/ layouts
