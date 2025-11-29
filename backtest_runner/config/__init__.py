"""配置模块"""

from .strategy_registry import (
    StrategyRegistry,
    get_global_registry,
    register_default_strategies,
    STRATEGIES,
)
from .argparser import create_argument_parser
from .runtime_loader import load_runtime_config
from .strategy_builder import build_strategy_instance

__all__ = [
    'StrategyRegistry',
    'get_global_registry',
    'register_default_strategies',
    'STRATEGIES',
    'create_argument_parser',
    'load_runtime_config',
    'build_strategy_instance',
]
