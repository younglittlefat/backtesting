"""
信号过滤器模块

提供各种信号质量过滤器，用于改善交易策略的信号质量和减少假信号。

过滤器分类:
- trend_filters: 趋势确认类过滤器
- volume_filters: 成交量确认类过滤器
- volatility_filters: 波动率控制过滤器
- confirmation_filters: 信号确认过滤器
- momentum_filters: 动量指标过滤器
- defensive_filters: 防御性过滤器
"""

from .base import BaseFilter
from .trend_filters import SlopeFilter, ADXFilter
from .volume_filters import VolumeFilter
from .confirmation_filters import ConfirmationFilter
from .defensive_filters import LossProtectionFilter

__all__ = [
    'BaseFilter',
    'SlopeFilter', 'ADXFilter',
    'VolumeFilter',
    'ConfirmationFilter',
    'LossProtectionFilter'
]