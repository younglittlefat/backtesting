#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
signal_generator 包

实盘交易信号生成器模块，用于每天收盘后分析股票池中的所有标的，生成买入/卖出信号。

主要组件：
- SignalGenerator: 核心信号生成器类
- detectors: 信号检测器子包（MACD/SMA/KAMA）
- reports: 报告打印模块
- cli: 命令行接口模块
- config: 配置常量模块

使用示例：
    from signal_generator import SignalGenerator

    generator = SignalGenerator(
        strategy_class=SmaCross,
        strategy_params={'n1': 10, 'n2': 20},
        cash=100000,
        data_dir='data/csv/daily'
    )

    signal = generator.get_signal('510050.SH')

命令行使用：
    python -m signal_generator --stock-list stocks.csv --strategy sma_cross
"""

from .config import COST_MODELS, DEFAULT_CASH, DEFAULT_LOOKBACK_DAYS
from .core import SignalGenerator
from .detectors import (
    BaseSignalDetector,
    MacdSignalDetector,
    SmaSignalDetector,
    KamaSignalDetector,
)
from .reports import (
    print_signal_report,
    print_portfolio_status,
    print_trade_plan,
)

__all__ = [
    # 核心类
    'SignalGenerator',
    # 检测器
    'BaseSignalDetector',
    'MacdSignalDetector',
    'SmaSignalDetector',
    'KamaSignalDetector',
    # 报告函数
    'print_signal_report',
    'print_portfolio_status',
    'print_trade_plan',
    # 配置
    'COST_MODELS',
    'DEFAULT_CASH',
    'DEFAULT_LOOKBACK_DAYS',
]

__version__ = '1.0.0'
