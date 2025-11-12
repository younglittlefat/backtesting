# KAMA策略Phase 2止损参数优化实验 - 上下文文档

**实验日期**: 2025-11-11
**实验阶段**: Phase 2（止损保护参数网格搜索）
**负责人**: Claude Code
**验收人**: Task Agent（待分配）

---

## 📋 实验概览

### 实验目标
优化KAMA自适应均线策略的连续止损保护参数，找到最佳的`max_consecutive_losses`和`pause_bars`组合。

### 实验范围
- **Phase 2A**: 最佳过滤器Baseline（无止损对照组）- 60次回测
- **Phase 2B**: 止损参数网格搜索 - 960次回测
- **总计**: 1020次回测，预计耗时2-3小时

---

## 🎯 Phase 1核心发现（作为Phase 2基础）

Phase 1已完成信号过滤器测试，关键结论：

### 性能表现
| 配置 | 夏普比率 | 收益率 | 最大回撤 | 胜率 |
|------|----------|--------|----------|------|
| **Baseline** | 1.69 | 34.63% | -5.27% | 84.54% |
| **ADX Only** | 1.68 | 29.53% | -4.71% | 85.96% |
| **ADX+Slope** | 1.58 | 23.75% | -4.38% | 88.04% |

### 关键洞察
1. **KAMA Baseline优异**: 夏普1.69远超SMA (0.61)和MACD (0.6)
2. **ADX过滤器最优**: 几乎不降低夏普（-0.6%），回撤改善10.6%
3. **Confirm过滤器不适用**: 与KAMA自适应特性冲突，导致零交易

### Phase 2选择的配置
基于Phase 1结果，Phase 2将测试3种过滤器配置：
1. **baseline**: 无过滤器（夏普1.69）
2. **adx_only**: ADX过滤器（夏普1.68）
3. **adx_slope**: ADX+Slope组合（回撤最优-4.38%）

---

## 🔬 Phase 2实验设计

### Phase 2A: 最佳过滤器Baseline（无止损对照组）

**目的**: 建立对照组，验证Phase 1结果的可复现性

**测试配置**: 3种过滤器 × 20标的 = 60次回测
- `baseline`: 无过滤器
- `adx_only`: ADX过滤器
- `adx_slope`: ADX+Slope组合

**止损配置**: `enable_loss_protection=False`

**预期耗时**: 10-15分钟

### Phase 2B: 止损参数网格搜索

**目的**: 优化连续止损保护参数

**网格参数**:
- `max_consecutive_losses`: [2, 3, 4, 5] - 连续亏损次数阈值
- `pause_bars`: [5, 10, 15, 20] - 暂停交易K线数

**测试矩阵**: 4×4×3×20 = 960次回测
- 16个参数组合
- 3种过滤器配置
- 20只ETF标的

**预期耗时**: 2-3小时

---

## 📊 预期成果与验收标准

### 输出文件

实验完成后将生成以下CSV文件：
```
results/
├── phase2a_baseline.csv        # Phase 2A结果（60行）
├── phase2b_loss_protection_grid.csv  # Phase 2B结果（960行）
└── phase2_summary_statistics.csv     # 汇总统计（按配置分组）
```

### 关键指标

每条记录应包含以下字段：
- `ts_code`: 标的代码
- `config_name`: 配置名称（如`baseline_loss3_pause10`）
- `return_pct`: 收益率
- `sharpe_ratio`: 夏普比率（主要优化目标）
- `max_drawdown_pct`: 最大回撤
- `win_rate_pct`: 胜率
- `num_trades`: 交易次数
- `avg_trade_duration`: 平均持仓时间
- `exposure_time_pct`: 持仓时间占比
- `enable_adx_filter`, `enable_volume_filter`, `enable_slope_filter`: 过滤器开关
- `enable_loss_protection`, `max_consecutive_losses`, `pause_bars`: 止损配置

### 验收检查清单

#### 数据完整性
- [ ] phase2a_baseline.csv包含60条记录（3配置×20标的）
- [ ] phase2b_loss_protection_grid.csv包含960条记录（16参数×3配置×20标的）
- [ ] 所有必需字段存在且无缺失值（NaN除外）
- [ ] 夏普比率范围合理（建议-1到5之间，除非零交易）

#### 性能表现
- [ ] Phase 2A结果与Phase 1 Baseline一致（误差<5%）
- [ ] Phase 2B至少有一个配置的夏普比率 > Phase 2A对应配置
- [ ] 止损保护配置的回撤 < 无止损配置

