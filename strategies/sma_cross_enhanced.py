"""
增强版双均线交叉策略 (Enhanced SMA Crossover Strategy)

在原有双均线策略基础上，增加了多个信号质量过滤器，用于减少假信号，提高胜率。

策略逻辑:
- 短期均线上穿长期均线 -> 买入信号（金叉）
- 短期均线下穿长期均线 -> 卖出信号（死叉）
- 所有买入信号必须通过启用的过滤器

过滤器:
1. SlopeFilter: 均线斜率过滤（确保均线向上）
2. ADXFilter: ADX趋势强度过滤（确保趋势足够强）
3. VolumeFilter: 成交量放大确认（确保资金认可）
4. ConfirmationFilter: 持续确认过滤（防止假突破）
"""

import sys
import random
from pathlib import Path
import pandas as pd
from backtesting.lib import crossover

# 添加项目根目录到路径（用于直接运行）
if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from strategies.base_strategy import BaseEnhancedStrategy
from strategies.filters import (
    SlopeFilter, ADXFilter, VolumeFilter,
    ConfirmationFilter
)
from strategies.indicators import ATR


def SMA(values, n):
    """
    简单移动平均线

    Args:
        values: 价格序列
        n: 窗口大小

    Returns:
        移动平均值序列
    """
    return pd.Series(values).rolling(n).mean()


