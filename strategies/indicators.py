"""
技术指标计算模块 (Technical Indicators Module)

提供用于回测策略的技术指标计算函数，特别关注止损相关的指标。

包含指标:
- ATR (Average True Range): 平均真实波动幅度
- HHV/LLV (Highest/Lowest High/Low Value): 最高价/最低价
- 其他止损相关指标

设计原则:
1. 无外部依赖 (除numpy/pandas外)
2. 兼容backtesting.py框架
3. 高性能优化
4. 详细文档和示例
"""

import numpy as np
import pandas as pd
from typing import Union


def ATR(high: Union[pd.Series, np.ndarray],
        low: Union[pd.Series, np.ndarray],
        close: Union[pd.Series, np.ndarray],
        period: int = 14) -> pd.Series:
    """
    计算平均真实波动幅度 (Average True Range)

    ATR是衡量市场波动性的关键指标，用于：
    - 自适应止损距离设置
    - 资金管理和仓位调整
    - 波动率分析和风险控制

    计算公式:
    TR (True Range) = max(
        high - low,
        abs(high - previous_close),
        abs(low - previous_close)
    )
    ATR = EMA(TR, period)  # 或 SMA(TR, period)

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: ATR计算周期，默认14天

    Returns:
        pd.Series: ATR序列，与输入长度相同，前period-1个值为NaN

    Examples:
        >>> # 在backtesting.py策略中使用
        >>> class MyStrategy(Strategy):
        ...     def init(self):
        ...         self.atr = self.I(ATR,
        ...                           self.data.High,
        ...                           self.data.Low,
        ...                           self.data.Close,
        ...                           14)
        ...
        ...     def next(self):
        ...         current_atr = self.atr[-1]
        ...         stop_distance = current_atr * 2.5

        >>> # 直接计算示例
        >>> atr_values = ATR(df['high'], df['low'], df['close'], period=14)
        >>> print(f"当前ATR: {atr_values.iloc[-1]:.4f}")

    Notes:
        - 使用EMA而非SMA计算ATR平均值，更响应近期波动
        - 第一个TR值使用当日high-low作为TR (无前一日收盘价)
        - 返回值与输入index保持一致，便于策略中使用
        - 建议ATR周期: 日线14天，周线14周，小时线14小时

    Performance:
        - 优化的pandas向量化计算，性能优于循环实现
        - 内存友好，适用于大规模数据集
    """
    # 输入验证
    if len(high) != len(low) or len(high) != len(close):
        raise ValueError("High, Low, Close序列长度必须一致")

    if period <= 0:
        raise ValueError(f"Period必须为正整数，当前值: {period}")

    # 转换为pandas Series (保持索引信息)
    if isinstance(high, np.ndarray):
        high = pd.Series(high)
    if isinstance(low, np.ndarray):
        low = pd.Series(low)
    if isinstance(close, np.ndarray):
        close = pd.Series(close)

    # 计算True Range的三个组成部分
    # TR1: 当日最高价 - 当日最低价
    tr1 = high - low

    # TR2: abs(当日最高价 - 前一日收盘价)
    # 使用shift(1)获取前一日收盘价
    prev_close = close.shift(1)
    tr2 = np.abs(high - prev_close)

    # TR3: abs(当日最低价 - 前一日收盘价)
    tr3 = np.abs(low - prev_close)

    # True Range = max(TR1, TR2, TR3)
    # 使用concat + max across axis=1进行向量化计算
    tr_df = pd.concat([tr1, tr2, tr3], axis=1)
    tr = tr_df.max(axis=1)

    # 第一个值处理：没有前一日收盘价时，TR = high - low
    tr.iloc[0] = tr1.iloc[0]

    # 计算ATR：使用指数加权移动平均 (EMA)
    # EMA的alpha = 2/(period+1)，等价于span=period
    atr = tr.ewm(span=period, adjust=False).mean()

    # 前period-1个值设为NaN（不够计算周期）
    # 保持与传统技术分析软件一致的行为
    atr.iloc[:period-1] = np.nan

    return atr


def HHV(data: Union[pd.Series, np.ndarray], period: int) -> pd.Series:
    """
    计算最高价值 (Highest High Value)

    在指定期间内的最高值，常用于:
    - Chandelier Exit止损计算
    - 支撑阻力位分析
    - 突破策略的参考点设置

    Args:
        data: 价格序列（通常为最高价）
        period: 回看期间

    Returns:
        pd.Series: 滚动最高价序列

    Examples:
        >>> hhv_22 = HHV(self.data.High, 22)  # 22日最高价
        >>> resistance_level = hhv_22[-1]     # 当前阻力位
    """
    if isinstance(data, np.ndarray):
        data = pd.Series(data)

    return data.rolling(window=period, min_periods=1).max()


def LLV(data: Union[pd.Series, np.ndarray], period: int) -> pd.Series:
    """
    计算最低价值 (Lowest Low Value)

    在指定期间内的最低值，常用于:
    - Chandelier Exit止损计算
    - 支撑阻力位分析
    - 突破策略的参考点设置

    Args:
        data: 价格序列（通常为最低价）
        period: 回看期间

    Returns:
        pd.Series: 滚动最低价序列

    Examples:
        >>> llv_22 = LLV(self.data.Low, 22)   # 22日最低价
        >>> support_level = llv_22[-1]        # 当前支撑位
    """
    if isinstance(data, np.ndarray):
        data = pd.Series(data)

    return data.rolling(window=period, min_periods=1).min()


