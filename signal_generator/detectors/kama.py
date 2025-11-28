#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KAMA 信号检测器模块

检测 KAMA（Kaufman自适应移动平均）信号，支持持续确认过滤。
"""

from typing import Dict, Any
import pandas as pd
from .base import BaseSignalDetector


class KamaSignalDetector(BaseSignalDetector):
    """KAMA 信号检测器"""

    def detect_signal(self, strategy, result: Dict, df: pd.DataFrame = None) -> Dict:
        """
        检测 KAMA 信号

        Args:
            strategy: KAMA策略实例
            result: 初始化的结果字典
            df: 价格数据 DataFrame（用于获取收盘价）

        Returns:
            更新后的结果字典
        """
        if df is None:
            result['message'] = 'KAMA检测器需要传入价格数据'
            return result

        kama_now = strategy.kama[-1]
        kama_prev = strategy.kama[-2] if len(strategy.kama) > 1 else kama_now
        price_now = df['Close'].iloc[-1]
        price_prev = df['Close'].iloc[-2] if len(df) > 1 else price_now

        result['sma_short'] = price_now  # 复用字段名用于报告
        result['sma_long'] = kama_now
        signal_strength = ((price_now - kama_now) / kama_now) * 100 if kama_now else 0.0
        result['signal_strength'] = signal_strength

        # 参数
        enable_confirm = bool(self.strategy_params.get('enable_confirm_filter', False))
        confirm_bars = int(self.strategy_params.get('confirm_bars', 2))
        confirm_bars_sell = int(self.strategy_params.get('confirm_bars_sell', 0))

        # 交叉
        buy_cross = (price_prev <= kama_prev) and (price_now > kama_now)
        sell_cross = (price_prev >= kama_prev) and (price_now < kama_now)

        # 买入确认（延迟入场：最近 n 根价格>KAMA 且窗口内出现过一次上穿）
        buy_ok = False
        if enable_confirm and confirm_bars and confirm_bars > 1:
            from strategies.filters.confirmation_filters import ConfirmationFilter
            cf = ConfirmationFilter(enabled=True, confirm_bars=confirm_bars)
            # 传递价格序列与KAMA序列
            buy_ok = cf.filter_signal(strategy, 'buy', sma_short=df['Close'], sma_long=strategy.kama)
        elif enable_confirm and confirm_bars == 1:
            buy_ok = buy_cross
        else:
            buy_ok = buy_cross

        # 卖出确认（可选）
        sell_ok = False
        if confirm_bars_sell and confirm_bars_sell > 1:
            n = int(confirm_bars_sell)
            if len(df) >= n and len(strategy.kama) >= n:
                sell_ok = all((df['Close'].iloc[-i] < strategy.kama[-i]) for i in range(1, n + 1))
            else:
                sell_ok = False
        else:
            sell_ok = sell_cross

        if buy_ok:
            result['signal'] = 'BUY'
            result['message'] = f'KAMA持续确认买入信号（n={confirm_bars}）！价格上穿KAMA'
        elif sell_ok:
            result['signal'] = 'SELL'
            result['message'] = f'KAMA卖出信号{"（持续确认）" if confirm_bars_sell and confirm_bars_sell>1 else ""}！价格下穿KAMA'
        elif price_now > kama_now:
            result['signal'] = 'HOLD_LONG'
            result['message'] = f'持有多头。价格在KAMA上方（{signal_strength:.2f}%）'
        else:
            result['signal'] = 'HOLD_SHORT'
            result['message'] = f'持有空头。价格在KAMA下方（{signal_strength:.2f}%）'

        return result
