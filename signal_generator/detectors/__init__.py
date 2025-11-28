#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号检测器子包

提供多种策略的信号检测器：
- MacdSignalDetector: MACD金叉/死叉检测
- SmaSignalDetector: SMA金叉/死叉检测
- KamaSignalDetector: KAMA信号检测
"""

from .base import BaseSignalDetector
from .macd import MacdSignalDetector
from .sma import SmaSignalDetector
from .kama import KamaSignalDetector

__all__ = [
    'BaseSignalDetector',
    'MacdSignalDetector',
    'SmaSignalDetector',
    'KamaSignalDetector',
]
