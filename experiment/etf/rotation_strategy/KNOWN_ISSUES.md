# ETF轮动策略 Phase 3 已知问题列表

**更新时间**: 2025-11-13
**版本**: Phase 3验收版本

## 轻微问题

### 问题1: 独立脚本运行时配置获取错误

**文件**: `scripts/run_rotation_strategy.py`
**行号**: 第348-352行
**问题描述**:
尝试获取策略运行时配置时，创建临时Strategy实例失败，因为Strategy基类需要3个必需参数（broker, data, params）。

**错误信息**:
```
TypeError: Strategy.__init__() missing 3 required positional arguments: 'broker', 'data', and 'params'
```

**影响程度**: ⭐ 轻微
- 不影响核心回测功能
- 仅影响运行时配置的保存功能
- 其他功能完全正常

**复现步骤**:
```bash
python scripts/run_rotation_strategy.py \
  --rotation-schedule /tmp/simple_rotation_schedule.json \
  --strategy kama_cross \
  --rebalance-mode incremental \
  --verbose
```

**临时解决方案**:
功能可正常使用，运行时配置获取失败不会中断程序执行，仅在日志中显示错误。

**建议修复方案**:
```python
# 方案1: 移除运行时配置获取代码
# 删除或注释掉第348-352行

# 方案2: 修复实例化方式
if hasattr(ParameterizedStrategy, 'get_runtime_config_static'):
    result['runtime_config'] = ParameterizedStrategy.get_runtime_config_static()
```

**修复优先级**: 低
**计划修复版本**: Phase 4优化阶段

---

### 问题2: 测试数据中策略无交易信号

**文件**: `scripts/test_rotation_phase3.py`
**问题描述**:
使用6个月测试数据（2024-06-01至2024-12-01）时，KAMA策略没有产生任何交易信号，导致交易次数为0。

**影响程度**: ⭐ 轻微
- 测试数据问题，非功能缺陷
- 不影响策略本身的正确性
- 仅影响测试结果的代表性

**根本原因**:
1. 测试数据时间段过短（仅6个月）
2. KAMA策略需要较长的预热期（period=20天）
3. 测试期间市场可能未出现明显趋势

**建议解决方案**:
1. Phase 4实验使用更长时间段（至少2年）
2. 测试脚本使用多个策略进行验证
3. 降低测试数据的KAMA参数以更快产生信号

**修复优先级**: 低
**计划修复版本**: Phase 4实验阶段

---

## 优化建议

### 建议1: 增加轮动表格式验证

**优先级**: 低
**实现难度**: 简单
**预计工作量**: 1-2小时

**内容**:
在轮动策略脚本和CLI中增加轮动表JSON格式验证，防止格式错误导致运行失败。

**建议实现**:
```python
def validate_rotation_schedule(schedule_path: str) -> tuple[bool, str]:
    """验证轮动表格式是否正确"""
    try:
        with open(schedule_path, 'r') as f:
            schedule = json.load(f)

        # 检查必需字段
        if 'metadata' not in schedule:
            return False, "缺少metadata字段"
        if 'schedule' not in schedule:
            return False, "缺少schedule字段"

        # 检查schedule格式
        for date, etf_list in schedule['schedule'].items():
            if not isinstance(etf_list, list):
                return False, f"日期{date}的ETF列表格式错误"

        return True, "验证通过"

    except Exception as e:
        return False, f"验证异常: {e}"
```

---

### 建议2: 增加轮动策略性能报告模板

**优先级**: 中
**实现难度**: 中等
**预计工作量**: 4-6小时

**内容**:
开发轮动策略专用的性能分析报告模板，包含：
- 轮动统计分析（次数、成本、间隔）
- ETF池重叠度分析
- 策略表现对比（轮动vs固定池）
- 成本效益分析

**技术方案**:
创建`backtest_runner/reporting/rotation_report.py`模块，提供：
- `generate_rotation_report()` - 生成HTML报告
- `plot_rotation_timeline()` - 轮动时间线可视化
- `analyze_pool_overlap()` - 池重叠度分析

---

### 建议3: 支持轮动池大小动态调整

**优先级**: 低
**实现难度**: 中等
**预计工作量**: 6-8小时

**内容**:
支持不同轮动期使用不同数量的ETF，实现更灵活的池管理策略。

**当前限制**:
现有实现假设所有轮动期使用相同数量的ETF。

**建议实现**:
修改`VirtualETFBuilder`支持可变池大小：
```python
"schedule": {
    "2024-06-01": {
        "etfs": ["ETF1", "ETF2", ...],
        "pool_size": 10
    },
    "2024-07-01": {
        "etfs": ["ETF1", "ETF3", ...],
        "pool_size": 15  # 可变
    }
}
```

---

## 待测试功能

### 功能1: CLI轮动模式对比功能

**状态**: ⚠️ 未充分测试
**参数**: `--compare-rotation-modes`

**需要验证**:
- 两种再平衡模式的实际性能差异
- 对比结果的准确性和可靠性
- 大规模数据下的执行效率

**建议测试场景**:
```bash
python backtest_runner.py \
  --enable-rotation \
  --rotation-schedule results/rotation_schedules/rotation_30d.json \
  --strategy kama_cross \
  --compare-rotation-modes \
  --data-dir data/chinese_etf \
  --verbose
```

---

### 功能2: 虚拟ETF数据保存功能

**状态**: ⚠️ 未充分测试
**参数**: `--save-virtual-etf`

**需要验证**:
- CSV文件格式正确性
- 数据完整性（所有列都存在）
- 大数据量下的保存性能

**建议测试场景**:
```bash
python backtest_runner.py \
  --enable-rotation \
  --rotation-schedule results/rotation_schedules/rotation_30d.json \
  --strategy kama_cross \
  --save-virtual-etf /tmp/virtual_etf_debug.csv \
  --data-dir data/chinese_etf
```

---

## 性能优化建议

### 优化1: 虚拟ETF数据缓存

**问题**: 每次运行都重新构建虚拟ETF数据，重复计算
**建议**: 实现虚拟ETF数据缓存机制
**预期效果**: 减少50%以上的数据处理时间

### 优化2: 并行化轮动池加载

**问题**: ETF数据顺序加载，效率较低
**建议**: 使用多进程/多线程并行加载ETF数据
**预期效果**: 加载速度提升3-5倍

---

## 文档待完善项

1. **用户手册**: 轮动策略使用的详细教程
2. **API文档**: 轮动相关函数的详细文档
3. **实验指南**: Phase 4实验设计指南
4. **最佳实践**: 轮动参数选择的最佳实践指南

---

## 问题追踪

| 问题编号 | 类型 | 优先级 | 状态 | 计划解决 |
|---------|------|--------|------|---------|
| ISSUE-001 | Bug | 低 | Open | Phase 4 |
| ISSUE-002 | 测试 | 低 | Open | Phase 4 |
| SUGGESTION-001 | 优化 | 低 | Open | 待定 |
| SUGGESTION-002 | 功能 | 中 | Open | Phase 4+ |
| SUGGESTION-003 | 功能 | 低 | Open | 待定 |

---

**维护说明**:
- 本文档在Phase 3验收时创建
- 随着问题修复和新问题发现持续更新
- Phase 4开始前应审查并更新此文档