#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
贪心搜索指标提取CLI

供Shell脚本调用，从回测结果提取标准化指标并输出JSON。

用法：
    python -m greedy_search.cli extract_baseline <backtest_dir> <output_json>
    python -m greedy_search.cli filter_stage1 <backtest_dir> <candidates_dir> <core_options...>
    python -m greedy_search.cli filter_stage_k <backtest_dir> <candidates_dir> <k>
    python -m greedy_search.cli gen_combos <candidates_dir> <k>
"""

import sys
import os
import json
import argparse

# 确保能导入greedy_search模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from greedy_search.metrics_extractor import (
    extract_metrics_from_csv,
    find_global_summary,
)
from greedy_search.candidate_filter import (
    filter_stage1_candidates,
    filter_stage_k_candidates,
    extract_baseline_metrics,
    load_candidates,
    save_candidates,
)
from greedy_search.combo_generator import (
    generate_k_combinations,
    format_combo_exp_name,
    format_combo_options_str,
)


def cmd_extract_baseline(args):
    """提取Baseline指标"""
    backtest_dir = args.backtest_dir
    output_json = args.output_json

    try:
        metrics = extract_baseline_metrics(backtest_dir, verbose=True)

        # 保存到JSON
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        print(f"✓ 已保存到: {output_json}")
        return 0

    except FileNotFoundError as e:
        print(f"错误: {e}")
        return 1
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_filter_stage1(args):
    """阶段1筛选"""
    backtest_dir = args.backtest_dir
    candidates_dir = args.candidates_dir
    core_options = args.core_options

    # 加载Baseline
    baseline_json = os.path.join(candidates_dir, 'baseline.json')
    with open(baseline_json, 'r', encoding='utf-8') as f:
        baseline_metrics = json.load(f)

    candidates = filter_stage1_candidates(
        backtest_dir=backtest_dir,
        baseline_metrics=baseline_metrics,
        core_options=core_options,
        verbose=True,
    )

    if not candidates:
        print("\n✗ 错误: 阶段1没有任何候选通过筛选，流程终止")
        return 1

    # 保存候选池
    candidates_json = os.path.join(candidates_dir, 'candidates_k1.json')
    save_candidates(candidates, candidates_json)

    print(f"\n✓ 阶段1完成: {len(candidates)}/{len(core_options)} 个候选通过筛选")
    print(f"✓ 候选池已保存到: {candidates_json}")
    return 0


def cmd_filter_stage_k(args):
    """阶段k筛选"""
    backtest_dir = args.backtest_dir
    candidates_dir = args.candidates_dir
    k = args.k
    prev_k = k - 1

    # 加载前一阶段候选
    prev_json = os.path.join(candidates_dir, f'candidates_k{prev_k}.json')
    prev_candidates = load_candidates(prev_json)

    candidates = filter_stage_k_candidates(
        backtest_dir=backtest_dir,
        prev_candidates=prev_candidates,
        k=k,
        verbose=True,
    )

    if not candidates:
        print(f"\n✗ 阶段{k}: 没有任何候选通过严格递增筛选，流程终止")
        return 1

    # 保存候选池
    candidates_json = os.path.join(candidates_dir, f'candidates_k{k}.json')
    save_candidates(candidates, candidates_json)

    print(f"\n✓ 阶段{k}完成: {len(candidates)} 个候选通过筛选")
    print(f"✓ 候选池已保存到: {candidates_json}")
    return 0


def cmd_gen_combos(args):
    """生成k变量组合"""
    candidates_dir = args.candidates_dir
    k = args.k
    prev_k = k - 1

    # 加载前一阶段候选
    prev_json = os.path.join(candidates_dir, f'candidates_k{prev_k}.json')
    prev_candidates = load_candidates(prev_json)

    combos = generate_k_combinations(prev_candidates, k)

    # 输出组合列表（供Shell读取）
    for combo in combos:
        exp_name = format_combo_exp_name(combo, k)
        options_str = format_combo_options_str(combo)
        print(f"{exp_name} {options_str}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='贪心搜索实验框架CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # extract_baseline
    p1 = subparsers.add_parser('extract_baseline', help='提取Baseline指标')
    p1.add_argument('backtest_dir', help='回测输出目录')
    p1.add_argument('output_json', help='输出JSON路径')

    # filter_stage1
    p2 = subparsers.add_parser('filter_stage1', help='阶段1候选筛选')
    p2.add_argument('backtest_dir', help='回测输出目录')
    p2.add_argument('candidates_dir', help='候选池目录')
    p2.add_argument('core_options', nargs='+', help='核心超参选项列表')

    # filter_stage_k
    p3 = subparsers.add_parser('filter_stage_k', help='阶段k候选筛选')
    p3.add_argument('backtest_dir', help='回测输出目录')
    p3.add_argument('candidates_dir', help='候选池目录')
    p3.add_argument('k', type=int, help='当前阶段数')

    # gen_combos
    p4 = subparsers.add_parser('gen_combos', help='生成k变量组合')
    p4.add_argument('candidates_dir', help='候选池目录')
    p4.add_argument('k', type=int, help='当前阶段数')

    args = parser.parse_args()

    if args.command == 'extract_baseline':
        return cmd_extract_baseline(args)
    elif args.command == 'filter_stage1':
        return cmd_filter_stage1(args)
    elif args.command == 'filter_stage_k':
        return cmd_filter_stage_k(args)
    elif args.command == 'gen_combos':
        return cmd_gen_combos(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
