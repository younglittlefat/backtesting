#!/usr/bin/env python3
"""
生成MACD策略止损实验的可视化图表

生成内容：
1. Loss Protection参数热力图（max_consecutive_losses vs pause_bars）
2. Trailing Stop参数对比图
3. 各策略表现对比图（柱状图）
4. Combined参数3D热力图

作者: Claude Code
日期: 2025-11-09
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional

# 设置中文字体（支持中文显示）
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置seaborn样式
sns.set_style('whitegrid')
sns.set_palette('husl')


def load_results(output_dir: Path) -> dict:
    """
    加载所有实验结果

    Returns:
        dict: 包含各阶段结果的字典
    """
    results = {}

    csv_files = {
        'baseline': 'results_baseline.csv',
        'loss_protection': 'results_loss_protection.csv',
        'trailing_stop': 'results_trailing_stop.csv',
        'combined': 'results_combined.csv',
    }

    for key, filename in csv_files.items():
        csv_path = output_dir / filename
        if csv_path.exists():
            results[key] = pd.read_csv(csv_path)
            print(f"✅ 加载 {filename}: {len(results[key])} 条记录")
        else:
            print(f"⚠️  未找到 {filename}")
            results[key] = pd.DataFrame()

    return results


def plot_loss_protection_heatmap(df: pd.DataFrame, output_dir: Path, metric: str = 'sharpe_ratio') -> None:
    """
    绘制Loss Protection参数热力图

    Args:
        df: Loss Protection结果DataFrame
        output_dir: 输出目录
        metric: 要可视化的指标（默认: sharpe_ratio）
    """
    if df.empty:
        print("⚠️  Loss Protection数据为空，跳过热力图生成")
        return

    print(f"\n生成Loss Protection热力图 (metric={metric})...")

    # 计算每个参数组合的平均值
    pivot_data = df.groupby(['max_consecutive_losses', 'pause_bars'])[metric].mean().reset_index()
    pivot_table = pivot_data.pivot(index='max_consecutive_losses', columns='pause_bars', values=metric)

    # 绘制热力图
    fig, ax = plt.subplots(figsize=(10, 8))

    sns.heatmap(
        pivot_table,
        annot=True,
        fmt='.2f',
        cmap='RdYlGn' if metric == 'sharpe_ratio' else 'RdYlGn_r',
        center=pivot_table.mean().mean(),
        linewidths=0.5,
        cbar_kws={'label': metric.replace('_', ' ').title()},
        ax=ax
    )

    ax.set_xlabel('Pause Bars', fontsize=12, fontweight='bold')
    ax.set_ylabel('Max Consecutive Losses', fontsize=12, fontweight='bold')
    ax.set_title(f'Loss Protection Parameter Heatmap - {metric.replace("_", " ").title()}',
                 fontsize=14, fontweight='bold', pad=20)

    # 标记最佳参数
    if metric == 'sharpe_ratio' or 'return' in metric:
        best_idx = pivot_table.stack().idxmax()
    else:  # drawdown等，越小越好
        best_idx = pivot_table.stack().idxmin()

    # 在热力图上标记最佳参数
    best_row = list(pivot_table.index).index(best_idx[0])
    best_col = list(pivot_table.columns).index(best_idx[1])
    ax.add_patch(plt.Rectangle((best_col, best_row), 1, 1, fill=False, edgecolor='blue', lw=3))

    plt.tight_layout()
    output_file = output_dir / f'heatmap_loss_protection_{metric}.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"✅ 热力图已保存: {output_file}")


def plot_trailing_stop_comparison(df: pd.DataFrame, output_dir: Path) -> None:
    """
    绘制Trailing Stop参数对比图

    Args:
        df: Trailing Stop结果DataFrame
        output_dir: 输出目录
    """
    if df.empty:
        print("⚠️  Trailing Stop数据为空，跳过对比图生成")
        return

    print(f"\n生成Trailing Stop参数对比图...")

    # 计算每个参数的平均值
    metrics = ['sharpe_ratio', 'return_pct', 'max_drawdown_pct', 'win_rate_pct']
    avg_by_pct = df.groupby('trailing_stop_pct')[metrics].mean()

    # 创建2x2子图
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    metric_titles = {
        'sharpe_ratio': 'Sharpe Ratio',
        'return_pct': 'Return (%)',
        'max_drawdown_pct': 'Max Drawdown (%)',
        'win_rate_pct': 'Win Rate (%)',
    }

    for idx, metric in enumerate(metrics):
        ax = axes[idx]

        # 绘制柱状图
        bars = ax.bar(
            [f"{p*100:.0f}%" for p in avg_by_pct.index],
            avg_by_pct[metric],
            color='steelblue',
            alpha=0.7,
            edgecolor='black'
        )

        # 标记最佳值
        if metric in ['sharpe_ratio', 'return_pct', 'win_rate_pct']:
            best_idx = avg_by_pct[metric].idxmax()
        else:
            best_idx = avg_by_pct[metric].idxmin()

        best_pos = list(avg_by_pct.index).index(best_idx)
        bars[best_pos].set_color('green')
        bars[best_pos].set_alpha(0.9)

        # 在柱子上方显示数值
        for i, v in enumerate(avg_by_pct[metric]):
            ax.text(i, v, f'{v:.2f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.set_xlabel('Trailing Stop Percentage', fontsize=11, fontweight='bold')
        ax.set_ylabel(metric_titles[metric], fontsize=11, fontweight='bold')
        ax.set_title(f'{metric_titles[metric]} by Trailing Stop %', fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

    plt.suptitle('Trailing Stop Parameter Comparison', fontsize=16, fontweight='bold', y=1.00)
    plt.tight_layout()

    output_file = output_dir / 'comparison_trailing_stop.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"✅ Trailing Stop对比图已保存: {output_file}")


def plot_strategy_comparison(results: dict, output_dir: Path) -> None:
    """
    绘制各策略表现对比图

    Args:
        results: 包含所有策略结果的字典
        output_dir: 输出目录
    """
    print(f"\n生成策略表现对比图...")

    # 合并所有结果
    all_results = []
    for strategy_name, df in results.items():
        if not df.empty:
            all_results.append(df)

    if not all_results:
        print("⚠️  没有可用数据，跳过策略对比图生成")
        return

    combined_df = pd.concat(all_results, ignore_index=True)

    # 计算每个策略的平均值
    metrics = ['sharpe_ratio', 'return_pct', 'max_drawdown_pct', 'win_rate_pct']
    avg_by_strategy = combined_df.groupby('strategy')[metrics].mean()

    # 策略排序（按夏普比率）
    avg_by_strategy = avg_by_strategy.sort_values('sharpe_ratio', ascending=False)

    # 创建2x2子图
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    metric_titles = {
        'sharpe_ratio': 'Sharpe Ratio',
        'return_pct': 'Return (%)',
        'max_drawdown_pct': 'Max Drawdown (%)',
        'win_rate_pct': 'Win Rate (%)',
    }

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    for idx, metric in enumerate(metrics):
        ax = axes[idx]

        # 绘制柱状图
        bars = ax.bar(
            avg_by_strategy.index,
            avg_by_strategy[metric],
            color=colors[:len(avg_by_strategy)],
            alpha=0.7,
            edgecolor='black'
        )

        # 标记最佳策略
        if metric in ['sharpe_ratio', 'return_pct', 'win_rate_pct']:
            best_idx = avg_by_strategy[metric].idxmax()
        else:
            best_idx = avg_by_strategy[metric].idxmin()

        best_pos = list(avg_by_strategy.index).index(best_idx)
        bars[best_pos].set_edgecolor('gold')
        bars[best_pos].set_linewidth(3)

        # 在柱子上方显示数值
        for i, v in enumerate(avg_by_strategy[metric]):
            ax.text(i, v, f'{v:.2f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.set_xlabel('Strategy', fontsize=11, fontweight='bold')
        ax.set_ylabel(metric_titles[metric], fontsize=11, fontweight='bold')
        ax.set_title(f'{metric_titles[metric]} by Strategy', fontsize=12, fontweight='bold')
        ax.set_xticklabels(avg_by_strategy.index, rotation=15, ha='right')
        ax.grid(axis='y', alpha=0.3)

    plt.suptitle('Strategy Performance Comparison', fontsize=16, fontweight='bold', y=1.00)
    plt.tight_layout()

    output_file = output_dir / 'comparison_all_strategies.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"✅ 策略对比图已保存: {output_file}")


def plot_combined_heatmaps(df: pd.DataFrame, output_dir: Path) -> None:
    """
    绘制Combined策略的多个热力图（每个trailing_stop_pct一个）

    Args:
        df: Combined结果DataFrame
        output_dir: 输出目录
    """
    if df.empty:
        print("⚠️  Combined数据为空，跳过热力图生成")
        return

    print(f"\n生成Combined策略热力图...")

    unique_pcts = sorted(df['trailing_stop_pct'].unique())
    n_pcts = len(unique_pcts)

    if n_pcts == 0:
        print("⚠️  没有trailing_stop_pct数据")
        return

    # 创建子图
    fig, axes = plt.subplots(1, n_pcts, figsize=(6*n_pcts, 5))
    if n_pcts == 1:
        axes = [axes]

    for idx, pct in enumerate(unique_pcts):
        ax = axes[idx]

        # 过滤数据
        df_pct = df[df['trailing_stop_pct'] == pct]

        # 计算平均夏普比率
        pivot_data = df_pct.groupby(['max_consecutive_losses', 'pause_bars'])['sharpe_ratio'].mean().reset_index()
        pivot_table = pivot_data.pivot(index='max_consecutive_losses', columns='pause_bars', values='sharpe_ratio')

        # 绘制热力图
        sns.heatmap(
            pivot_table,
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            center=pivot_table.mean().mean(),
            linewidths=0.5,
            cbar_kws={'label': 'Sharpe Ratio'},
            ax=ax
        )

        ax.set_xlabel('Pause Bars', fontsize=10, fontweight='bold')
        ax.set_ylabel('Max Consecutive Losses', fontsize=10, fontweight='bold')
        ax.set_title(f'Trailing Stop = {pct*100:.0f}%', fontsize=12, fontweight='bold')

    plt.suptitle('Combined Strategy - Sharpe Ratio Heatmaps', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    output_file = output_dir / 'heatmap_combined_by_trailing_stop.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"✅ Combined热力图已保存: {output_file}")


def plot_parameter_sensitivity(df: pd.DataFrame, output_dir: Path, strategy: str) -> None:
    """
    绘制参数敏感性分析图（箱线图）

    Args:
        df: 结果DataFrame
        output_dir: 输出目录
        strategy: 策略名称
    """
    if df.empty:
        print(f"⚠️  {strategy}数据为空，跳过敏感性分析图")
        return

    print(f"\n生成{strategy}参数敏感性分析图...")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    if strategy == 'loss_protection':
        # max_consecutive_losses的影响
        df.boxplot(column='sharpe_ratio', by='max_consecutive_losses', ax=axes[0])
        axes[0].set_xlabel('Max Consecutive Losses', fontsize=11, fontweight='bold')
        axes[0].set_ylabel('Sharpe Ratio', fontsize=11, fontweight='bold')
        axes[0].set_title('Sensitivity to Max Consecutive Losses', fontsize=12, fontweight='bold')
        axes[0].get_figure().suptitle('')  # 移除默认标题

        # pause_bars的影响
        df.boxplot(column='sharpe_ratio', by='pause_bars', ax=axes[1])
        axes[1].set_xlabel('Pause Bars', fontsize=11, fontweight='bold')
        axes[1].set_ylabel('Sharpe Ratio', fontsize=11, fontweight='bold')
        axes[1].set_title('Sensitivity to Pause Bars', fontsize=12, fontweight='bold')
        axes[1].get_figure().suptitle('')

    elif strategy == 'trailing_stop':
        # trailing_stop_pct的影响
        df.boxplot(column='sharpe_ratio', by='trailing_stop_pct', ax=axes[0])
        axes[0].set_xlabel('Trailing Stop Percentage', fontsize=11, fontweight='bold')
        axes[0].set_ylabel('Sharpe Ratio', fontsize=11, fontweight='bold')
        axes[0].set_title('Sensitivity to Trailing Stop %', fontsize=12, fontweight='bold')
        axes[0].get_figure().suptitle('')

        # 第二个图显示胜率
        df.boxplot(column='win_rate_pct', by='trailing_stop_pct', ax=axes[1])
        axes[1].set_xlabel('Trailing Stop Percentage', fontsize=11, fontweight='bold')
        axes[1].set_ylabel('Win Rate (%)', fontsize=11, fontweight='bold')
        axes[1].set_title('Win Rate vs Trailing Stop %', fontsize=12, fontweight='bold')
        axes[1].get_figure().suptitle('')

    plt.tight_layout()

    output_file = output_dir / f'sensitivity_{strategy}.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"✅ {strategy}敏感性分析图已保存: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='生成MACD策略止损实验的可视化图表')
    parser.add_argument('--output-dir', type=str,
                        default='experiment/etf/macd_cross/grid_search_stop_loss',
                        help='实验结果目录')

    args = parser.parse_args()
    output_dir = Path(args.output_dir)

    print(f"\n{'='*70}")
    print("生成可视化图表")
    print(f"{'='*70}")
    print(f"结果目录: {output_dir}")
    print()

    # 加载结果
    results = load_results(output_dir)

    # 1. Loss Protection热力图
    if not results['loss_protection'].empty:
        plot_loss_protection_heatmap(results['loss_protection'], output_dir, 'sharpe_ratio')
        plot_loss_protection_heatmap(results['loss_protection'], output_dir, 'max_drawdown_pct')
        plot_parameter_sensitivity(results['loss_protection'], output_dir, 'loss_protection')

    # 2. Trailing Stop对比图
    if not results['trailing_stop'].empty:
        plot_trailing_stop_comparison(results['trailing_stop'], output_dir)
        plot_parameter_sensitivity(results['trailing_stop'], output_dir, 'trailing_stop')

    # 3. 策略对比图
    plot_strategy_comparison(results, output_dir)

    # 4. Combined热力图
    if not results['combined'].empty:
        plot_combined_heatmaps(results['combined'], output_dir)

    print(f"\n{'='*70}")
    print("✅ 所有可视化图表生成完成！")
    print(f"{'='*70}")
    print(f"图表保存位置: {output_dir}")


if __name__ == '__main__':
    main()
