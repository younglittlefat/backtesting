# -*- coding: utf-8 -*-
"""
组合生成模块

生成贪心搜索各阶段需要测试的超参组合。
"""

from itertools import combinations
from typing import List, Dict, Any, Set, Tuple


def check_all_subs_passed(
    combo: Tuple[str, ...],
    prev_candidates: List[Dict[str, Any]],
    prev_k: int,
) -> bool:
    """
    检查组合的所有k-1子组合是否都在前一阶段候选池中

    Args:
        combo: 当前组合（元组）
        prev_candidates: 前一阶段候选列表
        prev_k: 前一阶段的变量数

    Returns:
        是否所有子组合都通过
    """
    # 构建前一阶段候选的选项集合
    prev_option_sets = set()
    for cand in prev_candidates:
        prev_option_sets.add(tuple(sorted(cand['options'])))

    combo_list = list(combo)
    sub_combos = list(combinations(combo_list, prev_k))

    for sub in sub_combos:
        sub_key = tuple(sorted(sub))
        if sub_key not in prev_option_sets:
            return False

    return True


def generate_k_combinations(
    prev_candidates: List[Dict[str, Any]],
    k: int,
) -> List[Tuple[str, ...]]:
    """
    从前一阶段候选生成k变量组合

    只返回所有k-1子组合都在前一阶段候选池中的组合。

    Args:
        prev_candidates: 前一阶段候选列表
        k: 当前阶段的变量数

    Returns:
        需要测试的组合列表
    """
    prev_k = k - 1

    # 收集所有出现过的选项
    all_options: Set[str] = set()
    for cand in prev_candidates:
        all_options.update(cand['options'])

    all_options_sorted = sorted(list(all_options))

    # 生成所有k变量组合
    all_combos = list(combinations(all_options_sorted, k))

    # 筛选：只保留所有子组合都在前一阶段的
    experiments_to_run = []
    for combo in all_combos:
        if check_all_subs_passed(combo, prev_candidates, prev_k):
            experiments_to_run.append(combo)

    return experiments_to_run


def format_combo_exp_name(combo: Tuple[str, ...], k: int) -> str:
    """
    格式化组合为实验名

    Args:
        combo: 组合元组
        k: 阶段数

    Returns:
        实验名，如 "k2_enable-adx-filter_enable-slope-filter"
    """
    return f"k{k}_" + "_".join(combo)


def format_combo_options_str(combo: Tuple[str, ...]) -> str:
    """
    格式化组合为选项字符串（空格分隔）

    Args:
        combo: 组合元组

    Returns:
        选项字符串，如 "enable-adx-filter enable-slope-filter"
    """
    return " ".join(combo)
