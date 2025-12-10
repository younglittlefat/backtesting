#!/usr/bin/env python3
"""
分析聚类 vs 贪心对比实验结果

主要分析:
1. 配对比较: 同维度同周期下 clustering vs greedy
2. 汇总统计: 聚类胜出次数、平均提升幅度
3. 相关性分析: 池内相关性与回测表现的关系
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

# 实验目录
EXPERIMENT_DIR = Path(__file__).parent.parent
ANALYSIS_DIR = EXPERIMENT_DIR / "analysis"


def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """加载池生成和回测结果数据"""
    pool_summary_path = ANALYSIS_DIR / "pool_generation_summary.csv"
    backtest_summary_path = ANALYSIS_DIR / "backtest_results_summary.csv"

    pool_df = pd.DataFrame()
    backtest_df = pd.DataFrame()

    if pool_summary_path.exists():
        pool_df = pd.read_csv(pool_summary_path)
        print(f"加载池生成汇总: {len(pool_df)} 条记录")

    if backtest_summary_path.exists():
        backtest_df = pd.read_csv(backtest_summary_path)
        print(f"加载回测汇总: {len(backtest_df)} 条记录")

    return pool_df, backtest_df


def pairwise_comparison(backtest_df: pd.DataFrame) -> pd.DataFrame:
    """配对比较: 同维度同周期下 clustering vs greedy"""
    comparisons = []

    for dimension in backtest_df['dimension'].unique():
        for period in backtest_df['period'].unique():
            for market in backtest_df['market'].unique():
                subset = backtest_df[
                    (backtest_df['dimension'] == dimension) &
                    (backtest_df['period'] == period) &
                    (backtest_df['market'] == market)
                ]

                greedy = subset[subset['algorithm'] == 'greedy']
                clustering = subset[subset['algorithm'] == 'clustering']

                if len(greedy) == 0 or len(clustering) == 0:
                    continue

                greedy_sharpe = greedy['sharpe_mean'].values[0]
                clustering_sharpe = clustering['sharpe_mean'].values[0]
                greedy_return = greedy['return_mean'].values[0]
                clustering_return = clustering['return_mean'].values[0]

                sharpe_diff = clustering_sharpe - greedy_sharpe
                return_diff = clustering_return - greedy_return

                # 判断胜者
                sharpe_winner = "clustering" if sharpe_diff > 0 else ("greedy" if sharpe_diff < 0 else "tie")
                return_winner = "clustering" if return_diff > 0 else ("greedy" if return_diff < 0 else "tie")

                comparisons.append({
                    'dimension': dimension,
                    'period': period,
                    'market': market,
                    'greedy_sharpe': greedy_sharpe,
                    'clustering_sharpe': clustering_sharpe,
                    'sharpe_diff': sharpe_diff,
                    'sharpe_winner': sharpe_winner,
                    'greedy_return': greedy_return,
                    'clustering_return': clustering_return,
                    'return_diff': return_diff,
                    'return_winner': return_winner,
                })

    return pd.DataFrame(comparisons)


def summary_statistics(comparison_df: pd.DataFrame) -> Dict:
    """汇总统计"""
    total = len(comparison_df)

    if total == 0:
        return {}

    # 夏普比率统计
    sharpe_clustering_wins = (comparison_df['sharpe_winner'] == 'clustering').sum()
    sharpe_greedy_wins = (comparison_df['sharpe_winner'] == 'greedy').sum()
    sharpe_ties = (comparison_df['sharpe_winner'] == 'tie').sum()

    # 收益率统计
    return_clustering_wins = (comparison_df['return_winner'] == 'clustering').sum()
    return_greedy_wins = (comparison_df['return_winner'] == 'greedy').sum()

    # 平均提升
    avg_sharpe_diff = comparison_df['sharpe_diff'].mean()
    avg_return_diff = comparison_df['return_diff'].mean()

    # 按市场分组
    bear_market = comparison_df[comparison_df['market'] == 'bear_market']
    bull_market = comparison_df[comparison_df['market'] == 'bull_market']

    stats = {
        'total_comparisons': total,
        'sharpe_clustering_wins': sharpe_clustering_wins,
        'sharpe_greedy_wins': sharpe_greedy_wins,
        'sharpe_ties': sharpe_ties,
        'sharpe_clustering_win_rate': sharpe_clustering_wins / total if total > 0 else 0,
        'avg_sharpe_diff': avg_sharpe_diff,
        'return_clustering_wins': return_clustering_wins,
        'return_greedy_wins': return_greedy_wins,
        'avg_return_diff': avg_return_diff,
        'bear_market_sharpe_diff': bear_market['sharpe_diff'].mean() if len(bear_market) > 0 else np.nan,
        'bull_market_sharpe_diff': bull_market['sharpe_diff'].mean() if len(bull_market) > 0 else np.nan,
    }

    return stats


def correlation_analysis(pool_df: pd.DataFrame, backtest_df: pd.DataFrame) -> pd.DataFrame:
    """分析池内相关性与回测表现的关系"""
    if pool_df.empty or backtest_df.empty:
        return pd.DataFrame()

    # 合并数据
    merged = pd.merge(
        pool_df[['config_name', 'dimension', 'period', 'algorithm', 'avg_correlation', 'max_correlation']],
        backtest_df[['dimension', 'period', 'algorithm', 'market', 'sharpe_mean', 'return_mean']],
        on=['dimension', 'period', 'algorithm'],
        how='inner'
    )

    return merged


def generate_report(
    comparison_df: pd.DataFrame,
    stats: Dict,
    pool_df: pd.DataFrame,
    backtest_df: pd.DataFrame
) -> str:
    """生成分析报告"""
    report = []
    report.append("# 聚类 vs 贪心对比实验结果报告")
    report.append("")
    report.append("## 1. 实验概述")
    report.append("")
    report.append(f"- 总对比组数: {stats.get('total_comparisons', 0)}")
    report.append(f"- 评分维度: {comparison_df['dimension'].nunique() if not comparison_df.empty else 0} 个")
    report.append(f"- 筛选周期: {comparison_df['period'].nunique() if not comparison_df.empty else 0} 个")
    report.append(f"- 市场周期: {comparison_df['market'].nunique() if not comparison_df.empty else 0} 个")
    report.append("")

    report.append("## 2. 核心结论")
    report.append("")

    # 夏普比率对比
    clustering_win_rate = stats.get('sharpe_clustering_win_rate', 0)
    avg_sharpe_diff = stats.get('avg_sharpe_diff', 0)

    if clustering_win_rate > 0.5:
        conclusion = "聚类选择优于贪心算法"
    elif clustering_win_rate < 0.5:
        conclusion = "贪心算法优于聚类选择"
    else:
        conclusion = "两种算法表现相当"

    report.append(f"**主要结论**: {conclusion}")
    report.append("")
    report.append(f"- 聚类胜出次数: {stats.get('sharpe_clustering_wins', 0)}/{stats.get('total_comparisons', 0)} ({clustering_win_rate:.1%})")
    report.append(f"- 贪心胜出次数: {stats.get('sharpe_greedy_wins', 0)}/{stats.get('total_comparisons', 0)}")
    report.append(f"- 平均夏普差异: {avg_sharpe_diff:+.4f} (正值表示聚类更优)")
    report.append(f"- 平均收益差异: {stats.get('avg_return_diff', 0):+.2f}%")
    report.append("")

    report.append("## 3. 分市场分析")
    report.append("")
    report.append(f"- 熊市(2022-2023)平均夏普差异: {stats.get('bear_market_sharpe_diff', np.nan):+.4f}")
    report.append(f"- 牛市(2024-2025)平均夏普差异: {stats.get('bull_market_sharpe_diff', np.nan):+.4f}")
    report.append("")

    report.append("## 4. 详细对比表")
    report.append("")
    if not comparison_df.empty:
        report.append("| 维度 | 周期 | 市场 | 贪心夏普 | 聚类夏普 | 差异 | 胜者 |")
        report.append("|------|------|------|----------|----------|------|------|")
        for _, row in comparison_df.iterrows():
            winner_emoji = "聚类" if row['sharpe_winner'] == 'clustering' else ("贪心" if row['sharpe_winner'] == 'greedy' else "平")
            report.append(
                f"| {row['dimension']} | {row['period']} | {row['market']} | "
                f"{row['greedy_sharpe']:.3f} | {row['clustering_sharpe']:.3f} | "
                f"{row['sharpe_diff']:+.3f} | {winner_emoji} |"
            )
    report.append("")

    report.append("## 5. 相关性分析")
    report.append("")
    if not pool_df.empty:
        # 按算法分组统计相关性
        greedy_corr = pool_df[pool_df['algorithm'] == 'greedy']['avg_correlation'].mean()
        clustering_corr = pool_df[pool_df['algorithm'] == 'clustering']['avg_correlation'].mean()
        report.append(f"- 贪心算法平均池内相关性: {greedy_corr:.4f}")
        report.append(f"- 聚类算法平均池内相关性: {clustering_corr:.4f}")
        report.append(f"- 相关性降低: {(greedy_corr - clustering_corr) / greedy_corr * 100:.1f}%")
    report.append("")

    report.append("## 6. 建议")
    report.append("")
    if clustering_win_rate > 0.6:
        report.append("- 推荐使用聚类选择算法，在多数场景下表现更优")
    elif clustering_win_rate < 0.4:
        report.append("- 建议继续使用贪心算法，聚类选择未能带来显著提升")
    else:
        report.append("- 两种算法各有优劣，可根据具体场景选择")
        report.append("- 聚类选择在降低池内相关性方面有优势")
    report.append("")

    return "\n".join(report)


def main():
    print("=" * 60)
    print("分析聚类 vs 贪心对比实验结果")
    print("=" * 60)

    # 加载数据
    pool_df, backtest_df = load_data()

    if backtest_df.empty:
        print("\n错误: 未找到回测结果，请先运行 run_backtests.py")
        return

    # 配对比较
    print("\n执行配对比较...")
    comparison_df = pairwise_comparison(backtest_df)

    if comparison_df.empty:
        print("错误: 无法生成配对比较结果")
        return

    # 保存配对比较结果
    comparison_path = ANALYSIS_DIR / "pairwise_comparison.csv"
    comparison_df.to_csv(comparison_path, index=False, encoding='utf-8-sig')
    print(f"配对比较结果已保存: {comparison_path}")

    # 汇总统计
    print("\n计算汇总统计...")
    stats = summary_statistics(comparison_df)

    # 相关性分析
    print("\n执行相关性分析...")
    corr_analysis = correlation_analysis(pool_df, backtest_df)
    if not corr_analysis.empty:
        corr_path = ANALYSIS_DIR / "correlation_vs_performance.csv"
        corr_analysis.to_csv(corr_path, index=False, encoding='utf-8-sig')
        print(f"相关性分析结果已保存: {corr_path}")

    # 生成报告
    print("\n生成分析报告...")
    report = generate_report(comparison_df, stats, pool_df, backtest_df)

    report_path = EXPERIMENT_DIR / "RESULTS.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"分析报告已保存: {report_path}")

    # 打印核心结论
    print("\n" + "=" * 60)
    print("核心结论")
    print("=" * 60)
    print(f"聚类胜出率: {stats.get('sharpe_clustering_win_rate', 0):.1%}")
    print(f"平均夏普差异: {stats.get('avg_sharpe_diff', 0):+.4f}")
    print(f"平均收益差异: {stats.get('avg_return_diff', 0):+.2f}%")


if __name__ == "__main__":
    main()
