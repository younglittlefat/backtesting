"""
无偏技术指标计算模块

实现不直接暴露历史收益水平的技术指标，用于消除选择性偏差。

核心指标：
1. trend_consistency: 趋势一致性评分 - 衡量价格趋势的稳定性
2. price_efficiency: 价格发现效率 - 基于价量关系的效率评分

这些指标专注于市场结构特征，而非历史收益率本身。
"""
from typing import Optional, Tuple

import numpy as np
import pandas as pd


def calculate_trend_consistency(
    close: pd.Series,
    window: int = 63,
    min_periods: Optional[int] = None
) -> float:
    """
    计算趋势一致性评分

    趋势一致性衡量价格趋势的稳定性和单向性，而不依赖具体的涨跌幅度。
    高一致性表示价格呈现清晰的单向趋势（无论上涨或下跌），
    低一致性表示价格震荡或频繁反转。

    **理论依据**：
    趋势跟踪策略在趋势一致的市场中表现更好，因为：
    - 减少虚假信号和来回止损
    - 趋势持续时间更长，利润空间更大
    - 风险暴露更可控

    **无偏性说明**：
    本指标不使用收益率的绝对值，只关注趋势方向的稳定性，
    因此不会偏向"过去涨得好"或"跌得惨"的标的。

    Args:
        close: 收盘价序列
        window: 计算窗口，默认63天（约3个月）
        min_periods: 最少需要的数据点，默认为window的80%

    Returns:
        趋势一致性评分 (0-1)
        - 接近1: 趋势高度一致（强趋势）
        - 接近0.5: 趋势中性或震荡
        - 接近0: 趋势混乱或频繁反转

    Example:
        >>> close = pd.Series([100, 102, 104, 103, 105, 107, 106, 108])
        >>> score = calculate_trend_consistency(close, window=5)
        >>> print(f"趋势一致性: {score:.2f}")
    """
    if min_periods is None:
        min_periods = int(window * 0.8)

    if len(close) < min_periods:
        return np.nan

    # 计算日收益率
    returns = close.pct_change().dropna()

    if len(returns) < min_periods:
        return np.nan

    # === 维度1: 方向一致性 (Directional Consistency) ===
    # 计算正收益天数占比，转换为偏离中性的程度
    positive_ratio = (returns > 0).rolling(window, min_periods=min_periods).mean()
    # 将0.5-1映射到0-1（0.5为中性，1为完全一致）
    directional_consistency = (positive_ratio - 0.5).abs() * 2

    # === 维度2: 价格单调性 (Price Monotonicity) ===
    # 评估价格相对历史位置的单调性
    def monotonicity_score(x):
        """计算价格序列的单调性"""
        if len(x) < 2:
            return 0.5
        # 当前价格超过历史价格的比例
        current_price = x.iloc[-1]
        historical_prices = x.iloc[:-1]
        higher_than_ratio = np.sum(current_price >= historical_prices) / len(historical_prices)
        # 将0-1映射到偏离0.5的程度
        return abs(higher_than_ratio - 0.5) * 2

    price_monotonicity = close.rolling(window, min_periods=min_periods).apply(
        monotonicity_score, raw=False
    )

    # === 维度3: 趋势持续性 (Trend Persistence) ===
    # 计算连续同向天数的平均占比
    sign_changes = (returns.rolling(2).apply(lambda x: x.iloc[0] * x.iloc[1] < 0, raw=False))
    change_frequency = sign_changes.rolling(window, min_periods=min_periods).mean()
    # 反转频率越低，持续性越高
    trend_persistence = 1 - change_frequency

    # === 综合评分 ===
    # 三个维度的加权平均
    weights = {
        'directional': 0.4,   # 方向一致性权重最高
        'monotonicity': 0.3,  # 价格单调性次之
        'persistence': 0.3    # 持续性
    }

    # 对齐三个指标的长度
    min_len = min(
        len(directional_consistency.dropna()),
        len(price_monotonicity.dropna()),
        len(trend_persistence.dropna())
    )

    if min_len == 0:
        return np.nan

    # 取最近的有效值进行综合
    final_score = (
        weights['directional'] * float(directional_consistency.iloc[-1]) +
        weights['monotonicity'] * float(price_monotonicity.iloc[-1]) +
        weights['persistence'] * float(trend_persistence.iloc[-1])
    )

    # 确保返回值在0-1之间
    final_score = np.clip(final_score, 0.0, 1.0)

    return float(final_score)


