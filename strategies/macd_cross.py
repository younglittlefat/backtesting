"""
MACD金叉死叉策略 (MACD Crossover Strategy)

MACD (Moving Average Convergence Divergence) 是经典的动量趋势跟踪指标，
通过快速EMA和慢速EMA的差值来捕捉趋势变化。

策略逻辑:
- MACD线上穿信号线 -> 买入信号（金叉）
- MACD线下穿信号线 -> 卖出信号（死叉）

Phase 1: 基础金叉死叉信号 ✅
Phase 2: 信号质量过滤器（ADX、成交量、斜率、确认）✅
Phase 3: 连续止损保护 ✅
Phase 4: 增强信号（零轴交叉、双重金叉、背离）
"""

import sys
from pathlib import Path
import pandas as pd
import random
from backtesting import Strategy
from backtesting.lib import crossover
import numpy as np

# 添加项目根目录到路径（用于直接运行）
if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from strategies.filters import ADXFilter, VolumeFilter


def MACD(close, fast_period=12, slow_period=26, signal_period=9):
    """
    计算MACD指标

    MACD由三个部分组成:
    1. MACD线 (DIF): 快速EMA - 慢速EMA
    2. 信号线 (DEA): MACD线的EMA
    3. 柱状图 (Histogram): MACD线 - 信号线

    Args:
        close: 收盘价序列
        fast_period: 快速EMA周期 (默认12)
        slow_period: 慢速EMA周期 (默认26)
        signal_period: 信号线EMA周期 (默认9)

    Returns:
        tuple: (macd_line, signal_line, histogram)
    """
    close_series = pd.Series(close)

    # 计算快速和慢速EMA
    ema_fast = close_series.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close_series.ewm(span=slow_period, adjust=False).mean()

    # MACD线 (DIF)
    macd_line = ema_fast - ema_slow

    # 信号线 (DEA)
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

    # 柱状图
    histogram = macd_line - signal_line

    return macd_line.values, signal_line.values, histogram.values


