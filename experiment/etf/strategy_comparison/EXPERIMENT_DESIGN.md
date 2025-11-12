# 三策略对比实验设计文档

**实验代号**: `strategy_comparison`
**创建日期**: 2025-11-11
**实验目标**: 对比SMA、MACD、KAMA三种均线策略在中国ETF池上的表现，评估最佳超参和止损方案的综合效果

---

## 1. 实验背景

### 1.1 问题陈述

在已实现的三种均线策略中（SMA双均线、MACD交叉、KAMA自适应均线），需要通过标准化的对比实验：
- 评估各策略的**稳健性**（夏普比率平均值和中位数）
- 评估各策略的**盈利能力**（总收益）
- 验证止损保护对各策略的**增益效果**

### 1.2 已知基线

基于已完成的实验，各策略已验证的最佳配置：

| 策略 | 基础参数 | 最佳止损方案 | 止损参数 | 实验来源 |
|------|---------|-------------|---------|----------|
| **SMA** | n1=10, n2=20 | Loss Protection | max_losses=3, pause=10 | `experiment/etf/sma_cross/stop_loss_comparison/` |
| **MACD** | 需优化 | Combined | max_losses=2, pause=5, trail=3% | `experiment/etf/macd_cross/grid_search_stop_loss/` |
| **KAMA** | period=20, fast=2, slow=30 | 待测试 | 待定 | `strategies/kama_cross.py` |

**注**:
- SMA使用固定基础参数（n1=10, n2=20），已在多次实验中验证
- MACD需要优化基础参数（fast_period, slow_period, signal_period），范围：fast[8-20], slow[20-40], signal[5-15]
- KAMA使用默认参数（kama_period=20, kama_fast=2, kama_slow=30）

---

## 2. 实验设计

### 2.1 测试标的

**固定股票池**: `results/trend_etf_pool.csv`
- 来源：ETF三层漏斗筛选系统（`etf_selector/`模块）
- 数量：约20只中国ETF
- 筛选标准：趋势性、流动性、基本面等7维度评分

### 2.2 测试周期

**回测时间窗口**: 2023-11至2025-11（约2年）
- 与已有实验保持一致，便于横向对比
- 覆盖不同市场环境（趋势+震荡）

### 2.3 测试矩阵

每个策略测试**两种配置**：

| 配置ID | 描述 | 说明 |
|--------|------|------|
| **Baseline** | 最佳基础参数 + 无止损 | 评估策略本身质量 |
| **BestStopLoss** | 最佳基础参数 + 最佳止损 | 评估止损增益效果 |

**总测试场景**: 3策略 × 2配置 = 6个场景
**总测试次数**: 6场景 × 20只ETF = 120次回测

### 2.4 评估指标

#### 2.4.1 稳健性指标（主要）

| 指标 | 说明 | 评价标准 |
|------|------|----------|
| **平均夏普比率** | 所有标的夏普比率算术平均 | 越高越好，>1为优秀 |
| **夏普比率中位数** | 所有标的夏普比率中位数 | 抗离群值，评估典型表现 |
| **夏普比率标准差** | 不同标的间夏普的波动 | 越小越稳定 |

#### 2.4.2 盈利能力指标（次要）

| 指标 | 说明 | 评价标准 |
|------|------|----------|
| **平均收益率** | 所有标的收益率算术平均 | 越高越好 |
| **收益率中位数** | 所有标的收益率中位数 | 抗离群值 |
| **总收益率** | 所有标的收益率之和 | 评估绝对盈利能力 |

#### 2.4.3 风险控制指标（辅助）

| 指标 | 说明 | 评价标准 |
|------|------|----------|
| **平均最大回撤** | 所有标的最大回撤平均 | 越小越好 |
| **平均胜率** | 所有标的胜率平均 | >50%为优 |
| **平均交易次数** | 所有标的交易次数平均 | 评估交易频率 |

---

## 3. 技术实现方案

### 3.1 目录结构

