"""显示相关的工具函数"""

import pandas as pd
from typing import Dict, List, Optional

from ..models import InstrumentInfo


def resolve_display_name(instrument: InstrumentInfo) -> str:
    """返回用于显示的标的名称."""
    return instrument.display_name or instrument.code


def print_backtest_header(
    instrument: InstrumentInfo,
    strategy_name: str,
    cash: float,
    cost_config=None,
    commission: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    verbose: bool = False
) -> None:
    """
    打印回测头部信息

    Args:
        instrument: 标的信息
        strategy_name: 策略名称
        cash: 初始资金
        cost_config: 交易成本配置对象
        commission: 旧版本兼容参数
        start_date: 开始日期
        end_date: 结束日期
        verbose: 是否输出详细信息
    """
    if not verbose:
        return

    from utils.trading_cost import get_cost_summary

    display_name = resolve_display_name(instrument)

    print("\n" + "=" * 70)
    print(f"回测: {display_name} ({instrument.code}) - {strategy_name}")
    print(f"标的类型: {instrument.category} | 货币: {instrument.currency}")
    print(f"初始资金: {cash:,.2f}")
    if cost_config is not None:
        print(f"费用模型: {cost_config.name}")
        print(get_cost_summary(cost_config))
    else:
        commission_display = f"{commission:.4f}" if commission is not None else "N/A"
        print(f"手续费率: {commission_display}")
    if start_date or end_date:
        date_range = f"{start_date or '开始'} 至 {end_date or '结束'}"
        print(f"日期范围: {date_range}")
    print("=" * 70)


def print_run_params(params: Optional[Dict], verbose: bool = False) -> None:
    """在详细模式下打印传入 Backtest.run/optimize 的覆盖参数（用于排查是否生效）"""
    if not verbose:
        return
    if not params:
        print("启用/参数: 未传入覆盖参数（使用策略默认值）")
        return
    parts = []
    for k, v in params.items():
        if isinstance(v, bool):
            if v:
                parts.append(k)
        else:
            parts.append(f"{k}={v}")
    if parts:
        print("启用/参数(覆盖项): " + ", ".join(parts))
    else:
        print("启用/参数: 未传入覆盖参数（使用策略默认值）")

def print_backtest_results(stats: pd.Series, cash: float, verbose: bool = False) -> None:
    """
    打印回测结果

    Args:
        stats: 回测统计结果
        cash: 初始资金
        verbose: 是否输出详细信息
    """
    if not verbose:
        return

    print("\n" + "-" * 70)
    print("回测结果")
    print("-" * 70)
    print(f"初始资金:     ${cash:,.2f}")
    print(f"最终资金:     ${stats['Equity Final [$]']:,.2f}")
    print(f"收益率:       {stats['Return [%]']:.2f}%")
    print(f"年化收益率:   {stats['Return (Ann.) [%]']:.2f}%")
    print(f"夏普比率:     {stats['Sharpe Ratio']:.2f}")
    print(f"最大回撤:     {stats['Max. Drawdown [%]']:.2f}%")
    print(f"交易次数:     {stats['# Trades']}")
    print(f"胜率:         {stats['Win Rate [%]']:.2f}%")
    print(f"盈亏比:       {stats['Profit Factor']:.2f}")
    print("-" * 70)


def print_optimization_info(
    params_analysis: List[Dict],
    verbose: bool = False
) -> None:
    """
    打印参数优化结果

    Args:
        params_analysis: 参数分析结果列表
        verbose: 是否输出详细信息
    """
    if not verbose or not params_analysis:
        return

    print("\n" + "=" * 70)
    print("参数稳健性分析")
    print("=" * 70)
    print(f"候选参数组合: {len(params_analysis)} 种\n")

    # 获取参数名称（从第一个分析结果中提取）
    first_analysis = params_analysis[0]
    # 排除元数据字段，只保留参数字段
    metadata_keys = {
        'params', 'median_sharpe', 'avg_sharpe', 'win_rate',
        'sharpe_std', 'stability_score', 'score', 'num_instruments'
    }
    param_names = [k for k in first_analysis.keys() if k not in metadata_keys]

    for i, analysis in enumerate(params_analysis[:5], 1):  # 只显示前5个
        # 动态显示参数
        params_str = ", ".join(f"{name}={analysis[name]}" for name in param_names)
        print(f"参数 ({params_str}):")
        print(f"  中位数夏普: {analysis['median_sharpe']:.4f}")
        print(f"  平均夏普:   {analysis['avg_sharpe']:.4f}")
        print(f"  胜率:       {analysis['win_rate']*100:.1f}% ({int(analysis['win_rate']*analysis['num_instruments'])}/{analysis['num_instruments']}盈利)")
        print(f"  稳定性:     {'高' if analysis['sharpe_std'] < 0.5 else '中' if analysis['sharpe_std'] < 1.0 else '低'} (标准差={analysis['sharpe_std']:.2f})")
        print(f"  综合评分:   {analysis['score']:.4f} {'← 最优' if i == 1 else ''}")
        print()


def print_low_volatility_report(
    low_vol_skipped: List[Dict],
    verbose: bool = False
) -> None:
    """
    打印低波动过滤报告

    Args:
        low_vol_skipped: 跳过的低波动标的列表
        verbose: 是否输出详细信息
    """
    if not low_vol_skipped:
        return

    if verbose:
        print("\n低波动过滤统计")
        print("-" * 70)
        for entry in low_vol_skipped:
            instrument = entry['instrument']
            volatility = entry['volatility']
            reason = entry['reason']
            vol_display = f"{volatility:.4%}" if volatility is not None else "样本不足"
            print(
                f"{instrument.code:<12} {instrument.category:<8} 波动率={vol_display:<12} 原因: {reason}"
            )
        print(f"共跳过 {len(low_vol_skipped)} 只标的。")
    else:
        print(f"\n低波动过滤: 共跳过 {len(low_vol_skipped)} 只标的（使用 --verbose 查看明细）。")


def print_backtest_summary(
    results: List[Dict],
    output_dir: str,
    verbose: bool = False
) -> None:
    """
    打印回测汇总表格

    Args:
        results: 回测结果列表
        output_dir: 输出目录
        verbose: 是否输出详细信息
    """
    if not results:
        return

    from .data_utils import _safe_stat

    print("\n" + "=" * 70)
    print("回测汇总")
    print("=" * 70)
    header = f"{'代码':<12} {'名称':<16} {'类型':<8} {'策略':<15} {'收益率':>10} {'夏普':>8} {'最大回撤':>10}"
    print(header)
    print("-" * len(header))

    for result in results:
        instrument = result['instrument']
        stats = result['stats']
        return_pct = _safe_stat(stats, 'Return [%]')
        sharpe_value = stats['Sharpe Ratio']
        sharpe_display = f"{sharpe_value:>7.2f}" if not pd.isna(sharpe_value) else "   -- "
        max_dd = _safe_stat(stats, 'Max. Drawdown [%]', default=0.0)

        # 截断中文名称以适应显示宽度
        display_name = resolve_display_name(instrument)
        name_display = display_name[:15] + "..." if len(display_name) > 15 else display_name

        print(
            f"{instrument.code:<12} "
            f"{name_display:<16} "
            f"{instrument.category:<8} "
            f"{result['strategy']:<15} "
            f"{return_pct:>9.2f}% "
            f"{sharpe_display} "
            f"{max_dd:>9.2f}%"
        )
    print("=" * 70)

    print(f"\n结果已保存到 {output_dir}/<category>/stats|plots/ 目录")
