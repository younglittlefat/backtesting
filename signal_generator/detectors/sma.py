#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SMA 信号检测器模块

检测 SMA 金叉/死叉信号，支持持续确认过滤。
"""

from typing import Dict, Any
from .base import BaseSignalDetector


class SmaSignalDetector(BaseSignalDetector):
    """SMA 信号检测器"""

    def detect_signal(self, strategy, result: Dict) -> Dict:
        """
        检测 SMA 信号

        Args:
            strategy: SMA策略实例
            result: 初始化的结果字典

        Returns:
            更新后的结果字典
        """
        sma_short = strategy.sma1[-1]
        sma_long = strategy.sma2[-1]
        sma_short_prev = strategy.sma1[-2] if len(strategy.sma1) > 1 else sma_short
        sma_long_prev = strategy.sma2[-2] if len(strategy.sma2) > 1 else sma_long

        result['sma_short'] = sma_short
        result['sma_long'] = sma_long
        signal_strength = ((sma_short - sma_long) / sma_long) * 100
        result['signal_strength'] = signal_strength

        # 读取确认参数（来自运行时配置或CLI覆盖）
        enable_confirm = bool(self.strategy_params.get('enable_confirm_filter', False))
        confirm_bars = int(self.strategy_params.get('confirm_bars', 2))
        confirm_bars_sell = int(self.strategy_params.get('confirm_bars_sell', 0))

        # 基础交叉
        buy_cross = (sma_short_prev <= sma_long_prev) and (sma_short > sma_long)
        sell_cross = (sma_short_prev >= sma_long_prev) and (sma_short < sma_long)

        # 买入确认（延迟入场语义）
        buy_ok = False
        if enable_confirm and confirm_bars and confirm_bars > 1:
            from strategies.filters.confirmation_filters import ConfirmationFilter
            cf = ConfirmationFilter(enabled=True, confirm_bars=confirm_bars)
            buy_ok = cf.filter_signal(strategy, 'buy', sma_short=strategy.sma1, sma_long=strategy.sma2)
        elif enable_confirm and confirm_bars == 1:
            # 单根确认=当根发生上穿
            buy_ok = buy_cross
        else:
            # 未启用确认：当根发生上穿即买入
            buy_ok = buy_cross

        # 卖出确认（可选；若未设置或<=1，则当根下穿即卖出）
        sell_ok = False
        if confirm_bars_sell and confirm_bars_sell > 1:
            n = int(confirm_bars_sell)
            if len(strategy.sma1) >= n and len(strategy.sma2) >= n:
                # 最近 n 根持续短<长
                sell_ok = all((strategy.sma1[-i] < strategy.sma2[-i]) for i in range(1, n + 1))
            else:
                sell_ok = False
        else:
            sell_ok = sell_cross

        if buy_ok:
            result['signal'] = 'BUY'
            confirm_text = "（持续确认）" if enable_confirm and confirm_bars > 1 else ""
            n1_val = getattr(strategy, 'n1', '-')
            n2_val = getattr(strategy, 'n2', '-')
            result['message'] = f'金叉买入信号{confirm_text}！短期均线({n1_val}日)上穿长期均线({n2_val}日)'
        elif sell_ok:
            result['signal'] = 'SELL'
            confirm_text = "（持续确认）" if confirm_bars_sell and confirm_bars_sell > 1 else ""
            n1_val = getattr(strategy, 'n1', '-')
            n2_val = getattr(strategy, 'n2', '-')
            result['message'] = f'死叉卖出信号{confirm_text}！短期均线({n1_val}日)下穿长期均线({n2_val}日)'
        elif sma_short > sma_long:
            result['signal'] = 'HOLD_LONG'
            result['message'] = f'持有多头。短期均线在长期均线上方（{signal_strength:.2f}%）'
        else:
            result['signal'] = 'HOLD_SHORT'
            result['message'] = f'持有空头。短期均线在长期均线下方（{signal_strength:.2f}%）'

        return result