```
experiment/etf/strategy_comparison/
├── EXPERIMENT_DESIGN.md          # 本文件：实验设计文档
├── DEVELOPMENT_PLAN.md           # 开发计划和任务分解
├── compare_strategies.py         # 主实验脚本
├── configs/
│   ├── sma_baseline.json        # SMA基础配置（无止损）
│   ├── sma_best_stop_loss.json  # SMA最佳止损配置
│   ├── macd_baseline.json       # MACD基础配置（无止损）
│   ├── macd_best_stop_loss.json # MACD最佳止损配置
│   ├── kama_baseline.json       # KAMA基础配置（无止损）
│   └── kama_best_stop_loss.json # KAMA最佳止损配置
├── results/
│   ├── raw/                      # 原始回测结果（每个场景的详细数据）
│   ├── comparison_summary.csv    # 汇总对比表
│   ├── RESULTS.md               # 实验结果报告
│   └── visualizations/          # 可视化图表
│       ├── sharpe_comparison.png
│       ├── return_comparison.png
│       └── risk_metrics.png
└── logs/
    └── experiment_YYYYMMDD_HHMMSS.log
```

### 3.2 核心实现逻辑

#### 3.2.1 策略配置管理

```python
# 策略配置字典结构
STRATEGY_CONFIGS = {
    'SMA': {
        'baseline': {
            'strategy_class': 'sma_cross_enhanced',
            'params': {'n1': 10, 'n2': 20},
            'stop_loss': None
        },
        'best_stop_loss': {
            'strategy_class': 'sma_cross_enhanced',
            'params': {'n1': 10, 'n2': 20},
            'stop_loss': {
                'type': 'loss_protection',
                'max_consecutive_losses': 3,
                'pause_bars': 10
            }
        }
    },
    'MACD': {
        'baseline': {
            'strategy_class': 'macd_cross',
            'params': None,  # 需要优化
            'optimize': True,
            'optimize_params': {
                'fast_period': range(8, 21, 2),
                'slow_period': range(20, 41, 2),
                'signal_period': range(5, 16, 2),
            },
            'stop_loss': None
        },
        'best_stop_loss': {
            'strategy_class': 'macd_cross',
            'params': None,  # 继承baseline优化结果
            'stop_loss': {
                'type': 'combined',
                'max_consecutive_losses': 2,
                'pause_bars': 5,
                'trailing_stop_pct': 0.03
            }
        }
    },
    'KAMA': {
        'baseline': {
            'strategy_class': 'kama_cross',
            'params': {
                'kama_period': 20,
                'kama_fast': 2,
                'kama_slow': 30
            },
            'stop_loss': None
        },
        'best_stop_loss': {
            'strategy_class': 'kama_cross',
            'params': {
                'kama_period': 20,
                'kama_fast': 2,
                'kama_slow': 30
            },
            'stop_loss': {
                'type': 'loss_protection',  # 先测试Loss Protection
                'max_consecutive_losses': 3,
                'pause_bars': 10
            }
        }
    }
}
```

#### 3.2.2 实验执行流程

```
开始实验
    ↓
加载股票池 (results/trend_etf_pool.csv)
    ↓
对于每个策略 (SMA, MACD, KAMA):
    ↓
    1. 测试 Baseline 配置
       - 加载基础参数
       - 如需优化：运行参数优化（仅MACD）
       - 对每只ETF运行回测
       - 保存原始结果到 raw/{strategy}_baseline/
       ↓
    2. 测试 BestStopLoss 配置
       - 继承Baseline的基础参数（如MACD优化结果）
       - 添加止损保护配置
       - 对每只ETF运行回测
       - 保存原始结果到 raw/{strategy}_best_stop_loss/
    ↓
汇总统计分析
    ↓
生成对比报告和可视化
    ↓
结束
```

#### 3.2.3 关键技术点

1. **MACD参数优化处理**
   - Baseline阶段：对每只ETF独立优化基础参数
   - BestStopLoss阶段：复用Baseline的优化参数，仅添加止损
   - 原因：确保止损效果不受参数优化影响

2. **止损方案实现**
   - SMA: `enable_loss_protection=True, max_consecutive_losses=3, pause_bars=10`
   - MACD: `enable_loss_protection=True, enable_trailing_stop=True, ...`（Combined方案）
   - KAMA: 先测试Loss Protection，必要时测试Combined

3. **数据处理**
   - 使用 `backtest_runner` 模块的标准化接口
   - 复用现有的ETF数据读取逻辑（`data/chinese_etf/daily/`）
   - 结果输出格式与现有实验保持一致

