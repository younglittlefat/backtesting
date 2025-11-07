"""
双均线回测引擎

用于评估ETF标的对趋势跟踪策略的适应性。
使用简单的双均线策略（MA(20,50)）进行回测，计算年化收益率、最大回撤和收益回撤比。
"""
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def dual_ma_backtest(
    data: pd.DataFrame,
    short: int = 20,
    long: int = 50,
    use_adj: bool = True,
) -> Tuple[float, float, float]:
    """双均线策略回测

    策略逻辑：
    - 当短期均线 > 长期均线时，持仓（做多）
    - 当短期均线 <= 长期均线时，空仓（不持有）
    - 信号在计算当天收盘后生成，次日开盘执行

    Args:
        data: OHLCV数据DataFrame，索引为日期
              必须包含 'close' 或 'adj_close' 列
        short: 短期均线周期，默认20天
        long: 长期均线周期，默认50天
        use_adj: 是否使用复权价格，默认True

    Returns:
        (年化收益率, 最大回撤, 收益回撤比)
        - 年化收益率: 策略的年化收益率（小数形式，如0.15表示15%）
        - 最大回撤: 最大回撤（负数，如-0.20表示-20%）
        - 收益回撤比: 年化收益率 / |最大回撤|

    Example:
        >>> data = loader.load_etf_daily('159915.SZ')
        >>> annual_ret, max_dd, ret_dd_ratio = dual_ma_backtest(data)
        >>> print(f"年化收益: {annual_ret:.2%}, 最大回撤: {max_dd:.2%}, 收益回撤比: {ret_dd_ratio:.2f}")

    Raises:
        ValueError: 数据不足或缺少必需字段
    """
    # 数据验证
    if len(data) == 0:
        raise ValueError("输入数据为空")

    if len(data) < long + 1:
        raise ValueError(f"数据长度不足，需要至少 {long + 1} 天，实际只有 {len(data)} 天")

    # 选择价格列
    if use_adj and 'adj_close' in data.columns:
        close = data['adj_close']
    elif 'close' in data.columns:
        close = data['close']
    else:
        raise ValueError("数据中缺少 'close' 或 'adj_close' 列")

    # 计算均线
    ma_short = close.rolling(window=short, min_periods=short).mean()
    ma_long = close.rolling(window=long, min_periods=long).mean()

    # 生成交易信号: 1=持仓, 0=空仓
    # shift(1)表示信号在当天收盘后生成，次日开盘执行
    signal = (ma_short > ma_long).astype(int).shift(1)

    # 计算收益率
    returns = close.pct_change()

    # 策略收益 = 信号 * 市场收益
    strategy_returns = signal * returns

    # 计算净值曲线（从1开始）
    equity = (1 + strategy_returns).cumprod()

    # 处理可能的NaN（前期数据不足时）
    equity = equity.fillna(1.0)

    # 年化收益率
    total_days = len(data)
    total_return = equity.iloc[-1] - 1

    if total_return <= -1:  # 完全亏损
        annual_return = -1.0
    else:
        annual_return = (1 + total_return) ** (252 / total_days) - 1

    # 最大回撤
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_dd = drawdown.min()

    # 收益回撤比
    if max_dd == 0:
        # 没有回撤，返回一个较大的值或特殊值
        return_dd_ratio = np.inf if annual_return > 0 else 0.0
    else:
        return_dd_ratio = annual_return / abs(max_dd)

    return float(annual_return), float(max_dd), float(return_dd_ratio)


def calculate_backtest_metrics(
    data: pd.DataFrame,
    short: int = 20,
    long: int = 50,
    use_adj: bool = True,
) -> Dict[str, float]:
    """计算回测指标（返回字典格式）

    便于后续筛选流程使用的封装函数。

    Args:
        data: OHLCV数据DataFrame
        short: 短期均线周期
        long: 长期均线周期
        use_adj: 是否使用复权价格

    Returns:
        包含以下键的字典：
        - 'annual_return': 年化收益率
        - 'max_drawdown': 最大回撤
        - 'return_dd_ratio': 收益回撤比

    Example:
        >>> data = loader.load_etf_daily('159915.SZ')
        >>> metrics = calculate_backtest_metrics(data)
        >>> print(f"收益回撤比: {metrics['return_dd_ratio']:.2f}")
    """
    annual_return, max_dd, ret_dd_ratio = dual_ma_backtest(
        data, short=short, long=long, use_adj=use_adj
    )

    return {
        'annual_return': annual_return,
        'max_drawdown': max_dd,
        'return_dd_ratio': ret_dd_ratio,
    }


def batch_backtest(
    etf_codes: list,
    data_loader,
    short: int = 20,
    long: int = 50,
    use_adj: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """批量回测多个ETF

    Args:
        etf_codes: ETF代码列表
        data_loader: ETFDataLoader实例
        short: 短期均线周期
        long: 长期均线周期
        use_adj: 是否使用复权价格
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        verbose: 是否打印进度信息

    Returns:
        包含所有ETF回测结果的DataFrame，索引为ts_code，列为：
        - annual_return: 年化收益率
        - max_drawdown: 最大回撤
        - return_dd_ratio: 收益回撤比

    Example:
        >>> loader = ETFDataLoader()
        >>> codes = ['159915.SZ', '510300.SH', '512690.SH']
        >>> results = batch_backtest(codes, loader, verbose=True)
        >>> print(results.sort_values('return_dd_ratio', ascending=False))
    """
    results = []

    for i, ts_code in enumerate(etf_codes):
        if verbose and (i + 1) % 100 == 0:
            print(f"进度: {i + 1}/{len(etf_codes)}")

        try:
            # 加载数据
            data = data_loader.load_etf_daily(
                ts_code,
                start_date=start_date,
                end_date=end_date,
                use_adj=use_adj,
            )

            # 回测
            metrics = calculate_backtest_metrics(
                data, short=short, long=long, use_adj=use_adj
            )

            results.append({
                'ts_code': ts_code,
                'annual_return': metrics['annual_return'],
                'max_drawdown': metrics['max_drawdown'],
                'return_dd_ratio': metrics['return_dd_ratio'],
            })

        except (FileNotFoundError, ValueError) as e:
            if verbose:
                print(f"跳过 {ts_code}: {e}")
            continue

    # 转换为DataFrame
    if len(results) == 0:
        return pd.DataFrame(columns=['ts_code', 'annual_return', 'max_drawdown', 'return_dd_ratio'])

    df = pd.DataFrame(results)
    df = df.set_index('ts_code')

    return df
