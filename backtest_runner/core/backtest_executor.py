"""回测执行器"""

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from backtesting import Backtest

from ..models import InstrumentInfo
from ..utils.display_utils import (
    resolve_display_name,
    print_backtest_header,
    print_backtest_results,
)


def run_single_backtest(
    data,
    strategy_class,
    instrument: InstrumentInfo,
    strategy_name,
    cash: float = 10000,
    cost_config: Optional = None,
    commission: float = 0.002,
    optimize: bool = False,
    output_dir: str = 'results',
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    verbose: bool = False,
    save_params_file: Optional[str] = None,  # 保留参数但不在函数内使用
    filter_params: Optional[Dict] = None,  # 新增：过滤器参数
) -> Tuple[pd.Series, Backtest]:
    """
    运行单次回测。

    Args:
        data: OHLCV数据
        strategy_class: 策略类
        instrument: 标的信息
        strategy_name: 策略名称
        cash: 初始资金
        cost_config: 交易成本配置对象（优先使用）
        commission: 旧版本兼容参数，当 cost_config 为 None 时使用
        optimize: 是否优化参数
        output_dir: 输出目录
        start_date: 开始日期
        end_date: 结束日期
        verbose: 是否输出详细信息
        save_params_file: 保存参数文件路径（保留用于向后兼容）
        filter_params: 过滤器参数字典（仅对sma_cross_enhanced策略有效）

    Returns:
        (stats, bt_result): 回测统计结果和Backtest对象
    """
    # 确定使用的成本配置
    if cost_config is not None:
        from utils.trading_cost import TradingCostCalculator
        cost_calculator = TradingCostCalculator(cost_config)
        spread = cost_config.spread
    else:
        # 向后兼容：如果没有提供 cost_config，使用旧的 commission 参数
        cost_calculator = commission
        spread = 0.0

    # 打印回测头部信息
    print_backtest_header(
        instrument=instrument,
        strategy_name=strategy_name,
        cash=cash,
        cost_config=cost_config,
        commission=commission if cost_config is None else None,
        start_date=start_date,
        end_date=end_date,
        verbose=verbose
    )

    bt = Backtest(
        data,
        strategy_class,
        cash=cash,
        commission=cost_calculator,
        exclusive_orders=True,
        finalize_trades=True,
    )

    if optimize:
        stats = _run_optimization(
            bt=bt,
            strategy_class=strategy_class,
            filter_params=filter_params,
            verbose=verbose
        )
    else:
        stats = _run_backtest(
            bt=bt,
            filter_params=filter_params,
            verbose=verbose
        )

    # 打印回测结果
    print_backtest_results(stats=stats, cash=cash, verbose=verbose)

    # 保存结果
    from ..io.result_writer import save_results
    save_results(
        stats=stats,
        instrument=instrument,
        strategy_name=strategy_name,
        output_dir=output_dir,
        optimized=optimize,
        cash=cash,
        verbose=verbose,
    )

    # 生成图表
    _generate_plot(
        bt=bt,
        instrument=instrument,
        strategy_name=strategy_name,
        output_dir=output_dir,
        verbose=verbose
    )

    # 返回 stats 和 bt 对象（用于获取优化参数）
    return stats, bt


def _run_optimization(
    bt: Backtest,
    strategy_class,
    filter_params: Optional[Dict] = None,
    verbose: bool = False
) -> pd.Series:
    """
    运行参数优化

    Args:
        bt: Backtest对象
        strategy_class: 策略类
        filter_params: 过滤器参数
        verbose: 是否输出详细信息

    Returns:
        优化后的统计结果
    """
    # 从策略类获取优化参数和约束
    # 需要从模块级别访问，因为OPTIMIZE_PARAMS和CONSTRAINTS定义在模块而非类中
    strategy_module = sys.modules[strategy_class.__module__]
    optimize_params = getattr(strategy_module, 'OPTIMIZE_PARAMS', {
        'n1': range(5, 51, 5),
        'n2': range(20, 201, 20),
    })
    constraints = getattr(strategy_module, 'CONSTRAINTS', lambda p: p.n1 < p.n2)

    if verbose:
        print("\n开始参数优化...")
        print(f"参数空间: {optimize_params}")

    # 合并过滤器参数
    run_kwargs = {**optimize_params}
    if filter_params:
        # 将单值参数转换为单元素列表，以便优化器能够识别和传递这些参数
        # 如果不这样做，bt.optimize() 会忽略非可迭代的参数
        normalized_filter_params = {}
        for key, value in filter_params.items():
            # 如果值不是可迭代对象（排除字符串），转换为单元素列表
            if not hasattr(value, '__iter__') or isinstance(value, str):
                normalized_filter_params[key] = [value]
            else:
                normalized_filter_params[key] = value
        run_kwargs.update(normalized_filter_params)
        if verbose:
            print(f"\n调试: 过滤器参数转换")
            print(f"  原始参数: {filter_params}")
            print(f"  转换后参数: {normalized_filter_params}")

    stats = bt.optimize(
        **run_kwargs,
        constraint=constraints,
        maximize='Sharpe Ratio',
        max_tries=200,
        random_state=42,
    )

    if verbose:
        print("\n最优参数:")
        if hasattr(stats._strategy, 'n1'):
            print(f"  短期均线 (n1): {stats._strategy.n1}")
        if hasattr(stats._strategy, 'n2'):
            print(f"  长期均线 (n2): {stats._strategy.n2}")

    return stats


def _run_backtest(
    bt: Backtest,
    filter_params: Optional[Dict] = None,
    verbose: bool = False
) -> pd.Series:
    """
    运行普通回测

    Args:
        bt: Backtest对象
        filter_params: 过滤器参数
        verbose: 是否输出详细信息

    Returns:
        统计结果
    """
    if verbose:
        print("\n运行回测...")

    # 传入过滤器参数
    run_kwargs = filter_params if filter_params else {}
    stats = bt.run(**run_kwargs)

    return stats


def _generate_plot(
    bt: Backtest,
    instrument: InstrumentInfo,
    strategy_name: str,
    output_dir: str,
    verbose: bool = False
) -> None:
    """
    生成回测图表

    Args:
        bt: Backtest对象
        instrument: 标的信息
        strategy_name: 策略名称
        output_dir: 输出目录
        verbose: 是否输出详细信息
    """
    plot_dir = Path(output_dir) / instrument.category / 'plots'
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_file = plot_dir / f"{instrument.code}_{strategy_name}.html"
    if verbose:
        print(f"\n生成图表: {plot_file}")
    bt.plot(filename=str(plot_file), open_browser=False)
