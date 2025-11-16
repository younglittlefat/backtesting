"""
KAMA自适应均线交叉策略 (KAMA Adaptive Moving Average Crossover Strategy)

KAMA（Kaufman's Adaptive Moving Average）是一个智能的技术指标，能够根据市场效率
自动调整其响应速度：
- 趋势期间：快速跟随价格变化，减少滞后
- 震荡期间：平滑滤波，减少假信号
- 自适应性：无需人工调整参数，系统自动适应市场状态

策略逻辑:
- 价格从下方突破KAMA线 -> 买入信号（金叉）
- 价格从上方跌破KAMA线 -> 卖出信号（死叉）
- 所有信号必须通过启用的过滤器

Phase 1 功能 ✅:
- KAMA指标计算
- 基础交易信号生成
- 效率比率过滤器
- KAMA斜率确认

Phase 2 功能 ✅:
- ADX趋势强度过滤器（enable_adx_filter）
- 成交量确认过滤器（enable_volume_filter）
- 价格斜率过滤器（enable_slope_filter）
- 持续确认过滤器（enable_confirm_filter）

Phase 3 功能 ✅:
- 连续止损保护（enable_loss_protection）
- 完整的盈亏跟踪和暂停机制

未来扩展（Phase 4）:
- 跟踪止损
- 多周期确认机制
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
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


def calculate_kama(prices, period=20, fastest_period=2, slowest_period=30):
    """
    计算KAMA (Kaufman's Adaptive Moving Average) 指标

    KAMA通过效率比率自适应调整平滑常数，在趋势期快速响应，在震荡期平滑滤波。

    算法步骤:
    1. 计算效率比率 (Efficiency Ratio, ER)
    2. 计算自适应平滑常数 (Smoothing Constant, SC)
    3. 递推计算KAMA值

    Args:
        prices: 价格序列 (pandas.Series or array-like)
        period: 效率比率计算周期 (default: 20)
        fastest_period: 快速平滑周期 (default: 2)
        slowest_period: 慢速平滑周期 (default: 30)

    Returns:
        pandas.Series: KAMA指标值序列
    """
    prices = pd.Series(prices)
    n = len(prices)

    # 参数验证
    if fastest_period >= slowest_period:
        raise ValueError("fastest_period必须小于slowest_period")

    if period < 2:
        raise ValueError("period必须至少为2")

    # 初始化结果序列
    kama = pd.Series(index=prices.index, dtype=float)
    efficiency_ratio = pd.Series(index=prices.index, dtype=float)

    # 计算平滑常数
    fastest_sc = 2.0 / (fastest_period + 1)  # 快速EMA平滑常数
    slowest_sc = 2.0 / (slowest_period + 1)  # 慢速EMA平滑常数

    # KAMA初始值：使用第一个有效价格
    first_valid_idx = period
    if first_valid_idx >= n:
        return kama  # 返回全NaN序列

    kama.iloc[first_valid_idx] = prices.iloc[first_valid_idx]

    # 逐步计算KAMA
    for i in range(first_valid_idx + 1, n):
        # 1. 计算效率比率 (ER)
        # Change = abs(当前价格 - period期前价格)
        change = abs(prices.iloc[i] - prices.iloc[i - period])

        # Volatility = sum(abs(相邻价格变化))，过去period期
        volatility = 0
        for j in range(i - period + 1, i + 1):
            volatility += abs(prices.iloc[j] - prices.iloc[j - 1])

        # ER = Change / Volatility （处理分母为0的情况）
        if volatility == 0:
            er = 0  # 价格无变化，设ER为0（最平滑）
        else:
            er = change / volatility

        efficiency_ratio.iloc[i] = er

        # 2. 计算自适应平滑常数 (SC)
        # SC = [ER * (fastest_SC - slowest_SC) + slowest_SC]^2
        sc = er * (fastest_sc - slowest_sc) + slowest_sc
        sc = sc * sc  # 平方处理，增加非线性响应

        # 3. 计算KAMA值
        # KAMA[today] = KAMA[yesterday] + SC * (Price - KAMA[yesterday])
        kama.iloc[i] = kama.iloc[i - 1] + sc * (prices.iloc[i] - kama.iloc[i - 1])

    return kama


def calculate_efficiency_ratio(prices, period=20):
    """
    单独计算效率比率，用于信号过滤

    Args:
        prices: 价格序列
        period: 计算周期

    Returns:
        pandas.Series: 效率比率序列 (0-1之间)
    """
    prices = pd.Series(prices)
    n = len(prices)

    efficiency_ratio = pd.Series(index=prices.index, dtype=float)

    for i in range(period, n):
        # Change = abs(当前价格 - period期前价格)
        change = abs(prices.iloc[i] - prices.iloc[i - period])

        # Volatility = sum(abs(相邻价格变化))
        volatility = 0
        for j in range(i - period + 1, i + 1):
            volatility += abs(prices.iloc[j] - prices.iloc[j - 1])

        # ER = Change / Volatility
        if volatility == 0:
            er = 0
        else:
            er = change / volatility

        efficiency_ratio.iloc[i] = er

    return efficiency_ratio


def calculate_slope(series, lookback=3):
    """
    计算序列的斜率（线性趋势方向）

    Args:
        series: 数据序列
        lookback: 回溯期数

    Returns:
        pandas.Series: 斜率序列（正数=上升，负数=下降）
    """
    series = pd.Series(series)
    slopes = pd.Series(index=series.index, dtype=float)

    for i in range(lookback, len(series)):
        # 使用最小二乘法计算斜率
        y = series.iloc[i-lookback+1:i+1].values
        x = np.arange(len(y))

        # 斜率 = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        n = len(y)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator != 0:
            slope = (n * sum_xy - sum_x * sum_y) / denominator
        else:
            slope = 0

        slopes.iloc[i] = slope

    return slopes


class KamaCrossStrategy(BaseEnhancedStrategy):
    """
    KAMA自适应均线交叉策略

    Phase 1功能 ✅:
    - KAMA指标计算
    - 基础交易信号（价格与KAMA交叉）
    - 效率比率过滤器（避免震荡市假信号）
    - KAMA斜率确认（确保趋势方向）

    Phase 2功能 ✅:
    - ADX趋势强度过滤器
    - 成交量确认过滤器
    - 价格斜率过滤器
    - 持续确认过滤器

    Phase 3功能 ✅:
    - 连续止损保护
    - 完整的盈亏跟踪和暂停机制

    参数:
        # KAMA核心参数
        kama_period: KAMA计算周期 (default: 20)
        kama_fast: 快速平滑周期 (default: 2)
        kama_slow: 慢速平滑周期 (default: 30)

        # Phase 1信号增强参数
        enable_efficiency_filter: 启用效率比率过滤 (default: True)
        min_efficiency_ratio: 最小效率比率阈值 (default: 0.3)
        enable_slope_confirmation: 启用KAMA斜率确认 (default: True)
        min_slope_periods: KAMA斜率确认周期 (default: 3)

        # Phase 2通用过滤器
        enable_slope_filter: 启用价格斜率过滤器 (default: False) ⭐推荐
        enable_adx_filter: 启用ADX趋势强度过滤器 (default: False) ⭐推荐
        enable_volume_filter: 启用成交量确认过滤器 (default: False) ⭐推荐
        enable_confirm_filter: 启用持续确认过滤器 (default: False)

        # Phase 2过滤器参数（继承自BaseEnhancedStrategy，可覆盖）
        slope_lookback: 斜率计算回溯期 (default: 5)
        adx_period: ADX计算周期 (default: 14)
        adx_threshold: ADX阈值 (default: 25)
        volume_period: 成交量均值周期 (default: 20)
        volume_ratio: 成交量放大倍数 (default: 1.2)
        confirm_bars: 确认所需K线数 (default: 3)

        # Phase 3止损保护参数（继承自BaseEnhancedStrategy）
        enable_loss_protection: 启用连续止损保护 (default: False) ⭐推荐
        max_consecutive_losses: 连续亏损次数阈值 (default: 3)
        pause_bars: 暂停交易K线数 (default: 10)

    注意: 此策略继承自 BaseEnhancedStrategy，自动获得所有增强功能
    """

    # KAMA核心参数
    kama_period = 20
    kama_fast = 2
    kama_slow = 30

    # Phase 1信号增强参数
    enable_efficiency_filter = False
    min_efficiency_ratio = 0.3
    enable_slope_confirmation = False
    min_slope_periods = 3

    # Phase 2通用过滤器开关（继承自BaseEnhancedStrategy，可启用）
    enable_slope_filter = False
    enable_adx_filter = False
    enable_volume_filter = False
    enable_confirm_filter = False

    # Phase 2过滤器参数（继承自BaseEnhancedStrategy，可覆盖）
    slope_lookback = 5
    adx_period = 14
    adx_threshold = 25
    volume_period = 20
    volume_ratio = 1.2
    confirm_bars = 0  # 默认不启用持续确认（与 enable_confirm_filter=False 保持一致）

    # Phase 3止损保护开关（继承自BaseEnhancedStrategy，可启用）
    enable_loss_protection = False

    # Phase 3止损保护参数（基于实验推荐值）
    max_consecutive_losses = 3
    pause_bars = 10

    # 调试开关
    debug_loss_protection = False

    def init(self):
        """策略初始化：计算所需指标和初始化过滤器"""

        # 计算KAMA指标
        self.kama = self.I(
            calculate_kama,
            self.data.Close,
            self.kama_period,
            self.kama_fast,
            self.kama_slow,
            name='KAMA'
        )

        # 计算效率比率（用于Phase 1过滤器）
        self.efficiency_ratio = self.I(
            calculate_efficiency_ratio,
            self.data.Close,
            self.kama_period,
            name='EfficiencyRatio'
        )

        # 计算KAMA斜率（用于Phase 1趋势确认）
        self.kama_slope = self.I(
            calculate_slope,
            self.kama,
            self.min_slope_periods,
            name='KamaSlope'
        )

        # Phase 2: 初始化通用过滤器
        self.slope_filter = SlopeFilter(
            enabled=self.enable_slope_filter,
            lookback=self.slope_lookback,
            require_both=False  # KAMA策略不需要两条均线，只关注价格斜率
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

        # 初始化止损保护状态（Phase 3功能）
        self.entry_price = 0  # 入场价格
        self.consecutive_losses = 0  # 连续亏损计数
        self.paused_until_bar = -1  # 暂停到第几根K线
        self.current_bar = 0  # 当前K线计数
        self.total_trades = 0  # 交易总数
        self.triggered_pauses = 0  # 触发暂停次数

        # 调试输出
        if self.enable_loss_protection and self.debug_loss_protection:
            print(f"[KAMA止损保护] 已启用: max_consecutive_losses={self.max_consecutive_losses}, pause_bars={self.pause_bars}")

    def next(self):
        """策略主逻辑：生成交易信号"""

        # Phase 3: 检查止损保护状态
        if self.enable_loss_protection:
            self.current_bar += 1
            # 检查是否在暂停期
            if self.current_bar < self.paused_until_bar:
                return  # 暂停期内不交易

        # 获取当前数据
        current_price = self.data.Close[-1]
        current_kama = self.kama[-1]

        # 检查数据有效性
        if pd.isna(current_kama):
            return

        # Phase 1: 基础交叉信号
        # 买入信号：价格从下方突破KAMA线
        buy_signal = crossover(self.data.Close, self.kama)
        # 卖出信号：价格从上方跌破KAMA线
        sell_signal = crossover(self.kama, self.data.Close)

        # Phase 1: KAMA特有过滤器与基础有效性开关
        signal_valid = True

        # 1) 效率比率过滤器
        # 说明：当启用“持续确认”时，实际建仓通常发生在金叉之后的第N根K线上。
        # 因此应在“触发入场”的当根重新检查过滤条件，而不是仅在发生金叉的当根检查。
        if self.enable_efficiency_filter:
            if buy_signal or self.enable_confirm_filter:
                current_er = self.efficiency_ratio[-1]
                if pd.isna(current_er) or current_er < self.min_efficiency_ratio:
                    signal_valid = False

        # 2) KAMA斜率确认过滤器（同上，入场当根需满足条件）
        if self.enable_slope_confirmation:
            if buy_signal or self.enable_confirm_filter:
                current_slope = self.kama_slope[-1]
                if pd.isna(current_slope) or current_slope <= 0:
                    signal_valid = False

        # -------------------------
        # 持续确认逻辑（修复：原实现仅在金叉当根检查，导致 confirm_bars>1 永不入场）
        # 现在定义“入场候选信号”为：
        #   - 未启用持续确认：金叉当根
        #   - 启用持续确认：过去 confirm_bars 根内发生过一次金叉，且最近 confirm_bars 根都满足 Close>KAMA
        # 这样会在金叉后的第 confirm_bars 根才入场，符合“持续确认”的预期语义。
        # -------------------------
        entry_signal = False
        if self.enable_confirm_filter and self.confirm_bars and self.confirm_bars > 1:
            n = int(self.confirm_bars)
            # 连续 n 根收盘价在 KAMA 之上（包含当前这根）
            consecutive_above = True
            for i in range(1, n + 1):
                c = self.data.Close[-i]
                k = self.kama[-i]
                if pd.isna(c) or pd.isna(k) or c <= k:
                    consecutive_above = False
                    break
            # 最近 n 根内是否出现过一次“上穿”（金叉）
            recent_cross = False
            # 检查[-n, -1]这 n 根内是否有一次从下到上
            # 条件：上一根在下方，这一根在上方
            for i in range(1, n + 1):
                prev_c = self.data.Close[-(i + 1)]
                prev_k = self.kama[-(i + 1)]
                cur_c = self.data.Close[-i]
                cur_k = self.kama[-i]
                if (not pd.isna(prev_c) and not pd.isna(prev_k) and
                        not pd.isna(cur_c) and not pd.isna(cur_k) and
                        prev_c <= prev_k and cur_c > cur_k):
                    recent_cross = True
                    break
            entry_signal = consecutive_above and recent_cross
        else:
            # 未启用持续确认或 confirm_bars<=1，沿用“金叉当根入场”
            entry_signal = buy_signal

        # Phase 2: 通用过滤器集成（入场当根检查）
        if signal_valid and entry_signal:
            # 3) 价格斜率过滤器（使用收盘价作为短均线，KAMA作为长均线）
            if self.slope_filter.enabled:
                if not self.slope_filter.filter_signal(
                    self, 'buy',
                    sma_short=self.data.Close,
                    sma_long=self.kama
                ):
                    signal_valid = False

            # 4) ADX趋势强度过滤器
            if self.adx_filter.enabled:
                if not self.adx_filter.filter_signal(self, 'buy'):
                    signal_valid = False

            # 5) 成交量确认过滤器
            if self.volume_filter.enabled:
                if not self.volume_filter.filter_signal(self, 'buy'):
                    signal_valid = False

        # 执行交易决策
        if entry_signal and signal_valid and not self.position:
            self.buy()
            # 记录入场价格
            if self.enable_loss_protection:
                self.entry_price = self.data.Close[-1]
                if self.debug_loss_protection:
                    print(f"[KAMA止损保护] Bar {self.current_bar}: 买入 @ {self.entry_price:.4f}")
        elif sell_signal and self.position:
            self._close_position_with_loss_tracking()

    def _close_position_with_loss_tracking(self):
        """
        平仓并跟踪盈亏（用于止损保护）

        如果启用了止损保护，会跟踪连续亏损次数，并在达到阈值后暂停交易
        """
        if not self.enable_loss_protection or not self.position:
            self.position.close()
            return

        # 计算盈亏
        exit_price = self.data.Close[-1]
        is_loss = (self.position.is_long and exit_price < self.entry_price) or \
                  (self.position.is_short and exit_price > self.entry_price)

        # 平仓
        self.position.close()
        self.total_trades += 1

        # 更新连续亏损计数
        if is_loss:
            self.consecutive_losses += 1
            if self.debug_loss_protection:
                print(f"[KAMA止损保护] Bar {self.current_bar}: 亏损交易 #{self.total_trades} (连续亏损: {self.consecutive_losses}/{self.max_consecutive_losses})")

            if self.consecutive_losses >= self.max_consecutive_losses:
                # 达到连续亏损阈值，启动暂停期
                self.paused_until_bar = self.current_bar + self.pause_bars
                self.consecutive_losses = 0  # 重置计数
                self.triggered_pauses += 1
                if self.debug_loss_protection:
                    print(f"[KAMA止损保护] ⚠️ 触发暂停 #{self.triggered_pauses}: Bar {self.current_bar} → {self.paused_until_bar} (暂停{self.pause_bars}根K线)")
        else:
            # 盈利则重置连续亏损计数
            self.consecutive_losses = 0
            if self.debug_loss_protection:
                print(f"[KAMA止损保护] Bar {self.current_bar}: 盈利交易 #{self.total_trades} (重置连续亏损)")

        # 重置入场价格
        self.entry_price = 0

    def get_runtime_config(self):
        """扩展运行时配置，添加KAMA特有参数"""
        config = super().get_runtime_config()
        config["strategy_specific"] = {
            "kama_period": self.kama_period,
            "kama_fast": self.kama_fast,
            "kama_slow": self.kama_slow,
            "enable_efficiency_filter": self.enable_efficiency_filter,
            "min_efficiency_ratio": self.min_efficiency_ratio,
            "enable_slope_confirmation": self.enable_slope_confirmation,
            "min_slope_periods": self.min_slope_periods,
        }
        return config

    def get_runtime_config_schema(self):
        """扩展配置结构定义，添加KAMA参数验证规则"""
        schema = super().get_runtime_config_schema()
        schema["strategy_specific"] = {
            "kama_period": {"type": "int", "default": 20, "range": [5, 50]},
            "kama_fast": {"type": "int", "default": 2, "range": [2, 10]},
            "kama_slow": {"type": "int", "default": 30, "range": [15, 100]},
            "enable_efficiency_filter": {"type": "bool", "default": True},
            "min_efficiency_ratio": {"type": "float", "default": 0.3, "range": [0.0, 1.0]},
            "enable_slope_confirmation": {"type": "bool", "default": True},
            "min_slope_periods": {"type": "int", "default": 3, "range": [2, 10]},
        }
        return schema


# Optimization configuration for Backtest.optimize()
# Backtest runner will import these at module level instead of assuming n1/n2.
# Keep the search space modest to avoid very long runs by default.
OPTIMIZE_PARAMS = {
    # KAMA core parameters
    "kama_period": range(10, 31, 5),   # 10, 15, 20, 25, 30
    "kama_fast": range(2, 7, 1),       # 2..6
    "kama_slow": range(20, 61, 10),    # 20, 30, 40, 50, 60
    # Strategy-specific filters can be toggled via CLI; we don't sweep them here by default.
}
# Constraints: fastest smoothing period must be strictly less than slowest.
CONSTRAINTS = lambda p: (p.kama_fast < p.kama_slow)


if __name__ == '__main__':
    """
    简单测试脚本，验证KAMA计算正确性
    """
    # 创建测试数据
    test_prices = pd.Series([
        10.0, 10.5, 11.0, 10.8, 10.9, 11.2, 11.5, 11.3, 11.1, 11.4,
        11.8, 12.0, 11.9, 12.1, 12.3, 12.5, 12.2, 12.4, 12.6, 12.8,
        13.0, 12.9, 13.1, 13.3, 13.5, 13.2, 13.4, 13.6, 13.8, 14.0
    ])

    print("=== KAMA指标计算测试 ===")

    # 测试KAMA计算
    try:
        kama = calculate_kama(test_prices, period=10, fastest_period=2, slowest_period=20)
        print("✅ KAMA计算成功")
        print(f"KAMA前5个有效值: {kama.dropna().head().round(4).tolist()}")
        print(f"KAMA后5个值: {kama.tail().round(4).tolist()}")
    except Exception as e:
        print(f"❌ KAMA计算失败: {e}")

    # 测试效率比率计算
    try:
        er = calculate_efficiency_ratio(test_prices, period=10)
        print("✅ 效率比率计算成功")
        print(f"效率比率后5个值: {er.tail().round(4).tolist()}")
    except Exception as e:
        print(f"❌ 效率比率计算失败: {e}")

    # 测试斜率计算
    try:
        slopes = calculate_slope(kama, lookback=3)
        print("✅ 斜率计算成功")
        print(f"KAMA斜率后5个值: {slopes.tail().round(6).tolist()}")
    except Exception as e:
        print(f"❌ 斜率计算失败: {e}")

    print("\n=== 测试完成 ===")
