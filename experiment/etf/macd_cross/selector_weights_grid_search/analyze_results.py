#!/usr/bin/env python3
"""分析无偏权重网格搜索实验结果"""

import pandas as pd
import json
import sys

# 读取结果
results_file = "/mnt/d/git/backtesting/experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/experiment_results.csv"
df = pd.read_csv(results_file)

# 将百分比转换为可读格式
df['annual_return_pct'] = df['annual_return'] * 100
df['max_drawdown_pct'] = df['max_drawdown'] * 100

print("=" * 70)
print("ETF筛选器无偏权重网格搜索实验结果分析")
print("=" * 70)
print(f"完成实验数: {len(df)} / 22")
print()

# 统计分析
print("=" * 70)
print("整体统计摘要")
print("=" * 70)
print(f"平均夏普比率: {df['sharpe_ratio'].mean():.4f}")
print(f"夏普比率中位数: {df['sharpe_ratio'].median():.4f}")
print(f"夏普比率范围: [{df['sharpe_ratio'].min():.4f}, {df['sharpe_ratio'].max():.4f}]")
print(f"标准差: {df['sharpe_ratio'].std():.4f}")
print()
print(f"平均年化收益: {df['annual_return_pct'].mean():.2f}%")
print(f"年化收益范围: [{df['annual_return_pct'].min():.2f}%, {df['annual_return_pct'].max():.2f}%]")
print()
print(f"平均最大回撤: {df['max_drawdown_pct'].mean():.2f}%")
print(f"最大回撤范围: [{df['max_drawdown_pct'].min():.2f}%, {df['max_drawdown_pct'].max():.2f}%]")
print()
print(f"平均筛选ETF数量: {df['etf_count'].mean():.1f}")
print(f"ETF数量范围: [{df['etf_count'].min()}, {df['etf_count'].max()}]")
print()

# TOP 5配置
print("=" * 70)
print("TOP 5 最优配置（按夏普比率排序）")
print("=" * 70)
top5 = df.nlargest(5, 'sharpe_ratio').reset_index(drop=True)
for idx, row in top5.iterrows():
    print(f"\n第 {idx+1} 名 (实验ID: {int(row['experiment_id'])})")
    print(f"  权重配置:")
    print(f"    - ADX: {row['adx_weight']:.2f}")
    print(f"    - 趋势一致性: {row['trend_consistency_weight']:.2f}")
    print(f"    - 价格效率: {row['price_efficiency_weight']:.2f}")
    print(f"    - 流动性: {row['liquidity_weight']:.2f}")
    print(f"  性能指标:")
    print(f"    - 夏普比率: {row['sharpe_ratio']:.4f}")
    print(f"    - 年化收益: {row['annual_return_pct']:.2f}%")
    print(f"    - 最大回撤: {row['max_drawdown_pct']:.2f}%")
    print(f"    - 筛选ETF数量: {int(row['etf_count'])}只")

# 参数相关性分析
print()
print("=" * 70)
print("参数与夏普比率的相关性分析")
print("=" * 70)
weight_cols = ['adx_weight', 'trend_consistency_weight', 'price_efficiency_weight', 'liquidity_weight']
correlations = df[weight_cols].corrwith(df['sharpe_ratio']).sort_values(ascending=False)
for param, corr in correlations.items():
    param_name = param.replace('_weight', '').replace('_', ' ').title()
    print(f"{param_name:25s}: {corr:>8.4f}")

# 按ETF数量分组分析
print()
print("=" * 70)
print("按筛选ETF数量分组的性能对比")
print("=" * 70)
etf_groups = df.groupby('etf_count').agg({
    'sharpe_ratio': ['count', 'mean', 'std', 'min', 'max'],
    'annual_return_pct': 'mean',
    'max_drawdown_pct': 'mean'
}).round(4)
print(etf_groups)

# 检查参数敏感性
print()
print("=" * 70)
print("关键发现")
print("=" * 70)
sharpe_range = df['sharpe_ratio'].max() - df['sharpe_ratio'].min()
sharpe_std = df['sharpe_ratio'].std()
print(f"1. 夏普比率变化范围: {sharpe_range:.4f}")
print(f"2. 夏普比率标准差: {sharpe_std:.4f}")
if sharpe_std < 0.01:
    print("   ✓ 结果高度稳定，参数对性能影响极小")
    print("   ✓ 所有权重配置产生几乎相同的结果")
elif sharpe_std < 0.05:
    print("   ✓ 结果稳定，参数敏感性较低")
else:
    print("   ⚠ 参数对性能有显著影响")

# 检查ETF数量影响
etf_17 = df[df['etf_count'] == 17]['sharpe_ratio'].mean()
etf_18 = df[df['etf_count'] == 18]['sharpe_ratio'].mean()
print(f"\n3. ETF数量对性能的影响:")
print(f"   - 17只ETF: 平均夏普比率 = {etf_17:.4f}")
print(f"   - 18只ETF: 平均夏普比率 = {etf_18:.4f}")
print(f"   - 差异: {abs(etf_18 - etf_17):.4f}")
if abs(etf_18 - etf_17) < 0.001:
    print("   ✓ ETF数量变化对性能影响可忽略")

# 最优配置建议
print()
print("=" * 70)
print("最优配置建议")
print("=" * 70)
best = df.loc[df['sharpe_ratio'].idxmax()]
print(f"推荐配置 (实验ID: {int(best['experiment_id'])}):")
print(f"  ADX权重:        {best['adx_weight']:.2f}")
print(f"  趋势一致性权重:  {best['trend_consistency_weight']:.2f}")
print(f"  价格效率权重:    {best['price_efficiency_weight']:.2f}")
print(f"  流动性权重:      {best['liquidity_weight']:.2f}")
print(f"  动量权重:        0.00 (完全去除)")
print()
print(f"预期性能:")
print(f"  夏普比率:   {best['sharpe_ratio']:.4f}")
print(f"  年化收益:   {best['annual_return_pct']:.2f}%")
print(f"  最大回撤:   {best['max_drawdown_pct']:.2f}%")
print(f"  筛选ETF:    {int(best['etf_count'])}只")

print()
print("=" * 70)