---

## 4. 预期结果

### 4.1 假设验证

**H1**: 止损保护对所有策略都有正向增益
**预期**: BestStopLoss配置的夏普比率 > Baseline

**H2**: KAMA策略因自适应特性，稳健性最优
**预期**: KAMA的夏普比率标准差最小

**H3**: MACD策略经优化后盈利能力最强
**预期**: MACD的平均收益率最高

### 4.2 关键对比点

| 对比维度 | 预期排名（从优到劣） | 依据 |
|---------|---------------------|------|
| **稳健性** | KAMA > SMA > MACD | KAMA自适应，MACD参数敏感 |
| **盈利能力** | MACD > KAMA > SMA | MACD捕捉趋势更激进 |
| **止损增益** | SMA > MACD > KAMA | SMA最简单，止损效果最明显 |
| **综合表现** | KAMA ≈ MACD > SMA | 平衡稳健性和收益 |

---

## 5. 实验交付物

### 5.1 代码交付物

- [ ] `compare_strategies.py`: 主实验脚本（支持命令行参数）
- [ ] `configs/`: 6个策略配置JSON文件
- [ ] 单元测试（可选）：验证配置加载和结果解析

### 5.2 文档交付物

- [x] `EXPERIMENT_DESIGN.md`: 本文件
- [ ] `DEVELOPMENT_PLAN.md`: 开发任务分解
- [ ] `RESULTS.md`: 实验结果报告
  - 汇总统计表
  - 假设验证结论
  - 策略推荐建议

### 5.3 数据交付物

- [ ] `results/raw/`: 120次回测的原始结果文件
- [ ] `results/comparison_summary.csv`: 汇总对比表
- [ ] `results/visualizations/`: 对比图表（PNG格式）

---

## 6. 开发排期

**预估开发时间**: 4-6小时

| 阶段 | 任务 | 预估时间 |
|------|------|----------|
| **Phase 1** | 配置文件准备 | 30分钟 |
| **Phase 2** | 主脚本开发 | 2小时 |
| **Phase 3** | 实验执行 | 1-2小时（取决于计算资源） |
| **Phase 4** | 结果分析和报告 | 1小时 |
| **Phase 5** | 可视化和文档完善 | 30分钟 |

**依赖条件**:
- 股票池文件存在：`results/trend_etf_pool.csv`
- ETF数据完整：`data/chinese_etf/daily/`
- KAMA策略已实现并可用（已确认✅）

---

## 7. 风险和注意事项

### 7.1 技术风险

1. **MACD参数优化耗时**
   - 风险：每只ETF优化可能需5-10分钟
   - 缓解：并行优化，或使用缓存机制

2. **KAMA策略未充分测试**
   - 风险：首次大规模回测可能遇到未知bug
   - 缓解：先在1-2只ETF上试跑

3. **结果可比性**
   - 风险：MACD优化可能选出过拟合参数
   - 缓解：使用训练集/测试集分离（可选）

### 7.2 数据风险

1. **ETF数据缺失**
   - 检查：运行前验证所有ETF数据完整性
   - 处理：缺失标的跳过，记录日志

2. **复权因子问题**
   - 确保：使用后复权价格（已在系统中配置）

---

## 8. 后续扩展

实验完成后，可扩展的方向：

1. **参数敏感性分析**: 测试参数小幅变化对结果的影响
2. **组合策略**: 探索多策略加权组合的可能性
3. **时间窗口滚动**: 测试不同时间段的稳定性
4. **过滤器影响**: 添加ADX/成交量过滤器的对比
5. **不同市场环境**: 分别统计牛市/熊市/震荡市表现

---

## 9. 参考文档

- **ETF筛选系统**: `requirement_docs/20251106_china_etf_filter_for_trend_following.md`
- **SMA止损实验**: `experiment/etf/sma_cross/stop_loss_comparison/RESULTS.md`
- **MACD止损实验**: `experiment/etf/macd_cross/grid_search_stop_loss/RESULTS.md`
- **KAMA策略实现**: `strategies/kama_cross.py`
- **止损实现文档**: `requirement_docs/20251109_native_stop_loss_implementation.md`

---

**实验负责人**: Claude
**审批状态**: 待用户确认
**版本**: v1.0
