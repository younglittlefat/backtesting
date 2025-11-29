"""
backtest_runner 包

模块化的回测执行器，从单文件 backtest_runner.py 重构而来

模块结构：
- cli/: CLI 子模块（主入口、标准模式、轮动模式）
- config/: 配置模块（参数解析、策略注册、运行时配置加载、策略构建器）
- core/: 核心模块（回测执行、优化）
- data/: 数据模块（虚拟 ETF 构建）
- io/: IO 模块（结果写入、汇总生成）
- processing/: 处理模块（过滤器构建、标的处理、结果聚合）
- utils/: 工具模块（参数解析、数据工具、显示工具）
"""

from .models import (
    BacktestConfig,
    BacktestResult,
    BacktestResults,
    RobustParamsResult,
)

# 从 cli 子模块导出 main 函数，便于外部调用
from .cli import main

__version__ = "2.0.0"
__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BacktestResults",
    "RobustParamsResult",
    "main",
]