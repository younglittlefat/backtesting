"""
backtest_runner 包

模块化的回测执行器，从单文件 backtest_runner.py 重构而来
"""

from .models import (
    BacktestConfig,
    BacktestResult,
    BacktestResults,
    RobustParamsResult,
)

__version__ = "1.0.0"
__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BacktestResults",
    "RobustParamsResult",
]