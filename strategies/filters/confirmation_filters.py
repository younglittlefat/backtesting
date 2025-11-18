"""
信号确认类过滤器

包含:
- ConfirmationFilter: 持续确认过滤器（防假突破，带“延迟入场”语义）
"""

from .base import BaseFilter
import pandas as pd


class ConfirmationFilter(BaseFilter):
    """
    持续确认过滤器（防假突破 / 延迟入场）

    升级后的语义：
    - 若启用且 confirm_bars > 1，则仅在“发生过一次向上穿越（短上穿长）且之后连续 n 根都在上方”的当根返回 True。
      这等价于“金叉后持续确认 n 根，再在第 n 根入场”，从而避免金叉当根直接入场导致的反复。
    - 若启用且 confirm_bars <= 1，则仅在“当前这根发生向上穿越”时返回 True（视为即时确认）。
    - 仅对买入（'buy'）信号生效；卖出侧由其它过滤器或策略自行处理。

    参数:
        confirm_bars: 确认所需的K线数量，默认3
    """

    def __init__(self, enabled=True, confirm_bars=3):
        super().__init__(enabled=enabled)
        self.confirm_bars = confirm_bars

    def filter_signal(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号（延迟入场判定）

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数，应包含 'sma_short' 和 'sma_long'

        Returns:
            bool: True表示信号通过过滤
        """
        # 仅处理买入侧；卖出侧直接放行
        if signal_type != 'buy':
            return True

        sma_short = kwargs.get('sma_short')
        sma_long = kwargs.get('sma_long')

        if sma_short is None or sma_long is None:
            # 如果没有提供均线数据，尝试从策略实例获取
            if hasattr(strategy, 'sma1') and hasattr(strategy, 'sma2'):
                sma_short = strategy.sma1
                sma_long = strategy.sma2
            else:
                return True  # 无法获取数据，放行

        # 将输入视为类序列对象（如 backtesting.Series）；仅使用索引负号访问
        n = int(self.confirm_bars or 0)
        if n <= 0:
            # 参数异常，视为不通过；与旧逻辑保持一致（默认3需显式启用才生效）
            return False

        # 至少需要看 n+1 根（用于检测穿越的“前一根”）
        needed = max(2, n + 1)
        if len(sma_short) < needed or len(sma_long) < needed:
            return False  # 数据不足

        # 即时确认（n<=1）：仅当本根发生向上穿越返回 True
        if n <= 1:
            prev_s = sma_short[-2]
            prev_l = sma_long[-2]
            cur_s = sma_short[-1]
            cur_l = sma_long[-1]
            if any(pd.isna(x) for x in (prev_s, prev_l, cur_s, cur_l)):
                return False
            return (prev_s <= prev_l) and (cur_s > cur_l)

        # 延迟确认（n>1）：
        # 条件1：最近 n 根均满足 短 > 长
        for i in range(1, n + 1):
            s = sma_short[-i]
            l = sma_long[-i]
            if pd.isna(s) or pd.isna(l) or s <= l:
                return False

        # 条件2：最近 n 根内是否至少出现一次“向上穿越”
        recent_cross = False
        for i in range(1, n + 1):
            prev_s = sma_short[-(i + 1)]
            prev_l = sma_long[-(i + 1)]
            cur_s = sma_short[-i]
            cur_l = sma_long[-i]
            if any(pd.isna(x) for x in (prev_s, prev_l, cur_s, cur_l)):
                continue
            if prev_s <= prev_l and cur_s > cur_l:
                recent_cross = True
                break

        return recent_cross
