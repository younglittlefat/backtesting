# ETF Selector 评分正交性分析

> **状态**: ✅ 已完成
> **完成日期**: 2025-12-06
> **输出目录**: `experiment/etf/selector_score/`

## 背景

### 问题描述

在 ETF 筛选系统中，我们使用多个 score 维度对 ETF 进行评分和排序：
- `adx_mean`: ADX 趋势强度
- `trend_consistency`: 趋势一致性
- `price_efficiency`: 价格发现效率
- `liquidity_score`: 流动性评分

当前的做法是通过**贪心搜索**确定各 score 的组合权重，但这存在信息冗余风险。通过计算各 score 之间的相关性矩阵，找出**信息不重复**（正交）的 score 组合。

### 正交性判断标准

| 相关系数 |r| | 含义 | 组合建议 |
|-----------|------|------|
| < 0.3 | 正交/独立 | ✅ 可以组合，信息互补 |
| 0.3 - 0.6 | 中度相关 | ⚠️ 可组合但需调整权重 |
| > 0.6 | 高度相关 | ❌ 信息重复，应二选一 |

---

## 实验结论

**数据来源**: `experiment/etf/selector_score/single_primary/single_adx_pool_2019_2021_all_scores.csv`（165 只 ETF）
**分析方法**: Spearman 秩相关系数

### 相关性矩阵（核心 Score）

|                    | adx_mean | trend_consistency | price_efficiency | liquidity_score |
|--------------------|----------|-------------------|------------------|-----------------|
| **adx_mean**       | 1.000    | 0.126             | 0.063            | 0.365           |
| **trend_consistency** | 0.126 | 1.000             | 0.008            | 0.015           |
| **price_efficiency**  | 0.063 | 0.008             | 1.000            | 0.146           |
| **liquidity_score**   | 0.365 | 0.015             | 0.146            | 1.000           |

### 关键发现

#### ❌ 高度相关（应避免同时使用，|r| ≥ 0.6）

| Score 对 | 相关系数 | 建议 |
|----------|----------|------|
| `excess_return_60d` vs `idr` | **0.982** | 二选一，本质相同 |
| `momentum_3m` vs `excess_return_60d` | **0.961** | 二选一 |
| `momentum_3m` vs `idr` | **0.942** | 二选一 |

**结论**: `momentum_3m`、`excess_return_60d`、`idr` 三个指标高度重叠，测量的是同一维度信息（短期收益/动量），应只选其一。

#### ⚠️ 中度相关（0.3 ≤ |r| < 0.6）

| Score 对 | 相关系数 | 说明 |
|----------|----------|------|
| `trend_consistency` vs `trend_quality` | 0.577 | 都反映趋势稳定性 |
| `price_efficiency` vs `momentum_12m` | 0.494 | 价格效率与长期动量相关 |
| `adx_mean` vs `liquidity_score` | 0.365 | 高流动性标的趋势更强 |

#### ✅ 正交组合（|r| < 0.3，可安全组合）

**核心 4 个 Primary Score 之间基本正交**：

| Score 对 | 相关系数 | 评价 |
|----------|----------|------|
| `trend_consistency` vs `price_efficiency` | 0.008 | 几乎独立 ✅ |
| `trend_consistency` vs `liquidity_score` | 0.015 | 几乎独立 ✅ |
| `adx_mean` vs `price_efficiency` | 0.063 | 正交 ✅ |
| `adx_mean` vs `trend_consistency` | 0.126 | 正交 ✅ |
| `price_efficiency` vs `liquidity_score` | 0.146 | 正交 ✅ |

### 结论与建议

1. **核心 4 个 Score 可放心组合**: `adx_mean`、`trend_consistency`、`price_efficiency`、`liquidity_score` 之间相关性很低（|r| < 0.37），组合使用能捕捉不同维度信息。

2. **动量类指标应只选其一**: `momentum_3m`、`excess_return_60d`、`idr` 高度相关（r > 0.94），选择其中任一即可，推荐 `momentum_3m`（计算最简单）。

3. **`trend_quality` 与 `trend_consistency` 有冗余**: 相关性 0.577，如需同时使用应降低其中一个权重。

---

## 用法

### 运行相关性分析

```bash
# 单文件分析
python scripts/analyze_score_correlation.py \
    experiment/etf/selector_score/single_primary/single_adx_pool_2019_2021_all_scores.csv \
    --output-dir experiment/etf/selector_score

# 指定要分析的 score 列
python scripts/analyze_score_correlation.py all_scores.csv \
    --score-columns "adx_mean,trend_consistency,price_efficiency,liquidity_score"
```

### 输出文件

| 文件 | 说明 |
|------|------|
| `correlation_matrix.csv` | 相关性矩阵数据 |
| `correlation_heatmap.png` | 热力图可视化 |
| `analysis_report.txt` | 完整分析报告 |

---

## 相关文件

- `scripts/analyze_score_correlation.py` - 正交性分析脚本
- `experiment/etf/selector_score/correlation_matrix.csv` - 相关性矩阵结果
- `experiment/etf/selector_score/correlation_heatmap.png` - 热力图
- `experiment/etf/selector_score/analysis_report.txt` - 分析报告
