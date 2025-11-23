#!/usr/bin/env python3
"""
候选池管理工具

功能:
- 加载/保存候选池JSON文件
- 计算候选组合的子组合
- 评估候选是否满足"严格递增"条件
- 生成阶段统计报告

作者: Claude Code
日期: 2025-11-23
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Set, Tuple
from itertools import combinations


class CandidateManager:
    """候选池管理器"""

    def __init__(self, candidates_dir: str):
        """
        初始化管理器

        Args:
            candidates_dir: 候选池JSON文件所在目录
        """
        self.candidates_dir = candidates_dir
        self.baseline = None
        self.candidates_by_stage = {}  # {stage: [candidates]}

    def load_baseline(self) -> Dict:
        """加载Baseline指标"""
        baseline_path = os.path.join(self.candidates_dir, 'baseline.json')
        if not os.path.exists(baseline_path):
            raise FileNotFoundError(f"Baseline文件不存在: {baseline_path}")

        with open(baseline_path, 'r', encoding='utf-8') as f:
            self.baseline = json.load(f)

        return self.baseline

    def load_stage(self, k: int) -> List[Dict]:
        """
        加载阶段k的候选池

        Args:
            k: 阶段编号（1, 2, 3, ...）

        Returns:
            候选列表，每个候选格式为:
            {
                'options': ['enable-hysteresis', 'enable-atr-stop'],
                'sharpe_mean': 1.23,
                'sharpe_median': 1.18,
                'exp_name': 'k2_enable-hysteresis_enable-atr-stop'
            }
        """
        candidates_path = os.path.join(self.candidates_dir, f'candidates_k{k}.json')
        if not os.path.exists(candidates_path):
            return []

        with open(candidates_path, 'r', encoding='utf-8') as f:
            candidates = json.load(f)

        self.candidates_by_stage[k] = candidates
        return candidates

    def save_stage(self, k: int, candidates: List[Dict]):
        """
        保存阶段k的候选池

        Args:
            k: 阶段编号
            candidates: 候选列表
        """
        candidates_path = os.path.join(self.candidates_dir, f'candidates_k{k}.json')
        with open(candidates_path, 'w', encoding='utf-8') as f:
            json.dump(candidates, f, indent=2, ensure_ascii=False)

        self.candidates_by_stage[k] = candidates
        print(f"✓ 已保存阶段{k}候选池: {candidates_path} ({len(candidates)}个候选)")

    def get_all_options(self, k: int) -> Set[str]:
        """
        获取阶段k中出现的所有选项

        Args:
            k: 阶段编号

        Returns:
            选项集合
        """
        if k not in self.candidates_by_stage:
            self.load_stage(k)

        all_options = set()
        for cand in self.candidates_by_stage.get(k, []):
            all_options.update(cand['options'])

        return all_options

    def get_sub_combinations(self, options: List[str], sub_k: int) -> List[Tuple[str]]:
        """
        生成选项列表的所有sub_k变量子组合

        Args:
            options: 选项列表，如 ['A', 'B', 'C']
            sub_k: 子组合大小

        Returns:
            子组合列表，如 [('A', 'B'), ('A', 'C'), ('B', 'C')]
        """
        return list(combinations(sorted(options), sub_k))

    def check_strict_increase(
        self,
        candidate: Dict,
        prev_stage: int
    ) -> Tuple[bool, Dict]:
        """
        检查候选是否满足严格递增条件

        Args:
            candidate: 待检查的候选
            prev_stage: 前一阶段编号（候选的子组合所在阶段）

        Returns:
            (是否通过, 详细信息字典)
        """
        if prev_stage not in self.candidates_by_stage:
            self.load_stage(prev_stage)

        prev_candidates = self.candidates_by_stage.get(prev_stage, [])
        if not prev_candidates:
            return False, {'reason': f'阶段{prev_stage}无候选'}

        # 构建快速查找字典
        prev_dict = {}
        for cand in prev_candidates:
            key = tuple(sorted(cand['options']))
            prev_dict[key] = cand

        # 获取所有子组合
        sub_combos = self.get_sub_combinations(candidate['options'], prev_stage)

        # 找出所有子组合的最优值
        max_sub_sharpe_mean = -float('inf')
        max_sub_sharpe_median = -float('inf')
        found_subs = []

        for sub in sub_combos:
            if sub in prev_dict:
                sub_cand = prev_dict[sub]
                max_sub_sharpe_mean = max(max_sub_sharpe_mean, sub_cand['sharpe_mean'])
                max_sub_sharpe_median = max(max_sub_sharpe_median, sub_cand['sharpe_median'])
                found_subs.append({
                    'options': list(sub),
                    'sharpe_mean': sub_cand['sharpe_mean'],
                    'sharpe_median': sub_cand['sharpe_median']
                })

        if not found_subs:
            return False, {'reason': '所有子组合都未通过前一阶段筛选'}

        # 严格递增：两个指标都要超过
        mean_increase = candidate['sharpe_mean'] > max_sub_sharpe_mean
        median_increase = candidate['sharpe_median'] > max_sub_sharpe_median

        passes = mean_increase and median_increase

        info = {
            'passes': passes,
            'current_sharpe_mean': candidate['sharpe_mean'],
            'current_sharpe_median': candidate['sharpe_median'],
            'max_sub_sharpe_mean': max_sub_sharpe_mean,
            'max_sub_sharpe_median': max_sub_sharpe_median,
            'mean_increase': mean_increase,
            'median_increase': median_increase,
            'found_subs': found_subs
        }

        return passes, info

    def generate_stage_report(self, k: int) -> str:
        """
        生成阶段k的统计报告

        Args:
            k: 阶段编号

        Returns:
            Markdown格式的报告
        """
        if k not in self.candidates_by_stage:
            self.load_stage(k)

        candidates = self.candidates_by_stage.get(k, [])

        if not candidates:
            return f"# 阶段{k}报告\n\n无候选通过筛选\n"

        # 统计
        sharpe_means = [c['sharpe_mean'] for c in candidates]
        sharpe_medians = [c['sharpe_median'] for c in candidates]

        report = [
            f"# 阶段{k}候选池统计报告",
            "",
            f"## 基本信息",
            f"- **候选数量**: {len(candidates)}",
            f"- **涉及选项**: {sorted(self.get_all_options(k))}",
            "",
            f"## 性能分布",
            f"- **夏普均值**:",
            f"  - 最大: {max(sharpe_means):.4f}",
            f"  - 最小: {min(sharpe_means):.4f}",
            f"  - 平均: {sum(sharpe_means) / len(sharpe_means):.4f}",
            f"- **夏普中位数**:",
            f"  - 最大: {max(sharpe_medians):.4f}",
            f"  - 最小: {min(sharpe_medians):.4f}",
            f"  - 平均: {sum(sharpe_medians) / len(sharpe_medians):.4f}",
            "",
            f"## Top 10 候选（按夏普均值排序）",
            ""
        ]

        # 排序
        sorted_candidates = sorted(candidates, key=lambda x: x['sharpe_mean'], reverse=True)

        report.append("| 排名 | 选项组合 | 夏普均值 | 夏普中位数 |")
        report.append("|------|---------|---------|-----------|")

        for i, cand in enumerate(sorted_candidates[:10], 1):
            options_str = ', '.join(cand['options'])
            report.append(
                f"| {i} | {options_str} | {cand['sharpe_mean']:.4f} | {cand['sharpe_median']:.4f} |"
            )

        return '\n'.join(report)


def main():
    parser = argparse.ArgumentParser(description='候选池管理工具')
    parser.add_argument('--candidates-dir', required=True, help='候选池目录')
    parser.add_argument('--action', choices=['report', 'list', 'check'], default='report',
                        help='操作: report=生成报告, list=列出候选, check=检查严格递增')
    parser.add_argument('--stage', type=int, help='阶段编号')
    parser.add_argument('--output', help='输出文件路径（Markdown）')

    args = parser.parse_args()

    manager = CandidateManager(args.candidates_dir)

    if args.action == 'report':
        if args.stage is None:
            print("错误: --action=report 需要指定 --stage")
            sys.exit(1)

        report = manager.generate_stage_report(args.stage)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"✓ 报告已保存到: {args.output}")
        else:
            print(report)

    elif args.action == 'list':
        if args.stage is None:
            print("错误: --action=list 需要指定 --stage")
            sys.exit(1)

        candidates = manager.load_stage(args.stage)
        print(f"阶段{args.stage}候选数: {len(candidates)}")
        for cand in candidates:
            print(f"  - {cand['options']}: mean={cand['sharpe_mean']:.4f}, median={cand['sharpe_median']:.4f}")

    elif args.action == 'check':
        if args.stage is None or args.stage <= 1:
            print("错误: --action=check 需要指定 --stage >= 2")
            sys.exit(1)

        candidates = manager.load_stage(args.stage)
        prev_stage = args.stage - 1

        print(f"检查阶段{args.stage}的{len(candidates)}个候选是否满足严格递增条件...")
        print(f"参考阶段: {prev_stage}\n")

        for cand in candidates:
            passes, info = manager.check_strict_increase(cand, prev_stage)
            status = "✓ 通过" if passes else "✗ 未通过"
            print(f"{status} {cand['options']}")
            if not passes:
                print(f"  原因: {info.get('reason', '不满足严格递增')}")


if __name__ == '__main__':
    main()
