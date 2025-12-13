"""
Dynamic pool portfolio backtest runner.

This runner reuses PortfolioBacktestRunner but enforces rotation configuration,
loading precomputed rotation schedules to refresh the tradable pool during the
backtest window.
"""

import logging

from .config_loader import Config
from .portfolio_backtest_runner import PortfolioBacktestRunner

logger = logging.getLogger(__name__)


class DynamicPoolPortfolioRunner(PortfolioBacktestRunner):
    """
    Dynamic pool portfolio backtest runner.

    Requires:
    - config.rotation.enabled == True
    - config.rotation.schedule_path pointing to a precomputed schedule JSON
    """

    def __init__(self, config: Config):
        if not getattr(config.rotation, "enabled", False):
            raise ValueError("DynamicPoolPortfolioRunner requires rotation.enabled=true")
        if not getattr(config.rotation, "schedule_path", None):
            raise ValueError("DynamicPoolPortfolioRunner requires rotation.schedule_path")
        super().__init__(config)
