"""
ETF Trend Following v2 - Strategy Modules

This package contains independent signal generators for various trading strategies.
These are standalone modules that don't depend on backtesting.py's Strategy class.
"""

from .macd import MACDSignalGenerator
from .kama import KAMASignalGenerator
from .combo import ComboSignalGenerator

__all__ = ['MACDSignalGenerator', 'KAMASignalGenerator', 'ComboSignalGenerator']
