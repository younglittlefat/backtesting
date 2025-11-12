# KAMA策略超参数搜索实验

**实验日期**: 2025-11-11
**实验目标**: 系统性优化KAMA自适应均线策略的信号过滤器和止损保护参数
**预期收益**: 风险调整后收益提升30-80%（参考SMA/MACD实验）

---

## 🎯 快速开始

### 前置条件

```bash
# 1. 激活conda环境
conda activate backtesting

# 2. 确保数据文件存在
ls results/trend_etf_pool.csv  # 20只趋势型ETF
ls data/chinese_etf/daily/     # 日线数据目录
```

### 快速运行（推荐）

```bash
cd /mnt/d/git/backtesting

# ⭐ Phase 1: 过滤器实验（200次，约45秒-1分钟）✅ 已完成
python experiment/etf/kama_cross/hyperparameter_search/grid_search_phase1.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all

# ⭐ Phase 2: 止损参数优化（1020次，约2-3小时）🔲 新增
python experiment/etf/kama_cross/hyperparameter_search/grid_search_phase2.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all
```

### 分阶段运行（推荐用于大规模实验）

```bash
# Phase 1: 过滤器实验（200次，约45秒）✅ 已完成
# - Phase 1A: Baseline
# - Phase 1B: 单一过滤器
# - Phase 1C: 双过滤器组合
# - Phase 1D: 全组合
python experiment/etf/kama_cross/hyperparameter_search/grid_search_phase1.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all

# Phase 2A: 最佳过滤器Baseline（60次，约10-15分钟）
python experiment/etf/kama_cross/hyperparameter_search/grid_search_phase2.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases 2a

# Phase 2B: 止损参数网格搜索（960次，约2-3小时）
python experiment/etf/kama_cross/hyperparameter_search/grid_search_phase2.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases 2b
```

### 生成报告和可视化

```bash
# 生成可视化图表
python experiment/etf/kama_cross/hyperparameter_search/generate_visualizations.py

# 生成Markdown报告
python experiment/etf/kama_cross/hyperparameter_search/generate_report.py

# 查看报告
less experiment/etf/kama_cross/hyperparameter_search/results/RESULTS.md
```

---

## 📋 实验概览

### 实验矩阵

| 阶段 | 测试内容 | 回测次数 | 耗时 | 状态 |
|------|----------|----------|------|------|
| **Phase 1A** | Baseline对照组 | 20 | 45秒 | ✅ 已完成 |
| **Phase 1B** | 单一过滤器（ADX, Volume, Slope, Confirm） | 80 | 45秒 | ✅ 已完成 |
| **Phase 1C** | 双过滤器组合（4种精选组合） | 80 | 45秒 | ✅ 已完成 |
| **Phase 1D** | 全组合过滤器 | 20 | 45秒 | ✅ 已完成 |
| **Phase 2A** | 最佳过滤器Baseline（3种过滤器×20标的） | 60 | 10-15分钟 | 🔲 待运行 |
| **Phase 2B** | 止损参数网格搜索（4×4×3×20） | 960 | 2-3小时 | 🔲 待运行 |
| **总计** | - | **1220次** | **~2-3.5小时** | 🚧 进行中 |

**Phase 1核心发现** ⭐:
- **Baseline夏普**: 1.69（优异！远超SMA 0.61和MACD 0.6）
- **最佳过滤器**: ADX（夏普1.68，回撤-4.71%）
- **最佳组合**: ADX+Slope（夏普1.58，回撤-4.38%最优）
- **Confirm过滤器**: ❌ 不适用KAMA策略（与自适应特性冲突）

### 测试参数

**信号过滤器**（Phase 1）:
- **ADX趋势强度过滤器**: 过滤弱趋势环境
- **成交量确认过滤器**: 成交量放大确认
- **价格斜率过滤器**: 过滤震荡信号
- **持续确认过滤器**: 多K线持续确认

**止损保护参数**（Phase 2）:
- `max_consecutive_losses`: [2, 3, 4, 5]（连续亏损阈值）
- `pause_bars`: [5, 10, 15, 20]（暂停K线数）

**顶级配置对比**（Phase 3）:
- Config 0: 纯KAMA（Baseline）
- Config 1-2: 最佳过滤器配置
- Config 3: 仅止损保护
- Config 4-5: 过滤器 + 止损（⭐预期最优）
- Config 6: 全组合 + 止损

---

## 📊 预期成果

### 输出文件

**数据文件** (CSV):
```
results/
├── phase1a_baseline.csv
├── phase1b_single_filters.csv
├── phase1c_dual_filters.csv
├── phase1d_full_stack.csv
├── phase2b_loss_protection_grid.csv
├── phase3_top_configs.csv
└── summary_statistics.csv
```

**可视化图表** (PNG):
```
plots/
├── filter_comparison.png              # 过滤器对比柱状图
├── heatmap_loss_protection_sharpe.png # 止损参数热力图（夏普）
├── heatmap_loss_protection_drawdown.png # 止损参数热力图（回撤）
├── top_configs_comparison.png         # 顶级配置对比
├── synergy_analysis.png                # 协同效应分析
└── parameter_sensitivity.png           # 参数敏感性分析
```

