# KAMA策略超参数搜索实验 - 文档索引

**创建日期**: 2025-11-11
**实验状态**: 📋 设计完成，待开发实现

---

## 📚 文档列表

### 核心文档（已完成）

| 文件 | 说明 | 字数 | 状态 |
|------|------|------|------|
| **EXPERIMENT_DESIGN.md** | 详细实验设计文档 | ~7000字 | ✅ 完成 |
| **README.md** | 快速上手指南 | ~2500字 | ✅ 完成 |
| **DEVELOPMENT_PLAN.md** | 开发任务清单 | ~2000字 | ✅ 完成 |

### 待创建文档

| 文件 | 说明 | 优先级 | 预计字数 |
|------|------|--------|----------|
| **REQUIREMENTS.md** | 详细需求文档 | 低 | ~3000字 |
| **RESULTS.md** | 实验结果报告 | - | 实验后生成 |

---

## 🎯 实验概要

### 核心目标

通过系统性网格搜索回答以下关键问题：

1. **过滤器效果**: 6种过滤器各自对KAMA策略的增益
2. **最优组合**: 哪些过滤器组合效果最佳？
3. **止损参数**: 连续止损保护的最优配置
4. **协同效应**: 过滤器 + 止损的综合表现

### 实验规模

| 维度 | 测试内容 | 回测次数 | 预期耗时 |
|------|----------|----------|----------|
| **Dimension 1** | 信号过滤器组合 | 200次 | ~1小时 |
| **Dimension 2** | 止损保护参数 | 340次 | ~1.5-2小时 |
| **Dimension 3** | 顶级配置对比 | 140次 | ~30-40分钟 |
| **总计** | - | **680次** | **~3-4小时** |

### 测试矩阵

#### Phase 1: 信号过滤器（200次）

```
Phase 1A: Baseline（无过滤器）                    20次
Phase 1B: 单一过滤器（ADX/Volume/Slope/Confirm）  80次
Phase 1C: 双过滤器组合（4种精选组合）            80次
Phase 1D: 全组合过滤器                           20次
```

#### Phase 2: 止损保护（340次）

```
Phase 2A: 最佳过滤器无止损（对照）                20次
Phase 2B: 连续止损保护网格搜索（4×4）           320次
         - max_consecutive_losses: [2, 3, 4, 5]
         - pause_bars: [5, 10, 15, 20]
```

#### Phase 3: 顶级配置对比（140次）

```
Config 0: 纯KAMA（Baseline）
Config 1: 最佳单一过滤器
Config 2: 最佳双过滤器组合
Config 3: 仅止损保护
Config 4: 单一过滤器 + 止损 ⭐预期最优
Config 5: 双过滤器 + 止损 ⭐预期最优
Config 6: 全组合 + 止损
```

---

## 📊 预期成果

### 输出文件结构

```
experiment/etf/kama_cross/hyperparameter_search/
├── EXPERIMENT_DESIGN.md          ✅ 设计文档
├── README.md                      ✅ 快速指南
├── DEVELOPMENT_PLAN.md            ✅ 任务清单
├── INDEX.md                       ✅ 本索引文档
├── grid_search.py                 🔲 主实验脚本（待开发）
├── generate_visualizations.py    🔲 可视化脚本（待开发）
├── generate_report.py             🔲 报告生成脚本（待开发）
├── results/                       📁 实验结果目录
│   ├── phase1a_baseline.csv
│   ├── phase1b_single_filters.csv
│   ├── phase1c_dual_filters.csv
│   ├── phase1d_full_stack.csv
│   ├── phase2b_loss_protection_grid.csv
│   ├── phase3_top_configs.csv
│   ├── summary_statistics.csv
│   └── RESULTS.md                 📄 实验报告（实验后生成）
└── plots/                         📁 可视化图表目录
    ├── filter_comparison.png
    ├── heatmap_loss_protection_sharpe.png
    ├── heatmap_loss_protection_drawdown.png
    ├── top_configs_comparison.png
    ├── synergy_analysis.png
    └── parameter_sensitivity.png
```

### 关键洞察预期

1. **最优过滤器**: ADX + 成交量组合预期增益最大（+30-50%夏普）
2. **最佳止损参数**: `max_consecutive_losses=3, pause_bars=10`（参考SMA实验）
3. **协同效应**: 过滤器 + 止损预期正向协同（夏普提升60-80%）
4. **参数敏感性**: 止损参数不敏感，大部分组合表现稳定

---

## 🚀 快速开始

### 查看实验设计

```bash
# 详细设计文档（推荐首先阅读）
less experiment/etf/kama_cross/hyperparameter_search/EXPERIMENT_DESIGN.md

# 快速上手指南
less experiment/etf/kama_cross/hyperparameter_search/README.md

# 开发任务清单
less experiment/etf/kama_cross/hyperparameter_search/DEVELOPMENT_PLAN.md
```

