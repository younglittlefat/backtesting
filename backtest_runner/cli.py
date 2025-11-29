#!/usr/bin/env python3
"""
中国市场回测执行器 - CLI入口

此文件为向后兼容的薄包装层。
实际实现已拆分到 backtest_runner/cli/ 子模块中：
- cli/main.py: 主入口和参数验证
- cli/standard_mode.py: 标准回测模式
- cli/rotation_mode.py: 轮动策略模式
"""

import sys
from pathlib import Path

# 添加项目根目录到路径（确保可以直接运行此文件）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 从新的 cli 子模块导入 main 函数
from backtest_runner.cli import main

if __name__ == '__main__':
    sys.exit(main())