class SmaCrossEnhanced(BaseEnhancedStrategy):
    """
    增强版双均线交叉策略

    参数:
        n1: 短期均线周期 (默认10)
        n2: 长期均线周期 (默认20)

        # 过滤器开关
        enable_slope_filter: 启用均线斜率过滤器 (默认False)
        enable_adx_filter: 启用ADX趋势强度过滤器 (默认False)
        enable_volume_filter: 启用成交量确认过滤器 (默认False)
        enable_confirm_filter: 启用持续确认过滤器 (默认False)

        # 过滤器参数
        slope_lookback: 斜率计算回溯期 (默认5)
        adx_period: ADX计算周期 (默认14)
        adx_threshold: ADX阈值 (默认25)
        volume_period: 成交量均值周期 (默认20)
        volume_ratio: 成交量放大倍数 (默认1.2)
        confirm_bars: 确认所需K线数 (默认3)

        # 止损功能开关（Phase 6新增）
        enable_loss_protection: 启用连续止损保护 (默认False，推荐True，夏普比率+75%)

        # 止损参数（基于实验推荐值）
        max_consecutive_losses: 连续亏损次数阈值 (默认3)
        pause_bars: 暂停交易的K线数 (默认10)

    注意: 此策略继承自 BaseEnhancedStrategy，自动获得运行时参数导出能力
    """

    # 策略参数 - 定义为类变量以便优化
    n1 = 10  # 短期均线周期
    n2 = 20  # 长期均线周期

    # 过滤器开关（继承自 BaseEnhancedStrategy，可覆盖）
    enable_slope_filter = False
    enable_adx_filter = False
    enable_volume_filter = False
    enable_confirm_filter = False

    # 过滤器参数（继承自 BaseEnhancedStrategy，可覆盖）
    slope_lookback = 5
    adx_period = 14
    adx_threshold = 25
    volume_period = 20
    volume_ratio = 1.2
    confirm_bars = 0  # 0 表示默认不启用持续确认（与 enable_confirm_filter=False 一致）

    # 止损功能开关（Phase 6新增，继承自 BaseEnhancedStrategy）
    enable_loss_protection = False  # 启用连续止损保护（推荐，夏普比率+75%）

    # 止损参数（基于实验推荐值，继承自 BaseEnhancedStrategy）
    max_consecutive_losses = 3  # 连续亏损次数阈值
    pause_bars = 10  # 暂停交易的K线数

    # 调试开关
    debug_loss_protection = False  # 启用止损保护调试日志

    def init(self):
        """
        初始化策略

        计算短期和长期移动平均线，并初始化过滤器
        """
        # 计算短期移动平均线
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        # 计算长期移动平均线
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

        # 初始化过滤器
        self.slope_filter = SlopeFilter(
            enabled=self.enable_slope_filter,
            lookback=self.slope_lookback
        )
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
        self.confirm_filter = ConfirmationFilter(
            enabled=self.enable_confirm_filter,
            confirm_bars=self.confirm_bars
        )

        # ATR 自适应止损
        self.atr_indicator = None
        self.atr_trailing_stop = 0.0
        self.atr_stop_hits = 0
        if self.enable_atr_stop:
            self.atr_indicator = self.I(
                ATR,
                self.data.High,
                self.data.Low,
                self.data.Close,
                self.atr_period
            )

        # 初始化止损保护状态（Phase 6新增）
        if self.enable_loss_protection:
            self.entry_price = 0  # 入场价格
            self.consecutive_losses = 0  # 连续亏损计数
            self.paused_until_bar = -1  # 暂停到第几根K线
            self.current_bar = 0  # 当前K线计数
            self.debug_counter = 0  # 调试计数器，用于控制日志输出频率
            self.total_trades = 0  # 交易总数
            self.triggered_pauses = 0  # 触发暂停次数

    def _apply_filters(self, signal_type):
        """
        应用所有启用的过滤器

        Args:
            signal_type: 'buy' 或 'sell'

        Returns:
            bool: True表示信号通过所有过滤器
        """
        filters = [
            self.slope_filter,
            self.adx_filter,
            self.volume_filter,
            self.confirm_filter
        ]

        # 准备上下文信息
        kwargs = {
            'sma_short': self.sma1,
            'sma_long': self.sma2
        }

        # 检查所有过滤器
        for f in filters:
            if not f(self, signal_type, **kwargs):
                return False

        return True

    def next(self):
        """
        每个交易日调用一次

        根据均线交叉信号和过滤器决定买入或卖出
        """
        # 如果启用了止损保护，处理止损逻辑（Phase 6新增）
        if self.enable_loss_protection:
            self.current_bar += 1

            # 检查是否在暂停期 - 添加随机采样日志（5%概率）
            if self.current_bar < self.paused_until_bar:
                # 调试模式下5%的概率输出日志
                if self.debug_loss_protection and random.random() < 0.05:
                    print(f"[止损保护] Bar {self.current_bar}: 暂停期内 (暂停至Bar {self.paused_until_bar})")
                return  # 暂停期内不交易

        current_price = self.data.Close[-1]

        # ATR 自适应止损优先执行，避免与交叉信号冲突
        if self.enable_atr_stop and self.position:
            self._update_atr_trailing_stop(current_price)
            stop_price = self.atr_trailing_stop
            if stop_price:
                if self.position.is_long and current_price <= stop_price:
                    self.atr_stop_hits += 1
                    self._close_position_with_loss_tracking()
                    self.atr_trailing_stop = 0.0
                    return
                if self.position.is_short and current_price >= stop_price:
                    self.atr_stop_hits += 1
                    self._close_position_with_loss_tracking()
                    self.atr_trailing_stop = 0.0
                    return

        # 计算基础交叉信号
        buy_cross = crossover(self.sma1, self.sma2)   # 金叉
        sell_cross = crossover(self.sma2, self.sma1)  # 死叉

        # 持续确认逻辑（与 KAMA 一致的修复思路）：
        # - 启用且 confirm_bars>1 时，要求：
        #   (a) 最近 n 根均满足 短均线 > 长均线；
        #   (b) 最近 n 根内出现过一次“短均线从下到上穿越长均线”的事件。
        # - 否则沿用“金叉当根入场”。
        entry_signal = False
        if self.enable_confirm_filter and self.confirm_bars and self.confirm_bars > 1:
            n = int(self.confirm_bars)
            # 条件(a)：最近 n 根短均线持续在长均线上方
            consecutive_above = True
            for i in range(1, n + 1):
                s = self.sma1[-i]
                l = self.sma2[-i]
                if pd.isna(s) or pd.isna(l) or s <= l:
                    consecutive_above = False
                    break
            # 条件(b)：最近 n 根内出现过一次“上穿”
            recent_cross = False
            for i in range(1, n + 1):
                prev_s = self.sma1[-(i + 1)]
                prev_l = self.sma2[-(i + 1)]
                cur_s = self.sma1[-i]
                cur_l = self.sma2[-i]
                if (not pd.isna(prev_s) and not pd.isna(prev_l) and
                        not pd.isna(cur_s) and not pd.isna(cur_l) and
                        prev_s <= prev_l and cur_s > cur_l):
                    recent_cross = True
                    break
            entry_signal = consecutive_above and recent_cross
        else:
            entry_signal = buy_cross

        # 入场：在“确认完成”的当根再应用其它过滤器并下单
        if entry_signal:
            if self._apply_filters('buy'):
                # 仅当当前为空仓或持有空头时才执行多头入场；若为空头则先反手平仓
                if (not self.position) or self.position.is_short:
                    if self.position and self.position.is_short:
                        self._close_position_with_loss_tracking()
                    self.buy(size=0.90)  # 使用90%资金，避免保证金不足
                    if self.enable_loss_protection:
                        self.entry_price = self.data.Close[-1]
                    if self.enable_atr_stop:
                        self.atr_trailing_stop = 0.0
                        self._update_atr_trailing_stop(current_price)

        # 短期均线下穿长期均线 -> 卖出信号（死叉）
        elif sell_cross:
            # 应用过滤器
            if self._apply_filters('sell'):
                # 仅当当前为空仓或持有多头时才执行空头入场；若为多头则先反手平仓
                if (not self.position) or self.position.is_long:
                    if self.position and self.position.is_long:
                        self._close_position_with_loss_tracking()
                    # 卖出（做空）- 使用90%的可用资金
                    self.sell(size=0.90)
                    # 记录入场价格
                    if self.enable_loss_protection:
                        self.entry_price = self.data.Close[-1]
                    if self.enable_atr_stop:
                        self.atr_trailing_stop = 0.0
                        self._update_atr_trailing_stop(current_price)

    def _close_position_with_loss_tracking(self):
        """
        平仓并跟踪盈亏（用于止损保护）

        如果启用了止损保护，会跟踪连续亏损次数，并在达到阈值后暂停交易
        """
        if not self.position:
            return

        if not self.enable_loss_protection:
            self.position.close()
            self.atr_trailing_stop = 0.0
            return

        # 计算盈亏
        exit_price = self.data.Close[-1]
        is_loss = (self.position.is_long and exit_price < self.entry_price) or \
                  (self.position.is_short and exit_price > self.entry_price)

        # 平仓
        self.position.close()
        self.total_trades += 1

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
        # 清空 ATR 止损
        self.atr_trailing_stop = 0.0

    def _update_atr_trailing_stop(self, current_price: float):
        """
        根据当前仓位方向更新 ATR 动态止损线。
        """
        if not self.enable_atr_stop or self.atr_indicator is None or not self.position:
            return

        current_atr = self.atr_indicator[-1]
        if pd.isna(current_atr):
            return

        if self.position.is_long:
            stop_candidate = current_price - (current_atr * self.atr_multiplier)
            if not self.atr_trailing_stop:
                self.atr_trailing_stop = stop_candidate
            else:
                self.atr_trailing_stop = max(self.atr_trailing_stop, stop_candidate)
        else:
            stop_candidate = current_price + (current_atr * self.atr_multiplier)
            if not self.atr_trailing_stop:
                self.atr_trailing_stop = stop_candidate
            else:
                self.atr_trailing_stop = min(self.atr_trailing_stop, stop_candidate)


