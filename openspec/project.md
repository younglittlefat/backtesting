# Project Context

## Purpose
Python backtesting toolkit with custom strategy runners and automation for daily ETF/fund workflows.
Supports research, optimization, and execution of rule-based strategies with reproducible outputs.

## Tech Stack
- Python 3.9+ with Conda env `backtesting`
- Core libs: pandas, numpy, scipy, backtesting.py, bokeh/plotly for visualization
- Tooling: pytest, coverage, ruff, flake8, mypy; shell wrappers (`run_backtest.sh`, `generate_daily_signals.sh`)

## Project Conventions

### Code Style
- 4-space indentation, ≤100-char lines (ruff); snake_case functions/vars, CamelCase classes, UPPER_SNAKE constants
- Keep modules under `backtesting/`; strategies in `strategies/`, helpers in `utils/`, data in `data/`, results in `results/`
- Run `ruff check . --fix`, `flake8 backtesting`, and `mypy backtesting` before merging

### Architecture Patterns
- Backtest orchestration in `backtesting/backtesting.py` with stats in `_stats.py`, plotting glue in `_plotting.py`
- Strategy building blocks live in `backtesting/lib.py`; CLI entry points `backtest_runner.py` and `run_backtest.sh`
- Daily signal pipeline uses `generate_daily_signals.sh`, portfolio state in `positions/`, configs in `config/`

### Testing Strategy
- Unit/integration: `pytest backtesting/test` or `python -m backtesting.test`; mark slow cases with `@pytest.mark.slow`
- Coverage: `coverage run -m backtesting.test && coverage report`; target >90% for core modules
- Prefer smoke tests for plotting (metadata assertions) and assert on orders/metrics for strategies

### Git Workflow
- Commit prefixes with scope tags (`BUG:`, `MNT:`, `BRK:`); subjects <72 chars; flag breaking changes early
- Confirm CI parity locally (lint, type, tests) before PR; use PR templates with affected subsystems and executed tests

## Domain Context
- Focus on ETF/fund trading in China A-share market; data fetched via Tushare scripts and exported to CSV
- Baseline strategies: MACD, SMA Cross Enhanced, KAMA Cross with optional filters (ADX, volume, slope, confirm)
- Risk controls include loss-protection, trailing stops, hysteresis/zero-axis guards, confirm-bars sell, min-hold
- Workloads: stock list prefiltering (`etf_selector`), backtest optimization, daily signal generation and execution

## Important Constraints
- Must run inside Conda env `backtesting`; repository lives on Windows drive (`/mnt/d/...`) under WSL
- Use POSIX paths (or `pathlib`) instead of Windows-style; avoid destructive git resets
- Do not implement new features without approved OpenSpec proposals; keep docstrings purposeful and lines ≤100
- Python 3.9 baseline; prefer ASCII output unless file already uses Unicode

## External Dependencies
- Tushare data APIs for ETF/fund prices/dividends; CSV exports consumed by backtests
- Optional plotting stack (bokeh/plotly) for interactive equity curves and trade visuals
- Conda/pip for environment management; coverage/pytest/ruff/flake8/mypy for validation
