# MACD策略止损超参网格搜索实验

**实验日期**: 2025-11-09
**实验目标**: 通过网格搜索优化MACD策略的止损保护参数，提升风险调整后收益（夏普比率）

## 📋 目录

- [实验背景](#实验背景)
- [快速开始](#快速开始)
- [实验方案](#实验方案)
- [文件说明](#文件说明)
- [使用指南](#使用指南)
- [结果分析](#结果分析)

## 🎯 实验背景

MACD策略（`strategies/macd_cross.py`）已实现三种止损方式：
1. **连续止损保护（Loss Protection）**: 连续N次亏损后暂停交易
2. **跟踪止损（Trailing Stop）**: 价格回撤达到阈值时止损
3. **组合止损（Combined）**: 同时启用上述两种止损

根据SMA策略的止损实验结果，连续止损保护表现优异：
- 夏普比率提升 **+75%** (0.61 → 1.07)
- 最大回撤降低 **-34%** (-21% → -14%)
- 胜率提升 **+27%** (48% → 61%)

但该实验仅测试了**固定参数**。本实验通过系统性网格搜索，为MACD策略找到最优止损参数组合。

## 🚀 快速开始

### 前置条件

1. 激活 `backtesting` conda 环境：
```bash
conda activate backtesting
```

2. 确保数据文件存在：
   - 标的池: `results/trend_etf_pool.csv`
   - 数据目录: `data/chinese_etf/daily/`

### 快速运行（推荐从这里开始）

**方式1: 运行Phase 1（Baseline + Loss Protection，约2-3小时）**

```bash
cd /mnt/d/git/backtesting

# 运行Baseline实验
python experiment/etf/macd_cross/grid_search_stop_loss/grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases baseline

# 运行Loss Protection网格搜索
python experiment/etf/macd_cross/grid_search_stop_loss/grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases loss
```

**方式2: 运行完整实验（所有阶段，约6-8小时）**

```bash
cd /mnt/d/git/backtesting

python experiment/etf/macd_cross/grid_search_stop_loss/grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all
```

### 生成可视化和报告

```bash
cd /mnt/d/git/backtesting

# 生成可视化图表
python experiment/etf/macd_cross/grid_search_stop_loss/generate_visualizations.py

# 生成Markdown报告
python experiment/etf/macd_cross/grid_search_stop_loss/generate_report.py
```

## 📊 实验方案

### Phase 1: Baseline（无止损对照组）

- **参数**: 无
- **测试次数**: 20只标的 × 1配置 = 20次
- **预计耗时**: ~5-10分钟

### Phase 2: Loss Protection（连续止损保护）⭐ 优先级最高

- **参数网格**:
  - `max_consecutive_losses`: [2, 3, 4, 5]
  - `pause_bars`: [5, 10, 15, 20]
- **参数组合**: 4 × 4 = 16种
- **测试次数**: 20只标的 × 16组合 = 320次
- **预计耗时**: ~2-3小时

### Phase 3: Trailing Stop（跟踪止损）

- **参数网格**:
  - `trailing_stop_pct`: [0.03, 0.05, 0.07, 0.10]
- **参数组合**: 4种
- **测试次数**: 20只标的 × 4组合 = 80次
- **预计耗时**: ~30-45分钟

### Phase 4: Combined（组合止损）

- **参数网格**:
  - `max_consecutive_losses`: [2, 3, 4]
  - `pause_bars`: [5, 10, 15]
  - `trailing_stop_pct`: [0.03, 0.05, 0.07]
- **参数组合**: 3 × 3 × 3 = 27种
- **测试次数**: 20只标的 × 27组合 = 540次
- **预计耗时**: ~3-4小时

**总计**: 48种参数组合，960次回测，预计总耗时 **6-8小时**

## 📁 文件说明

### 核心脚本

| 文件 | 说明 |
|------|------|
| `grid_search.py` | 主实验脚本，执行网格搜索回测 |
| `generate_visualizations.py` | 生成可视化图表（热力图、对比图） |
| `generate_report.py` | 生成Markdown格式的详细报告 |
| `REQUIREMENTS.md` | 实验需求文档 |
| `README.md` | 本文档 |

### 输出文件

| 文件 | 说明 |
|------|------|
| `results_baseline.csv` | Baseline实验结果 |
| `results_loss_protection.csv` | Loss Protection网格搜索结果 |
| `results_trailing_stop.csv` | Trailing Stop网格搜索结果 |
| `results_combined.csv` | Combined网格搜索结果 |
| `all_results.csv` | 合并所有实验结果 |
| `summary_statistics.csv` | 汇总统计 |
| `RESULTS.md` | 详细实验报告 |
| `*.png` | 可视化图表 |

## 📖 使用指南

### 命令行参数

```bash
python grid_search.py [options]
```

**必需参数**:
- `--stock-list <path>`: 股票列表CSV文件（需包含 `ts_code` 列）
- `--data-dir <path>`: 数据目录路径

**可选参数**:
- `--output-dir <path>`: 输出目录（默认: `experiment/etf/macd_cross/grid_search_stop_loss`）
- `--phases <choice>`: 运行的实验阶段
  - `all`: 所有阶段（默认）
  - `baseline`: 仅Baseline
  - `loss`: 仅Loss Protection
  - `trailing`: 仅Trailing Stop
  - `combined`: 仅Combined

### 分阶段运行示例

```bash
# 1. 先运行Baseline（快速验证）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases baseline

# 2. 运行Loss Protection（重点实验）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases loss

# 3. 运行Trailing Stop
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases trailing

# 4. 运行Combined
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases combined

# 5. 生成汇总报告（需要所有阶段完成）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases all
```

### 查看结果

```bash
# 查看CSV结果
cat experiment/etf/macd_cross/grid_search_stop_loss/summary_statistics.csv

# 查看详细报告
less experiment/etf/macd_cross/grid_search_stop_loss/RESULTS.md

# 查看可视化图表（需要图像查看器）
open experiment/etf/macd_cross/grid_search_stop_loss/*.png
```

## 📈 结果分析

### 关键指标

实验关注以下核心指标：

1. **夏普比率（Sharpe Ratio）**: 主要优化目标，衡量风险调整后收益
2. **平均收益率（Avg Return）**: 年化收益率
3. **最大回撤（Max Drawdown）**: 回撤控制能力
4. **胜率（Win Rate）**: 盈利交易占比

### 预期成果

1. **最优参数配置**
   - 连续止损保护的最佳 `(max_consecutive_losses, pause_bars)` 组合
   - 跟踪止损的最佳 `trailing_stop_pct` 值
   - 组合止损的最佳三参数配置

2. **性能提升报告**
   - 相比Baseline，夏普比率提升百分比
   - 最大回撤降低幅度
   - 胜率改善情况

3. **参数敏感性洞察**
   - 哪些参数对结果影响最大？
   - 哪些参数区间相对稳定？
   - 是否存在过拟合风险？

### 可视化图表

实验会生成以下图表：

1. **Loss Protection热力图**: 展示 `max_consecutive_losses` vs `pause_bars` 对夏普比率的影响
2. **Trailing Stop对比图**: 展示不同 `trailing_stop_pct` 的表现
3. **策略对比图**: 对比Baseline、Loss Protection、Trailing Stop、Combined的整体表现
4. **Combined热力图**: 按 `trailing_stop_pct` 分组的热力图
5. **参数敏感性分析**: 箱线图展示参数变化对结果的影响

## ⚠️ 注意事项

### 计算资源

- 总实验次数：48次 × 20标的 = 960次回测
- 每次回测启用 `--optimize`，需要遍历MACD参数空间
- 预计总耗时：6-8小时
- **建议**: 分阶段执行，先完成Phase 1验证可行性

### 过拟合风险

- 网格搜索可能导致参数过拟合历史数据
- **缓解措施**:
  - 关注参数稳定性（敏感性分析）
  - 优先选择参数不敏感区域的配置
  - 未来在不同市场环境中验证

### 数据质量

- 确保 `results/trend_etf_pool.csv` 中的标的数据完整
- 数据时间范围：2023-11至2025-11
- 检查是否有停牌或异常数据

## 🔄 后续扩展

实验完成后的可选扩展方向：

1. **多市场验证**
   - 在美股ETF池上重复实验
   - 验证参数的跨市场通用性

2. **组合过滤器**
   - 同时启用ADX、成交量等过滤器
   - 测试止损 + 过滤器的组合效果

3. **滚动窗口回测**
   - Walk-forward分析
   - 评估参数的时间稳定性

4. **实盘验证**
   - 使用最优参数进行模拟盘测试
   - 收集实际交易的表现数据

## 📚 参考资料

- **MACD策略文档**: `requirement_docs/20251109_macd_strategy_implementation.md`
- **止损实验参考**: `requirement_docs/20251109_native_stop_loss_implementation.md`
- **SMA止损实验代码**: `experiment/etf/sma_cross/stop_loss_comparison/compare_stop_loss.py`
- **策略实现代码**: `strategies/macd_cross.py`

## 📝 许可证

本实验代码为Backtesting.py项目的一部分，遵循项目许可证。

---

**最后更新**: 2025-11-09
**作者**: Claude Code
