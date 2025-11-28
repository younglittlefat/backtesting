#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号检测器基类模块

定义信号检测的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import numpy as np


class BaseSignalDetector(ABC):
    """信号检测器基类"""

    def __init__(self, strategy_params: Dict[str, Any] = None):
        """
        初始化信号检测器

        Args:
            strategy_params: 策略参数字典
        """
        self.strategy_params = strategy_params or {}

    @abstractmethod
    def detect_signal(self, strategy, result: Dict) -> Dict:
        """
        检测信号

        Args:
            strategy: 策略实例（来自backtesting）
            result: 初始化的结果字典

        Returns:
            更新后的结果字典，包含信号和相关指标
        """
        pass

    @staticmethod
    def create_empty_result(ts_code: str) -> Dict:
        """
        创建空的结果字典

        Args:
            ts_code: 标的代码

        Returns:
            初始化的结果字典
        """
        return {
            'ts_code': ts_code,
            'signal': 'ERROR',
            'price': 0,
            'adj_price': 0,
            'real_price': 0,
            'adj_factor': 1.0,
            'sma_short': 0,
            'sma_long': 0,
            'signal_strength': 0,
            'message': ''
        }
