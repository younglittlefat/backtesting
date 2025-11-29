"""
运行时配置加载器

职责：
- 从配置文件加载策略参数和运行时配置
- 将配置合并到 args 对象
"""

import sys
from pathlib import Path
from typing import Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.strategy_params_manager import StrategyParamsManager

# 配置块名称列表，用于从 runtime_config 中加载
CONFIG_SECTIONS = [
    'filters',
    'loss_protection',
    'anti_whipsaw',
    'trailing_stop',
    'atr_stop',
]


def load_runtime_config(args: Any, config_path: str, strategy_name: str) -> None:
    """
    从配置文件加载运行时参数到 args 对象

    Args:
        args: argparse 解析后的参数对象
        config_path: 配置文件路径
        strategy_name: 策略名称
    """
    params_manager = StrategyParamsManager(config_path)

    # 加载策略参数（如优化后的参数）
    loaded_params = params_manager.get_strategy_params(strategy_name)

    # 加载运行时配置
    runtime_config = params_manager.get_runtime_config(strategy_name) or {}

    # 将各配置块合并到 args
    for section in CONFIG_SECTIONS:
        section_config = runtime_config.get(section, {})
        for key, value in section_config.items():
            setattr(args, key, value)
