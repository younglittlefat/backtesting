"""
防御性过滤器

包含:
- LossProtectionFilter: 连续止损保护过滤器
"""

from .base import BaseFilter


class LossProtectionFilter(BaseFilter):
    """
    连续止损保护过滤器

    过滤逻辑：连续亏损N次后暂停M个周期

    参数:
        max_losses: 最大连续亏损次数，默认3
        pause_bars: 暂停的K线数量，默认10
    """

    def __init__(self, enabled=True, max_losses=3, pause_bars=10):
        super().__init__(enabled=enabled)
        self.max_losses = max_losses
        self.pause_bars = pause_bars
        self.consecutive_losses = 0
        self.paused_until_bar = -1
        self.last_trade_bar = -1
        self.last_trade_pl = 0

    def _update_trade_history(self, strategy):
        """
        更新交易历史，检测亏损次数

        Args:
            strategy: 策略实例
        """
        # 获取当前bar索引
        current_bar = len(strategy.data.Close) - 1

        # 检查是否有新的交易完成
        if hasattr(strategy, 'trades') and len(strategy.trades) > 0:
            # 获取最后一笔交易
            last_trade = strategy.trades[-1]

            # 检查这笔交易是否是新的（避免重复统计）
            if hasattr(last_trade, 'exit_bar'):
                exit_bar = last_trade.exit_bar
                if exit_bar != self.last_trade_bar and exit_bar is not None:
                    self.last_trade_bar = exit_bar

                    # 检查盈亏
                    pl = last_trade.pl
                    if pl < 0:
                        self.consecutive_losses += 1
                    else:
                        self.consecutive_losses = 0

    def filter_signal(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数

        Returns:
            bool: True表示信号通过过滤
        """
        # 获取当前bar索引
        current_bar = len(strategy.data.Close) - 1

        # 更新交易历史
        self._update_trade_history(strategy)

        # 检查是否在暂停期内
        if current_bar < self.paused_until_bar:
            return False

        # 检查是否达到最大连续亏损
        if self.consecutive_losses >= self.max_losses:
            # 设置暂停期
            self.paused_until_bar = current_bar + self.pause_bars
            # 重置连续亏损计数
            self.consecutive_losses = 0
            return False

        return True
