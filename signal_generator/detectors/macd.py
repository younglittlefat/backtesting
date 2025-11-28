#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MACD 信号检测器模块

检测 MACD 金叉/死叉信号，支持 Anti-Whipsaw 过滤。
"""

from typing import Dict, Any
import numpy as np
from .base import BaseSignalDetector


class MacdSignalDetector(BaseSignalDetector):
    """MACD 信号检测器"""

    def detect_signal(self, strategy, result: Dict) -> Dict:
        """
        检测 MACD 信号

        Args:
            strategy: MACD策略实例
            result: 初始化的结果字典

        Returns:
            更新后的结果字典
        """
        macd_line = strategy.macd_line[-1]
        signal_line = strategy.signal_line[-1]
        macd_line_prev = strategy.macd_line[-2] if len(strategy.macd_line) > 1 else macd_line
        signal_line_prev = strategy.signal_line[-2] if len(strategy.signal_line) > 1 else signal_line

        result['sma_short'] = macd_line  # 兼容性：用macd_line代替
        result['sma_long'] = signal_line  # 兼容性：用signal_line代替

        # 计算信号强度
        signal_strength = macd_line - signal_line  # MACD柱状图值
        result['signal_strength'] = signal_strength

        # 读取 Anti-Whipsaw 参数
        enable_hysteresis = bool(self.strategy_params.get('enable_hysteresis', False))
        hysteresis_mode = self.strategy_params.get('hysteresis_mode', 'std')
        hysteresis_k = float(self.strategy_params.get('hysteresis_k', 0.5))
        hysteresis_window = int(self.strategy_params.get('hysteresis_window', 20))
        hysteresis_abs = float(self.strategy_params.get('hysteresis_abs', 0.001))
        confirm_bars_sell = int(self.strategy_params.get('confirm_bars_sell', 0))
        enable_zero_axis = bool(self.strategy_params.get('enable_zero_axis', False))

        def zero_axis_ok(sig_type: str) -> bool:
            if not enable_zero_axis:
                return True
            if sig_type == 'BUY':
                return macd_line > 0 and signal_line > 0
            else:
                return macd_line < 0 and signal_line < 0

        def hysteresis_ok(sig_type: str) -> bool:
            if not enable_hysteresis:
                return True
            hist_now = macd_line - signal_line
            if sig_type == 'BUY' and not (hist_now > 0):
                return False
            if sig_type == 'SELL' and not (hist_now < 0):
                return False
            if hysteresis_mode == 'std':
                hist_series = np.array(strategy.histogram, dtype=float)
                win = max(5, hysteresis_window)
                if len(hist_series) < win:
                    return False
                thr = float(np.nanstd(hist_series[-win:])) * hysteresis_k
                thr = max(thr, 0.0)
                return abs(hist_now) > thr
            else:
                return abs(hist_now) > hysteresis_abs

        def sell_confirm_ok() -> bool:
            n = max(1, confirm_bars_sell)
            if n <= 1:
                return True
            if len(strategy.macd_line) < n or len(strategy.signal_line) < n:
                return False
            for i in range(1, n + 1):
                if not (strategy.macd_line[-i] < strategy.signal_line[-i]):
                    return False
            return True

        # 检测原始交叉
        buy_cross = macd_line_prev <= signal_line_prev and macd_line > signal_line
        sell_cross = macd_line_prev >= signal_line_prev and macd_line < signal_line

        # 金叉：MACD线从下方穿过信号线（并通过 ZeroAxis/Hysteresis）
        if buy_cross and zero_axis_ok('BUY') and hysteresis_ok('BUY'):
            result['signal'] = 'BUY'
            fast = getattr(strategy, 'fast_period', 12)
            slow = getattr(strategy, 'slow_period', 26)
            sig = getattr(strategy, 'signal_period', 9)
            result['message'] = f'MACD金叉买入信号！MACD({fast},{slow},{sig})线上穿信号线'
        # 死叉：MACD线从上方穿过信号线（并通过 ZeroAxis/Hysteresis/Confirm）
        elif sell_cross and zero_axis_ok('SELL') and hysteresis_ok('SELL') and sell_confirm_ok():
            result['signal'] = 'SELL'
            fast = getattr(strategy, 'fast_period', 12)
            slow = getattr(strategy, 'slow_period', 26)
            sig = getattr(strategy, 'signal_period', 9)
            result['message'] = f'MACD死叉卖出信号！MACD({fast},{slow},{sig})线下穿信号线'
        else:
            # 若发生交叉但被过滤，输出日志并标注原因
            reasons = []
            if buy_cross and not zero_axis_ok('BUY'):
                reasons.append('零轴约束(BUY)')
            if buy_cross and not hysteresis_ok('BUY'):
                hist_series = np.array(strategy.histogram, dtype=float)
                win = max(5, hysteresis_window)
                if hysteresis_mode == 'std' and len(hist_series) >= win:
                    thr = float(np.nanstd(hist_series[-win:])) * hysteresis_k
                    reasons.append(f'滞回阈值(BUY, |Hist|={abs(signal_strength):.6f}<=thr={max(thr,0.0):.6f})')
                elif hysteresis_mode == 'abs':
                    reasons.append(f'滞回阈值(BUY, |Hist|={abs(signal_strength):.6f}<=eps={hysteresis_abs:.6f})')
            if sell_cross:
                if not zero_axis_ok('SELL'):
                    reasons.append('零轴约束(SELL)')
                if not hysteresis_ok('SELL'):
                    hist_series = np.array(strategy.histogram, dtype=float)
                    win = max(5, hysteresis_window)
                    if hysteresis_mode == 'std' and len(hist_series) >= win:
                        thr = float(np.nanstd(hist_series[-win:])) * hysteresis_k
                        reasons.append(f'滞回阈值(SELL, |Hist|={abs(signal_strength):.6f}<=thr={max(thr,0.0):.6f})')
                    elif hysteresis_mode == 'abs':
                        reasons.append(f'滞回阈值(SELL, |Hist|={abs(signal_strength):.6f}<=eps={hysteresis_abs:.6f})')
                if not sell_confirm_ok():
                    reasons.append(f'卖出确认不足(n={confirm_bars_sell})')
            if reasons:
                print(f"[过滤] {result['ts_code']} 交叉被拦截: {', '.join(reasons)}")
                if buy_cross:
                    result['signal'] = 'HOLD_LONG' if macd_line > signal_line else 'HOLD_SHORT'
                    result['message'] = f'触发金叉但被过滤：{", ".join(reasons)}'
                elif sell_cross:
                    result['signal'] = 'HOLD_SHORT'
                    result['message'] = f'触发死叉但被过滤：{", ".join(reasons)}'

        # 持有状态
        if result['signal'] == 'ERROR' and macd_line > signal_line:
            result['signal'] = 'HOLD_LONG'
            result['message'] = f'持有多头。MACD线在信号线上方（柱状图: {signal_strength:.4f}）'
        elif result['signal'] == 'ERROR':
            result['signal'] = 'HOLD_SHORT'
            result['message'] = f'持有空头。MACD线在信号线下方（柱状图: {signal_strength:.4f}）'

        return result
