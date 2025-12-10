#!/usr/bin/env python3
"""
批量生成ETF池

读取configs目录下的所有配置文件，调用etf_selector生成对应的ETF池
同时计算并记录每个池的平均相关性
"""
import json
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from etf_selector.config_loader import ConfigLoader
from etf_selector.selector import TrendETFSelector
from etf_selector.data_loader import ETFDataLoader
from etf_selector.portfolio import PortfolioOptimizer

# 实验目录
EXPERIMENT_DIR = Path(__file__).parent.parent
CONFIGS_DIR = EXPERIMENT_DIR / "configs"
POOLS_DIR = EXPERIMENT_DIR / "pools"
ANALYSIS_DIR = EXPERIMENT_DIR / "analysis"


def calculate_pool_correlation(
    pool_df: pd.DataFrame,
    data_loader: ETFDataLoader,
    start_date: str,
    end_date: str
) -> Dict[str, float]:
    """计算池内ETF的平均相关性"""
    optimizer = PortfolioOptimizer(data_loader=data_loader)

    etf_codes = pool_df['ts_code'].tolist()

    if len(etf_codes) < 2:
        return {'avg_correlation': 0.0, 'max_correlation': 0.0, 'num_etfs': len(etf_codes)}

    # 计算收益率矩阵
    returns_df = optimizer.calculate_returns_matrix(
        etf_codes, start_date=start_date, end_date=end_date
    )

    if returns_df.empty or returns_df.shape[1] < 2:
        return {'avg_correlation': np.nan, 'max_correlation': np.nan, 'num_etfs': len(etf_codes)}

    # 计算相关系数矩阵
    corr_matrix = returns_df.corr()

    # 提取上三角（不含对角线）
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    upper_triangle = corr_matrix.values[mask]

    # 过滤NaN
    valid_corrs = upper_triangle[~np.isnan(upper_triangle)]

    if len(valid_corrs) == 0:
        return {'avg_correlation': np.nan, 'max_correlation': np.nan, 'num_etfs': len(etf_codes)}

    return {
        'avg_correlation': float(np.mean(np.abs(valid_corrs))),
        'max_correlation': float(np.max(np.abs(valid_corrs))),
        'num_etfs': returns_df.shape[1]
    }


def generate_single_pool(config_path: Path, verbose: bool = True) -> Optional[Dict]:
    """生成单个ETF池"""
    config_name = config_path.stem

    if verbose:
        print(f"\n{'='*60}")
        print(f"处理配置: {config_name}")
        print(f"{'='*60}")

    try:
        # 加载配置
        config = ConfigLoader.load_from_json(str(config_path))

        # 创建数据加载器和选择器
        data_loader = ETFDataLoader(config.data_dir)
        selector = TrendETFSelector(config=config, data_loader=data_loader)

        # 执行筛选
        results = selector.run_pipeline(
            start_date=config.start_date,
            end_date=config.end_date,
            verbose=verbose
        )

        if not results:
            print(f"  警告: {config_name} 未产生任何结果")
            return None

        # 导出结果
        output_path = PROJECT_ROOT / config.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        selector.export_results(results, str(output_path))

        # 计算池内相关性
        pool_df = pd.DataFrame(results)
        corr_stats = calculate_pool_correlation(
            pool_df, data_loader, config.start_date, config.end_date
        )

        # 解析配置名称
        parts = config_name.split('_')
        # 格式: {dimension}_{period}_{algorithm}
        # 例如: adx_score_2019_2021_greedy
        algorithm = parts[-1]  # greedy 或 clustering
        period = f"{parts[-3]}_{parts[-2]}"  # 2019_2021
        dimension = '_'.join(parts[:-3])  # adx_score

        result_info = {
            'config_name': config_name,
            'dimension': dimension,
            'period': period,
            'algorithm': algorithm,
            'num_etfs': len(results),
            'output_path': str(output_path),
            **corr_stats
        }

        if verbose:
            print(f"\n  结果统计:")
            print(f"    ETF数量: {result_info['num_etfs']}")
            print(f"    平均相关性: {result_info['avg_correlation']:.4f}")
            print(f"    最大相关性: {result_info['max_correlation']:.4f}")

        return result_info

    except Exception as e:
        print(f"  错误: 处理 {config_name} 时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_all_pools(verbose: bool = True) -> pd.DataFrame:
    """生成所有ETF池"""
    POOLS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    # 获取所有配置文件
    config_files = sorted(CONFIGS_DIR.glob("*.json"))

    if not config_files:
        print("错误: 未找到配置文件，请先运行 generate_configs.py")
        return pd.DataFrame()

    print(f"找到 {len(config_files)} 个配置文件")

    results = []
    for i, config_path in enumerate(config_files, 1):
        print(f"\n[{i}/{len(config_files)}] ", end="")
        result = generate_single_pool(config_path, verbose=verbose)
        if result:
            results.append(result)

    # 汇总结果
    if results:
        summary_df = pd.DataFrame(results)

        # 保存汇总
        summary_path = ANALYSIS_DIR / "pool_generation_summary.csv"
        summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
        print(f"\n\n汇总已保存: {summary_path}")

        # 打印相关性对比
        print("\n" + "=" * 60)
        print("相关性对比 (聚类 vs 贪心)")
        print("=" * 60)

        for dimension in summary_df['dimension'].unique():
            for period in summary_df['period'].unique():
                subset = summary_df[
                    (summary_df['dimension'] == dimension) &
                    (summary_df['period'] == period)
                ]

                greedy_row = subset[subset['algorithm'] == 'greedy']
                clustering_row = subset[subset['algorithm'] == 'clustering']

                if len(greedy_row) > 0 and len(clustering_row) > 0:
                    greedy_corr = greedy_row['avg_correlation'].values[0]
                    clustering_corr = clustering_row['avg_correlation'].values[0]
                    diff = greedy_corr - clustering_corr
                    winner = "聚类" if diff > 0 else "贪心"

                    print(f"\n{dimension} | {period}:")
                    print(f"  贪心: {greedy_corr:.4f} | 聚类: {clustering_corr:.4f} | 差异: {diff:+.4f} ({winner}更低)")

        return summary_df

    return pd.DataFrame()


def main():
    warnings.filterwarnings('ignore')

    print("=" * 60)
    print("批量生成ETF池 (聚类 vs 贪心对比实验)")
    print("=" * 60)

    # 检查配置文件是否存在
    if not CONFIGS_DIR.exists() or not list(CONFIGS_DIR.glob("*.json")):
        print("\n配置文件不存在，先生成配置...")
        from generate_configs import generate_all_configs
        generate_all_configs()

    # 生成所有池
    summary_df = generate_all_pools(verbose=True)

    if not summary_df.empty:
        print("\n" + "=" * 60)
        print("生成完成!")
        print("=" * 60)
        print(f"成功生成 {len(summary_df)} 个ETF池")
        print(f"池文件目录: {POOLS_DIR}")
        print(f"汇总文件: {ANALYSIS_DIR / 'pool_generation_summary.csv'}")


if __name__ == "__main__":
    main()
