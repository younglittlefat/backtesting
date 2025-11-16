# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `backtesting/`; strategy building blocks are in `backtesting/lib.py`, stats in `_stats.py`, and plotting glue in `_plotting.py`. Tests sit in `backtesting/test/` and shadow the package layout. Sample strategies stay in `strategies/`, helpers in `utils/`, datasets in `data/`, and generated artefacts in `results/`. Convenience entry points include `backtest_runner.py`, `run_backtest.sh`, and `open_plots.sh`. Documentation assets are stored in `doc/`.

## Build, Test, and Development Commands
Always start with `conda activate backtesting`, then install tooling through `pip install -e .[dev]`. Use `pytest backtesting/test` for the full suite or `pytest backtesting/test/test_stats.py::test_equity_curve` for a single case. `coverage run -m pytest backtesting/test && coverage report` tracks instrumentation. End-to-end strategy checks run via `python backtest_runner.py --config my_config.yaml` or `./run_backtest.sh`.

## Coding Style & Naming Conventions
Use 4-space indentation and keep lines ≤100 characters to satisfy Ruff (`pyproject.toml`). Name modules, functions, and variables in `snake_case`, classes in `CamelCase`, constants in upper snake. Run `ruff check . --fix`, `flake8 backtesting`, and `mypy backtesting` before submission. Provide purposeful docstrings and prefer keyword-only strategy parameters for clarity.

## Testing Guidelines
Place companion `test_*.py` files in `backtesting/test/`. Use Pytest parametrization for dataset coverage and mark slow cases with `@pytest.mark.slow` so they can be skipped via `pytest -m "not slow"`. Keep coverage at or above CI levels (>90% for core modules) and assert on both metrics and generated orders. Plotting tweaks need smoke tests that validate figure metadata instead of rendered pixels.

## Commit & Pull Request Guidelines
Prefix commits with the project’s scope tags (`BUG:`, `MNT:`, `BRK:`) and keep subjects under 72 characters. PRs must describe affected subsystems, link issues, list executed tests, and include metrics or screenshots for visual changes. Confirm CI passes and flag breaking changes early.

## Environment Notes
Work in Ubuntu 24 under WSL while the repository stays on the Windows drive (`/mnt/d/git/backtesting`). Normalize Windows paths sent to scripts (`D:\...`) into `/mnt/d/...` or rely on `pathlib` helpers for portability. Python 3.9+ is required; recreate the conda env with `conda create -n backtesting python=3.9` if needed.

## Additional References
- `CLAUDE.md` contains extended context on module responsibilities (`backtesting/backtesting.py`, `_stats.py`, `_plotting.py`, `_util.py`) and the data flow from OHLCV inputs through broker execution to visualization.
- Use the same source to cross-check environment recreation steps and alternative test entry points such as `python -m backtesting.test`.
- Documentation builds live in `doc/` with `build.sh`; refer there when updating notebooks or pdoc outputs.

## Strategy Baselines & Hyperparameters
- 纯基线（所有增强/过滤关闭）
  - `enable_hysteresis=False`、`enable_zero_axis=False`
  - `confirm_bars_sell=0`、`min_hold_bars=0`
  - `enable_confirm_filter=False`，其余 `enable_*` 默认均为 False
- 运行命令（按需是否优化）
  - 基线（不优化）:
    ```
    ./run_backtest.sh \
      --stock-list results/trend_etf_pool.csv \
      --strategy macd_cross \
      --data-dir data/chinese_etf/daily \
      --output-dir results/exp_macd_base
    ```
  - 基线 + 优化（仅优化 EMA 周期）:
    ```
    ./run_backtest.sh \
      --stock-list results/trend_etf_pool.csv \
      --strategy macd_cross \
      --optimize \
      --data-dir data/chinese_etf/daily \
      --output-dir results/exp_macd_base_opt
    ```
- 可调超参（CLI → 策略）
  - 核心周期：`fast_period`、`slow_period`、`signal_period`（约束：fast<slow）
  - 过滤器：
    - `--enable-adx-filter`，`--adx-period`，`--adx-threshold`
    - `--enable-volume-filter`，`--volume-period`，`--volume-ratio`
    - `--enable-slope-filter`，`--slope-lookback`
    - `--enable-confirm-filter`，`--confirm-bars`
  - 风控：
    - `--enable-loss-protection`，`--max-consecutive-losses`，`--pause-bars`
    - `--enable-trailing-stop`，`--trailing-stop-pct`
  - Anti‑Whipsaw/卖出侧：
    - `--enable-hysteresis`，`--hysteresis-mode`，`--hysteresis-k`，`--hysteresis-window`，`--hysteresis-abs`
    - `--confirm-bars-sell`（0 关闭） ，`--min-hold-bars`（0 关闭）
    - `--enable-zero-axis`，`--zero-axis-mode`
- 说明
  - 不传即为默认（纯基线）；支持连字符/下划线别名（如 `--enable-hysteresis`/`--enable_hysteresis`）。
  - `--verbose` 会打印“覆盖参数”，用于核实开关是否实际生效。

### SMA Cross Enhanced（sma_cross_enhanced）
- 纯基线
  - `enable_slope_filter=False`、`enable_adx_filter=False`、`enable_volume_filter=False`、`enable_confirm_filter=False`
  - `confirm_bars=0`、`enable_loss_protection=False`
- 命令
  ```
  ./run_backtest.sh \
    --stock-list results/trend_etf_pool.csv \
    --strategy sma_cross_enhanced \
    --data-dir data/chinese_etf/daily \
    --output-dir results/exp_sma_enhanced_base
  ```
- 可调项：同“过滤器/风控”，使用相同 CLI；SMA 周期如需优化请在策略/优化器中开放。

### KAMA（kama_cross）
- 纯基线
  - `enable_efficiency_filter=False`、`enable_slope_confirmation=False`
  - `enable_slope_filter=False`、`enable_adx_filter=False`、`enable_volume_filter=False`、`enable_confirm_filter=False`
  - `confirm_bars=0`、`enable_loss_protection=False`
- 命令
  ```
  ./run_backtest.sh \
    --stock-list results/trend_etf_pool.csv \
    --strategy kama_cross \
    --data-dir data/chinese_etf/daily \
    --output-dir results/exp_kama_base
  ```
- 可调项
  - 通用过滤器/风控：同上，使用统一 CLI
  - 策略特有（已暴露到 CLI）：
    - 核心：`--kama-period`、`--kama-fast`、`--kama-slow`
    - Phase 1：`--enable-efficiency-filter`（`--min-efficiency-ratio`）、`--enable-slope-confirmation`（`--min-slope-periods`）