# 参数优化配置 - 基础参数
OPTIMIZE_PARAMS = {
    'n1': range(5, 51, 5),      # 短期均线: 5, 10, 15, ..., 50
    'n2': range(20, 201, 20),   # 长期均线: 20, 40, 60, ..., 200
}

# 参数优化配置 - 包含过滤器（用于测试过滤器效果）
OPTIMIZE_PARAMS_WITH_FILTERS = {
    'n1': range(5, 51, 5),
    'n2': range(20, 201, 20),
    'enable_slope_filter': [False, True],
    'enable_adx_filter': [False, True],
    'enable_volume_filter': [False, True],
    'enable_confirm_filter': [False, True],
}

# 参数约束: 短期均线必须小于长期均线
CONSTRAINTS = lambda p: p.n1 < p.n2


if __name__ == '__main__':
    """测试策略"""
    from backtesting import Backtest
    from backtesting.test import GOOG

    print("=" * 60)
    print("测试增强版双均线交叉策略")
    print("=" * 60)
    print()

    # 测试1: 不启用任何过滤器（应该和原版一样）
    print("测试1: 不启用任何过滤器")
    bt = Backtest(GOOG, SmaCrossEnhanced, cash=10000, commission=0.002)
    stats = bt.run()
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    # 测试2: 启用均线斜率过滤器
    print("测试2: 启用均线斜率过滤器")
    bt = Backtest(GOOG, SmaCrossEnhanced, cash=10000, commission=0.002)
    stats = bt.run(enable_slope_filter=True)
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
    print()

    # 测试3: 启用所有过滤器
    print("测试3: 启用所有过滤器")
    bt = Backtest(GOOG, SmaCrossEnhanced, cash=10000, commission=0.002)
    stats = bt.run(
        enable_slope_filter=True,
        enable_adx_filter=True,
        enable_volume_filter=True,
        enable_confirm_filter=True
    )
    print(f"  收益率: {stats['Return [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.2f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")
