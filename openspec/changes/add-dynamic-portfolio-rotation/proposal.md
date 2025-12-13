# Change: Full dynamic pool portfolio backtest runner

## Why
- Current `PortfolioBacktestRunner` only supports static pools; requirement `REQ-20251213-PORTFOLIO-DYNAMIC` calls for full-pool dynamic filtering with precomputed rotation schedules.
- Need a repeatable path to validate Gemini-style CTA best practices (rotation schedule, buffer, clustering) without look-ahead bias.

## What Changes
- Add `DynamicPoolPortfolioRunner` that consumes precomputed rotation schedules, updates tradable pools on rotation days, and rebalances with existing scoring/cluster/stop logic.
- Extend config/CLI to enable dynamic mode (`rotation.enabled`, `rotation.schedule_path`, `rotation.period_days`, `rotation.pool_size`) and guard against misconfiguration.
- Provide fixtures/tests + rotation schedule loader to prove no look-ahead, schedule gaps handled, and backward compatibility for static runner.

## Impact
- Affected specs: `portfolio-dynamic-filtering`
- Affected code: `etf_trend_following_v2/src/portfolio_backtest_runner.py`, new `dynamic_pool_runner.py`, `config_loader.py`, CLI/wrappers, tests/fixtures
