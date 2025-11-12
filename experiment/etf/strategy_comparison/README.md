# 三策略对比实验

**实验目标**: 对比SMA、MACD、KAMA三种均线策略在中国ETF池上的表现，评估最佳超参和止损方案的综合效果

## 快速开始

### 1. 环境准备

```bash
# 确保在backtesting环境中
conda activate backtesting

# 验证股票池文件存在
ls -lh results/trend_etf_pool.csv

# 验证ETF数据完整
ls data/chinese_etf/daily/*.csv | wc -l
```

### 2. 试运行（单标的验证）

```bash
python compare_strategies.py \
    --stock-list results/trend_etf_pool.csv \
    --data-dir data/chinese_etf/daily \
    --output-dir results \
    --test-mode \
    --test-stocks 510300.SH
```

### 3. 全量执行

```bash
python compare_strategies.py \
    --stock-list results/trend_etf_pool.csv \
    --data-dir data/chinese_etf/daily \
    --output-dir results \
    --log-file logs/experiment_$(date +%Y%m%d_%H%M%S).log
```

### 4. 查看结果

```bash
# 汇总对比表
cat results/comparison_summary.csv

# 详细报告
cat results/RESULTS.md

# 可视化图表
ls results/visualizations/*.png
```

## 目录结构

```
experiment/etf/strategy_comparison/
├── README.md                     # 本文件
├── EXPERIMENT_DESIGN.md          # 实验设计文档（详细）
├── DEVELOPMENT_PLAN.md           # 开发计划和任务分解
├── compare_strategies.py         # 主实验脚本（待开发）
├── configs/                      # 策略配置文件（6个JSON，待创建）
├── results/
│   ├── raw/                      # 原始回测结果
│   ├── comparison_summary.csv    # 汇总对比表（实验后生成）
│   ├── RESULTS.md               # 实验结果报告（实验后生成）
│   └── visualizations/          # 可视化图表（实验后生成）
└── logs/                         # 实验日志
```

## 测试矩阵

| 策略 | 配置 | 基础参数 | 止损方案 | 说明 |
|------|------|---------|---------|------|
| **SMA** | Baseline | n1=10, n2=20 | 无 | 基线表现 |
| **SMA** | BestStopLoss | n1=10, n2=20 | Loss Protection (max_losses=3, pause=10) | 最佳止损 |
| **MACD** | Baseline | 需优化 | 无 | 基线表现 |
| **MACD** | BestStopLoss | 继承优化结果 | Combined (max_losses=2, pause=5, trail=3%) | 最佳止损 |
| **KAMA** | Baseline | period=20, fast=2, slow=30 | 无 | 基线表现 |
| **KAMA** | BestStopLoss | period=20, fast=2, slow=30 | Loss Protection (max_losses=3, pause=10) | 最佳止损 |

**总测试次数**: 6场景 × 20只ETF = 120次回测

## 评估指标

### 主要指标（稳健性）
- **平均夏普比率**: 所有标的夏普比率算术平均（越高越好，>1为优秀）
- **夏普比率中位数**: 抗离群值，评估典型表现
- **夏普比率标准差**: 不同标的间波动（越小越稳定）

### 次要指标（盈利能力）
- **平均收益率**: 所有标的收益率算术平均
- **收益率中位数**: 抗离群值
- **总收益率**: 所有标的收益率之和（评估绝对盈利能力）

### 辅助指标（风险控制）
- **平均最大回撤**: 越小越好
- **平均胜率**: >50%为优
- **平均交易次数**: 评估交易频率

## 实验假设

**H1**: 止损保护对所有策略都有正向增益
**预期**: BestStopLoss配置的夏普比率 > Baseline

**H2**: KAMA策略因自适应特性，稳健性最优
**预期**: KAMA的夏普比率标准差最小

**H3**: MACD策略经优化后盈利能力最强
**预期**: MACD的平均收益率最高

## 开发状态

- [x] 实验设计文档（EXPERIMENT_DESIGN.md）
- [x] 开发计划（DEVELOPMENT_PLAN.md）
- [x] 目录结构创建
- [ ] 策略配置文件（configs/*.json）
- [ ] 主实验脚本（compare_strategies.py）
- [ ] 单标的试运行验证
- [ ] 全量回测执行
- [ ] 结果分析和报告生成
- [ ] 可视化图表生成

**当前状态**: 📋 规划完成，待开发

## 参考文档

- **ETF筛选系统**: `requirement_docs/20251106_china_etf_filter_for_trend_following.md`
- **SMA止损实验**: `experiment/etf/sma_cross/stop_loss_comparison/RESULTS.md`
- **MACD止损实验**: `experiment/etf/macd_cross/grid_search_stop_loss/RESULTS.md`
- **KAMA策略实现**: `strategies/kama_cross.py`
- **止损实现文档**: `requirement_docs/20251109_native_stop_loss_implementation.md`

## 预估时间

**总开发时间**: 4-6小时
- 配置文件准备: 30分钟
- 主脚本开发: 2小时
- 实验执行: 1-2小时
- 结果分析和报告: 1小时
- 可视化和文档完善: 30分钟

## 联系方式

**实验负责人**: Claude
**创建日期**: 2025-11-11
**版本**: v1.0
