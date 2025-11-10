#!/usr/bin/env python3
"""
生成MACD策略止损实验的详细报告（Markdown格式）

生成 RESULTS.md 报告，包含：
1. 实验概述
2. 各策略表现统计
3. 最佳参数推荐
4. 参数敏感性分析
5. 结论和建议

作者: Claude Code
日期: 2025-11-09
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


def load_results(output_dir: Path) -> Dict[str, pd.DataFrame]:
    """加载所有实验结果"""
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
        else:
            results[key] = pd.DataFrame()

    return results


def generate_overview_section(results: Dict[str, pd.DataFrame]) -> str:
    """生成实验概述部分"""
    total_tests = sum(len(df) for df in results.values())
    total_stocks = len(results['baseline']) if not results['baseline'].empty else 0

    md = "## 1. 实验概述\n\n"
    md += "### 1.1 实验目标\n\n"
    md += "通过网格搜索优化MACD策略的止损保护参数，提升风险调整后收益（夏普比率）。\n\n"
    md += "### 1.2 实验配置\n\n"
    md += f"- **测试标的**: {total_stocks} 只中国ETF\n"
    md += f"- **测试周期**: 2023-11至2025-11（约2年）\n"
    md += f"- **总测试次数**: {total_tests}\n"
    md += "- **优化方法**: 每个止损参数组合下，优化MACD基础参数（fast_period, slow_period, signal_period）\n"
    md += "- **优化目标**: 夏普比率最大化\n\n"

    md += "### 1.3 测试方案\n\n"
    md += "| 方案 | 描述 | 参数组合数 | 测试次数 |\n"
    md += "|------|------|-----------|----------|\n"
    md += f"| Baseline | 无止损对照组 | 1 | {len(results['baseline'])} |\n"
    md += f"| Loss Protection | 连续止损保护 | 16 | {len(results['loss_protection'])} |\n"
    md += f"| Trailing Stop | 跟踪止损 | 4 | {len(results['trailing_stop'])} |\n"
    md += f"| Combined | 组合止损 | 27 | {len(results['combined'])} |\n\n"

    return md


def generate_baseline_section(df: pd.DataFrame) -> str:
    """生成Baseline结果部分"""
    if df.empty:
        return "## 2. Baseline结果\n\n无数据。\n\n"

    md = "## 2. Baseline结果（无止损对照组）\n\n"
    md += "### 2.1 汇总统计\n\n"

    stats = {
        '平均收益率 (%)': df['return_pct'].mean(),
        '收益率标准差 (%)': df['return_pct'].std(),
        '平均夏普比率': df['sharpe_ratio'].mean(),
        '夏普标准差': df['sharpe_ratio'].std(),
        '平均最大回撤 (%)': df['max_drawdown_pct'].mean(),
        '平均胜率 (%)': df['win_rate_pct'].mean(),
        '平均交易次数': df['num_trades'].mean(),
    }

    md += "| 指标 | 值 |\n"
    md += "|------|----|\n"
    for key, value in stats.items():
        md += f"| {key} | {value:.2f} |\n"

    md += "\n### 2.2 最佳/最差标的\n\n"

    # 最佳标的
    best_idx = df['sharpe_ratio'].idxmax()
    best = df.loc[best_idx]
    md += f"**最佳标的**: {best['ts_code']}\n"
    md += f"- 夏普比率: {best['sharpe_ratio']:.2f}\n"
    md += f"- 收益率: {best['return_pct']:.2f}%\n"
    md += f"- 最大回撤: {best['max_drawdown_pct']:.2f}%\n\n"

    # 最差标的
    worst_idx = df['sharpe_ratio'].idxmin()
    worst = df.loc[worst_idx]
    md += f"**最差标的**: {worst['ts_code']}\n"
    md += f"- 夏普比率: {worst['sharpe_ratio']:.2f}\n"
    md += f"- 收益率: {worst['return_pct']:.2f}%\n"
    md += f"- 最大回撤: {worst['max_drawdown_pct']:.2f}%\n\n"

    return md


def generate_loss_protection_section(df: pd.DataFrame, baseline_df: pd.DataFrame) -> str:
    """生成Loss Protection结果部分"""
    if df.empty:
        return "## 3. Loss Protection结果\n\n无数据。\n\n"

    md = "## 3. Loss Protection结果（连续止损保护）\n\n"
    md += "### 3.1 参数网格搜索结果\n\n"

    # 计算每个参数组合的平均表现
    avg_by_params = df.groupby(['max_consecutive_losses', 'pause_bars']).agg({
        'sharpe_ratio': 'mean',
        'return_pct': 'mean',
        'max_drawdown_pct': 'mean',
        'win_rate_pct': 'mean',
    }).round(2)

    md += "**平均夏普比率 by 参数组合**:\n\n"
    md += avg_by_params['sharpe_ratio'].to_markdown() + "\n\n"

    # 找出最佳参数
    best_params = avg_by_params['sharpe_ratio'].idxmax()
    best_sharpe = avg_by_params['sharpe_ratio'].max()

    md += "### 3.2 最佳参数推荐\n\n"
    md += f"- **max_consecutive_losses**: {best_params[0]}\n"
    md += f"- **pause_bars**: {best_params[1]}\n"
    md += f"- **平均夏普比率**: {best_sharpe:.2f}\n\n"

    # 与Baseline对比
    if not baseline_df.empty:
        baseline_sharpe = baseline_df['sharpe_ratio'].mean()
        improvement = (best_sharpe - baseline_sharpe) / baseline_sharpe * 100

        md += "### 3.3 相比Baseline的改进\n\n"
        md += f"- Baseline平均夏普: {baseline_sharpe:.2f}\n"
        md += f"- Loss Protection最佳夏普: {best_sharpe:.2f}\n"
        md += f"- **提升幅度**: {improvement:+.1f}%\n\n"

    # 参数敏感性分析
    md += "### 3.4 参数敏感性\n\n"

    # 按max_consecutive_losses分组
    by_losses = df.groupby('max_consecutive_losses')['sharpe_ratio'].agg(['mean', 'std']).round(2)
    md += "**按 max_consecutive_losses 分组**:\n\n"
    md += by_losses.to_markdown() + "\n\n"

    # 按pause_bars分组
    by_pause = df.groupby('pause_bars')['sharpe_ratio'].agg(['mean', 'std']).round(2)
    md += "**按 pause_bars 分组**:\n\n"
    md += by_pause.to_markdown() + "\n\n"

    return md


def generate_trailing_stop_section(df: pd.DataFrame, baseline_df: pd.DataFrame) -> str:
    """生成Trailing Stop结果部分"""
    if df.empty:
        return "## 4. Trailing Stop结果\n\n无数据。\n\n"

    md = "## 4. Trailing Stop结果（跟踪止损）\n\n"
    md += "### 4.1 参数对比\n\n"

    # 计算每个参数的平均表现
    avg_by_pct = df.groupby('trailing_stop_pct').agg({
        'sharpe_ratio': 'mean',
        'return_pct': 'mean',
        'max_drawdown_pct': 'mean',
        'win_rate_pct': 'mean',
    }).round(2)

    md += avg_by_pct.to_markdown() + "\n\n"

    # 找出最佳参数
    best_pct = avg_by_pct['sharpe_ratio'].idxmax()
    best_sharpe = avg_by_pct['sharpe_ratio'].max()

    md += "### 4.2 最佳参数推荐\n\n"
    md += f"- **trailing_stop_pct**: {best_pct*100:.0f}%\n"
    md += f"- **平均夏普比率**: {best_sharpe:.2f}\n\n"

    # 与Baseline对比
    if not baseline_df.empty:
        baseline_sharpe = baseline_df['sharpe_ratio'].mean()
        improvement = (best_sharpe - baseline_sharpe) / baseline_sharpe * 100

        md += "### 4.3 相比Baseline的改进\n\n"
        md += f"- Baseline平均夏普: {baseline_sharpe:.2f}\n"
        md += f"- Trailing Stop最佳夏普: {best_sharpe:.2f}\n"
        md += f"- **提升幅度**: {improvement:+.1f}%\n\n"

    return md


def generate_combined_section(df: pd.DataFrame, baseline_df: pd.DataFrame) -> str:
    """生成Combined结果部分"""
    if df.empty:
        return "## 5. Combined结果\n\n无数据。\n\n"

    md = "## 5. Combined结果（组合止损）\n\n"
    md += "### 5.1 最佳参数组合\n\n"

    # 找出最佳参数组合
    avg_by_params = df.groupby(['max_consecutive_losses', 'pause_bars', 'trailing_stop_pct'])['sharpe_ratio'].mean()
    best_params = avg_by_params.idxmax()
    best_sharpe = avg_by_params.max()

    md += f"- **max_consecutive_losses**: {best_params[0]}\n"
    md += f"- **pause_bars**: {best_params[1]}\n"
    md += f"- **trailing_stop_pct**: {best_params[2]*100:.0f}%\n"
    md += f"- **平均夏普比率**: {best_sharpe:.2f}\n\n"

    # 与Baseline对比
    if not baseline_df.empty:
        baseline_sharpe = baseline_df['sharpe_ratio'].mean()
        improvement = (best_sharpe - baseline_sharpe) / baseline_sharpe * 100

        md += "### 5.2 相比Baseline的改进\n\n"
        md += f"- Baseline平均夏普: {baseline_sharpe:.2f}\n"
        md += f"- Combined最佳夏普: {best_sharpe:.2f}\n"
        md += f"- **提升幅度**: {improvement:+.1f}%\n\n"

    # Top 5 参数组合
    md += "### 5.3 Top 5 参数组合\n\n"
    top5 = avg_by_params.nlargest(5).reset_index()
    top5.columns = ['max_losses', 'pause_bars', 'trailing_stop_pct', 'avg_sharpe']
    top5['trailing_stop_pct'] = top5['trailing_stop_pct'].apply(lambda x: f"{x*100:.0f}%")

    md += top5.to_markdown(index=False) + "\n\n"

    return md


def generate_comparison_section(results: Dict[str, pd.DataFrame]) -> str:
    """生成各策略对比部分"""
    md = "## 6. 策略对比\n\n"
    md += "### 6.1 整体表现\n\n"

    # 合并所有结果并计算平均值
    comparison_data = []

    for strategy_name, df in results.items():
        if df.empty:
            continue

        avg_stats = {
            '策略': strategy_name,
            '平均夏普': df['sharpe_ratio'].mean(),
            '平均收益(%)': df['return_pct'].mean(),
            '平均回撤(%)': df['max_drawdown_pct'].mean(),
            '平均胜率(%)': df['win_rate_pct'].mean(),
        }
        comparison_data.append(avg_stats)

    if comparison_data:
        comparison_df = pd.DataFrame(comparison_data)
        comparison_df = comparison_df.round(2)
        comparison_df = comparison_df.sort_values('平均夏普', ascending=False)

        md += comparison_df.to_markdown(index=False) + "\n\n"

    # 找出最佳策略
    if comparison_data:
        best_strategy = comparison_df.iloc[0]
        md += f"**最佳策略**: {best_strategy['策略']}\n\n"

    return md


def generate_conclusion_section(results: Dict[str, pd.DataFrame]) -> str:
    """生成结论和建议部分"""
    md = "## 7. 结论和建议\n\n"

    md += "### 7.1 主要发现\n\n"

    # 比较各策略的改进幅度
    if not results['baseline'].empty:
        baseline_sharpe = results['baseline']['sharpe_ratio'].mean()

        improvements = {}
        for strategy_name in ['loss_protection', 'trailing_stop', 'combined']:
            if not results[strategy_name].empty:
                avg_sharpe = results[strategy_name].groupby(
                    list(results[strategy_name].columns[results[strategy_name].columns.str.contains('consecutive|pause|trailing')])
                )['sharpe_ratio'].mean().max()
                improvement = (avg_sharpe - baseline_sharpe) / baseline_sharpe * 100
                improvements[strategy_name] = improvement

        if improvements:
            best_improvement_strategy = max(improvements, key=improvements.get)
            best_improvement = improvements[best_improvement_strategy]

            md += f"1. **最有效的止损方式**: {best_improvement_strategy}，相比Baseline提升 **{best_improvement:+.1f}%**\n"

    md += "2. **参数敏感性**: 根据实验结果，参数变化对结果的影响程度\n"
    md += "3. **稳定性**: 各策略在不同标的上的表现稳定性\n\n"

    md += "### 7.2 推荐配置\n\n"

    # 为每种策略提供推荐配置
    if not results['loss_protection'].empty:
        best_loss = results['loss_protection'].groupby(['max_consecutive_losses', 'pause_bars'])['sharpe_ratio'].mean().idxmax()
        md += f"**Loss Protection推荐**:\n"
        md += f"```bash\n"
        md += f"--enable-macd-loss-protection \\\n"
        md += f"--macd-max-consecutive-losses {best_loss[0]} \\\n"
        md += f"--macd-pause-bars {best_loss[1]}\n"
        md += f"```\n\n"

    if not results['trailing_stop'].empty:
        best_trailing = results['trailing_stop'].groupby('trailing_stop_pct')['sharpe_ratio'].mean().idxmax()
        md += f"**Trailing Stop推荐**:\n"
        md += f"```bash\n"
        md += f"--enable-macd-trailing-stop \\\n"
        md += f"--macd-trailing-stop-pct {best_trailing}\n"
        md += f"```\n\n"

    if not results['combined'].empty:
        best_combined = results['combined'].groupby(['max_consecutive_losses', 'pause_bars', 'trailing_stop_pct'])['sharpe_ratio'].mean().idxmax()
        md += f"**Combined推荐**:\n"
        md += f"```bash\n"
        md += f"--enable-macd-loss-protection \\\n"
        md += f"--macd-max-consecutive-losses {best_combined[0]} \\\n"
        md += f"--macd-pause-bars {best_combined[1]} \\\n"
        md += f"--enable-macd-trailing-stop \\\n"
        md += f"--macd-trailing-stop-pct {best_combined[2]}\n"
        md += f"```\n\n"

    md += "### 7.3 后续工作\n\n"
    md += "1. **跨市场验证**: 在美股ETF上验证参数的通用性\n"
    md += "2. **组合过滤器**: 测试止损 + ADX/成交量过滤器的组合效果\n"
    md += "3. **滚动窗口回测**: Walk-forward分析，评估参数的时间稳定性\n"
    md += "4. **实盘验证**: 使用推荐参数进行模拟盘测试\n\n"

    return md


def generate_report(output_dir: Path) -> None:
    """生成完整报告"""
    print(f"\n{'='*70}")
    print("生成实验报告")
    print(f"{'='*70}")

    # 加载结果
    results = load_results(output_dir)

    # 生成报告内容
    report_md = f"# MACD策略止损超参网格搜索实验报告\n\n"
    report_md += f"**实验日期**: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    report_md += f"**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report_md += "---\n\n"

    # 各个部分
    report_md += generate_overview_section(results)
    report_md += generate_baseline_section(results['baseline'])
    report_md += generate_loss_protection_section(results['loss_protection'], results['baseline'])
    report_md += generate_trailing_stop_section(results['trailing_stop'], results['baseline'])
    report_md += generate_combined_section(results['combined'], results['baseline'])
    report_md += generate_comparison_section(results)
    report_md += generate_conclusion_section(results)

    # 添加可视化图表索引
    report_md += "## 8. 可视化图表\n\n"
    report_md += "实验生成了以下可视化图表：\n\n"
    report_md += "1. `heatmap_loss_protection_sharpe_ratio.png` - Loss Protection参数热力图（夏普比率）\n"
    report_md += "2. `heatmap_loss_protection_max_drawdown_pct.png` - Loss Protection参数热力图（最大回撤）\n"
    report_md += "3. `comparison_trailing_stop.png` - Trailing Stop参数对比图\n"
    report_md += "4. `comparison_all_strategies.png` - 各策略表现对比图\n"
    report_md += "5. `heatmap_combined_by_trailing_stop.png` - Combined策略热力图\n"
    report_md += "6. `sensitivity_loss_protection.png` - Loss Protection参数敏感性分析\n"
    report_md += "7. `sensitivity_trailing_stop.png` - Trailing Stop参数敏感性分析\n\n"

    # 保存报告
    report_file = output_dir / 'RESULTS.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_md)

    print(f"✅ 报告已保存: {report_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='生成MACD策略止损实验报告')
    parser.add_argument('--output-dir', type=str,
                        default='experiment/etf/macd_cross/grid_search_stop_loss',
                        help='实验结果目录')

    args = parser.parse_args()
    output_dir = Path(args.output_dir)

    generate_report(output_dir)

    print(f"\n{'='*70}")
    print("✅ 报告生成完成！")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
