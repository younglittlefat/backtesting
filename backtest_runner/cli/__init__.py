"""
CLI 子模块

将原 cli.py 拆分为：
- main.py: 主入口和参数验证
- standard_mode.py: 标准回测模式
- rotation_mode.py: 轮动策略模式
"""

from .main import main

__all__ = ['main']