**详细报告**:
- `results/RESULTS.md`: 完整实验报告（包含所有阶段结果和核心发现）

### 关键指标

| 指标 | 权重 | 目标 |
|------|------|------|
| **夏普比率** | 40% | 最大化（主要优化目标） |
| **最大回撤** | 30% | 最小化 |
| **平均收益率** | 20% | 保持或提升 |
| **胜率** | 10% | 提升 |

### 预期洞察

1. **最优过滤器**: 哪个过滤器或组合增益最大？
2. **最佳止损参数**: KAMA策略的最优连续止损保护配置
3. **协同效应**: 过滤器 + 止损是否存在正向协同（1+1>2）？
4. **参数敏感性**: 哪些参数区间稳定可靠？

---

## 📖 实验背景

### KAMA策略特性

**核心优势**:
- ✅ **自适应性**: 根据市场效率自动调整响应速度
- ✅ **趋势期**: 快速跟随价格变化
- ✅ **震荡期**: 平滑滤波，减少假信号

**已实现功能**:
- Phase 1: KAMA指标计算 + 效率比率过滤 + 斜率确认 ✅
- Phase 2: ADX/成交量/价格斜率/持续确认过滤器 ✅
- Phase 3: 连续止损保护 ✅

### 实验必要性

**当前问题**:
1. ❓ 6种过滤器各自对KAMA策略的增益未验证
2. ❓ 最优过滤器组合未知
3. ❓ 止损参数是否适配KAMA策略？
4. ❓ 过滤器 + 止损的协同效应如何？

**参考实验**:
- **SMA策略**: Loss Protection最优（夏普+75%，回撤-34%）
- **MACD策略**: Combined最优（夏普0.94，max_loss=2, pause=5）

---

## 🔧 命令行参数

### 必需参数

- `--stock-list <path>`: 股票列表CSV文件（需包含`ts_code`列）
- `--data-dir <path>`: 数据目录路径

### 可选参数

- `--output-dir <path>`: 输出目录（默认: `experiment/etf/kama_cross/hyperparameter_search/results`）
- `--phases <choice>`: 运行的实验阶段
  - `all`: 所有阶段（默认）
  - `phase1`: Phase 1（过滤器实验）
  - `phase2`: Phase 2（止损优化）
  - `phase3`: Phase 3（顶级配置对比）

### 使用示例

```bash
# 仅运行过滤器实验
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases phase1 \
  --output-dir ./my_results

# 完整实验（所有阶段）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all
```

---

## ⚠️ 注意事项

### 计算资源

- **总实验次数**: 680次回测
- **预计耗时**: 3-4小时
- **建议**: 分阶段执行，先完成Phase 1验证可行性

### 过拟合风险

**缓解措施**:
1. 关注参数稳定性（敏感性分析）
2. 优先选择参数不敏感区域的配置
3. 未来在不同市场环境中验证

### 数据质量

- 确保`results/trend_etf_pool.csv`中的标的数据完整
- 数据时间范围：2023-11至2025-11
- 检查是否有停牌或异常数据

---

## 📁 文件说明

| 文件 | 说明 | 状态 |
|------|------|------|
| **EXPERIMENT_DESIGN.md** | 详细实验设计文档 | ✅ 完成 |
| **README.md** | 快速上手指南（本文档） | ✅ 完成 |
| **DEVELOPMENT_PLAN.md** | 开发计划和任务清单 | ✅ 完成 |
| **grid_search_phase1.py** | Phase 1实验脚本（过滤器测试） | ✅ 完成 |
| **grid_search_phase2.py** | Phase 2实验脚本（止损参数优化） | ✅ 完成 |
| **results/PHASE1_ACCEPTANCE_REPORT.md** | Phase 1验收报告 | ✅ 完成 |
| **generate_visualizations.py** | 可视化生成脚本 | 🔲 待开发 |
| **generate_report.py** | 报告生成脚本 | 🔲 待开发 |

---

## 🚀 后续扩展

实验完成后的可选扩展方向：

1. **跟踪止损实验**: 测试`trailing_stop_pct`参数
2. **多市场验证**: 在美股ETF池上重复实验
3. **滚动窗口回测**: Walk-forward分析
4. **实盘模拟**: 使用最优配置进行模拟盘测试

---

## 📚 参考资料

- **KAMA策略文档**: `requirement_docs/20251111_kama_adaptive_strategy_implementation.md`
- **策略实现代码**: `strategies/kama_cross.py`
- **SMA止损实验**: `experiment/etf/sma_cross/stop_loss_comparison/`
- **MACD参数优化**: `experiment/etf/macd_cross/grid_search_stop_loss/`

---

**最后更新**: 2025-11-11
**作者**: Claude Code
**实验状态**: 📋 设计完成，待开发实现
