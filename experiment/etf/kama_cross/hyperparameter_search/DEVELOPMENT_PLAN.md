# KAMA策略超参数搜索实验 - 开发任务清单

**文档日期**: 2025-11-11
**实验目标**: 优化KAMA策略的信号过滤器和止损参数
**当前状态**: ✅ Phase 1完成，待开发Phase 2/3

---

## ✅ 已完成

1. ✅ **实验设计文档** (`EXPERIMENT_DESIGN.md`)
   - 完整的实验方案设计（3个维度，7个阶段）
   - 680次回测的详细规划
   - 预期耗时：3-4小时

2. ✅ **快速上手指南** (`README.md`)
   - 用户友好的快速启动指南
   - 命令行使用示例
   - 预期成果说明

3. ✅ **Phase 1实验完成** (`grid_search_phase1.py`) - 2025-11-11
   - ✅ run_phase_1a_baseline() - Baseline对照组（20次）
   - ✅ run_phase_1b_single_filters() - 单一过滤器（80次）
   - ✅ run_phase_1c_dual_filters() - 双过滤器组合（80次）
   - ✅ run_phase_1d_full_stack() - 全组合过滤器（20次）
   - ✅ 实验成功率：200/200 (100%)
   - ✅ 实验耗时：45秒（远快于预计1小时）
   - ✅ 生成结果文件：5个CSV + 汇总统计

4. ✅ **Phase 1验收报告**
   - 关键发现：KAMA Baseline夏普比率1.69（优异）
   - 最佳过滤器：ADX（夏普1.68，回撤-4.71%）
   - 问题发现：Confirm过滤器过严导致零交易
   - 详见：`results/PHASE1_ACCEPTANCE_REPORT.md`

---

## 🔲 待开发任务

### 任务1: Phase 1问题修复（优先级：高）

**问题**: Confirm过滤器导致4个配置零交易
- confirm_only
- volume_confirm
- slope_confirm
- full_stack

**解决方案**:
1. 检查KAMA策略中confirm_bars默认值
2. 将confirm_bars从当前值（可能是5）降低到2-3
3. 重新运行Phase 1C和1D实验
4. 预计工作量：30分钟

### 任务2: Phase 2脚本开发（优先级：中）

#### `grid_search_phase2.py` - 止损保护参数搜索

**功能模块**:
```python
✅ 参考Phase 1架构
🔲 run_phase_2a_best_filter_baseline()  # 最佳过滤器无止损对照
🔲 run_phase_2b_loss_protection_grid()  # 止损参数网格搜索（4×4=16组合）
🔲 generate_summary_statistics()        # 汇总统计
```

**网格参数**:
- max_consecutive_losses: [2, 3, 4, 5]
- pause_bars: [5, 10, 15, 20]
- 总测试：20标的 × 17配置 = 340次

**预计工作量**: 2-3小时

---

### 任务2: 可视化脚本（优先级：中）

#### `generate_visualizations.py` - 图表生成

**功能模块**:
```python
🔲 plot_filter_comparison()         # 过滤器对比柱状图
🔲 plot_loss_protection_heatmap()   # 止损参数热力图
🔲 plot_top_configs_radar()         # 顶级配置雷达图
🔲 plot_synergy_analysis()          # 协同效应分析
🔲 plot_parameter_sensitivity()     # 参数敏感性箱线图
```

**预计工作量**: 3-4小时

---

### 任务3: 报告生成脚本（优先级：中）

#### `generate_report.py` - Markdown报告生成

**功能模块**:
```python
🔲 generate_markdown_report()       # 主报告生成函数
🔲 _generate_phase1_section()       # Phase 1结果章节
🔲 _generate_phase2_section()       # Phase 2结果章节
🔲 _generate_phase3_section()       # Phase 3结果章节
🔲 _generate_summary_tables()       # 汇总表格
🔲 _generate_recommendations()      # 推荐配置
```

**预计工作量**: 2-3小时

---

### 任务4: 辅助文件（优先级：低）

#### `REQUIREMENTS.md` - 详细需求文档

**内容**:
```markdown
🔲 1. 背景与动机（详细版）
🔲 2. 实验设计细节
🔲 3. 技术实现规范
🔲 4. 数据格式定义
🔲 5. 错误处理策略
🔲 6. 单元测试要求
```

**预计工作量**: 1-2小时

