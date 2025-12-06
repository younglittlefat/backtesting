#!/usr/bin/env python3
"""
Score 正交检验分析脚本

计算各个 score 之间的相关性矩阵和池子重叠度，用于指导 score 组合权重设计。

使用方法:
    # 单文件分析
    python scripts/analyze_score_correlation.py path/to/all_scores.csv

    # 多文件池子重叠度分析（英文逗号分隔）
    python scripts/analyze_score_correlation.py pool1.csv,pool2.csv,pool3.csv

    # 指定输出目录
    python scripts/analyze_score_correlation.py all_scores.csv --output-dir results/correlation

输出:
    - correlation_matrix.csv: 相关性矩阵
    - correlation_heatmap.png: 热力图可视化
    - jaccard_similarity.csv: 池子重叠度（多文件时）
    - analysis_report.txt: 分析报告和建议
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def load_score_data(file_path: str) -> pd.DataFrame:
    """加载 score 数据文件"""
    df = pd.read_csv(file_path)
    return df


def calculate_correlation_matrix(
    df: pd.DataFrame,
    score_columns: list = None,
    method: str = 'spearman'
) -> pd.DataFrame:
    """
    计算 score 相关性矩阵

    Args:
        df: 包含 score 数据的 DataFrame
        score_columns: 要计算相关性的列名列表，默认自动检测
        method: 相关性计算方法，'spearman'（推荐）或 'pearson'

    Returns:
        相关性矩阵 DataFrame
    """
    # 默认的 score 列（按优先级排列）
    default_score_columns = [
        # 核心 4 个单 score
        'adx_mean', 'trend_consistency', 'price_efficiency', 'liquidity_score',
        # 动量
        'momentum_3m', 'momentum_12m',
        # 新版评分输入
        'excess_return_20d', 'excess_return_60d', 'trend_quality', 'volume_trend', 'idr',
    ]

    if score_columns is None:
        # 自动检测存在的列
        score_columns = [col for col in default_score_columns if col in df.columns]

    if len(score_columns) < 2:
        raise ValueError(f"至少需要2个 score 列进行相关性分析，当前只有: {score_columns}")

    # 提取 score 数据
    df_scores = df[score_columns].copy()

    # 转换为数值类型（处理可能的字符串）
    for col in score_columns:
        df_scores[col] = pd.to_numeric(df_scores[col], errors='coerce')

    # 计算相关性矩阵
    corr_matrix = df_scores.corr(method=method)

    return corr_matrix


def calculate_jaccard_similarity(pools: dict) -> pd.DataFrame:
    """
    计算多个池子之间的 Jaccard 相似度

    Args:
        pools: 字典 {池子名称: set(ts_code)}

    Returns:
        Jaccard 相似度矩阵 DataFrame
    """
    pool_names = list(pools.keys())
    n = len(pool_names)

    jaccard_matrix = pd.DataFrame(
        np.zeros((n, n)),
        index=pool_names,
        columns=pool_names
    )

    for i, name1 in enumerate(pool_names):
        for j, name2 in enumerate(pool_names):
            set1 = pools[name1]
            set2 = pools[name2]
            if len(set1 | set2) > 0:
                jaccard = len(set1 & set2) / len(set1 | set2)
            else:
                jaccard = 0.0
            jaccard_matrix.loc[name1, name2] = jaccard

    return jaccard_matrix


def interpret_correlation(corr_value: float) -> str:
    """解读相关系数"""
    abs_corr = abs(corr_value)
    if abs_corr < 0.3:
        return "正交/独立 ✅"
    elif abs_corr < 0.6:
        return "中度相关 ⚠️"
    else:
        return "高度相关 ❌"


def generate_report(
    corr_matrix: pd.DataFrame,
    jaccard_matrix: pd.DataFrame = None,
    output_path: Path = None
) -> str:
    """
    生成分析报告

    Args:
        corr_matrix: 相关性矩阵
        jaccard_matrix: Jaccard 相似度矩阵（可选）
        output_path: 输出路径（可选）

    Returns:
        报告文本
    """
    lines = []
    lines.append("=" * 70)
    lines.append("Score 正交检验分析报告")
    lines.append("=" * 70)
    lines.append("")

    # 相关性矩阵分析
    lines.append("【1. 相关性矩阵】")
    lines.append("-" * 50)
    lines.append(corr_matrix.round(3).to_string())
    lines.append("")

    # 关键发现
    lines.append("【2. 关键发现】")
    lines.append("-" * 50)

    score_pairs = []
    columns = corr_matrix.columns.tolist()
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            col1, col2 = columns[i], columns[j]
            corr_value = corr_matrix.loc[col1, col2]
            if not np.isnan(corr_value):
                score_pairs.append((col1, col2, corr_value))

    # 按相关性绝对值排序
    score_pairs.sort(key=lambda x: abs(x[2]), reverse=True)

    lines.append("相关性排序（从高到低）:")
    for col1, col2, corr in score_pairs:
        interpretation = interpret_correlation(corr)
        lines.append(f"  {col1} vs {col2}: {corr:.3f} {interpretation}")

    lines.append("")

    # 组合建议
    lines.append("【3. 组合建议】")
    lines.append("-" * 50)

    # 找出正交的组合
    orthogonal_pairs = [(c1, c2, c) for c1, c2, c in score_pairs if abs(c) < 0.3]
    redundant_pairs = [(c1, c2, c) for c1, c2, c in score_pairs if abs(c) >= 0.6]

    if orthogonal_pairs:
        lines.append("✅ 推荐组合（正交，|r| < 0.3）:")
        for col1, col2, corr in orthogonal_pairs[:5]:
            lines.append(f"   - {col1} + {col2} (r={corr:.3f})")
    else:
        lines.append("⚠️ 未发现完全正交的 score 组合")

    lines.append("")

    if redundant_pairs:
        lines.append("❌ 避免同时使用（高度相关，|r| >= 0.6）:")
        for col1, col2, corr in redundant_pairs:
            lines.append(f"   - {col1} vs {col2} (r={corr:.3f})，建议二选一")

    lines.append("")

    # Jaccard 分析（如果有）
    if jaccard_matrix is not None:
        lines.append("【4. 池子重叠度分析 (Jaccard)】")
        lines.append("-" * 50)
        lines.append(jaccard_matrix.round(3).to_string())
        lines.append("")

        lines.append("重叠度解读:")
        pool_names = jaccard_matrix.columns.tolist()
        for i in range(len(pool_names)):
            for j in range(i + 1, len(pool_names)):
                name1, name2 = pool_names[i], pool_names[j]
                jaccard = jaccard_matrix.loc[name1, name2]
                if jaccard < 0.2:
                    interp = "几乎不重叠，互补性强 ✅"
                elif jaccard < 0.5:
                    interp = "部分重叠 ⚠️"
                else:
                    interp = "高度重叠，选出相似ETF ❌"
                lines.append(f"  {name1} vs {name2}: {jaccard:.3f} {interp}")

    lines.append("")
    lines.append("=" * 70)

    report = "\n".join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 分析报告已保存: {output_path}")

    return report


def plot_heatmap(corr_matrix: pd.DataFrame, output_path: Path):
    """绘制相关性热力图"""
    try:
        import matplotlib
        matplotlib.use('Agg')  # 非交互式后端
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.figure(figsize=(10, 8))

        # 使用 seaborn 绘制热力图
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.3f',
            cmap='RdYlGn_r',  # 红(高相关)-黄-绿(低相关)
            vmin=-1,
            vmax=1,
            center=0,
            square=True,
            linewidths=0.5
        )

        plt.title('Score Correlation Matrix (Spearman)', fontsize=14)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"✅ 热力图已保存: {output_path}")

    except ImportError as e:
        print(f"⚠️ 无法生成热力图，缺少依赖: {e}")
        print("   请安装: pip install matplotlib seaborn")


def main():
    parser = argparse.ArgumentParser(
        description='Score 正交检验分析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'input_files',
        type=str,
        help='输入文件路径，多个文件用英文逗号分隔'
    )
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=None,
        help='输出目录，默认与第一个输入文件同目录'
    )
    parser.add_argument(
        '--method',
        type=str,
        choices=['spearman', 'pearson'],
        default='spearman',
        help='相关性计算方法，默认 spearman'
    )
    parser.add_argument(
        '--score-columns',
        type=str,
        default=None,
        help='要分析的 score 列名，逗号分隔，默认自动检测'
    )

    args = parser.parse_args()

    # 解析输入文件
    input_files = [f.strip() for f in args.input_files.split(',')]
    input_files = [f for f in input_files if f]  # 过滤空字符串

    if len(input_files) == 0:
        print("❌ 请提供至少一个输入文件")
        return 1

    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(input_files[0]).parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # 解析 score 列
    score_columns = None
    if args.score_columns:
        score_columns = [c.strip() for c in args.score_columns.split(',')]

    print("=" * 60)
    print("Score 正交检验分析")
    print("=" * 60)
    print(f"输入文件: {input_files}")
    print(f"输出目录: {output_dir}")
    print(f"相关性方法: {args.method}")
    print()

    # 情况1: 单文件 - 计算 score 相关性矩阵
    if len(input_files) == 1:
        file_path = input_files[0]
        print(f"📂 加载数据: {file_path}")

        df = load_score_data(file_path)
        print(f"   加载了 {len(df)} 条记录")

        print(f"\n📊 计算相关性矩阵...")
        corr_matrix = calculate_correlation_matrix(df, score_columns, args.method)

        # 保存相关性矩阵
        corr_output = output_dir / 'correlation_matrix.csv'
        corr_matrix.to_csv(corr_output)
        print(f"✅ 相关性矩阵已保存: {corr_output}")

        # 绘制热力图
        heatmap_output = output_dir / 'correlation_heatmap.png'
        plot_heatmap(corr_matrix, heatmap_output)

        # 生成报告
        report_output = output_dir / 'analysis_report.txt'
        report = generate_report(corr_matrix, output_path=report_output)
        print()
        print(report)

    # 情况2: 多文件 - 计算池子重叠度
    else:
        print(f"📂 加载 {len(input_files)} 个池子文件...")

        pools = {}
        all_dfs = []

        for file_path in input_files:
            file_path = Path(file_path)
            if not file_path.exists():
                print(f"   ⚠️ 文件不存在: {file_path}")
                continue

            df = load_score_data(str(file_path))
            pool_name = file_path.stem  # 使用文件名作为池子名称

            if 'ts_code' in df.columns:
                pools[pool_name] = set(df['ts_code'].tolist())
                all_dfs.append(df)
                print(f"   ✅ {pool_name}: {len(df)} 只ETF")
            else:
                print(f"   ⚠️ {pool_name}: 缺少 ts_code 列")

        if len(pools) < 2:
            print("❌ 至少需要2个有效的池子文件")
            return 1

        # 计算 Jaccard 相似度
        print(f"\n📊 计算池子重叠度 (Jaccard)...")
        jaccard_matrix = calculate_jaccard_similarity(pools)

        # 保存 Jaccard 矩阵
        jaccard_output = output_dir / 'jaccard_similarity.csv'
        jaccard_matrix.to_csv(jaccard_output)
        print(f"✅ Jaccard 相似度矩阵已保存: {jaccard_output}")

        # 如果所有文件都有 score 列，也计算相关性
        corr_matrix = None
        if all_dfs:
            # 合并所有数据计算相关性
            combined_df = pd.concat(all_dfs, ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['ts_code'], keep='first')

            try:
                print(f"\n📊 计算合并数据的相关性矩阵...")
                corr_matrix = calculate_correlation_matrix(combined_df, score_columns, args.method)

                corr_output = output_dir / 'correlation_matrix.csv'
                corr_matrix.to_csv(corr_output)
                print(f"✅ 相关性矩阵已保存: {corr_output}")

                heatmap_output = output_dir / 'correlation_heatmap.png'
                plot_heatmap(corr_matrix, heatmap_output)

            except ValueError as e:
                print(f"   ⚠️ 无法计算相关性: {e}")

        # 生成报告
        report_output = output_dir / 'analysis_report.txt'
        report = generate_report(corr_matrix, jaccard_matrix, output_path=report_output)
        print()
        print(report)

    print()
    print("✅ 分析完成!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