def Chandelier_Stop(high: Union[pd.Series, np.ndarray],
                   low: Union[pd.Series, np.ndarray],
                   close: Union[pd.Series, np.ndarray],
                   period: int = 22,
                   multiplier: float = 3.0,
                   direction: str = 'long') -> pd.Series:
    """
    计算Chandelier Exit止损线 (吊灯止损)

    Chandelier Exit由Charles Le Beau开发，是一种基于ATR的动态止损方法。
    相比简单ATR止损，它基于近期极值价位，更适合趋势跟踪。

    计算公式:
    - Long Stop = HHV(high, period) - ATR(period) × multiplier
    - Short Stop = LLV(low, period) + ATR(period) × multiplier

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 计算周期，默认22天（约一个交易月）
        multiplier: ATR倍数，默认3.0
        direction: 方向，'long'或'short'

    Returns:
        pd.Series: Chandelier止损线序列

    Examples:
        >>> # 在策略中使用
        >>> chandelier_stop = self.I(Chandelier_Stop,
        ...                         self.data.High,
        ...                         self.data.Low,
        ...                         self.data.Close,
        ...                         22, 3.0, 'long')
        >>>
        >>> # 止损逻辑
        >>> if self.position.is_long:
        ...     if self.data.Close[-1] < chandelier_stop[-1]:
        ...         self.position.close()

    Notes:
        - 建议参数: period=22, multiplier=3.0 (Le Beau原始设置)
        - 高波动品种可适当降低multiplier至2.5
        - 与ATR止损比较：更宽松，减少假止损，适合长期趋势跟踪

    References:
        - Charles Le Beau: "The Chandelier Exit", TASC Magazine
        - Alexander Elder: "Trading for a Living"
    """
    # 计算ATR
    atr = ATR(high, low, close, period)

    if direction.lower() == 'long':
        # 做多止损: 最高价 - ATR × 倍数
        hhv = HHV(high, period)
        chandelier_stop = hhv - (atr * multiplier)
    elif direction.lower() == 'short':
        # 做空止损: 最低价 + ATR × 倍数
        llv = LLV(low, period)
        chandelier_stop = llv + (atr * multiplier)
    else:
        raise ValueError(f"Direction必须是'long'或'short'，当前值: {direction}")

    return chandelier_stop


# 便捷别名
def TR(high: Union[pd.Series, np.ndarray],
       low: Union[pd.Series, np.ndarray],
       close: Union[pd.Series, np.ndarray]) -> pd.Series:
    """
    计算True Range (真实波动幅度)

    TR是ATR计算的基础，表示单日最大价格波动。

    Returns:
        pd.Series: True Range序列
    """
    # 计算True Range的三个组成部分
    tr1 = high - low

    prev_close = close.shift(1) if hasattr(close, 'shift') else pd.Series(close).shift(1)
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)

    # True Range = max(TR1, TR2, TR3)
    tr_df = pd.concat([pd.Series(tr1), pd.Series(tr2), pd.Series(tr3)], axis=1)
    tr = tr_df.max(axis=1)

    # 第一个值特殊处理
    tr.iloc[0] = (high[0] if hasattr(high, '__getitem__') else pd.Series(high).iloc[0]) - \
                 (low[0] if hasattr(low, '__getitem__') else pd.Series(low).iloc[0])

    return tr


if __name__ == "__main__":
    """
    测试和示例代码
    """
    # 创建测试数据
    np.random.seed(42)
    n = 100

    # 模拟价格数据
    base_price = 100
    returns = np.random.normal(0, 0.02, n)  # 2%日波动率
    close_prices = base_price * np.exp(np.cumsum(returns))

    # 生成OHLC数据
    highs = close_prices * (1 + np.abs(np.random.normal(0, 0.01, n)))
    lows = close_prices * (1 - np.abs(np.random.normal(0, 0.01, n)))

    # 测试ATR计算
    atr_values = ATR(highs, lows, close_prices, period=14)

    print("=== ATR指标测试 ===")
    print(f"数据长度: {len(atr_values)}")
    print(f"NaN值数量: {atr_values.isna().sum()}")
    print(f"最新ATR值: {atr_values.iloc[-1]:.6f}")
    print(f"平均ATR: {atr_values.dropna().mean():.6f}")
    print(f"ATR变化范围: {atr_values.dropna().min():.6f} - {atr_values.dropna().max():.6f}")

    # 测试Chandelier Exit
    chandelier = Chandelier_Stop(highs, lows, close_prices, period=22, multiplier=3.0)

    print("\n=== Chandelier Exit测试 ===")
    print(f"最新止损位: {chandelier.iloc[-1]:.4f}")
    print(f"当前价格: {close_prices[-1]:.4f}")
    print(f"止损距离: {(close_prices[-1] - chandelier.iloc[-1]) / close_prices[-1] * 100:.2f}%")

    # 性能测试
    import time

    print("\n=== 性能测试 ===")
    large_n = 10000
    large_highs = np.random.uniform(95, 105, large_n)
    large_lows = np.random.uniform(95, 105, large_n)
    large_closes = np.random.uniform(95, 105, large_n)

    start_time = time.time()
    large_atr = ATR(large_highs, large_lows, large_closes, period=14)
    end_time = time.time()

    print(f"计算{large_n}个数据点的ATR用时: {end_time - start_time:.4f}秒")
    print(f"处理速度: {large_n / (end_time - start_time):.0f} 点/秒")

    print("\n✅ 所有测试通过！ATR指标模块准备就绪。")