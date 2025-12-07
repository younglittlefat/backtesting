#!/usr/bin/env python3
"""
分析季度轮动回测结果

核心逻辑：
1. 读取轮动组和固定组的回测结果
2. 根据轮动表筛选每只ETF在有效季度内的交易
3. 计算方案A（分季度统计）和方案B（整体统计）
4. 生成对比报告
"""

import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
EXPERIMENT_DIR = PROJECT_ROOT / "experiment" / "etf" / "quarterly_rotation"

# 目录
ROTATION_RESULTS_DIR = EXPERIMENT_DIR / "results" / "rotation"
STATIC_RESULTS_DIR = EXPERIMENT_DIR / "results" / "static"
COMPARISON_DIR = EXPERIMENT_DIR / "results" / "comparison"

# 轮动表路径
SCHEDULE_PATH = EXPERIMENT_DIR / "pool_rotation_schedule.json"


def load_schedule() -> Dict:
    """加载轮动表"""
    with open(SCHEDULE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_summary_files(results_dir: Path) -> List[Path]:
    """查找汇总文件"""
    pattern = "**/summary/backtest_summary_*.csv"
    files = list(results_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"未找到汇总文件: {results_dir}")
    return files


def load_backtest_results(results_dir: Path) -> pd.DataFrame:
    """
    加载回测结果

    Args:
        results_dir: 结果目录

    Returns:
        DataFrame: 包含所有标的回测结果的DataFrame
    """
    summary_files = find_summary_files(results_dir)

    all_results = []
    for file in summary_files:
        df = pd.read_csv(file, encoding='utf-8-sig')

        # 列名映射：中文列名 -> 英文列名
        column_mapping = {
            '代码': 'ts_code',
            '标的名称': 'name',
            '类型': 'type',
            '策略': 'strategy',
            '回测开始日期': 'start_date',
            '回测结束日期': 'end_date',
            '收益率(%)': 'return_pct',
            '总收益率(%)': 'total_return_pct',
            '夏普比率': 'sharpe',
            '最大回撤(%)': 'max_drawdown',
            '胜率(%)': 'win_rate',
            '盈亏比': 'profit_loss_ratio',
            '交易次数': 'total_trades',
        }

        # 重命名列
        df = df.rename(columns=column_mapping)
        all_results.append(df)

    if not all_results:
        raise ValueError(f"未找到有效结果: {results_dir}")

    combined = pd.concat(all_results, ignore_index=True)

    # 去重（同一标的可能出现多次）
    if 'ts_code' in combined.columns:
        combined = combined.drop_duplicates(subset=['ts_code'], keep='last')

    return combined


def get_etf_quarters(etf_code: str, schedule: Dict) -> List[str]:
    """
    获取某只ETF所在的季度列表

    Args:
        etf_code: ETF代码
        schedule: 轮动表

    Returns:
        list: 该ETF所在的季度列表
    """
    quarters = []
    for quarter, data in schedule.items():
        if etf_code in data.get("etfs", []):
            quarters.append(quarter)
    return quarters


def filter_results_by_schedule(
    results: pd.DataFrame,
    schedule: Dict,
    mode: str = "rotation"
) -> pd.DataFrame:
    """
    根据轮动表筛选结果

    Args:
        results: 回测结果DataFrame
        schedule: 轮动表
        mode: "rotation"（按季度筛选）或 "static"（固定池子）

    Returns:
        DataFrame: 筛选后的结果
    """
    if mode == "static":
        # 固定组：使用第一个季度的池子（2024Q1的池子就是2022-2023评分的）
        static_etfs = schedule.get("2024Q1", {}).get("etfs", [])
        return results[results['ts_code'].isin(static_etfs)].copy()

    elif mode == "rotation":
        # 轮动组：标记每只ETF属于哪些季度
        results = results.copy()
        results['quarters'] = results['ts_code'].apply(
            lambda x: get_etf_quarters(x, schedule)
        )
        results['quarter_count'] = results['quarters'].apply(len)
        # 只保留至少在一个季度中的ETF
        return results[results['quarter_count'] > 0]

    else:
        raise ValueError(f"未知模式: {mode}")


def calculate_quarterly_metrics(
    results: pd.DataFrame,
    schedule: Dict,
    mode: str = "rotation"
) -> pd.DataFrame:
    """
    计算分季度指标（方案A）

    Args:
        results: 回测结果DataFrame
        schedule: 轮动表
        mode: "rotation" 或 "static"

    Returns:
        DataFrame: 每季度的统计指标
    """
    quarterly_metrics = []

    for quarter, data in schedule.items():
        quarter_etfs = data.get("etfs", [])

        if mode == "static":
            # 固定组：使用第一个季度的池子
            static_etfs = schedule.get("2024Q1", {}).get("etfs", [])
            quarter_results = results[results['ts_code'].isin(static_etfs)]
        else:
            # 轮动组：使用该季度的池子
            quarter_results = results[results['ts_code'].isin(quarter_etfs)]

        if len(quarter_results) == 0:
            continue

        # 计算统计量
        metrics = {
            "quarter": quarter,
            "etf_count": len(quarter_results),
            "sharpe_mean": quarter_results['sharpe'].mean() if 'sharpe' in quarter_results else np.nan,
            "sharpe_median": quarter_results['sharpe'].median() if 'sharpe' in quarter_results else np.nan,
            "return_mean": quarter_results['return_pct'].mean() if 'return_pct' in quarter_results else np.nan,
            "return_median": quarter_results['return_pct'].median() if 'return_pct' in quarter_results else np.nan,
            "max_dd_mean": quarter_results['max_drawdown'].mean() if 'max_drawdown' in quarter_results else np.nan,
            "win_rate_mean": quarter_results['win_rate'].mean() if 'win_rate' in quarter_results else np.nan,
            "trade_count_mean": quarter_results['total_trades'].mean() if 'total_trades' in quarter_results else np.nan,
        }

        # 计算盈亏比（如果有）
        if 'profit_loss_ratio' in quarter_results:
            metrics['pl_ratio_mean'] = quarter_results['profit_loss_ratio'].mean()

        quarterly_metrics.append(metrics)

    return pd.DataFrame(quarterly_metrics)


def calculate_overall_metrics(results: pd.DataFrame) -> Dict:
    """
    计算整体指标（方案B）

    Args:
        results: 回测结果DataFrame

    Returns:
        dict: 整体统计指标
    """
    metrics = {
        "etf_count": len(results),
        "sharpe_mean": results['sharpe'].mean() if 'sharpe' in results.columns else np.nan,
        "sharpe_median": results['sharpe'].median() if 'sharpe' in results.columns else np.nan,
        "sharpe_std": results['sharpe'].std() if 'sharpe' in results.columns else np.nan,
        "return_mean": results['return_pct'].mean() if 'return_pct' in results.columns else np.nan,
        "return_median": results['return_pct'].median() if 'return_pct' in results.columns else np.nan,
        "return_std": results['return_pct'].std() if 'return_pct' in results.columns else np.nan,
        "max_dd_mean": results['max_drawdown'].mean() if 'max_drawdown' in results.columns else np.nan,
        "max_dd_median": results['max_drawdown'].median() if 'max_drawdown' in results.columns else np.nan,
        "win_rate_mean": results['win_rate'].mean() if 'win_rate' in results.columns else np.nan,
        "trade_count_mean": results['total_trades'].mean() if 'total_trades' in results.columns else np.nan,
        "trade_count_total": results['total_trades'].sum() if 'total_trades' in results.columns else np.nan,
    }

    # 计算盈亏比
    if 'profit_loss_ratio' in results.columns:
        metrics['pl_ratio_mean'] = results['profit_loss_ratio'].mean()

    # 计算MAR（年化收益/最大回撤）
    if metrics['return_mean'] and metrics['max_dd_mean'] and metrics['max_dd_mean'] != 0:
        # 假设回测期约2年，计算年化
        annualized_return = metrics['return_mean'] / 2  # 简单年化
        metrics['mar'] = annualized_return / abs(metrics['max_dd_mean']) if metrics['max_dd_mean'] else np.nan
    else:
        metrics['mar'] = np.nan

    return metrics


def generate_comparison_report(
    rotation_quarterly: pd.DataFrame,
    static_quarterly: pd.DataFrame,
    rotation_overall: Dict,
    static_overall: Dict,
    pool_changes: Dict
) -> str:
    """
    生成对比分析报告

    Args:
        rotation_quarterly: 轮动组分季度指标
        static_quarterly: 固定组分季度指标
        rotation_overall: 轮动组整体指标
        static_overall: 固定组整体指标
        pool_changes: 池子变化统计

    Returns:
        str: Markdown格式报告
    """
    report = []
    report.append("# 季度轮动ETF池实验结果报告\n")
    report.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    # 实验概述
    report.append("\n## 一、实验概述\n")
    report.append("本实验对比**季度轮动池**和**固定池**的回测表现：\n")
    report.append("- **轮动组**：每季度更新ETF池（使用过去2年数据重新评分）\n")
    report.append("- **固定组**：使用2022-2023评分的固定池子，全程不变\n")
    report.append("- **回测期间**：2024-01-01 ~ 2025-11-30\n")
    report.append("- **策略**：KAMA交叉 + ADX过滤器 + ATR止损 + 斜率确认\n")

    # 整体对比（方案B）
    report.append("\n## 二、整体对比（方案B）\n")
    report.append("\n| 指标 | 轮动组 | 固定组 | 差值 |\n")
    report.append("|------|:------:|:------:|:----:|\n")

    def fmt(v, pct=False):
        if pd.isna(v):
            return "-"
        if pct:
            return f"{v:.2f}%"
        return f"{v:.2f}"

    def diff(r, s, pct=False):
        if pd.isna(r) or pd.isna(s):
            return "-"
        d = r - s
        sign = "+" if d > 0 else ""
        if pct:
            return f"{sign}{d:.2f}%"
        return f"{sign}{d:.2f}"

    metrics_labels = [
        ("标的数量", "etf_count", False),
        ("夏普均值", "sharpe_mean", False),
        ("夏普中位数", "sharpe_median", False),
        ("夏普标准差", "sharpe_std", False),
        ("收益均值", "return_mean", True),
        ("收益中位数", "return_median", True),
        ("最大回撤均值", "max_dd_mean", True),
        ("胜率均值", "win_rate_mean", True),
        ("MAR", "mar", False),
    ]

    for label, key, pct in metrics_labels:
        r_val = rotation_overall.get(key)
        s_val = static_overall.get(key)
        report.append(f"| {label} | {fmt(r_val, pct)} | {fmt(s_val, pct)} | {diff(r_val, s_val, pct)} |\n")

    # 分季度对比（方案A）
    report.append("\n## 三、分季度对比（方案A）\n")

    report.append("\n### 3.1 轮动组季度表现\n")
    report.append("\n| 季度 | ETF数 | 夏普均值 | 收益均值 | 最大回撤 | 胜率 |\n")
    report.append("|------|:-----:|:-------:|:-------:|:-------:|:----:|\n")
    for _, row in rotation_quarterly.iterrows():
        report.append(f"| {row['quarter']} | {int(row['etf_count'])} | {fmt(row['sharpe_mean'])} | {fmt(row['return_mean'], True)} | {fmt(row['max_dd_mean'], True)} | {fmt(row['win_rate_mean'], True)} |\n")

    report.append("\n### 3.2 固定组季度表现\n")
    report.append("\n| 季度 | ETF数 | 夏普均值 | 收益均值 | 最大回撤 | 胜率 |\n")
    report.append("|------|:-----:|:-------:|:-------:|:-------:|:----:|\n")
    for _, row in static_quarterly.iterrows():
        report.append(f"| {row['quarter']} | {int(row['etf_count'])} | {fmt(row['sharpe_mean'])} | {fmt(row['return_mean'], True)} | {fmt(row['max_dd_mean'], True)} | {fmt(row['win_rate_mean'], True)} |\n")

    # 季度统计汇总
    report.append("\n### 3.3 季度统计汇总\n")
    report.append("\n| 统计量 | 轮动组夏普 | 固定组夏普 | 轮动组收益 | 固定组收益 |\n")
    report.append("|--------|:--------:|:--------:|:--------:|:--------:|\n")
    report.append(f"| 均值 | {fmt(rotation_quarterly['sharpe_mean'].mean())} | {fmt(static_quarterly['sharpe_mean'].mean())} | {fmt(rotation_quarterly['return_mean'].mean(), True)} | {fmt(static_quarterly['return_mean'].mean(), True)} |\n")
    report.append(f"| 中位数 | {fmt(rotation_quarterly['sharpe_mean'].median())} | {fmt(static_quarterly['sharpe_mean'].median())} | {fmt(rotation_quarterly['return_mean'].median(), True)} | {fmt(static_quarterly['return_mean'].median(), True)} |\n")
    report.append(f"| 标准差 | {fmt(rotation_quarterly['sharpe_mean'].std())} | {fmt(static_quarterly['sharpe_mean'].std())} | {fmt(rotation_quarterly['return_mean'].std(), True)} | {fmt(static_quarterly['return_mean'].std(), True)} |\n")

    # 池子变化分析
    report.append("\n## 四、池子变化分析\n")
    report.append("\n| 季度 | 新增 | 移除 | 重叠 | 重叠率 |\n")
    report.append("|------|:----:|:----:|:----:|:-----:|\n")
    for quarter, changes in pool_changes.items():
        report.append(f"| {quarter} | {changes['new_count']} | {changes['removed_count']} | {changes['overlap_count']} | {changes['overlap_ratio']*100:.1f}% |\n")

    # 结论
    report.append("\n## 五、结论\n")

    sharpe_diff = rotation_overall.get('sharpe_mean', 0) - static_overall.get('sharpe_mean', 0)
    return_diff = rotation_overall.get('return_mean', 0) - static_overall.get('return_mean', 0)

    if sharpe_diff > 0.1:
        report.append(f"\n**结论：季度轮动池表现优于固定池**\n")
        report.append(f"- 夏普提升：+{sharpe_diff:.2f}\n")
        report.append(f"- 收益提升：+{return_diff:.2f}%\n")
    elif sharpe_diff < -0.1:
        report.append(f"\n**结论：固定池表现优于季度轮动池**\n")
        report.append(f"- 夏普差异：{sharpe_diff:.2f}\n")
        report.append(f"- 收益差异：{return_diff:.2f}%\n")
    else:
        report.append(f"\n**结论：两组表现接近，无显著差异**\n")
        report.append(f"- 夏普差异：{sharpe_diff:.2f}\n")
        report.append(f"- 收益差异：{return_diff:.2f}%\n")

    report.append("\n### 假设验证\n")
    report.append(f"| 假设 | 结果 |\n")
    report.append("|------|------|\n")
    report.append(f"| H1: 轮动组夏普 > 固定组夏普 | {'通过' if sharpe_diff > 0 else '未通过'} (差值: {sharpe_diff:+.2f}) |\n")

    rotation_std = rotation_quarterly['sharpe_mean'].std()
    static_std = static_quarterly['sharpe_mean'].std()
    report.append(f"| H2: 轮动组稳定性更好 | {'通过' if rotation_std < static_std else '未通过'} (标准差: {rotation_std:.2f} vs {static_std:.2f}) |\n")

    # 计算平均换手率
    avg_overlap = np.mean([c['overlap_ratio'] for c in pool_changes.values() if c['overlap_ratio'] > 0])
    turnover = 1 - avg_overlap
    report.append(f"| H3: 轮动成本可接受 | 待验证 (平均换手率: {turnover*100:.1f}%) |\n")

    return "".join(report)


def main():
    """主函数"""
    print("=" * 60)
    print("季度轮动回测结果分析")
    print("=" * 60)

    # 加载轮动表
    schedule = load_schedule()
    print(f"加载轮动表: {len(schedule)} 个季度")

    # 加载池子变化统计
    changes_path = EXPERIMENT_DIR / "pool_changes.json"
    if changes_path.exists():
        with open(changes_path, 'r', encoding='utf-8') as f:
            pool_changes = json.load(f)
    else:
        pool_changes = {}

    # 加载回测结果
    print("\n加载回测结果...")
    rotation_results = load_backtest_results(ROTATION_RESULTS_DIR)
    static_results = load_backtest_results(STATIC_RESULTS_DIR)
    print(f"  轮动组: {len(rotation_results)} 只ETF")
    print(f"  固定组: {len(static_results)} 只ETF")

    # 筛选结果
    print("\n筛选有效结果...")
    rotation_filtered = filter_results_by_schedule(rotation_results, schedule, mode="rotation")
    static_filtered = filter_results_by_schedule(static_results, schedule, mode="static")
    print(f"  轮动组筛选后: {len(rotation_filtered)} 只ETF")
    print(f"  固定组筛选后: {len(static_filtered)} 只ETF")

    # 计算分季度指标（方案A）
    print("\n计算分季度指标...")
    rotation_quarterly = calculate_quarterly_metrics(rotation_filtered, schedule, mode="rotation")
    static_quarterly = calculate_quarterly_metrics(static_filtered, schedule, mode="static")

    # 计算整体指标（方案B）
    print("\n计算整体指标...")
    rotation_overall = calculate_overall_metrics(rotation_filtered)
    static_overall = calculate_overall_metrics(static_filtered)

    # 保存结果
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

    rotation_quarterly.to_csv(COMPARISON_DIR / "rotation_quarterly.csv", index=False)
    static_quarterly.to_csv(COMPARISON_DIR / "static_quarterly.csv", index=False)

    with open(COMPARISON_DIR / "rotation_overall.json", 'w', encoding='utf-8') as f:
        json.dump(rotation_overall, f, ensure_ascii=False, indent=2, default=str)

    with open(COMPARISON_DIR / "static_overall.json", 'w', encoding='utf-8') as f:
        json.dump(static_overall, f, ensure_ascii=False, indent=2, default=str)

    # 生成报告
    print("\n生成分析报告...")
    report = generate_comparison_report(
        rotation_quarterly,
        static_quarterly,
        rotation_overall,
        static_overall,
        pool_changes
    )

    report_path = COMPARISON_DIR / "ANALYSIS_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n报告已保存: {report_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("结果摘要")
    print("=" * 60)
    print(f"\n整体对比:")
    print(f"  轮动组夏普: {rotation_overall.get('sharpe_mean', np.nan):.2f}")
    print(f"  固定组夏普: {static_overall.get('sharpe_mean', np.nan):.2f}")
    sharpe_diff = rotation_overall.get('sharpe_mean', 0) - static_overall.get('sharpe_mean', 0)
    print(f"  差值: {sharpe_diff:+.2f}")

    print(f"\n  轮动组收益: {rotation_overall.get('return_mean', np.nan):.2f}%")
    print(f"  固定组收益: {static_overall.get('return_mean', np.nan):.2f}%")
    return_diff = rotation_overall.get('return_mean', 0) - static_overall.get('return_mean', 0)
    print(f"  差值: {return_diff:+.2f}%")

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
