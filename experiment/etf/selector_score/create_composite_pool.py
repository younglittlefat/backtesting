#!/usr/bin/env python3
"""
创建跨周期稳健组合权重ETF池

推荐权重配置:
- 成交量 40% (跨周期最稳定)
- 趋势一致性 30% (牛市增益)
- 流动性 20% (牛市爆发力)
- 12个月动量 10% (熊市防御)
"""

import pandas as pd
import numpy as np
from pathlib import Path


def normalize_scores(df, score_column):
    """Min-max归一化到[0,1]"""
    min_val = df[score_column].min()
    max_val = df[score_column].max()
    if max_val == min_val:
        return pd.Series(0.0, index=df.index)
    return (df[score_column] - min_val) / (max_val - min_val)


def main():
    # 数据路径
    pool_dir = Path('/mnt/d/git/backtesting/experiment/etf/selector_score/pool')

    # 读取各维度all_scores文件
    print("读取各维度评分数据...")
    volume_df = pd.read_csv(pool_dir / 'single_volume_pool_all_scores.csv')
    trend_consistency_df = pd.read_csv(pool_dir / 'single_trend_consistency_pool_2019_2021_all_scores.csv')
    liquidity_df = pd.read_csv(pool_dir / 'single_liquidity_score_pool_2019_2021_all_scores.csv')
    momentum_12m_df = pd.read_csv(pool_dir / 'single_momentum_12m_pool_2019_2021_all_scores.csv')

    print(f"成交量: {len(volume_df)} 只ETF")
    print(f"趋势一致性: {len(trend_consistency_df)} 只ETF")
    print(f"流动性: {len(liquidity_df)} 只ETF")
    print(f"12个月动量: {len(momentum_12m_df)} 只ETF")

    # 提取关键列
    volume_scores = volume_df[['ts_code', 'name', 'volume_trend']].rename(columns={'volume_trend': 'volume_score'})
    trend_scores = trend_consistency_df[['ts_code', 'trend_consistency']].rename(columns={'trend_consistency': 'trend_score'})
    liquidity_scores = liquidity_df[['ts_code', 'liquidity_score']]
    momentum_scores = momentum_12m_df[['ts_code', 'momentum_12m']].rename(columns={'momentum_12m': 'momentum_score'})

    # 合并数据 (使用inner join确保所有维度都有数据)
    print("\n合并数据...")
    merged = volume_scores.merge(trend_scores, on='ts_code', how='inner')
    merged = merged.merge(liquidity_scores, on='ts_code', how='inner')
    merged = merged.merge(momentum_scores, on='ts_code', how='inner')

    print(f"合并后: {len(merged)} 只ETF有完整评分")

    # 检查缺失值
    missing = merged[['volume_score', 'trend_score', 'liquidity_score', 'momentum_score']].isnull().sum()
    if missing.any():
        print(f"\n警告: 发现缺失值\n{missing}")
        merged = merged.dropna(subset=['volume_score', 'trend_score', 'liquidity_score', 'momentum_score'])
        print(f"删除缺失值后: {len(merged)} 只ETF")

    # Min-max归一化各维度得分
    print("\n归一化各维度得分...")
    merged['volume_norm'] = normalize_scores(merged, 'volume_score')
    merged['trend_norm'] = normalize_scores(merged, 'trend_score')
    merged['liquidity_norm'] = normalize_scores(merged, 'liquidity_score')
    merged['momentum_norm'] = normalize_scores(merged, 'momentum_score')

    # 计算组合加权得分
    print("\n计算组合加权得分 (成交量40%, 趋势一致性30%, 流动性20%, 12月动量10%)...")
    merged['composite_score'] = (
        0.40 * merged['volume_norm'] +
        0.30 * merged['trend_norm'] +
        0.20 * merged['liquidity_norm'] +
        0.10 * merged['momentum_norm']
    )

    # 按组合得分降序排列
    merged_sorted = merged.sort_values('composite_score', ascending=False)

    # 选择TOP 20
    top20 = merged_sorted.head(20).copy()

    print(f"\n=== TOP 20 跨周期稳健组合权重ETF ===")
    print(top20[['ts_code', 'name', 'composite_score', 'volume_norm', 'trend_norm', 'liquidity_norm', 'momentum_norm']].to_string(index=False))

    # 保存完整评分文件 (包含所有维度原始分和归一化分)
    output_all_scores = pool_dir / 'composite_cross_cycle_pool_all_scores.csv'
    merged_sorted.to_csv(output_all_scores, index=False, encoding='utf-8-sig')
    print(f"\n完整评分文件已保存: {output_all_scores}")

    # 保存TOP 20池 (仅包含ts_code和name)
    output_pool = pool_dir / 'composite_cross_cycle_pool.csv'
    top20[['ts_code', 'name']].to_csv(output_pool, index=False, encoding='utf-8-sig')
    print(f"TOP 20池文件已保存: {output_pool}")

    # 统计信息
    print(f"\n=== 统计信息 ===")
    print(f"组合得分范围: [{merged['composite_score'].min():.4f}, {merged['composite_score'].max():.4f}]")
    print(f"TOP 20 组合得分范围: [{top20['composite_score'].min():.4f}, {top20['composite_score'].max():.4f}]")
    print(f"TOP 20 各维度归一化均值:")
    print(f"  成交量: {top20['volume_norm'].mean():.4f}")
    print(f"  趋势一致性: {top20['trend_norm'].mean():.4f}")
    print(f"  流动性: {top20['liquidity_norm'].mean():.4f}")
    print(f"  12个月动量: {top20['momentum_norm'].mean():.4f}")


if __name__ == '__main__':
    main()
