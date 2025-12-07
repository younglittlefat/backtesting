# -*- coding: utf-8 -*-
"""
候选筛选模块

实现贪心搜索的各阶段筛选逻辑：
- 阶段1：OR逻辑（sharpe_mean > base OR sharpe_median > base）
- 阶段k：严格递增（两指标同时超过所有子组合最优值）
"""

import os
import json
from typing import Dict, List, Optional, Tuple, Any
from itertools import combinations

from .metrics_extractor import (
    extract_metrics_from_csv,
    find_global_summary,
    format_metrics_for_print,
)


def load_candidates(candidates_path: str) -> List[Dict[str, Any]]:
    """
    加载候选池JSON文件

    Args:
        candidates_path: JSON文件路径

    Returns:
        候选列表
    """
    with open(candidates_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_candidates(candidates: List[Dict[str, Any]], candidates_path: str) -> None:
    """
    保存候选池到JSON文件

    Args:
        candidates: 候选列表
        candidates_path: 输出路径
    """
    with open(candidates_path, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)


def filter_stage1_candidates(
    backtest_dir: str,
    baseline_metrics: Dict[str, Optional[float]],
    core_options: List[str],
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    阶段1候选筛选（OR逻辑）

    筛选条件：sharpe_mean > baseline OR sharpe_median > baseline

    Args:
        backtest_dir: 回测输出目录
        baseline_metrics: 基准指标
        core_options: 核心超参选项列表
        verbose: 是否打印详情

    Returns:
        通过筛选的候选列表
    """
    # 兜底处理：缺失值使用 -inf，确保比较不会抛 TypeError
    baseline_sharpe_mean = baseline_metrics.get('sharpe_mean')
    baseline_sharpe_median = baseline_metrics.get('sharpe_median')

    if baseline_sharpe_mean is None:
        baseline_sharpe_mean = float('-inf')
        if verbose:
            print("⚠ 警告: Baseline缺少sharpe_mean，使用-inf作为基准")
    if baseline_sharpe_median is None:
        baseline_sharpe_median = float('-inf')
        if verbose:
            print("⚠ 警告: Baseline缺少sharpe_median，使用-inf作为基准")

    if verbose:
        print(f"Baseline: sharpe={baseline_sharpe_mean:.4f}/{baseline_sharpe_median:.4f}")

    candidates = []

    for opt in core_options:
        exp_name = f"single_{opt}"
        exp_dir = os.path.join(backtest_dir, exp_name)

        summary_path = find_global_summary(exp_dir)
        if not summary_path:
            if verbose:
                print(f"  ⚠ {exp_name}: 未找到summary文件，跳过")
            continue

        try:
            metrics = extract_metrics_from_csv(summary_path)

            sharpe_mean = metrics.get('sharpe_mean')
            sharpe_median = metrics.get('sharpe_median')

            if sharpe_mean is None or sharpe_median is None:
                if verbose:
                    print(f"  ⚠ {exp_name}: 无法提取夏普指标，跳过")
                continue

            # OR逻辑判断
            passes = (sharpe_mean > baseline_sharpe_mean) or (sharpe_median > baseline_sharpe_median)

            if verbose:
                status = "✓ 通过" if passes else "✗ 未通过"
                metrics_str = format_metrics_for_print(metrics)
                print(f"  {status} {opt}: {metrics_str}")

            if passes:
                candidates.append({
                    'options': [opt],
                    'sharpe_mean': sharpe_mean,
                    'sharpe_median': sharpe_median,
                    'win_rate_mean': metrics.get('win_rate_mean'),
                    'win_rate_median': metrics.get('win_rate_median'),
                    'pl_ratio_mean': metrics.get('pl_ratio_mean'),
                    'pl_ratio_median': metrics.get('pl_ratio_median'),
                    'trades_mean': metrics.get('trades_mean'),
                    'trades_median': metrics.get('trades_median'),
                    'exp_name': exp_name,
                })

        except Exception as e:
            if verbose:
                print(f"  ⚠ {exp_name}: 提取失败 - {e}")

    return candidates


def filter_stage_k_candidates(
    backtest_dir: str,
    prev_candidates: List[Dict[str, Any]],
    k: int,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    阶段k候选筛选（严格递增）

    筛选条件：两个夏普指标都要超过所有k-1子组合的最优值

    Args:
        backtest_dir: 回测输出目录
        prev_candidates: 前一阶段的候选列表
        k: 当前阶段（变量数）
        verbose: 是否打印详情

    Returns:
        通过筛选的候选列表
    """
    import glob

    prev_k = k - 1

    # 构建前一阶段候选的快速查找字典
    prev_dict = {}
    for cand in prev_candidates:
        key = tuple(sorted(cand['options']))
        prev_dict[key] = cand

    # 查找所有阶段k的实验目录
    stage_k_dirs = glob.glob(os.path.join(backtest_dir, f'k{k}_*'))

    candidates = []

    for exp_dir in stage_k_dirs:
        exp_name = os.path.basename(exp_dir)

        # 解析选项
        options_str = exp_name[len(f'k{k}_'):]
        options = options_str.split('_')

        summary_path = find_global_summary(exp_dir)
        if not summary_path:
            if verbose:
                print(f"  ⚠ {exp_name}: 未找到summary文件，跳过")
            continue

        try:
            metrics = extract_metrics_from_csv(summary_path)

            sharpe_mean = metrics.get('sharpe_mean')
            sharpe_median = metrics.get('sharpe_median')

            if sharpe_mean is None or sharpe_median is None:
                if verbose:
                    print(f"  ⚠ {exp_name}: 无法提取夏普指标，跳过")
                continue

            # 计算所有子组合的最优值
            sub_combos = list(combinations(options, prev_k))

            max_sub_sharpe_mean = float('-inf')
            max_sub_sharpe_median = float('-inf')

            for sub in sub_combos:
                sub_key = tuple(sorted(sub))
                if sub_key in prev_dict:
                    sub_cand = prev_dict[sub_key]
                    # 兜底处理：子组合可能缺少夏普指标
                    sub_sharpe_mean = sub_cand.get('sharpe_mean')
                    sub_sharpe_median = sub_cand.get('sharpe_median')
                    if sub_sharpe_mean is not None:
                        max_sub_sharpe_mean = max(max_sub_sharpe_mean, sub_sharpe_mean)
                    if sub_sharpe_median is not None:
                        max_sub_sharpe_median = max(max_sub_sharpe_median, sub_sharpe_median)

            # 严格递增：两个指标都要超过
            passes = (sharpe_mean > max_sub_sharpe_mean) and (sharpe_median > max_sub_sharpe_median)

            if verbose:
                status = "✓ 通过" if passes else "✗ 未通过"
                metrics_str = format_metrics_for_print(metrics)
                print(f"  {status} {options_str}:")
                print(f"      当前: {metrics_str}")
                print(f"      子组合最优: sharpe={max_sub_sharpe_mean:.4f}/{max_sub_sharpe_median:.4f}")

            if passes:
                candidates.append({
                    'options': options,
                    'sharpe_mean': sharpe_mean,
                    'sharpe_median': sharpe_median,
                    'win_rate_mean': metrics.get('win_rate_mean'),
                    'win_rate_median': metrics.get('win_rate_median'),
                    'pl_ratio_mean': metrics.get('pl_ratio_mean'),
                    'pl_ratio_median': metrics.get('pl_ratio_median'),
                    'trades_mean': metrics.get('trades_mean'),
                    'trades_median': metrics.get('trades_median'),
                    'exp_name': exp_name,
                })

        except Exception as e:
            if verbose:
                print(f"  ⚠ {exp_name}: 提取失败 - {e}")

    return candidates


def extract_baseline_metrics(
    backtest_dir: str,
    verbose: bool = True,
) -> Dict[str, Optional[float]]:
    """
    提取Baseline实验的指标

    Args:
        backtest_dir: 回测输出目录
        verbose: 是否打印详情

    Returns:
        基准指标字典
    """
    baseline_dir = os.path.join(backtest_dir, 'baseline')
    summary_path = find_global_summary(baseline_dir)

    if not summary_path:
        raise FileNotFoundError(f"未找到Baseline的global_summary文件: {baseline_dir}")

    if verbose:
        print(f"读取: {summary_path}")

    metrics = extract_metrics_from_csv(summary_path)

    if verbose:
        print("✓ Baseline指标:")
        for key in ['sharpe_mean', 'sharpe_median', 'win_rate_mean', 'pl_ratio_mean', 'trades_mean']:
            val = metrics.get(key)
            if val is not None:
                if 'sharpe' in key:
                    print(f"  - {key}: {val:.4f}")
                elif 'win_rate' in key:
                    print(f"  - {key}: {val:.2f}%")
                elif 'trades' in key:
                    print(f"  - {key}: {val:.1f}")
                else:
                    print(f"  - {key}: {val:.2f}")
            else:
                print(f"  - {key}: N/A")

    return metrics
