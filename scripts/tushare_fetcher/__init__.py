"""
Tushare数据获取模块

提供模块化的数据获取功能，支持ETF、指数、基金数据的获取和管理。
"""

from .base_fetcher import BaseFetcher
from .etf_fetcher import ETFFetcher
from .index_fetcher import IndexFetcher
from .fund_fetcher import FundFetcher
from .strategy_selector import StrategySelector
from .rate_limiter import RateLimiter
from .data_processor import DataProcessor

__all__ = [
    'BaseFetcher',
    'ETFFetcher',
    'IndexFetcher',
    'FundFetcher',
    'StrategySelector',
    'RateLimiter',
    'DataProcessor',
]

__version__ = '1.0.0'