#### 结果可解释性
- [ ] 汇总统计表按平均夏普比率排序
- [ ] 识别出最优止损参数组合（针对每种过滤器配置）
- [ ] 参数敏感性分析：不同参数组合的性能分布

---

## 🎯 核心问题与预期答案

### 问题1: 止损保护是否有效？
**假设**: 连续止损保护应提升夏普比率并降低回撤（参考SMA +75%，MACD +28.8%）

**验证方法**:
- 对比Phase 2B最优配置 vs Phase 2A对照组
- 计算夏普比率提升百分比
- 计算回撤降低百分比

**预期结论**: 止损保护显著提升风险调整收益

### 问题2: 最优止损参数是什么？
**假设**: 基于MACD实验，预期`max_losses=2-3, pause_bars=5-10`效果较好

**验证方法**:
- 按平均夏普比率对所有参数组合排序
- 识别Top 3配置
- 检查参数是否集中在某个区间

**预期结论**: 提供针对KAMA策略的推荐止损参数

### 问题3: 不同过滤器配置的最优参数是否一致？
**假设**: 最优止损参数可能因过滤器配置而异

**验证方法**:
- 对每种过滤器配置单独找出最优参数
- 对比3种配置的最优参数是否相同

**预期结论**: 判断是否需要针对不同过滤器配置使用不同止损参数

### 问题4: 参数敏感性如何？
**假设**: 参数不敏感区域的配置更稳健（参考SMA实验）

**验证方法**:
- 计算夏普比率的标准差（按参数组合分组）
- 绘制参数热力图（如果实现可视化）

**预期结论**: 识别稳健的参数区间，避免过拟合

---

## 📝 验收任务（给Task Agent）

请按以下步骤进行Phase 2实验的验收和总结：

### 任务1: 数据质量验证
1. 读取`phase2a_baseline.csv`和`phase2b_loss_protection_grid.csv`
2. 检查数据完整性（记录数、字段完整性）
3. 统计成功率（有效回测数 / 预期回测数）
4. 识别异常值（NaN、Inf、超出合理范围的值）

### 任务2: 性能分析
1. 对比Phase 2A vs Phase 1 Baseline（验证可复现性）
2. 找出Phase 2B中每种过滤器配置的最优参数组合（Top 3）
3. 计算止损保护的性能提升（夏普比率、回撤、胜率）
4. 生成按配置分组的汇总统计表

### 任务3: 回答核心问题
1. 止损保护对KAMA策略是否有效？提升幅度如何？
2. 推荐的最优止损参数是什么？（针对每种过滤器配置）
3. 参数敏感性如何？是否存在稳健区间？

### 任务4: 生成验收报告
创建`results/PHASE2_ACCEPTANCE_REPORT.md`，包含：
- 实验状态（成功/失败/部分成功）
- 成功率统计
- 性能指标对比表
- 关键发现和推荐配置
- 问题与建议

---

## 🔗 参考资料

### 文件路径
- **实验脚本**: `experiment/etf/kama_cross/hyperparameter_search/grid_search_phase2.py`
- **Phase 1报告**: `experiment/etf/kama_cross/hyperparameter_search/results/PHASE1_ACCEPTANCE_REPORT.md`
- **策略实现**: `strategies/kama_cross.py`

### 参考实验
- **SMA止损实验**: `experiment/etf/sma_cross/stop_loss_comparison/`
  - Loss Protection: 夏普+75%，回撤-34%
- **MACD止损实验**: `experiment/etf/macd_cross/grid_search_stop_loss/`
  - Combined方案: 夏普0.94（max_loss=2, pause=5, trail=3%）

### 关键设计文档
- **KAMA策略文档**: `requirement_docs/20251111_kama_adaptive_strategy_implementation.md`
- **止损保护文档**: `requirement_docs/20251109_native_stop_loss_implementation.md`

---

## ⚠️ 注意事项

### 实验环境
- **Conda环境**: `backtesting`
- **Python版本**: 3.10
- **关键依赖**: backtesting.py, pandas, numpy

### 已知问题
1. **Confirm过滤器**: 已从Phase 2移除（与KAMA不兼容）
2. **数据缺失**: 部分ETF可能数据不完整，导致回测失败（可接受）
3. **零交易情况**: 某些极端参数组合可能导致零交易（NaN夏普），需要在分析中排除

### 时间预期
- Phase 2A: 10-15分钟
- Phase 2B: 2-3小时
- 验收和分析: 30-60分钟

---

**上下文准备完成时间**: 2025-11-11
**实验启动时间**: 待确定
**预计完成时间**: 启动后2-3.5小时

**下一步**: 启动Phase 2实验 → Task Agent验收 → 生成最终报告
