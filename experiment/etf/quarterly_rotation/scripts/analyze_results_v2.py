#!/usr/bin/env python3
"""
v2版本：分析分季度回测结果

核心功能：
1. 读取轮动组各季度的回测结果
2. 计算等权组合的季度收益率
3. 拼接组合净值曲线
4. 计算整体指标（总收益、夏普、最大回撤）
5. 与固定组进行对比

指标计算方法：
- 等权组合收益 = 池子内所有ETF收益率的平均值
- 组合净值 = 累积各季度的组合收益
- 夏普比率 = 年化收益 / 年化波动率
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
ROTATION_V2_DIR = EXPERIMENT_DIR / "results" / "rotation_v2"
STATIC_RESULTS_DIR = EXPERIMENT_DIR / "results" / "static"
COMPARISON_V2_DIR = EXPERIMENT_DIR / "results" / "comparison_v2"

# 季度定义
QUARTERS = [
    "2024Q1", "2024Q2", "2024Q3", "2024Q4",
    "2025Q1", "2025Q2", "2025Q3", "2025Q4"
]

# 每季度的月数（用于年化计算）
QUARTER_MONTHS = {
    "2024Q1": 3, "2024Q2": 3, "2024Q3": 3, "2024Q4": 3,
    "2025Q1": 3, "2025Q2": 3, "2025Q3": 3, "2025Q4": 2,  # 2025Q4只有2个月
}


def find_summary_file(results_dir: Path) -> Optional[Path]:
    """查找汇总文件"""
    pattern = "summary/backtest_summary_*.csv"
    files = list(results_dir.glob(pattern))
    if not files:
        return None
    # 返回最新的文件
    return max(files, key=lambda f: f.stat().st_mtime)


def load_quarter_results(quarter: str) -> pd.DataFrame:
    """
    加载某季度的回测结果

    Args:
        quarter: 季度名称，如 "2024Q1"

    Returns:
        DataFrame: 该季度所有ETF的回测结果
    """
    quarter_dir = ROTATION_V2_DIR / quarter
    summary_file = find_summary_file(quarter_dir)

    if not summary_file:
        raise FileNotFoundError(f"未找到 {quarter} 的汇总文件: {quarter_dir}")

    df = pd.read_csv(summary_file, encoding='utf-8-sig')

    # 列名映射
    # 注意：'总收益率(%)' 是实际收益率，'收益率(%)' 是年化收益率
    # 我们需要使用实际收益率来计算组合表现
    column_mapping = {
        '代码': 'ts_code',
        '标的名称': 'name',
        '收益率(%)': 'annualized_return_pct',  # 年化收益率
        '总收益率(%)': 'return_pct',  # 实际收益率（这是我们需要的）
        '夏普比率': 'sharpe',
        '最大回撤(%)': 'max_drawdown',
        '胜率(%)': 'win_rate',
        '盈亏比': 'profit_loss_ratio',
        '交易次数': 'total_trades',
    }
    df = df.rename(columns=column_mapping)

    return df


def load_static_results() -> pd.DataFrame:
    """
    加载固定组的回测结果

    Returns:
        DataFrame: 固定组所有ETF的回测结果
    """
    summary_file = find_summary_file(STATIC_RESULTS_DIR)

    if not summary_file:
        raise FileNotFoundError(f"未找到固定组的汇总文件: {STATIC_RESULTS_DIR}")

    df = pd.read_csv(summary_file, encoding='utf-8-sig')

    # 列名映射 - 使用总收益率（实际收益率）而非年化收益率
    column_mapping = {
        '代码': 'ts_code',
        '标的名称': 'name',
        '收益率(%)': 'annualized_return_pct',  # 年化收益率
        '总收益率(%)': 'return_pct',  # 实际收益率（这是我们需要的）
        '夏普比率': 'sharpe',
        '最大回撤(%)': 'max_drawdown',
        '胜率(%)': 'win_rate',
        '盈亏比': 'profit_loss_ratio',
        '交易次数': 'total_trades',
    }
    df = df.rename(columns=column_mapping)

    return df


def calculate_quarterly_portfolio_metrics(results: pd.DataFrame) -> Dict:
    """
    计算季度等权组合的指标

    Args:
        results: 该季度所有ETF的回测结果

    Returns:
        dict: 组合指标
    """
    metrics = {
        "etf_count": len(results),
        "portfolio_return": results['return_pct'].mean() if 'return_pct' in results.columns else np.nan,
        "sharpe_mean": results['sharpe'].mean() if 'sharpe' in results.columns else np.nan,
        "max_dd_mean": results['max_drawdown'].mean() if 'max_drawdown' in results.columns else np.nan,
        "win_rate_mean": results['win_rate'].mean() if 'win_rate' in results.columns else np.nan,
        "trade_count": results['total_trades'].sum() if 'total_trades' in results.columns else 0,
    }

    # 计算收益率的标准差（组合内分散度）
    if 'return_pct' in results.columns:
        metrics['return_std'] = results['return_pct'].std()

    return metrics


def calculate_rotation_metrics() -> Tuple[pd.DataFrame, Dict]:
    """
    计算轮动组的所有指标

    Returns:
        Tuple[DataFrame, Dict]:
            - 分季度指标DataFrame
            - 整体指标Dict
    """
    quarterly_metrics = []
    nav = 1.0  # 初始净值
    nav_series = [{"quarter": "start", "nav": 1.0}]

    for quarter in QUARTERS:
        print(f"  处理季度: {quarter}")

        try:
            results = load_quarter_results(quarter)
            metrics = calculate_quarterly_portfolio_metrics(results)
            metrics['quarter'] = quarter

            # 计算组合净值
            quarter_return = metrics['portfolio_return']
            if not pd.isna(quarter_return):
                nav = nav * (1 + quarter_return / 100)
            metrics['nav'] = nav

            nav_series.append({"quarter": quarter, "nav": nav})
            quarterly_metrics.append(metrics)

        except FileNotFoundError as e:
            print(f"    警告: {e}")
            quarterly_metrics.append({
                'quarter': quarter,
                'etf_count': 0,
                'portfolio_return': np.nan,
                'nav': nav,  # 保持上一季度净值
            })

    quarterly_df = pd.DataFrame(quarterly_metrics)

    # 计算整体指标
    total_return = (nav - 1) * 100
    total_months = sum(QUARTER_MONTHS.values())
    annualized_return = total_return * 12 / total_months

    # 计算季度收益的波动率并年化
    quarterly_returns = quarterly_df['portfolio_return'].dropna()
    if len(quarterly_returns) > 1:
        quarterly_std = quarterly_returns.std()
        annualized_std = quarterly_std * np.sqrt(4)  # 季度→年化
        sharpe = annualized_return / annualized_std if annualized_std > 0 else np.nan
    else:
        sharpe = np.nan

    # 计算最大回撤（从净值序列）
    nav_values = quarterly_df['nav'].values
    peak = np.maximum.accumulate(nav_values)
    drawdown = (nav_values - peak) / peak * 100
    max_drawdown = drawdown.min()

    overall_metrics = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "total_trades": quarterly_df['trade_count'].sum(),
        "avg_quarterly_return": quarterly_returns.mean(),
        "quarterly_return_std": quarterly_returns.std(),
        "final_nav": nav,
    }

    return quarterly_df, overall_metrics


def calculate_static_metrics() -> Tuple[pd.DataFrame, Dict]:
    """
    计算固定组的指标

    固定组需要按季度切片计算，以便与轮动组对比

    Returns:
        Tuple[DataFrame, Dict]:
            - 分季度指标DataFrame（每季度指标相同，因为是同一次回测）
            - 整体指标Dict
    """
    results = load_static_results()

    # 固定组整体指标（直接从回测结果计算）
    overall_metrics = {
        "total_return": results['return_pct'].mean(),
        "annualized_return": results['return_pct'].mean() * 12 / 23,  # 约23个月
        "sharpe": results['sharpe'].mean(),
        "max_drawdown": results['max_drawdown'].mean(),
        "total_trades": results['total_trades'].sum(),
        "etf_count": len(results),
    }

    # 固定组的"季度"指标（实际上是整体的平均分配）
    # 由于固定组是一次性回测，我们将总收益平均分配到各季度
    total_months = sum(QUARTER_MONTHS.values())
    nav = 1.0
    quarterly_metrics = []

    for quarter in QUARTERS:
        months = QUARTER_MONTHS[quarter]
        # 假设收益均匀分布到各月
        quarter_return = overall_metrics['total_return'] * months / total_months

        nav = nav * (1 + quarter_return / 100)

        quarterly_metrics.append({
            'quarter': quarter,
            'etf_count': len(results),
            'portfolio_return': quarter_return,
            'sharpe_mean': overall_metrics['sharpe'],
            'max_dd_mean': overall_metrics['max_drawdown'],
            'nav': nav,
        })

    quarterly_df = pd.DataFrame(quarterly_metrics)
    overall_metrics['final_nav'] = nav

    return quarterly_df, overall_metrics


def generate_comparison_report(
    rotation_quarterly: pd.DataFrame,
    static_quarterly: pd.DataFrame,
    rotation_overall: Dict,
    static_overall: Dict,
) -> str:
    """生成对比报告"""
    report = []
    report.append("# 季度轮动ETF池实验结果报告 (v2)\n")
    report.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    report.append("\n**v2改进**: 分季度独立回测，避免前视偏差\n")

    # 核心结论
    report.append("\n## 一、核心结论\n")

    rotation_return = rotation_overall.get('total_return', 0)
    static_return = static_overall.get('total_return', 0)
    rotation_sharpe = rotation_overall.get('sharpe', 0)
    static_sharpe = static_overall.get('sharpe', 0)

    if rotation_sharpe > static_sharpe + 0.1:
        winner = "轮动组"
        conclusion = "季度轮动策略有效"
    elif static_sharpe > rotation_sharpe + 0.1:
        winner = "固定组"
        conclusion = "固定池策略更优"
    else:
        winner = "无显著差异"
        conclusion = "两种策略表现接近"

    report.append(f"\n**结论: {conclusion}，优胜方为{winner}**\n")

    # 整体对比表
    report.append("\n| 指标 | 轮动组 | 固定组 | 差值 | 优胜方 |\n")
    report.append("|------|:------:|:------:|:----:|:------:|\n")

    def fmt(v, decimals=2):
        if pd.isna(v):
            return "-"
        return f"{v:.{decimals}f}"

    def winner_mark(r, s, higher_better=True):
        if pd.isna(r) or pd.isna(s):
            return "-"
        if higher_better:
            return "轮动组" if r > s else ("固定组" if s > r else "平")
        else:
            return "轮动组" if r < s else ("固定组" if s < r else "平")

    metrics_to_compare = [
        ("总收益率(%)", "total_return", True),
        ("年化收益率(%)", "annualized_return", True),
        ("夏普比率", "sharpe", True),
        ("最大回撤(%)", "max_drawdown", False),
        ("总交易次数", "total_trades", None),
        ("最终净值", "final_nav", True),
    ]

    for label, key, higher_better in metrics_to_compare:
        r_val = rotation_overall.get(key)
        s_val = static_overall.get(key)
        diff = (r_val - s_val) if (r_val and s_val) else np.nan
        w = winner_mark(r_val, s_val, higher_better) if higher_better is not None else "-"
        report.append(f"| {label} | {fmt(r_val)} | {fmt(s_val)} | {fmt(diff, 2)} | {w} |\n")

    # 分季度对比
    report.append("\n## 二、分季度对比\n")
    report.append("\n### 2.1 轮动组季度表现\n")
    report.append("\n| 季度 | ETF数 | 组合收益(%) | 组合净值 |\n")
    report.append("|------|:-----:|:----------:|:-------:|\n")
    for _, row in rotation_quarterly.iterrows():
        report.append(f"| {row['quarter']} | {int(row.get('etf_count', 0))} | {fmt(row.get('portfolio_return'))} | {fmt(row.get('nav'))} |\n")

    report.append("\n### 2.2 固定组季度表现\n")
    report.append("\n| 季度 | ETF数 | 组合收益(%) | 组合净值 |\n")
    report.append("|------|:-----:|:----------:|:-------:|\n")
    for _, row in static_quarterly.iterrows():
        report.append(f"| {row['quarter']} | {int(row.get('etf_count', 0))} | {fmt(row.get('portfolio_return'))} | {fmt(row.get('nav'))} |\n")

    # 假设验证
    report.append("\n## 三、假设验证\n")
    report.append("\n| 假设 | 预期 | 实际结果 | 状态 |\n")
    report.append("|------|------|----------|:----:|\n")

    h1_pass = rotation_sharpe > static_sharpe
    h1_status = "✅ 通过" if h1_pass else "❌ 未通过"
    report.append(f"| H1: 轮动组夏普 > 固定组 | 轮动更优 | {fmt(rotation_sharpe)} vs {fmt(static_sharpe)} | {h1_status} |\n")

    rotation_std = rotation_quarterly['portfolio_return'].std() if 'portfolio_return' in rotation_quarterly else np.nan
    static_std = static_quarterly['portfolio_return'].std() if 'portfolio_return' in static_quarterly else np.nan
    h2_pass = rotation_std < static_std if not (pd.isna(rotation_std) or pd.isna(static_std)) else False
    h2_status = "✅ 通过" if h2_pass else "❌ 未通过"
    report.append(f"| H2: 轮动组稳定性更好 | 波动更小 | 标准差 {fmt(rotation_std)} vs {fmt(static_std)} | {h2_status} |\n")

    # 数据来源
    report.append("\n## 四、数据来源\n")
    report.append(f"\n- 轮动组结果: `results/rotation_v2/*/summary/`\n")
    report.append(f"- 固定组结果: `results/static/summary/`\n")
    report.append(f"- 对比结果: `results/comparison_v2/`\n")

    return "".join(report)


def main():
    """主函数"""
    print("=" * 60)
    print("季度轮动回测结果分析 v2")
    print("=" * 60)

    COMPARISON_V2_DIR.mkdir(parents=True, exist_ok=True)

    # 计算轮动组指标
    print("\n计算轮动组指标...")
    rotation_quarterly, rotation_overall = calculate_rotation_metrics()

    # 计算固定组指标
    print("\n计算固定组指标...")
    static_quarterly, static_overall = calculate_static_metrics()

    # 保存结果
    print("\n保存结果...")
    rotation_quarterly.to_csv(COMPARISON_V2_DIR / "rotation_quarterly_v2.csv", index=False)
    static_quarterly.to_csv(COMPARISON_V2_DIR / "static_quarterly_v2.csv", index=False)

    with open(COMPARISON_V2_DIR / "rotation_overall_v2.json", 'w', encoding='utf-8') as f:
        json.dump(rotation_overall, f, ensure_ascii=False, indent=2, default=str)

    with open(COMPARISON_V2_DIR / "static_overall_v2.json", 'w', encoding='utf-8') as f:
        json.dump(static_overall, f, ensure_ascii=False, indent=2, default=str)

    # 生成报告
    print("\n生成对比报告...")
    report = generate_comparison_report(
        rotation_quarterly, static_quarterly,
        rotation_overall, static_overall
    )

    report_path = COMPARISON_V2_DIR / "ANALYSIS_REPORT_V2.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n报告已保存: {report_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("结果摘要")
    print("=" * 60)
    print(f"\n轮动组:")
    print(f"  总收益: {rotation_overall.get('total_return', np.nan):.2f}%")
    print(f"  夏普比率: {rotation_overall.get('sharpe', np.nan):.2f}")
    print(f"  最大回撤: {rotation_overall.get('max_drawdown', np.nan):.2f}%")

    print(f"\n固定组:")
    print(f"  总收益: {static_overall.get('total_return', np.nan):.2f}%")
    print(f"  夏普比率: {static_overall.get('sharpe', np.nan):.2f}")
    print(f"  最大回撤: {static_overall.get('max_drawdown', np.nan):.2f}%")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