def calculate_price_efficiency(
    close: pd.Series,
    volume: pd.Series,
    window: int = 252,
    min_periods: Optional[int] = None
) -> float:
    """
    计算价格发现效率评分

    价格效率衡量ETF价格变动与成交量之间的关系健康度，
    以及价格序列的平滑程度。高效的价格发现意味着：
    - 价格对信息的反应及时且平稳
    - 成交量与价格变动匹配良好
    - 价格跳跃和异常波动较少

    **理论依据**：
    - 市场微观结构理论：流动性好的市场价格发现更有效
    - 价格效率高的ETF更适合趋势跟踪，因为噪音少、信号清晰

    **无偏性说明**：
    本指标关注价格形成机制的质量，而非价格涨跌方向，
    因此不会偏向历史收益高的标的。

    Args:
        close: 收盘价序列
        volume: 成交量序列
        window: 计算窗口，默认252天（约1年）
        min_periods: 最少需要的数据点，默认为window的80%

    Returns:
        价格效率评分 (0-1)
        - 接近1: 价格发现高效，适合交易
        - 接近0: 价格噪音大，效率低

    Example:
        >>> close = pd.Series([100, 102, 101, 103, 105])
        >>> volume = pd.Series([1000, 1200, 900, 1100, 1300])
        >>> score = calculate_price_efficiency(close, volume, window=4)
        >>> print(f"价格效率: {score:.2f}")
    """
    if min_periods is None:
        min_periods = int(window * 0.8)

    if len(close) < min_periods or len(volume) < min_periods:
        return np.nan

    # 确保数据长度一致
    if len(close) != len(volume):
        # 对齐索引
        common_index = close.index.intersection(volume.index)
        close = close.loc[common_index]
        volume = volume.loc[common_index]

    if len(close) < min_periods:
        return np.nan

    # 计算收益率
    returns = close.pct_change().dropna()
    volume_aligned = volume.iloc[1:].reset_index(drop=True)  # 对齐长度
    returns_aligned = returns.reset_index(drop=True)

    if len(returns_aligned) < min_periods:
        return np.nan

    # === 维度1: 成交量-收益率协调性 (Volume-Return Coordination) ===
    # 理想情况：大的价格变动伴随大的成交量（信息驱动）
    # 计算成交量与收益率绝对值的相关性
    abs_returns = returns_aligned.abs()

    # 滚动相关性计算
    def rolling_corr(x, y, window, min_periods):
        """计算滚动相关系数"""
        corr_series = pd.Series(index=x.index, dtype=float)
        for i in range(len(x)):
            if i < min_periods - 1:
                corr_series.iloc[i] = np.nan
            else:
                start_idx = max(0, i - window + 1)
                x_window = x.iloc[start_idx:i+1]
                y_window = y.iloc[start_idx:i+1]
                if len(x_window) >= min_periods:
                    corr_series.iloc[i] = x_window.corr(y_window)
        return corr_series

    volume_return_corr = rolling_corr(
        abs_returns, volume_aligned,
        window=min(window, len(abs_returns)),
        min_periods=min_periods
    )

    # 取绝对值并标准化（正相关或负相关都表示协调）
    coord_score = volume_return_corr.abs().iloc[-1] if not pd.isna(volume_return_corr.iloc[-1]) else 0.0

    # === 维度2: 价格跳跃频率 (Price Jump Frequency) ===
    # 价格跳跃定义：收益率超过滚动标准差的2倍
    rolling_std = returns_aligned.rolling(20, min_periods=10).std()
    price_jumps = (returns_aligned.abs() > rolling_std * 2)

    jump_frequency = price_jumps.rolling(
        window=min(window, len(price_jumps)),
        min_periods=min_periods
    ).mean()

    # 跳跃频率越低，效率越高
    jump_efficiency = 1 - jump_frequency.iloc[-1] if not pd.isna(jump_frequency.iloc[-1]) else 0.5

    # === 维度3: 价格平滑度 (Price Smoothness) ===
    # 使用收益率的变异系数（CV）衡量波动的规律性
    # 较小的CV表示波动更可预测，价格发现更平稳
    returns_mean = returns_aligned.rolling(
        window=min(window, len(returns_aligned)),
        min_periods=min_periods
    ).mean()
    returns_std = returns_aligned.rolling(
        window=min(window, len(returns_aligned)),
        min_periods=min_periods
    ).std()

    # 避免除零
    cv = returns_std / (returns_mean.abs() + 1e-6)
    # CV越小越好，使用sigmoid函数映射到0-1
    # 典型CV在0.1-10之间，我们将CV=1映射到0.5
    smoothness_score = 1 / (1 + cv.iloc[-1]) if not pd.isna(cv.iloc[-1]) else 0.5

    # === 维度4: 价差稳定性 (Spread Stability) ===
    # 使用高低价差占收盘价的比例作为隐含价差的代理
    # 注意：这里我们没有日内高低价，用窗口内最大最小值代替
    rolling_high = close.rolling(20, min_periods=10).max()
    rolling_low = close.rolling(20, min_periods=10).min()
    implied_spread = (rolling_high - rolling_low) / close

    # 价差的稳定性：标准差越小越好
    spread_std = implied_spread.rolling(
        window=min(window, len(implied_spread)),
        min_periods=min_periods
    ).std()

    # 使用sigmoid映射：spread_std典型值在0.001-0.1之间
    spread_stability = 1 / (1 + spread_std.iloc[-1] * 20) if not pd.isna(spread_std.iloc[-1]) else 0.5

    # === 综合评分 ===
    weights = {
        'coordination': 0.35,   # 成交量协调性权重最高
        'jump_efficiency': 0.25,  # 跳跃频率
        'smoothness': 0.20,     # 价格平滑度
        'spread_stability': 0.20  # 价差稳定性
    }

    final_score = (
        weights['coordination'] * coord_score +
        weights['jump_efficiency'] * jump_efficiency +
        weights['smoothness'] * smoothness_score +
        weights['spread_stability'] * spread_stability
    )

    # 确保返回值在0-1之间
    final_score = np.clip(final_score, 0.0, 1.0)

    return float(final_score)


