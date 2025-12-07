# -*- coding: utf-8 -*-
"""
指标提取模块

从回测结果CSV文件中提取标准化指标。
支持中英文列名自动映射。
"""

import os
import glob
import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Any

# 标准列名映射（内部key -> 可能的中英文列名）
STANDARD_COL_MAPPING = {
    # 夏普比率
    'sharpe_mean': ['夏普-均值', 'Sharpe Ratio Mean'],
    'sharpe_median': ['夏普-中位数', 'Sharpe Ratio Median'],
    # 胜率
    'win_rate_mean': ['胜率-均值(%)', 'Win Rate [%] Mean'],
    'win_rate_median': ['胜率-中位数(%)', 'Win Rate [%] Median'],
    # 盈亏比
    'pl_ratio_mean': ['盈亏比-均值', 'Profit/Loss Ratio Mean'],
    'pl_ratio_median': ['盈亏比-中位数', 'Profit/Loss Ratio Median'],
    # 交易次数
    'trades_mean': ['交易次数-均值', '# Trades Mean'],
    'trades_median': ['交易次数-中位数', '# Trades Median'],
    # 收益率
    'return_mean': ['年化收益率-均值(%)', 'Return [%] Mean'],
    'return_median': ['年化收益率-中位数(%)', 'Return [%] Median'],
    # 最大回撤
    'max_dd_mean': ['最大回撤-均值(%)', 'Max. Drawdown [%] Mean'],
    'max_dd_median': ['最大回撤-中位数(%)', 'Max. Drawdown [%] Median'],
}

# 详细格式（每行一个标的）的列名映射
DETAIL_COL_MAPPING = {
    'sharpe': ['Sharpe Ratio', '夏普比率'],
    'win_rate': ['胜率(%)', 'Win Rate [%]'],
    'pl_ratio': ['盈亏比', 'Profit/Loss Ratio'],
    'trades': ['交易次数', '# Trades'],
    'return': ['年化收益率(%)', 'Return [%]'],
    'max_dd': ['最大回撤(%)', 'Max. Drawdown [%]'],
}


def _safe_float(val: Any) -> Optional[float]:
    """安全地将值转换为float，NaN/None返回None"""
    if val is None:
        return None
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _find_col(df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
    """在DataFrame中查找第一个匹配的列名"""
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def extract_metrics_from_summary(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """
    从global_summary DataFrame提取所有标准化指标

    支持两种格式：
    1. 汇总格式（单行）：直接提取均值/中位数列
    2. 详细格式（多行）：计算均值/中位数

    Args:
        df: global_summary的DataFrame

    Returns:
        标准化的指标字典，key为 sharpe_mean, win_rate_median 等
    """
    metrics = {}

    if len(df) == 1:
        # 汇总格式：直接提取
        for key, possible_names in STANDARD_COL_MAPPING.items():
            col = _find_col(df, possible_names)
            if col:
                metrics[key] = _safe_float(df[col].iloc[0])
            else:
                metrics[key] = None
    else:
        # 详细格式：需要计算统计值
        for base_key, possible_names in DETAIL_COL_MAPPING.items():
            col = _find_col(df, possible_names)
            if col:
                series = pd.to_numeric(df[col], errors='coerce')
                valid = series.dropna()
                if len(valid) > 0:
                    metrics[f'{base_key}_mean'] = float(valid.mean())
                    metrics[f'{base_key}_median'] = float(valid.median())
                else:
                    metrics[f'{base_key}_mean'] = None
                    metrics[f'{base_key}_median'] = None
            else:
                metrics[f'{base_key}_mean'] = None
                metrics[f'{base_key}_median'] = None

    return metrics


def extract_metrics_from_csv(csv_path: str) -> Dict[str, Optional[float]]:
    """
    从CSV文件路径提取指标

    Args:
        csv_path: CSV文件路径

    Returns:
        标准化的指标字典
    """
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    return extract_metrics_from_summary(df)


def find_global_summary(exp_dir: str) -> Optional[str]:
    """
    在实验目录中查找global_summary文件

    Args:
        exp_dir: 实验输出目录

    Returns:
        global_summary CSV路径，未找到返回None
    """
    summary_pattern = os.path.join(exp_dir, 'summary', 'global_summary_*.csv')
    matches = glob.glob(summary_pattern)
    return matches[0] if matches else None


def format_metrics_for_print(
    metrics: Dict[str, Optional[float]],
    include_sharpe: bool = True,
    include_win_rate: bool = True,
    include_pl_ratio: bool = True,
    include_trades: bool = True,
) -> str:
    """
    格式化指标用于打印输出

    Args:
        metrics: 指标字典
        include_*: 是否包含各类指标

    Returns:
        格式化的字符串
    """
    parts = []

    if include_sharpe:
        sm = metrics.get('sharpe_mean')
        smed = metrics.get('sharpe_median')
        if sm is not None and smed is not None:
            parts.append(f"sharpe={sm:.4f}/{smed:.4f}")
        else:
            parts.append("sharpe=N/A")

    if include_win_rate:
        wr = metrics.get('win_rate_mean')
        parts.append(f"win_rate={wr:.1f}%" if wr is not None else "win_rate=N/A")

    if include_pl_ratio:
        pl = metrics.get('pl_ratio_mean')
        parts.append(f"pl_ratio={pl:.2f}" if pl is not None else "pl_ratio=N/A")

    if include_trades:
        tr = metrics.get('trades_mean')
        parts.append(f"trades={tr:.0f}" if tr is not None else "trades=N/A")

    return ", ".join(parts)
