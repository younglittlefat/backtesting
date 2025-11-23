"""
技术指标计算模块

实现ADX、波动率、动量等技术指标的计算
"""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """计算ADX (Average Directional Index) 趋势强度指标

    ADX衡量趋势强度（非方向），数值越高表示趋势越强。
    算法参考Wilder (1978) New Concepts in Technical Trading Systems

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: ADX计算周期，默认14

    Returns:
        ADX值序列，范围通常0-100

    References:
        Wilder, J. W. (1978). New Concepts in Technical Trading Systems
    """
    # 步骤1: 计算方向运动 (Directional Movement)
    plus_dm = high.diff()  # +DM = 今日高 - 昨日高
    minus_dm = -low.diff()  # -DM = 昨日低 - 今日低

    # 应用规则：负值归零
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    # 应用规则：只保留较大的那个方向
    plus_dm[(plus_dm <= minus_dm)] = 0
    minus_dm[(minus_dm < plus_dm)] = 0

    # 步骤2: 计算真实波幅 (True Range)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 步骤3: 平滑移动平均 (Wilder's smoothing)
    # 使用EWM模拟Wilder平滑，alpha = 1/period
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di_smooth = plus_dm.ewm(alpha=alpha, adjust=False).mean()
    minus_di_smooth = minus_dm.ewm(alpha=alpha, adjust=False).mean()

    # 步骤4: 计算方向指标 (Directional Indicator)
    plus_di = 100 * plus_di_smooth / atr
    minus_di = 100 * minus_di_smooth / atr

    # 步骤5: 计算DX (Directional Index)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)

    # 处理分母为0的情况
    dx = dx.replace([np.inf, -np.inf], 0)

    # 步骤6: 计算ADX (平滑DX)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    return adx


def calculate_volatility(
    returns: pd.Series, window: int = 252, min_periods: Optional[int] = None
) -> float:
    """计算年化波动率

    Args:
        returns: 日收益率序列
        window: 计算窗口（交易日），默认252天（1年）
        min_periods: 最少需要的数据点，默认为window

    Returns:
        年化波动率（标量），如果数据不足返回NaN

    Example:
        >>> close = pd.Series([100, 101, 99, 102, 98])
        >>> returns = close.pct_change()
        >>> vol = calculate_volatility(returns, window=3)
        >>> print(f"年化波动率: {vol:.2%}")
    """
    if min_periods is None:
        min_periods = window

    # 计算日收益率的标准差
    daily_vol = returns.rolling(window=window, min_periods=min_periods).std()

    # 年化：假设一年252个交易日
    annual_vol = daily_vol * np.sqrt(252)

    # 返回最新值
    return float(annual_vol.iloc[-1])


def calculate_momentum(
    close: pd.Series, periods: Optional[List[int]] = None
) -> Dict[str, float]:
    """计算多期动量

    动量定义为当前价格相对于N天前价格的涨跌幅

    Args:
        close: 收盘价序列
        periods: 动量周期列表，默认[63, 252]（3个月、12个月）

    Returns:
        动量字典，键为'{period}d'，值为动量值（百分比小数）

    Example:
        >>> close = pd.Series([100, 105, 110, 115, 120])
        >>> momentum = calculate_momentum(close, periods=[2, 4])
        >>> print(momentum)
        {'2d': 0.1304, '4d': 0.20}  # 13.04%和20%
    """
    if periods is None:
        periods = [63, 252]

    momentum = {}
    for p in periods:
        if len(close) < p + 1:
            # 数据不足，返回NaN
            momentum[f'{p}d'] = np.nan
        else:
            # 当前价格 / N天前价格 - 1
            momentum[f'{p}d'] = float(close.iloc[-1] / close.iloc[-p - 1] - 1)

    return momentum


def calculate_rolling_adx_mean(
    high: pd.Series, low: pd.Series, close: pd.Series, adx_period: int = 14, window: int = 250
) -> float:
    """计算ADX的滚动均值

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        adx_period: ADX计算周期，默认14
        window: 滚动窗口（交易日），默认250天

    Returns:
        ADX均值（标量），如果数据不足返回NaN
    """
    adx = calculate_adx(high, low, close, period=adx_period)

    # 计算最近window天的ADX均值
    if len(adx) < window:
        # 数据不足，使用全部数据
        adx_mean = adx.mean()
    else:
        adx_mean = adx.tail(window).mean()

    return float(adx_mean)


def calculate_trend_r2(
    close: pd.Series,
    window: int = 60,
    min_periods: Optional[int] = None
) -> float:
    """计算价格在指定窗口内对时间的回归R^2，衡量趋势的平滑程度。"""
    if min_periods is None:
        min_periods = int(window * 0.8)

    if len(close) < min_periods:
        return np.nan

    window_close = close.dropna().tail(window)
    if len(window_close) < min_periods:
        return np.nan

    log_prices = np.log(window_close.values)
    x = np.arange(len(log_prices))

    # 线性回归拟合
    slope, intercept = np.polyfit(x, log_prices, 1)
    fitted = slope * x + intercept

    # 计算R^2
    ss_res = np.sum((log_prices - fitted) ** 2)
    ss_tot = np.sum((log_prices - np.mean(log_prices)) ** 2)
    if ss_tot == 0:
        return np.nan

    r_squared = 1 - ss_res / ss_tot
    return float(np.clip(r_squared, 0.0, 1.0))


def calculate_excess_return(
    close: pd.Series,
    benchmark_close: Optional[pd.Series],
    period: int
) -> float:
    """计算相对于基准的超额收益率。"""
    if period <= 0:
        return np.nan

    def _simple_return(series: pd.Series) -> float:
        series = series.dropna()
        if len(series) <= period:
            return np.nan
        return float(series.iloc[-1] / series.iloc[-period - 1] - 1)

    if benchmark_close is None:
        return _simple_return(close)

    aligned = pd.concat(
        [close.rename('asset'), benchmark_close.rename('benchmark')],
        axis=1,
        join='inner'
    ).dropna()

    if len(aligned) <= period:
        return _simple_return(close)

    asset_return = aligned['asset'].iloc[-1] / aligned['asset'].iloc[-period - 1] - 1
    benchmark_return = aligned['benchmark'].iloc[-1] / aligned['benchmark'].iloc[-period - 1] - 1
    return float(asset_return - benchmark_return)


def calculate_volume_trend(
    volume: pd.Series,
    short_window: int = 20,
    long_window: int = 60,
    min_periods: Optional[int] = None
) -> float:
    """计算成交量趋势（短均量与长均量之比）。"""
    if min_periods is None:
        min_periods = min(short_window, long_window)

    if len(volume) < min_periods or long_window <= 0 or short_window <= 0:
        return np.nan

    short_mean = volume.tail(short_window).mean()
    long_mean = volume.tail(long_window).mean()

    if long_mean is None or long_mean <= 0:
        return np.nan

    return float(short_mean / long_mean)