def calculate_liquidity_score(
    volume: pd.Series,
    close: pd.Series,
    window: int = 30,
    min_periods: Optional[int] = None
) -> float:
    """
    计算流动性评分

    基于成交量和价格的稳定性计算标准化的流动性评分。

    Args:
        volume: 成交量序列
        close: 收盘价序列
        window: 计算窗口，默认30天
        min_periods: 最少需要的数据点

    Returns:
        流动性评分 (0-1)
    """
    if min_periods is None:
        min_periods = int(window * 0.8)

    if len(volume) < min_periods:
        return np.nan

    # 成交额 = 成交量 * 价格
    turnover = volume * close

    # 计算平均成交额
    avg_turnover = turnover.rolling(window, min_periods=min_periods).mean()

    # 计算成交额的稳定性（变异系数的倒数）
    turnover_std = turnover.rolling(window, min_periods=min_periods).std()
    turnover_cv = turnover_std / (avg_turnover + 1e-6)

    # 稳定性评分：CV越小越好
    stability_score = 1 / (1 + turnover_cv.iloc[-1]) if not pd.isna(turnover_cv.iloc[-1]) else 0.5

    # 规模评分：使用log标准化
    # 假设10万元为基准（log10(100000) ≈ 5）
    size_score = np.log10(avg_turnover.iloc[-1] + 1) / 10.0 if not pd.isna(avg_turnover.iloc[-1]) else 0.0
    size_score = np.clip(size_score, 0.0, 1.0)

    # 综合评分
    final_score = 0.6 * size_score + 0.4 * stability_score

    return float(final_score)


def normalize_score(
    score: float,
    min_val: float = 0.0,
    max_val: float = 1.0
) -> float:
    """
    标准化评分到0-1区间

    Args:
        score: 原始评分
        min_val: 原始评分的最小值
        max_val: 原始评分的最大值

    Returns:
        标准化后的评分 (0-1)
    """
    if np.isnan(score):
        return np.nan

    if max_val <= min_val:
        return 0.5

    normalized = (score - min_val) / (max_val - min_val)
    return float(np.clip(normalized, 0.0, 1.0))


def calculate_all_unbiased_indicators(
    close: pd.Series,
    volume: pd.Series,
    trend_window: int = 63,
    efficiency_window: int = 252,
    liquidity_window: int = 30
) -> dict:
    """
    批量计算所有无偏指标

    Args:
        close: 收盘价序列
        volume: 成交量序列
        trend_window: 趋势一致性计算窗口
        efficiency_window: 价格效率计算窗口
        liquidity_window: 流动性评分计算窗口

    Returns:
        包含所有指标的字典
    """
    indicators = {}

    try:
        indicators['trend_consistency'] = calculate_trend_consistency(
            close, window=trend_window
        )
    except Exception as e:
        indicators['trend_consistency'] = np.nan
        print(f"Warning: Failed to calculate trend_consistency: {e}")

    try:
        indicators['price_efficiency'] = calculate_price_efficiency(
            close, volume, window=efficiency_window
        )
    except Exception as e:
        indicators['price_efficiency'] = np.nan
        print(f"Warning: Failed to calculate price_efficiency: {e}")

    try:
        indicators['liquidity_score'] = calculate_liquidity_score(
            volume, close, window=liquidity_window
        )
    except Exception as e:
        indicators['liquidity_score'] = np.nan
        print(f"Warning: Failed to calculate liquidity_score: {e}")

    return indicators
