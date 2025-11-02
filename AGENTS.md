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