---

## 📅 开发计划建议

### 方案A: 快速原型（推荐）

**目标**: 最快速度完成核心功能，尽快获得实验结果

**步骤**:
1. **Day 1**: 开发`grid_search.py`核心功能（Phase 1A-1D）
   - 实现Baseline和过滤器实验
   - 验证数据解析正确性
   - 运行Phase 1获得初步结果

2. **Day 2**: 完成止损实验和顶级对比
   - 实现Phase 2B和Phase 3
   - 运行完整实验（3-4小时）
   - 导出CSV结果

3. **Day 3**: 可视化和报告
   - 开发`generate_visualizations.py`
   - 开发`generate_report.py`
   - 生成完整实验报告

**总耗时**: 3天

---

### 方案B: 稳健开发（推荐用于长期项目）

**目标**: 完整开发所有功能，包含测试和文档

**步骤**:
1. **Week 1**: 核心脚本 + 单元测试
   - `grid_search.py`完整实现
   - 单元测试覆盖
   - Phase 1实验验证

2. **Week 2**: 可视化 + 报告 + 文档
   - `generate_visualizations.py`
   - `generate_report.py`
   - `REQUIREMENTS.md`

3. **Week 3**: 完整实验 + 分析
   - 运行完整680次回测
   - 深度结果分析
   - 撰写实验报告

**总耗时**: 3周

---

## 🚦 实施建议

### 立即可开始的工作

1. **开发`grid_search.py`** ⭐ 最高优先级
   - 参考`experiment/etf/macd_cross/grid_search_stop_loss/grid_search.py`
   - 适配KAMA策略的参数结构
   - 先实现Phase 1A-1B验证可行性

2. **验证backtest_runner接口**
   - 确认KAMA策略支持所有过滤器和止损参数
   - 测试命令行调用是否正确
   - 确认结果文件解析方式

### 技术难点预警

1. **结果解析**:
   - 需要从`backtest_runner`的输出中提取统计指标
   - 建议使用CSV汇总文件而非标准输出
   - 确保多次运行结果不冲突

2. **参数传递**:
   - 过滤器参数通过命令行传递给`run_backtest.sh`
   - 需要正确映射参数名称（如`--enable-adx-filter`）
   - 止损参数需要匹配策略类定义

3. **异常处理**:
   - 某些标的可能数据缺失导致回测失败
   - 需要捕获异常并记录日志
   - 失败的回测应跳过但不中断整体流程

---

## 📝 参考实现

### MACD网格搜索脚本结构

可以参考已有的MACD实验脚本：
```
experiment/etf/macd_cross/grid_search_stop_loss/
├── grid_search.py              # 参考其结构
├── generate_visualizations.py  # 参考可视化代码
├── generate_report.py          # 参考报告生成逻辑
```

**核心代码片段**（可直接复用）:
- 命令行参数解析
- subprocess调用backtest_runner
- CSV结果文件读写
- Matplotlib/Seaborn绘图模板

---

## ✅ 验收标准

### 核心功能验收

1. ✅ **实验完整性**:
   - 所有680次回测成功执行
   - 无数据缺失或异常
   - 运行时间在预期范围内（3-4小时）

2. ✅ **结果准确性**:
   - CSV文件包含所有必需字段
   - 统计指标计算正确（夏普、回撤、胜率等）
   - 汇总统计与原始数据一致

3. ✅ **可视化质量**:
   - 所有图表清晰可读
   - 热力图正确展示参数关系
   - 对比图突出关键差异

4. ✅ **报告完整性**:
   - `RESULTS.md`包含所有章节
   - 关键发现和推荐明确
   - 附录数据表完整

---

## 🔗 相关资源

### 代码参考

- **KAMA策略实现**: `strategies/kama_cross.py`
- **MACD网格搜索**: `experiment/etf/macd_cross/grid_search_stop_loss/`
- **SMA止损对比**: `experiment/etf/sma_cross/stop_loss_comparison/`

### 文档参考

- **KAMA策略文档**: `requirement_docs/20251111_kama_adaptive_strategy_implementation.md`
- **止损实验参考**: `requirement_docs/20251109_native_stop_loss_implementation.md`
- **本实验设计**: `EXPERIMENT_DESIGN.md`

---

**最后更新**: 2025-11-11
**下一步行动**: 开始开发`grid_search.py`核心脚本