class MACDSlopeFilter:
    """
    MACD斜率过滤器

    过滤逻辑：买入信号时MACD线必须向上（斜率为正）

    参数:
        enabled: 是否启用过滤器
        lookback: 斜率计算的回溯周期，默认5
    """

    def __init__(self, enabled=True, lookback=5):
        self.enabled = enabled
        self.lookback = lookback

    def __call__(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数，应包含 'macd_line'

        Returns:
            bool: True表示信号通过过滤
        """
        if not self.enabled:
            return True

        # 只过滤买入信号（金叉）
        if signal_type != 'buy':
            return True

        macd_line = kwargs.get('macd_line')

        if macd_line is None:
            # 尝试从策略实例获取
            if hasattr(strategy, 'macd_line'):
                macd_line = strategy.macd_line
            else:
                return True  # 无法获取数据，放行

        # 检查数据长度
        if len(macd_line) < self.lookback + 1:
            return False  # 数据不足，不交易

        # 计算MACD线斜率
        macd_slope = (macd_line[-1] - macd_line[-self.lookback - 1]) / self.lookback

        # 判断斜率是否向上
        return macd_slope > 0


class MACDConfirmationFilter:
    """
    MACD持续确认过滤器（防假突破）

    过滤逻辑：金叉后需持续N根K线MACD线持续在信号线上方才确认

    参数:
        enabled: 是否启用过滤器
        confirm_bars: 确认所需的K线数量，默认2
    """

    def __init__(self, enabled=True, confirm_bars=2):
        self.enabled = enabled
        self.confirm_bars = confirm_bars

    def __call__(self, strategy, signal_type, **kwargs):
        """
        过滤交易信号

        Args:
            strategy: 策略实例
            signal_type: 'buy' 或 'sell'
            **kwargs: 额外参数，应包含 'macd_line' 和 'signal_line'

        Returns:
            bool: True表示信号通过过滤
        """
        if not self.enabled:
            return True

        # 只过滤买入信号（金叉）
        if signal_type != 'buy':
            return True

        macd_line = kwargs.get('macd_line')
        signal_line = kwargs.get('signal_line')

        if macd_line is None or signal_line is None:
            # 尝试从策略实例获取
            if hasattr(strategy, 'macd_line') and hasattr(strategy, 'signal_line'):
                macd_line = strategy.macd_line
                signal_line = strategy.signal_line
            else:
                return True  # 无法获取数据，放行

        # 检查数据长度
        if len(macd_line) < self.confirm_bars or len(signal_line) < self.confirm_bars:
            return False  # 数据不足，不交易

        # 检查过去N根K线，MACD线是否持续在信号线上方
        cross_bars = 0
        for i in range(1, self.confirm_bars + 1):
            if macd_line[-i] > signal_line[-i]:
                cross_bars += 1
            else:
                break  # 如果有一根不满足，立即中断

        # 只有连续N根K线都满足条件才通过
        return cross_bars >= self.confirm_bars


class MacdCross(Strategy):
    """
    MACD金叉死叉策略（功能完整版）

    支持:
    - Phase 1: 基础金叉死叉信号 ✅
    - Phase 2: 信号质量过滤器（ADX、成交量、斜率、确认）✅
    - Phase 3: 止损保护 ✅
      - 连续止损保护 ✅
      - 跟踪止损 ✅
      - 组合止损方案 ✅
    - Phase 4: 增强信号（零轴交叉、双重金叉、背离）🔲

    参数:
        fast_period: 快速EMA周期 (默认12)
        slow_period: 慢速EMA周期 (默认26)
        signal_period: 信号线EMA周期 (默认9)

        # Phase 2: 过滤器开关
        enable_adx_filter: 启用ADX趋势强度过滤器 (默认False)
        enable_volume_filter: 启用成交量确认过滤器 (默认False)
        enable_slope_filter: 启用MACD斜率过滤器 (默认False)
        enable_confirm_filter: 启用持续确认过滤器 (默认False)

        # Phase 2: 过滤器参数
        adx_period: ADX计算周期 (默认14)
        adx_threshold: ADX阈值 (默认25)
        volume_period: 成交量均值周期 (默认20)
        volume_ratio: 成交量放大倍数 (默认1.2)
        slope_lookback: 斜率回溯周期 (默认5)
        confirm_bars: 持续确认K线数 (默认2)

        # Phase 3: 止损保护
        enable_loss_protection: 启用连续止损保护 (默认False) ⭐⭐⭐强烈推荐
        max_consecutive_losses: 连续亏损次数阈值 (默认3)
        pause_bars: 暂停交易K线数 (默认10)
        enable_trailing_stop: 启用跟踪止损 (默认False)
        trailing_stop_pct: 跟踪止损百分比 (默认0.05，即5%)
        debug_loss_protection: 启用止损保护调试日志 (默认False)

        # Phase 4: 增强信号
        enable_zero_cross: 启用零轴交叉信号 (默认False)
        enable_double_golden: 启用双重金叉信号 (默认False)
        enable_divergence: 启用背离信号检测 (默认False)
        divergence_lookback: 背离检测回溯周期 (默认20)
    """

    # === Phase 1: 核心参数 ===
    fast_period = 12
    slow_period = 26
    signal_period = 9

    # === Phase 2: 过滤器开关（后续实现） ===
    enable_adx_filter = False
    enable_volume_filter = False
    enable_slope_filter = False
    enable_confirm_filter = False

    # 过滤器参数
    adx_period = 14
    adx_threshold = 25
    volume_period = 20
    volume_ratio = 1.2
    slope_lookback = 5
    confirm_bars = 2

    # === Phase 3: 止损保护 ===
    enable_loss_protection = False
    max_consecutive_losses = 3
    pause_bars = 10

    # 跟踪止损
    enable_trailing_stop = False
    trailing_stop_pct = 0.05  # 默认5%

    # 调试开关
    debug_loss_protection = False  # 启用止损保护调试日志

    # === Phase 4: 增强信号（后续实现） ===
    enable_zero_cross = False
    enable_double_golden = False
    enable_divergence = False
    divergence_lookback = 20

    # === Anti-Whipsaw: 新增功能（自适应滞回、卖出确认、最短持有、零轴约束） ===
    # 自适应滞回阈值（用于交叉确认，避免贴线反复）
    enable_hysteresis = False         # 总开关（默认关闭，需显式 --enable-hysteresis 开启）
    hysteresis_mode = 'std'           # 'std' or 'abs'
    hysteresis_k = 0.5                # k * rolling_std(hist, window)
    hysteresis_window = 20            # rolling std 窗口
    hysteresis_abs = 0.001            # 绝对阈值模式的 epsilon

    # 卖出确认（对称于买入确认，弱死叉不立即卖；0 表示不做卖出确认）
    confirm_bars_sell = 0

    # 最短持有期（建仓后 N 根内忽略相反信号；0 表示不限制）
    min_hold_bars = 0

    # 零轴约束（买入需两线在零轴上方，卖出需两线在零轴下方）
    enable_zero_axis = False
    zero_axis_mode = 'symmetric'
    # 日志开关（过滤信号）
    debug_signal_filter = False

    def init(self):
        """
        初始化策略

        计算MACD指标并初始化过滤器
        """
        # 计算MACD指标
        macd_line, signal_line, histogram = self.I(
            MACD,
            self.data.Close,
            self.fast_period,
            self.slow_period,
            self.signal_period
        )

        self.macd_line = macd_line
        self.signal_line = signal_line
        self.histogram = histogram

        # Phase 2: 初始化过滤器
        self.adx_filter = ADXFilter(
            enabled=self.enable_adx_filter,
            period=self.adx_period,
            threshold=self.adx_threshold
        )
        self.volume_filter = VolumeFilter(
            enabled=self.enable_volume_filter,
            period=self.volume_period,
            ratio=self.volume_ratio
        )
        self.slope_filter = MACDSlopeFilter(
            enabled=self.enable_slope_filter,
            lookback=self.slope_lookback
        )
        self.confirm_filter = MACDConfirmationFilter(
            enabled=self.enable_confirm_filter,
            confirm_bars=self.confirm_bars
        )

        # Phase 3: 初始化止损追踪
        if self.enable_loss_protection:
            self.entry_price = 0  # 入场价格
            self.consecutive_losses = 0  # 连续亏损计数
            self.paused_until_bar = -1  # 暂停到第几根K线
            self.current_bar = 0  # 当前K线计数
            self.debug_counter = 0  # 调试计数器，用于控制日志输出频率
            self.total_trades = 0  # 交易总数
            self.triggered_pauses = 0  # 触发暂停次数

        # 跟踪止损初始化
        if self.enable_trailing_stop:
            self.highest_price = 0  # 持仓期间最高价（做多）或最低价（做空）
            self.stop_loss_price = 0  # 动态止损价格
            if not self.enable_loss_protection:
                # 如果没有启用连续止损保护，仍需要这些变量
                self.entry_price = 0
                self.current_bar = 0
                self.total_trades = 0
        # Anti-Whipsaw 需要的计数器：统一初始化并在 next() 中始终递增
        if not hasattr(self, 'current_bar'):
            self.current_bar = 0
        self.entry_bar = -1  # 建仓所在bar（用于最短持有期）
        # 买入确认（多根）所需的状态（当 confirm_bars>1 时使用）
        self._awaiting_buy_confirm = False
        self._buy_confirm_count = 0
        # 卖出确认（多根）所需的状态（当 confirm_bars_sell>1 时使用）
        self._awaiting_sell_confirm = False
        self._sell_confirm_count = 0

    def _apply_filters(self, signal_type):
        """
        应用所有启用的过滤器

        Args:
            signal_type: 'buy' 或 'sell'

        Returns:
            bool: True表示信号通过所有过滤器
        """
        filters = [
            self.adx_filter,
            self.volume_filter,
            self.slope_filter,
            self.confirm_filter
        ]

        # 准备上下文信息
        kwargs = {
            'macd_line': self.macd_line,
            'signal_line': self.signal_line
        }

        # 检查所有过滤器
        for f in filters:
            if not f(self, signal_type, **kwargs):
                return False

        return True

    # === Anti-Whipsaw: 工具方法 ===
    def _log_filter_reject(self, signal_type: str, reason: str):
        """在交叉被过滤时打印一条简洁的日志"""
        if getattr(self, 'debug_signal_filter', False):
            print(f"[过滤] {signal_type.upper()} 被拦截: {reason} (Bar {self.current_bar})")

    def _zero_axis_ok(self, signal_type: str) -> bool:
        if not self.enable_zero_axis:
            return True
        macd_now = self.macd_line[-1]
        sig_now = self.signal_line[-1]
        if self.zero_axis_mode == 'symmetric':
            if signal_type == 'buy':
                return macd_now > 0 and sig_now > 0
            else:
                return macd_now < 0 and sig_now < 0
        # 预留其他模式
        return True

    def _hysteresis_ok(self, signal_type: str) -> bool:
        if not self.enable_hysteresis:
            return True

        hist_now = self.macd_line[-1] - self.signal_line[-1]
        # 方向一致性：买入需 hist>0；卖出需 hist<0
        if signal_type == 'buy' and not (hist_now > 0):
            return False
        if signal_type == 'sell' and not (hist_now < 0):
            return False

        if self.hysteresis_mode == 'std':
            win = max(5, int(self.hysteresis_window))
            if len(self.histogram) < win:
                self._log_filter_reject(signal_type, f"滞回未通过: 数据不足(win={win})")
                return False  # 数据不足，不触发，避免噪声
            # 使用近 win 根柱状图估计阈值
            tail = np.array(self.histogram[-win:], dtype=float)
            thr = float(np.nanstd(tail)) * float(self.hysteresis_k)
            thr = max(thr, 0.0)
            ok = abs(hist_now) > thr
            if not ok:
                self._log_filter_reject(signal_type, f"滞回未通过: |Hist|={abs(hist_now):.6f} <= 阈值{thr:.6f} (std,k={self.hysteresis_k},win={win})")
            return ok
        else:
            # 绝对阈值模式
            thr = float(self.hysteresis_abs)
            ok = abs(hist_now) > thr
            if not ok:
                self._log_filter_reject(signal_type, f"滞回未通过: |Hist|={abs(hist_now):.6f} <= 阈值{thr:.6f} (abs)")
            return ok

    def _sell_confirmation_ok(self) -> bool:
        n = int(self.confirm_bars_sell)
        if n <= 1:
            return True
        if len(self.macd_line) < n or len(self.signal_line) < n:
            self._log_filter_reject('sell', f"卖出确认未通过: 数据不足(n={n})")
            return False
        # 过去 n 根均满足 MACD < Signal
        for i in range(1, self.confirm_bars_sell + 1):
            if not (self.macd_line[-i] < self.signal_line[-i]):
                self._log_filter_reject('sell', f"卖出确认未通过: 第{-i}根未满足 MACD<Signal")
                return False
        return True

    def _min_hold_ok_to_exit(self) -> bool:
        n = int(self.min_hold_bars)
        if n <= 0:
            return True
        if self.entry_bar < 0:
            return True
        held = self.current_bar - self.entry_bar
        ok = held >= n
        if not ok:
            self._log_filter_reject('sell', f"最短持有期未达: 已持有{held} < 要求{n}")
        return ok

    def next(self):
        """
        每个交易日调用一次

        根据MACD金叉死叉信号和过滤器决定买入或卖出
        """
        # 始终递增bar计数（供最短持有等使用）
        self.current_bar += 1

        # 如果开启了买入多根确认（confirm_bars>1），在这里处理“延迟确认”的状态机：
        # 逻辑：出现金叉当根不立即买入，而是要求连续 n 根 MACD>Signal，满足后再执行买入。
        if self.enable_confirm_filter and int(self.confirm_bars) > 1:
            if self._awaiting_buy_confirm:
                # 在等待确认期间，若仍保持 MACD>Signal，则累计；否则取消等待
                if self.macd_line[-1] > self.signal_line[-1]:
                    self._buy_confirm_count += 1
                else:
                    # 失去上方关系，取消等待
                    self._awaiting_buy_confirm = False
                    self._buy_confirm_count = 0
                # 到达确认根数，尝试执行买入（再次通过其余过滤器）
                if self._awaiting_buy_confirm and self._buy_confirm_count >= int(self.confirm_bars):
                    # 其余过滤器：ADX/量能/斜率、零轴、滞回
                    if not self._apply_filters('buy'):
                        # 未通过则放弃本次确认，等待下一次金叉再重新计数
                        self._awaiting_buy_confirm = False
                        self._buy_confirm_count = 0
                    elif not self._zero_axis_ok('buy') or not self._hysteresis_ok('buy'):
                        # 约束未通过，放弃确认
                        self._awaiting_buy_confirm = False
                        self._buy_confirm_count = 0
                    else:
                        # 确认通过：执行买入流程
                        if self.position:
                            self._close_position_with_loss_tracking()
                        self.buy(size=0.90)
                        if self.enable_loss_protection or self.enable_trailing_stop:
                            self.entry_price = self.data.Close[-1]
                        if self.enable_trailing_stop:
                            self.highest_price = self.data.Close[-1]
                            self.stop_loss_price = self.highest_price * (1 - self.trailing_stop_pct)
                            if self.debug_loss_protection:
                                print(f"[跟踪止损] Bar {self.current_bar}: 开多仓 入场={self.entry_price:.2f} 初始止损={self.stop_loss_price:.2f}")
                        self.entry_bar = self.current_bar
                        # 重置状态
                        self._awaiting_buy_confirm = False
                        self._buy_confirm_count = 0
                        # 本bar已完成交易，直接返回
                        return
        # 如果开启了卖出多根确认（confirm_bars_sell>1），在这里处理“延迟确认”的状态机：
        # 逻辑：出现死叉当根不立即卖出，而是要求连续 n 根 MACD<Signal，满足后再执行卖出。
        if int(self.confirm_bars_sell) > 1:
            if self._awaiting_sell_confirm:
                if self.macd_line[-1] < self.signal_line[-1]:
                    self._sell_confirm_count += 1
                else:
                    # 失去下方关系，取消等待
                    self._awaiting_sell_confirm = False
                    self._sell_confirm_count = 0
                # 到达确认根数，尝试执行卖出（再次通过其余过滤器）
                if self._awaiting_sell_confirm and self._sell_confirm_count >= int(self.confirm_bars_sell):
                    # 若持有仓位，先检查最短持有期
                    if self.position and not self._min_hold_ok_to_exit():
                        # 继续等待，直到满足持有期或形态失效
                        return
                    # 其余过滤器：ADX/量能/斜率、零轴、滞回
                    if not self._apply_filters('sell'):
                        self._awaiting_sell_confirm = False
                        self._sell_confirm_count = 0
                    elif not self._zero_axis_ok('sell') or not self._hysteresis_ok('sell'):
                        self._awaiting_sell_confirm = False
                        self._sell_confirm_count = 0
                    else:
                        # 执行卖出流程（可平多并开空）
                        if self.position:
                            self._close_position_with_loss_tracking()
                        self.sell(size=0.90)
                        if self.enable_loss_protection or self.enable_trailing_stop:
                            self.entry_price = self.data.Close[-1]
                        if self.enable_trailing_stop:
                            self.highest_price = self.data.Close[-1]
                            self.stop_loss_price = self.highest_price * (1 + self.trailing_stop_pct)
                            if self.debug_loss_protection:
                                print(f"[跟踪止损] Bar {self.current_bar}: 开空仓 入场={self.entry_price:.2f} 初始止损={self.stop_loss_price:.2f}")
                        self.entry_bar = self.current_bar
                        # 重置状态
                        self._awaiting_sell_confirm = False
                        self._sell_confirm_count = 0
                        return

        # 连续止损保护：检查是否在暂停期
        if self.enable_loss_protection:
            # 检查是否在暂停期 - 添加随机采样日志（5%概率）
            if self.current_bar < self.paused_until_bar:
                # 调试模式下5%的概率输出日志
                if self.debug_loss_protection and random.random() < 0.05:
                    print(f"[止损保护] Bar {self.current_bar}: 暂停期内 (暂停至Bar {self.paused_until_bar})")
                return  # 暂停期内不交易

        # 跟踪止损：检查持仓的止损触发
        if self.enable_trailing_stop and self.position:
            current_price = self.data.Close[-1]

            # 做多仓位的跟踪止损
            if self.position.is_long:
                # 更新最高价和止损价
                if current_price > self.highest_price:
                    self.highest_price = current_price
                    self.stop_loss_price = current_price * (1 - self.trailing_stop_pct)
                    if self.debug_loss_protection:
                        print(f"[跟踪止损] Bar {self.current_bar}: 更新止损线 最高={self.highest_price:.2f} 止损={self.stop_loss_price:.2f}")

                # 检查是否触发止损
                if current_price <= self.stop_loss_price:
                    if self.debug_loss_protection:
                        pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
                        print(f"[跟踪止损] Bar {self.current_bar}: ⚠️ 触发止损 价格={current_price:.2f} <= 止损={self.stop_loss_price:.2f} (盈亏={pnl_pct:.2f}%)")
                    self._close_position_with_loss_tracking()
                    return

            # 做空仓位的跟踪止损
            else:
                # 更新最低价和止损价
                if current_price < self.highest_price or self.highest_price == 0:
                    self.highest_price = current_price  # 对于做空，这是最低价
                    self.stop_loss_price = current_price * (1 + self.trailing_stop_pct)
                    if self.debug_loss_protection:
                        print(f"[跟踪止损] Bar {self.current_bar}: 更新止损线 最低={self.highest_price:.2f} 止损={self.stop_loss_price:.2f}")

                # 检查是否触发止损
                if current_price >= self.stop_loss_price:
                    if self.debug_loss_protection:
                        pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
                        print(f"[跟踪止损] Bar {self.current_bar}: ⚠️ 触发止损 价格={current_price:.2f} >= 止损={self.stop_loss_price:.2f} (盈亏={pnl_pct:.2f}%)")
                    self._close_position_with_loss_tracking()
                    return

        # MACD金叉 - 买入信号
        if crossover(self.macd_line, self.signal_line):
            # 如开启多根确认（confirm_bars>1），进入等待状态，不立即买入
            if self.enable_confirm_filter and int(self.confirm_bars) > 1:
                self._awaiting_buy_confirm = True
                # 第1根已满足（当前这根）
                self._buy_confirm_count = 1
                return
            # Phase 2: 应用过滤器（单根确认或未启用确认过滤）
            if not self._apply_filters('buy'):
                return  # 信号被过滤，不交易

            # Anti-Whipsaw: 零轴约束 + 滞回阈值
            if not self._zero_axis_ok('buy'):
                return
            if not self._hysteresis_ok('buy'):
                return

            # Phase 4: 检查增强信号（后续实现）

            # 如果有仓位，先平仓
            if self.position:
                self._close_position_with_loss_tracking()

            # 买入 - 使用90%的可用资金，避免保证金不足
            self.buy(size=0.90)

            # 记录入场价格和初始化跟踪止损
            if self.enable_loss_protection or self.enable_trailing_stop:
                self.entry_price = self.data.Close[-1]

            if self.enable_trailing_stop:
                self.highest_price = self.data.Close[-1]
                self.stop_loss_price = self.highest_price * (1 - self.trailing_stop_pct)
                if self.debug_loss_protection:
                    print(f"[跟踪止损] Bar {self.current_bar}: 开多仓 入场={self.entry_price:.2f} 初始止损={self.stop_loss_price:.2f}")
            # 记录建仓bar
            self.entry_bar = self.current_bar

        # MACD死叉 - 卖出信号
        elif crossover(self.signal_line, self.macd_line):
            # 如开启卖出多根确认（confirm_bars_sell>1），进入等待状态，不立即卖出
            if int(self.confirm_bars_sell) > 1:
                self._awaiting_sell_confirm = True
                self._sell_confirm_count = 1
                return
            # Phase 2: 应用过滤器
            if not self._apply_filters('sell'):
                return  # 信号被过滤，不交易

            # Anti-Whipsaw: 零轴约束 + 滞回阈值 + 卖出确认 + 最短持有期
            if not self._zero_axis_ok('sell'):
                return
            if not self._hysteresis_ok('sell'):
                return
            if not self._sell_confirmation_ok():
                return
            if not self._min_hold_ok_to_exit():
                return

            # Phase 4: 检查增强信号（后续实现）

            # 如果有仓位，先平仓
            if self.position:
                self._close_position_with_loss_tracking()

            # 卖出（做空）- 使用90%的可用资金
            self.sell(size=0.90)

            # 记录入场价格和初始化跟踪止损
            if self.enable_loss_protection or self.enable_trailing_stop:
                self.entry_price = self.data.Close[-1]

            if self.enable_trailing_stop:
                self.highest_price = self.data.Close[-1]
                self.stop_loss_price = self.highest_price * (1 + self.trailing_stop_pct)
                if self.debug_loss_protection:
                    print(f"[跟踪止损] Bar {self.current_bar}: 开空仓 入场={self.entry_price:.2f} 初始止损={self.stop_loss_price:.2f}")
            # 记录建仓bar
            self.entry_bar = self.current_bar

    def _close_position_with_loss_tracking(self):
        """
        平仓并跟踪盈亏（用于止损保护）

        如果启用了止损保护，会跟踪连续亏损次数，并在达到阈值后暂停交易
        """
        if not self.enable_loss_protection or not self.position:
            self.position.close()
            # 重置建仓bar
            self.entry_bar = -1
            return

        # 计算盈亏
        exit_price = self.data.Close[-1]
        is_loss = (self.position.is_long and exit_price < self.entry_price) or \
                  (self.position.is_short and exit_price > self.entry_price)

        # 平仓
        self.position.close()
        self.total_trades += 1
        # 重置建仓bar
        self.entry_bar = -1

        # 计算实际盈亏比例
        pnl_pct = 0
        if self.entry_price > 0:
            if self.position.is_long:
                pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100
            else:
                pnl_pct = (self.entry_price - exit_price) / self.entry_price * 100

        # 更新连续亏损计数
        if is_loss:
            self.consecutive_losses += 1
            # 调试模式下输出亏损日志
            if self.debug_loss_protection:
                print(f"[止损保护] 交易#{self.total_trades}: 亏损 {pnl_pct:.2f}% (连续亏损: {self.consecutive_losses}/{self.max_consecutive_losses})")

            if self.consecutive_losses >= self.max_consecutive_losses:
                # 达到连续亏损阈值，启动暂停期
                self.paused_until_bar = self.current_bar + self.pause_bars
                self.consecutive_losses = 0  # 重置计数
                self.triggered_pauses += 1
                # 调试模式下输出触发暂停日志
                if self.debug_loss_protection:
                    print(f"[止损保护] ⚠️ 触发暂停 (第{self.triggered_pauses}次): Bar {self.current_bar} → {self.paused_until_bar} (暂停{self.pause_bars}根K线)")
        else:
            # 盈利则重置连续亏损计数
            old_losses = self.consecutive_losses
            self.consecutive_losses = 0
            # 调试模式下输出盈利日志
            if self.debug_loss_protection:
                print(f"[止损保护] 交易#{self.total_trades}: 盈利 {pnl_pct:.2f}% (重置连续亏损: {old_losses} → 0)")

        # 重置入场价格
        self.entry_price = 0


# 参数优化配置 - Phase 1基础参数
OPTIMIZE_PARAMS = {
    'fast_period': range(8, 21, 2),      # 快速EMA: 8, 10, 12, ..., 20
    'slow_period': range(20, 41, 2),     # 慢速EMA: 20, 22, 24, ..., 40
    'signal_period': range(6, 15, 2),    # 信号线: 6, 8, 10, ..., 14
}

# 参数约束: 快速周期必须小于慢速周期
CONSTRAINTS = lambda p: p.fast_period < p.slow_period


if __name__ == '__main__':
    """测试策略"""
    from backtesting import Backtest
    from backtesting.test import GOOG

    print("=" * 60)
    print("测试MACD金叉死叉策略")
    print("=" * 60)
    print()

    # 测试1: 默认参数
    print("测试1: 默认参数 (12, 26, 9)")
    bt = Backtest(GOOG, MacdCross, cash=10000, commission=0.002)
    stats = bt.run()
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    # 测试2: 短期参数（更灵敏）
    print("测试2: 短期参数 (8, 20, 6)")
    bt = Backtest(GOOG, MacdCross, cash=10000, commission=0.002)
    stats = bt.run(fast_period=8, slow_period=20, signal_period=6)
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    # 测试3: 长期参数（更平滑）
    print("测试3: 长期参数 (15, 30, 10)")
    bt = Backtest(GOOG, MacdCross, cash=10000, commission=0.002)
    stats = bt.run(fast_period=15, slow_period=30, signal_period=10)
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)
