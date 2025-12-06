"""
汇总报告生成器

职责：
- 生成回测结果汇总 CSV
- 生成全局统计概括 CSV
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from backtest_runner.utils import resolve_display_name, _safe_stat


def save_summary_csv(
    all_results: List[Dict],
    output_dir: str,
    aggregate_output: Optional[str] = None,
) -> Path:
    """
    保存回测汇总 CSV

    Args:
        all_results: 回测结果列表
        output_dir: 输出目录
        aggregate_output: 指定的汇总文件路径（可选）

    Returns:
        保存的文件路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 确定输出路径
    if aggregate_output:
        aggregate_path = Path(aggregate_output)
    else:
        summary_dir = Path(output_dir) / 'summary'
        summary_dir.mkdir(parents=True, exist_ok=True)
        aggregate_path = summary_dir / f"backtest_summary_{timestamp}.csv"

    # 构建汇总 DataFrame
    summary_rows = []
    for result in all_results:
        instrument = result['instrument']
        stats = result['stats']

        # 原始总收益率（%）
        return_pct = _safe_stat(stats, 'Return [%]')
        sharpe_value = stats['Sharpe Ratio']
        max_dd = _safe_stat(stats, 'Max. Drawdown [%]', default=0.0)

        # 获取实际回测起止日期
        start_date = str(stats['Start'])[:10] if 'Start' in stats else '未知'
        end_date = str(stats['End'])[:10] if 'End' in stats else '未知'

        # 计算年化收益率（%）
        annual_return_pct = _calculate_annual_return(
            stats, return_pct, start_date, end_date
        )

        summary_rows.append({
            '代码': instrument.code,
            '标的名称': resolve_display_name(instrument),
            '类型': instrument.category,
            '策略': result['strategy'],
            '回测开始日期': start_date,
            '回测结束日期': end_date,
            '收益率(%)': round(annual_return_pct, 3) if annual_return_pct is not None else None,
            '总收益率(%)': round(return_pct, 3) if return_pct is not None else None,
            '夏普比率': round(sharpe_value, 3) if not pd.isna(sharpe_value) else None,
            '最大回撤(%)': round(max_dd, 3) if max_dd is not None else None,
            '胜率(%)': round(_safe_stat(stats, 'Win Rate [%]'), 2) if _safe_stat(stats, 'Win Rate [%]') is not None and not pd.isna(_safe_stat(stats, 'Win Rate [%]')) else None,
            '盈亏比': round(_safe_stat(stats, 'Profit/Loss Ratio'), 2) if _safe_stat(stats, 'Profit/Loss Ratio') is not None and not pd.isna(_safe_stat(stats, 'Profit/Loss Ratio')) else None,
            '交易次数': int(_safe_stat(stats, '# Trades')) if _safe_stat(stats, '# Trades') is not None and not pd.isna(_safe_stat(stats, '# Trades')) else None,
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(by='代码')
    aggregate_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(aggregate_path, index=False, encoding='utf-8-sig')
    print(f"汇总结果已保存: {aggregate_path}")

    # 生成全局概括 CSV
    try:
        save_global_summary_csv(aggregate_path)
    except Exception as exc:
        print(f"⚠️ 生成全局概括失败: {exc}")

    return aggregate_path


def _calculate_annual_return(
    stats: Dict,
    return_pct: Optional[float],
    start_date: str,
    end_date: str,
) -> Optional[float]:
    """
    计算年化收益率

    优先使用回测框架提供的年化收益率，否则用总收益率+起止日推算
    """
    annual_return_pct = _safe_stat(stats, 'Return (Ann.) [%]')

    if annual_return_pct is None and return_pct is not None:
        if start_date != '未知' and end_date != '未知':
            try:
                sd = pd.to_datetime(start_date, errors='coerce')
                ed = pd.to_datetime(end_date, errors='coerce')
                days = (ed - sd).days if pd.notna(sd) and pd.notna(ed) else None
                if days and days > 0:
                    base = 1.0 + (return_pct / 100.0)
                    if base >= 0:
                        annual_return_pct = (base ** (365.25 / days) - 1.0) * 100.0
            except Exception:
                annual_return_pct = None

    return annual_return_pct


def save_global_summary_csv(aggregate_path: Path) -> Path:
    """
    从明细汇总 CSV 中计算跨标的的全局概括并保存

    统计指标：
      - 年化收益率：均值/中位数（%）
      - 夏普比率：均值/中位数
      - 最大回撤：均值/中位数（%）
      - 胜率：均值/中位数（%）
      - 盈亏比：均值/中位数
      - 交易次数：均值/中位数

    Args:
        aggregate_path: 明细汇总 CSV 路径

    Returns:
        全局概括 CSV 路径
    """
    summary_dir = aggregate_path.parent
    source_file = aggregate_path.name

    df = pd.read_csv(aggregate_path)

    # 获取年化收益率
    ann_ret_pct = _extract_annual_return_column(df)

    # 获取夏普比率
    sharpe_col = _find_first_col(df, ['夏普比率', '夏普', 'Sharpe Ratio', 'sharpe'])
    if not sharpe_col:
        raise ValueError("未找到夏普比率列（候选：夏普比率/夏普/Sharpe Ratio）")
    sharpe = pd.to_numeric(df[sharpe_col], errors='coerce')

    # 获取最大回撤
    mdd_col = _find_first_col(df, ['最大回撤(%)', '最大回撤', 'Max. Drawdown [%]', 'Max. Drawdown'])
    if not mdd_col:
        raise ValueError("未找到最大回撤列（候选：最大回撤(%) / Max. Drawdown [%]）")
    mdd_pct = pd.to_numeric(df[mdd_col], errors='coerce')

    # 获取胜率（新增）
    win_rate_col = _find_first_col(df, ['胜率(%)', 'Win Rate [%]', 'win_rate'])
    win_rate = pd.to_numeric(df[win_rate_col], errors='coerce') if win_rate_col else pd.Series(dtype=float)

    # 获取盈亏比（新增）
    pl_ratio_col = _find_first_col(df, ['盈亏比', 'Profit/Loss Ratio', 'pl_ratio'])
    pl_ratio = pd.to_numeric(df[pl_ratio_col], errors='coerce') if pl_ratio_col else pd.Series(dtype=float)

    # 获取交易次数（新增）
    trades_col = _find_first_col(df, ['交易次数', '# Trades', 'trades', 'num_trades'])
    trades = pd.to_numeric(df[trades_col], errors='coerce') if trades_col else pd.Series(dtype=float)

    # 计算聚合统计
    n_instruments = int(len(df))
    ann_mean = float(round(ann_ret_pct.dropna().mean(), 2)) if ann_ret_pct.dropna().size else None
    ann_median = float(round(ann_ret_pct.dropna().median(), 2)) if ann_ret_pct.dropna().size else None
    sharpe_mean = float(round(sharpe.dropna().mean(), 2)) if sharpe.dropna().size else None
    sharpe_median = float(round(sharpe.dropna().median(), 2)) if sharpe.dropna().size else None
    mdd_mean = float(round(mdd_pct.dropna().mean(), 2)) if mdd_pct.dropna().size else None
    mdd_median = float(round(mdd_pct.dropna().median(), 2)) if mdd_pct.dropna().size else None

    # 新增指标统计
    win_rate_mean = float(round(win_rate.dropna().mean(), 2)) if win_rate.dropna().size else None
    win_rate_median = float(round(win_rate.dropna().median(), 2)) if win_rate.dropna().size else None
    pl_ratio_mean = float(round(pl_ratio.dropna().mean(), 2)) if pl_ratio.dropna().size else None
    pl_ratio_median = float(round(pl_ratio.dropna().median(), 2)) if pl_ratio.dropna().size else None
    trades_mean = float(round(trades.dropna().mean(), 1)) if trades.dropna().size else None
    trades_median = float(round(trades.dropna().median(), 1)) if trades.dropna().size else None

    # 组装结果并保存
    result = pd.DataFrame([{
        '标的数量': n_instruments,
        '年化收益率-均值(%)': ann_mean,
        '年化收益率-中位数(%)': ann_median,
        '夏普-均值': sharpe_mean,
        '夏普-中位数': sharpe_median,
        '最大回撤-均值(%)': mdd_mean,
        '最大回撤-中位数(%)': mdd_median,
        '胜率-均值(%)': win_rate_mean,
        '胜率-中位数(%)': win_rate_median,
        '盈亏比-均值': pl_ratio_mean,
        '盈亏比-中位数': pl_ratio_median,
        '交易次数-均值': trades_mean,
        '交易次数-中位数': trades_median,
        '来源文件': source_file,
    }])

    out_name = f"global_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    out_path = summary_dir / out_name
    result.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"全局概括已保存: {out_path}")

    return out_path


def _find_first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """查找 DataFrame 中第一个存在的列名"""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _extract_annual_return_column(df: pd.DataFrame) -> pd.Series:
    """
    从 DataFrame 中提取或计算年化收益率列

    尝试顺序：
    1. 直接读取年化收益率列
    2. 从 '收益率(%)' 列读取（新版明细）
    3. 从总收益率 + 回测期推算
    """
    # 尝试直接读取年化收益率列
    ann_ret_col = _find_first_col(df, [
        '年化收益率(%)', '年化收益率', 'CAGR(%)', 'CAGR',
        'annual_return(%)', 'annual_return',
        'Annual Return [%]', 'Annual Return'
    ])

    if ann_ret_col:
        ann_ret_pct = pd.to_numeric(df[ann_ret_col], errors='coerce')
        # 若单位不是百分比（0.12 而非 12），转为百分比
        if ann_ret_pct.dropna().abs().mean() <= 1.0:
            ann_ret_pct = ann_ret_pct * 100.0
        return ann_ret_pct

    # 新版明细：'收益率(%)' 已为年化
    if '收益率(%)' in df.columns and '总收益率(%)' in df.columns:
        ann_ret_pct = pd.to_numeric(df['收益率(%)'], errors='coerce')
        if ann_ret_pct.dropna().abs().mean() <= 1.0:
            ann_ret_pct = ann_ret_pct * 100.0
        return ann_ret_pct

    # 从总收益率 + 回测期推算
    total_ret_col = _find_first_col(df, [
        '收益率(%)', '总收益率(%)', '收益率', 'Total Return [%]', 'Return [%]'
    ])
    start_col = _find_first_col(df, ['回测开始日期', '开始日期', 'Start'])
    end_col = _find_first_col(df, ['回测结束日期', '结束日期', 'End'])

    if not total_ret_col or not start_col or not end_col:
        raise ValueError("缺少推算年化收益率所需的列（收益率/开始日期/结束日期）")

    total_ret_pct = pd.to_numeric(df[total_ret_col], errors='coerce')
    start_dt = pd.to_datetime(df[start_col], errors='coerce')
    end_dt = pd.to_datetime(df[end_col], errors='coerce')
    days = (end_dt - start_dt).dt.days

    years = days / 365.25
    with pd.option_context('mode.use_inf_as_na', True):
        base = 1.0 + (total_ret_pct / 100.0)
        base = base.where(base >= 0.0, other=pd.NA)
        ann = base.pow(1.0 / years) - 1.0
        ann = ann.where((years > 0) & base.notna(), other=pd.NA)
        ann_ret_pct = ann * 100.0

    return ann_ret_pct


def save_rotation_summary_csv(
    stats,
    rotation_stats: Dict,
    args,
) -> Path:
    """
    保存轮动策略汇总结果到 CSV

    Args:
        stats: 回测统计结果
        rotation_stats: 轮动统计信息
        args: 命令行参数

    Returns:
        保存的文件路径
    """
    result_dict = {
        # 基本信息
        'strategy': args.strategy,
        'rebalance_mode': args.rebalance_mode,
        'rotation_trading_cost_pct': args.rotation_trading_cost,
        'initial_cash': args.cash,

        # 轮动统计
        'total_rotations': rotation_stats['total_rotations'],
        'total_rebalance_cost_pct': rotation_stats['total_rebalance_cost_pct'],
        'avg_rotation_interval_days': rotation_stats.get('avg_rotation_interval_days'),
        'avg_active_etfs': rotation_stats['avg_active_etfs'],

        # 回测结果
        'start_date': str(stats['Start']),
        'end_date': str(stats['End']),
        'return_pct': stats['Return [%]'],
        'return_ann_pct': stats.get('Return (Ann.) [%]'),
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'num_trades': stats['# Trades'],
        'win_rate_pct': stats['Win Rate [%]'],

        # 启用的功能
        'enable_slope_filter': getattr(args, 'enable_slope_filter', False),
        'enable_adx_filter': getattr(args, 'enable_adx_filter', False),
        'enable_volume_filter': getattr(args, 'enable_volume_filter', False),
        'enable_confirm_filter': getattr(args, 'enable_confirm_filter', False),
        'enable_loss_protection': getattr(args, 'enable_loss_protection', False),
    }

    df = pd.DataFrame([result_dict])
    output_path = Path(args.aggregate_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    return output_path
