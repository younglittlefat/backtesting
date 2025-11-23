#!/usr/bin/env python3
"""
贪心筛选结果分析脚本

功能:
- 生成各阶段的详细分析报告
- 可视化剪枝过程（候选数量变化曲线）
- 对比最优组合与Baseline的性能提升
- 输出最终推荐配置

作者: Claude Code
日期: 2025-11-23
"""

import os
import sys
import json
import argparse
import glob
from typing import List, Dict
import pandas as pd


class GreedyResultAnalyzer:
    """贪心筛选结果分析器"""

    def __init__(self, output_dir: str):
        """
        初始化分析器

        Args:
            output_dir: 贪心测试输出目录（包含candidates/, reports/, backtests/）
        """
        self.output_dir = output_dir
        self.candidates_dir = os.path.join(output_dir, 'candidates')
        self.reports_dir = os.path.join(output_dir, 'reports')
        self.backtest_dir = os.path.join(output_dir, 'backtests')

        self.baseline = None
        self.stages_data = {}  # {stage: candidates_list}

    def load_baseline(self):
        """加载Baseline指标"""
        baseline_path = os.path.join(self.candidates_dir, 'baseline.json')
        if not os.path.exists(baseline_path):
            raise FileNotFoundError(f"Baseline文件不存在: {baseline_path}")

        with open(baseline_path, 'r', encoding='utf-8') as f:
            self.baseline = json.load(f)

    def load_all_stages(self):
        """加载所有阶段的候选池"""
        k = 1
        while True:
            candidates_path = os.path.join(self.candidates_dir, f'candidates_k{k}.json')
            if not os.path.exists(candidates_path):
                break

            with open(candidates_path, 'r', encoding='utf-8') as f:
                self.stages_data[k] = json.load(f)

            k += 1

    def generate_summary_report(self) -> str:
        """
        生成完整的汇总报告

        Returns:
            Markdown格式的报告
        """
        if not self.baseline:
            self.load_baseline()
        if not self.stages_data:
            self.load_all_stages()

        report = [
            "# MACD策略贪心筛选超参组合测试 - 汇总报告",
            "",
            f"## Baseline性能",
            f"- **夏普均值**: {self.baseline['sharpe_mean']:.4f}",
            f"- **夏普中位数**: {self.baseline['sharpe_median']:.4f}",
            "",
            "## 各阶段候选数量",
            ""
        ]

        max_stage = max(self.stages_data.keys()) if self.stages_data else 0

        report.append("| 阶段 | 候选数 | 夏普均值范围 | 夏普中位数范围 |")
        report.append("|------|--------|-------------|---------------|")

        for k in sorted(self.stages_data.keys()):
            candidates = self.stages_data[k]
            sharpe_means = [c['sharpe_mean'] for c in candidates]
            sharpe_medians = [c['sharpe_median'] for c in candidates]

            report.append(
                f"| 阶段{k} | {len(candidates)} | "
                f"{min(sharpe_means):.4f} - {max(sharpe_means):.4f} | "
                f"{min(sharpe_medians):.4f} - {max(sharpe_medians):.4f} |"
            )

        report.extend([
            "",
            f"## 剪枝效率",
            f"- **最终阶段**: 阶段{max_stage}",
            f"- **最终候选数**: {len(self.stages_data.get(max_stage, []))}",
            ""
        ])

        # 计算总实验数
        total_experiments = 1  # baseline
        for k, candidates in self.stages_data.items():
            # 阶段k测试的实验数 = 该阶段候选数 + 被剪枝的组合数
            # 但我们只统计成功的候选，所以这里简化为候选数
            # 实际测试数可能更多（包括未通过筛选的）
            total_experiments += len(candidates)

        # 更精确的统计：检查backtests目录
        backtest_dirs = glob.glob(os.path.join(self.backtest_dir, '*'))
        actual_experiments = len(backtest_dirs)

        report.extend([
            f"- **实际执行实验数**: {actual_experiments}（包括baseline和所有测试过的组合）",
            f"- **相比完整因子设计节省**: {1024 - actual_experiments} 个实验 ({(1024 - actual_experiments) / 1024 * 100:.1f}%)",
            "",
            "## 最优候选（全局Top 5）",
            ""
        ])

        # 收集所有候选，按夏普均值排序
        all_candidates = []
        for k, candidates in self.stages_data.items():
            for cand in candidates:
                cand['stage'] = k
                all_candidates.append(cand)

        all_candidates.sort(key=lambda x: x['sharpe_mean'], reverse=True)

        report.append("| 排名 | 阶段 | 选项组合 | 夏普均值 | 夏普中位数 | vs Baseline |")
        report.append("|------|------|---------|---------|-----------|-------------|")

        for i, cand in enumerate(all_candidates[:5], 1):
            options_str = ', '.join(cand['options'])
            improve_mean = (cand['sharpe_mean'] - self.baseline['sharpe_mean']) / self.baseline['sharpe_mean'] * 100
            improve_median = (cand['sharpe_median'] - self.baseline['sharpe_median']) / self.baseline['sharpe_median'] * 100

            report.append(
                f"| {i} | 阶段{cand['stage']} | {options_str} | "
                f"{cand['sharpe_mean']:.4f} | {cand['sharpe_median']:.4f} | "
                f"+{improve_mean:.1f}% / +{improve_median:.1f}% |"
            )

        report.extend([
            "",
            "## 推荐配置",
            ""
        ])

        if all_candidates:
            best = all_candidates[0]
            report.extend([
                f"### 最优配置（夏普均值最大）",
                f"- **选项**: {', '.join(best['options'])}",
                f"- **夏普均值**: {best['sharpe_mean']:.4f} (vs Baseline: +{(best['sharpe_mean'] - self.baseline['sharpe_mean']) / self.baseline['sharpe_mean'] * 100:.1f}%)",
                f"- **夏普中位数**: {best['sharpe_median']:.4f} (vs Baseline: +{(best['sharpe_median'] - self.baseline['sharpe_median']) / self.baseline['sharpe_median'] * 100:.1f}%)",
                "",
                "### 运行命令",
                "```bash",
                "./run_backtest.sh \\",
                "  --stock-list results/trend_etf_pool_2019_2022_optimized.csv \\",
                "  --strategy macd_cross \\",
                "  --optimize \\",
                "  --data-dir data/chinese_etf/daily \\",
                "  --start-date 20220102 \\",
                "  --end-date 20240102 \\"
            ])

            for opt in best['options']:
                if opt == 'confirm-bars-sell':
                    report.append(f"  --confirm-bars-sell 2 \\")
                elif opt == 'min-hold-bars':
                    report.append(f"  --min-hold-bars 3 \\")
                else:
                    report.append(f"  --{opt} \\")

            # 添加非store_true参数
            if 'enable-adx-filter' in best['options']:
                report.append("  --adx-period 14 --adx-threshold 25.0 \\")
            if 'enable-volume-filter' in best['options']:
                report.append("  --volume-period 20 --volume-ratio 1.2 \\")
            if 'enable-loss-protection' in best['options']:
                report.append("  --max-consecutive-losses 3 --pause-bars 10 \\")
            if 'enable-trailing-stop' in best['options']:
                report.append("  --trailing-stop-pct 0.05 \\")
            if 'enable-atr-stop' in best['options']:
                report.append("  --atr-period 14 --atr-multiplier 2.5 \\")
            if 'enable-hysteresis' in best['options']:
                report.append("  --hysteresis-mode std --hysteresis-k 0.5 --hysteresis-window 20 \\")
            if 'enable-zero-axis' in best['options']:
                report.append("  --zero-axis-mode symmetric \\")
            if 'enable-confirm-filter' in best['options']:
                report.append("  --confirm-bars 2 \\")

            # 移除最后的反斜杠
            report[-1] = report[-1].rstrip(' \\')
            report.append("```")

        return '\n'.join(report)

    def generate_stage_reports(self):
        """为每个阶段生成独立的详细报告"""
        if not self.stages_data:
            self.load_all_stages()

        for k, candidates in self.stages_data.items():
            report = self._generate_single_stage_report(k, candidates)

            report_path = os.path.join(self.reports_dir, f'stage_k{k}_report.md')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)

            print(f"✓ 生成阶段{k}报告: {report_path}")

    def _generate_single_stage_report(self, k: int, candidates: List[Dict]) -> str:
        """生成单个阶段的详细报告"""
        sharpe_means = [c['sharpe_mean'] for c in candidates]
        sharpe_medians = [c['sharpe_median'] for c in candidates]

        report = [
            f"# 阶段{k}详细报告",
            "",
            f"## 基本信息",
            f"- **候选数量**: {len(candidates)}",
            "",
            f"## 性能统计",
            f"### 夏普均值",
            f"- 最大: {max(sharpe_means):.4f}",
            f"- 最小: {min(sharpe_means):.4f}",
            f"- 平均: {sum(sharpe_means) / len(sharpe_means):.4f}",
            f"- 标准差: {pd.Series(sharpe_means).std():.4f}",
            "",
            f"### 夏普中位数",
            f"- 最大: {max(sharpe_medians):.4f}",
            f"- 最小: {min(sharpe_medians):.4f}",
            f"- 平均: {sum(sharpe_medians) / len(sharpe_medians):.4f}",
            f"- 标准差: {pd.Series(sharpe_medians).std():.4f}",
            "",
            f"## 完整候选列表（按夏普均值排序）",
            ""
        ]

        sorted_candidates = sorted(candidates, key=lambda x: x['sharpe_mean'], reverse=True)

        report.append("| 排名 | 选项组合 | 夏普均值 | 夏普中位数 |")
        report.append("|------|---------|---------|-----------|")

        for i, cand in enumerate(sorted_candidates, 1):
            options_str = ', '.join(cand['options'])
            report.append(
                f"| {i} | {options_str} | {cand['sharpe_mean']:.4f} | {cand['sharpe_median']:.4f} |"
            )

        return '\n'.join(report)

    def plot_pruning_curve(self, output_path: str = None):
        """
        绘制剪枝过程曲线（候选数量随阶段变化）

        Args:
            output_path: 输出图片路径，如果为None则显示
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("警告: matplotlib未安装，跳过绘图")
            return

        if not self.stages_data:
            self.load_all_stages()

        stages = sorted(self.stages_data.keys())
        candidate_counts = [len(self.stages_data[k]) for k in stages]

        plt.figure(figsize=(10, 6))
        plt.plot(stages, candidate_counts, marker='o', linewidth=2, markersize=8)
        plt.xlabel('阶段 (k)', fontsize=12)
        plt.ylabel('候选数量', fontsize=12)
        plt.title('贪心筛选剪枝过程', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.xticks(stages)

        # 标注每个点的数值
        for k, count in zip(stages, candidate_counts):
            plt.text(k, count + max(candidate_counts) * 0.02, str(count),
                     ha='center', va='bottom', fontsize=10)

        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✓ 剪枝曲线已保存: {output_path}")
        else:
            plt.show()

        plt.close()


def main():
    parser = argparse.ArgumentParser(description='贪心筛选结果分析脚本')
    parser.add_argument('--output-dir', required=True, help='贪心测试输出目录')
    parser.add_argument('--summary', action='store_true', help='生成汇总报告')
    parser.add_argument('--stage-reports', action='store_true', help='生成各阶段详细报告')
    parser.add_argument('--plot', action='store_true', help='绘制剪枝曲线')
    parser.add_argument('--all', action='store_true', help='执行所有分析')

    args = parser.parse_args()

    # 检查目录是否存在
    if not os.path.exists(args.output_dir):
        print(f"错误: 输出目录不存在: {args.output_dir}")
        sys.exit(1)

    analyzer = GreedyResultAnalyzer(args.output_dir)

    # 确保reports目录存在
    os.makedirs(analyzer.reports_dir, exist_ok=True)

    if args.all or args.summary:
        print("生成汇总报告...")
        report = analyzer.generate_summary_report()

        summary_path = os.path.join(analyzer.reports_dir, 'SUMMARY.md')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✓ 汇总报告已保存: {summary_path}\n")
        print(report)

    if args.all or args.stage_reports:
        print("\n生成各阶段详细报告...")
        analyzer.generate_stage_reports()

    if args.all or args.plot:
        print("\n绘制剪枝曲线...")
        plot_path = os.path.join(analyzer.reports_dir, 'pruning_curve.png')
        analyzer.plot_pruning_curve(plot_path)


if __name__ == '__main__':
    main()
