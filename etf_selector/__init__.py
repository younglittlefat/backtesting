"""
ETF趋势筛选系统

从大量ETF标的中系统化筛选出最适合趋势跟踪策略的标的池。
使用三级漏斗模型：初级筛选 → 核心筛选 → 组合优化
"""

__version__ = '1.0.0'
__author__ = 'Backtesting.py Team'

from .data_loader import ETFDataLoader
from .selector import TrendETFSelector
from .portfolio import PortfolioOptimizer

__all__ = [
    'ETFDataLoader',
    'TrendETFSelector',
    'PortfolioOptimizer',
]
