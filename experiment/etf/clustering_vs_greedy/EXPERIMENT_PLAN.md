# 聚类选择 vs 贪心算法 ETF池对比实验

## 1. 实验目标

验证新开发的**层次聚类选择算法**是否优于原有的**贪心算法+硬编码行业分类**，在多个评分维度和市场周期下进行系统对比。

### 核心假设

- **H1**: 聚类选择能产生更低相关性的ETF组合（数据驱动 vs 硬编码）
- **H2**: 低相关性组合在趋势跟踪策略中表现更好（夏普比率更高）
- **H3**: 聚类选择的优势在不同评分维度和市场周期中具有普适性

## 2. 实验设计

### 2.1 自变量（实验因子）

| 因子 | 水平 | 说明 |
|------|------|------|
| **选择算法** | 2 | `greedy`（贪心+硬编码行业）, `clustering`（层次聚类） |
| **评分维度** | 6 | ADX、流动性、价格效率、趋势一致性、动量12m、趋势质量 |
| **筛选周期** | 2 | 2019-2021（熊市前）, 2022-2023（牛市前） |

**实验矩阵**: 2 × 6 × 2 = **24组ETF池**

### 2.2 因变量（评估指标）

| 指标 | 优先级 | 说明 |
|------|--------|------|
| **夏普比率** | P0 | 风险调整收益，主要评估指标 |
| **年化收益率** | P1 | 绝对收益能力 |
| 最大回撤 | P2 | 风险控制 |
| 池内平均相关性 | P2 | 分散化程度（聚类核心价值） |
| 胜率 | P3 | 交易稳定性 |

### 2.3 控制变量

| 变量 | 固定值 | 说明 |
|------|--------|------|
| 回测策略 | KAMA | 固定参数，无优化 |
| 目标池大小 | 20 | 两种算法产出相同数量ETF |
| 聚类方法 | ward | 默认层次聚类方法 |
| 最低分数百分位 | 20% | 聚类时低分簇留空阈值 |
| 去重阈值 | [0.98, 0.95, 0.92, 0.90] | 贪心算法去重参数 |

### 2.4 回测周期

| 筛选周期 | 回测周期 | 市场特征 |
|----------|----------|----------|
| 2019-01-02 ~ 2021-12-31 | 2022-01-02 ~ 2023-12-31 | 熊市（样本外） |
| 2022-01-02 ~ 2023-12-31 | 2024-01-02 ~ 2025-11-30 | 牛市（样本外） |

## 3. 实验流程

### Phase 1: 生成ETF池（24组）

```
对于每个 (评分维度, 筛选周期) 组合:
    1. 使用相同的 stage1 + stage2 筛选
    2. 分别用 greedy 和 clustering 执行 stage3
    3. 输出两个池子: {dimension}_{period}_greedy.csv, {dimension}_{period}_clustering.csv
    4. 记录池内平均相关性
```

### Phase 2: 批量回测（24组 × 20只 = 480次回测）

```
对于每个 ETF池:
    使用固定 KAMA 策略回测对应周期
    收集: 夏普、收益率、回撤、胜率
```

### Phase 3: 统计分析

```
1. 配对比较: 同维度同周期下 clustering vs greedy
2. 汇总统计: 聚类胜出次数、平均提升幅度
3. 交互效应: 聚类优势是否因维度/周期而异
```

## 4. 目录结构

```
experiment/etf/clustering_vs_greedy/
├── EXPERIMENT_PLAN.md          # 本文档
├── RESULTS.md                  # 实验结果报告
├── configs/                    # 筛选配置文件
│   ├── adx_2019_2021_greedy.json
│   ├── adx_2019_2021_clustering.json
│   └── ...
├── pools/                      # 生成的ETF池
│   ├── adx_2019_2021_greedy.csv
│   ├── adx_2019_2021_clustering.csv
│   └── ...
├── backtests/                  # 回测结果
│   ├── bear_market/            # 2022-2023熊市回测
│   └── bull_market/            # 2024-2025牛市回测
├── analysis/                   # 分析结果
│   ├── pool_correlation_comparison.csv
│   ├── backtest_comparison.csv
│   └── summary_charts/
└── scripts/                    # 实验脚本
    ├── generate_pools.py       # 生成ETF池
    ├── run_backtests.py        # 批量回测
    └── analyze_results.py      # 结果分析
```

## 5. 评分维度配置

选择6个代表性维度（覆盖趋势、流动性、动量三大类）：

| 维度 | 类别 | 权重配置 |
|------|------|----------|
| adx_score | 趋势 | trend.weight=1, adx_score=1 |
| liquidity_score | 流动性 | liquidity.weight=1, liquidity_score=1 |
| price_efficiency | 流动性 | liquidity.weight=1, price_efficiency=1 |
| trend_consistency | 趋势 | trend.weight=1, trend_consistency=1 |
| momentum_12m | 动量 | return.weight=1, momentum_12m=1 |
| trend_quality | 趋势 | trend.weight=1, trend_quality=1 |

## 6. KAMA策略配置

```python
STRATEGY_CONFIG = {
    'strategy': 'kama_cross',
    'kama_period': 20,
    'kama_fast': 2,
    'kama_slow': 30,
    'enable_adx_filter': True,
    'adx_period': 14,
    'adx_threshold': 25.0,
    'enable_atr_stop': True,
    'atr_period': 14,
    'atr_multiplier': 2.5,
    'enable_slope_confirmation': True,
    'min_slope_periods': 3,
}
```

## 7. 成功标准

| 标准 | 阈值 | 说明 |
|------|------|------|
| 聚类胜出率 | > 50% | 在24组对比中聚类夏普更高的比例 |
| 平均夏普提升 | > 0.05 | 聚类相对贪心的平均夏普提升 |
| 相关性降低 | > 5% | 聚类池平均相关性低于贪心池 |

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 聚类参数过拟合 | 使用默认参数，不做网格搜索 |
| 样本量不足 | 24组对比 + 480次回测提供统计显著性 |
| 市场周期偏差 | 同时测试熊市和牛市 |
| 评分维度偏差 | 覆盖6个不同类别的维度 |

## 9. 开发任务

- [ ] Task 1: 创建配置文件生成脚本
- [ ] Task 2: 实现ETF池生成脚本（支持greedy/clustering切换）
- [ ] Task 3: 复用pool_comparison框架进行批量回测
- [ ] Task 4: 实现结果分析和可视化
- [ ] Task 5: 执行实验并撰写报告

## 10. 时间估算

| 阶段 | 预计耗时 |
|------|----------|
| 生成24组ETF池 | ~10分钟 |
| 480次回测 | ~30-60分钟 |
| 结果分析 | ~10分钟 |
| **总计** | **~1小时** |
