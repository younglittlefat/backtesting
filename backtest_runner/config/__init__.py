"""配置模块"""

from .strategy_registry import (
    StrategyRegistry,
    get_global_registry,
    register_default_strategies,
    STRATEGIES,
)
from .argparser import create_argument_parser

__all__ = [
    'StrategyRegistry',
    'get_global_registry',
    'register_default_strategies',
    'STRATEGIES',
    'create_argument_parser',
]