### 运行实验（待实现）

```bash
# 前置条件
conda activate backtesting

# 完整实验（待grid_search.py开发完成）
python experiment/etf/kama_cross/hyperparameter_search/grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all
```

---

## 📖 实验背景

### KAMA策略特性

**核心理念**: Kaufman自适应移动平均线，根据市场效率自动调整响应速度

**优势**:
- ✅ 趋势期快速跟随
- ✅ 震荡期平滑滤波
- ✅ 无需人工调参

**已实现功能**:
- Phase 1: KAMA指标 + 效率比率过滤 + 斜率确认 ✅
- Phase 2: ADX/成交量/价格斜率/持续确认过滤器 ✅
- Phase 3: 连续止损保护 ✅

### 为什么需要这个实验？

**当前问题**:
1. ❓ 6种过滤器效果未验证
2. ❓ 最优组合未知
3. ❓ 止损参数未优化
4. ❓ 协同效应未探索

**参考实验**:
- **SMA**: Loss Protection最优（夏普+75%，回撤-34%）
- **MACD**: Combined最优（夏普0.94）

**KAMA独特性**:
- 自适应特性可能减少对过滤器的依赖
- 需要独立实验验证，不能直接套用SMA/MACD结论

---

## 📝 评估指标

### 主要指标

| 指标 | 权重 | 目标 | 说明 |
|------|------|------|------|
| **夏普比率** | 40% | 最大化 | 风险调整后收益，主要优化目标 |
| **最大回撤** | 30% | 最小化 | 风险控制能力 |
| **平均收益率** | 20% | 保持或提升 | 绝对收益表现 |
| **胜率** | 10% | 提升 | 策略可靠性 |

### 次要指标

- 收益标准差（稳定性）
- 夏普比率标准差（鲁棒性）
- 最差标的收益（下行风险）
- 平均交易次数（活跃度）

---

## ⚙️ 开发状态

### 已完成

- ✅ **实验设计**: 完整的3维度7阶段方案
- ✅ **文档撰写**: 设计文档、快速指南、任务清单
- ✅ **目录结构**: 实验目录和文档索引

### 待开发（按优先级）

1. 🔲 **核心脚本**: `grid_search.py`（优先级：高）
   - 预计工作量：4-6小时
   - 参考：`experiment/etf/macd_cross/grid_search_stop_loss/grid_search.py`

2. 🔲 **可视化**: `generate_visualizations.py`（优先级：中）
   - 预计工作量：3-4小时
   - 包含5种图表类型

3. 🔲 **报告生成**: `generate_report.py`（优先级：中）
   - 预计工作量：2-3小时
   - 自动生成Markdown报告

4. 🔲 **需求文档**: `REQUIREMENTS.md`（优先级：低）
   - 预计工作量：1-2小时
   - 详细技术规范

### 预计总开发时间

- **快速原型**: 3天（核心功能 + 初步结果）
- **完整开发**: 3周（含测试和文档）

---

## 🔗 相关资源

### 代码参考

- **KAMA策略**: `strategies/kama_cross.py`
- **MACD网格搜索**: `experiment/etf/macd_cross/grid_search_stop_loss/`
- **SMA止损对比**: `experiment/etf/sma_cross/stop_loss_comparison/`
- **回测框架**: `backtest_runner.py`

### 文档参考

- **KAMA策略文档**: `requirement_docs/20251111_kama_adaptive_strategy_implementation.md`
- **止损实验参考**: `requirement_docs/20251109_native_stop_loss_implementation.md`
- **系统架构**: `requirement_docs/20251109_backtest_runner_refactoring_report.md`

### 数据资源

- **标的池**: `results/trend_etf_pool.csv`（20只趋势型ETF）
- **数据目录**: `data/chinese_etf/daily/`（2023-11至2025-11）

---

## 📅 下一步行动

### 立即可执行

1. **开始开发`grid_search.py`** ⭐ 最高优先级
   - 参考MACD实验的脚本结构
   - 先实现Phase 1A-1B验证可行性
   - 确保结果解析正确

2. **验证策略接口**
   - 确认KAMA策略支持所有过滤器参数
   - 测试命令行调用
   - 验证结果文件格式

### 短期目标（1周内）

1. 完成`grid_search.py`核心功能
2. 运行Phase 1实验（200次，约1小时）
3. 验证结果准确性

### 中期目标（2-3周内）

1. 完成完整实验（680次，约3-4小时）
2. 开发可视化和报告脚本
3. 生成完整实验报告

---

**最后更新**: 2025-11-11
**文档状态**: ✅ 实验设计完成
**开发状态**: 🔲 待开始实现
**实验状态**: 📋 设计阶段
