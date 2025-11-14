# Phase 4 开发进展报告

**报告时间**: 2025-11-13
**开发状态**: ✅ 开发完成，等待用户确认后执行实验
**预计实验耗时**: 7-9小时

---

## 📊 开发任务完成情况

| 任务ID | 任务名称 | 状态 | 输出文件 |
|--------|---------|------|----------|
| **任务1** | 修改prepare_rotation_schedule.py | ✅ 完成 | `scripts/prepare_rotation_schedule.py` |
| **任务2** | 开发固定池生成脚本 | ✅ 完成 | `scripts/generate_fixed_baseline_pool.py` |
| **任务3** | 生成30/60天轮动表 | ⏸️ 待执行 | 待生成 |
| **任务4** | 开发对比实验脚本 | ✅ 完成 | `experiment/etf/rotation_comparison/run_comparison.py` |
| **任务5** | 创建实验设计文档 | ✅ 完成 | `experiment/etf/rotation_comparison/EXPERIMENT_DESIGN.md` |

---

## ✅ 已完成的开发工作

### 1. 修改 `prepare_rotation_schedule.py` ⭐

**目的**: 支持纯评分排序模式（去除二阶段硬性阈值过滤）

**修改内容**:
- 添加`--no-score-threshold`参数（默认True，跳过百分位过滤）
- 添加`--use-score-threshold`参数（反向开关，启用百分位过滤）
- 配置传递到`FilterConfig`，控制筛选行为
- 启用`enable_unbiased_scoring=True`（无偏评分，避免动量偏差）

**关键代码**:
```python
# Line 87-94: 添加命令行参数
parser.add_argument(
    '--no-score-threshold', action='store_true', default=True,
    help='跳过二阶段百分位过滤，改为纯评分排序取top-N (默认: True)'
)
parser.add_argument(
    '--use-score-threshold', dest='no_score_threshold', action='store_false',
    help='启用二阶段百分位过滤（与默认行为相反）'
)

# Line 374-377: 应用配置
config.skip_stage2_percentile_filtering = args.no_score_threshold
config.skip_stage2_range_filtering = args.no_score_threshold
config.enable_unbiased_scoring = True
```

**使用示例**:
```bash
python scripts/prepare_rotation_schedule.py \
  --start-date 2023-11-01 \
  --end-date 2025-11-12 \
  --rotation-period 30 \
  --pool-size 20 \
  --data-dir data/chinese_etf \
  --output results/rotation_schedules/rotation_30d_full.json
# 默认已启用纯排序模式，无需额外参数
```

---

### 2. 开发 `generate_fixed_baseline_pool.py` ⭐

**目的**: 生成对照组固定ETF池（2023-11-01时点）

**核心功能**:
1. 使用2023-10-31之前的历史数据筛选（避免未来数据泄露）
2. 应用与轮动池相同的筛选规则（一阶段+纯排序）
3. 输出包含评分详情的CSV文件

**筛选配置**:
```python
config = FilterConfig()
config.target_portfolio_size = 20
config.min_turnover = 50_000              # 5万元流动性
config.min_listing_days = 60              # 60天上市期
config.skip_stage2_percentile_filtering = True  # 跳过百分位过滤
config.skip_stage2_range_filtering = True
config.enable_unbiased_scoring = True     # 启用无偏评分
```

**输出文件**: `results/rotation_fixed_pool/baseline_pool.csv`

**字段**:
- `ts_code`: ETF代码
- `name`: ETF名称
- `综合评分`: 最终排序依据
- `ADX`: 趋势强度
- `收益回撤比`: 风险调整后收益
- `年化收益`, `最大回撤`, `日均成交额`: 辅助指标

**使用示例**:
```bash
python scripts/generate_fixed_baseline_pool.py
# 使用默认参数即可
```

---

### 3. 开发 `run_comparison.py` 自动化实验脚本 ⭐⭐⭐

**目的**: 完全自动化执行3场景对比实验并生成报告

**功能模块**:

#### 3.1 实验配置管理
```python
EXPERIMENT_CONFIG = {
    'baseline': {
        'type': 'fixed',
        'pool_file': 'results/rotation_fixed_pool/baseline_pool.csv',
        'strategy': 'kama_cross',
        'output_dir': 'experiment/etf/rotation_comparison/results/baseline/'
    },
    'rotation_30d': {
        'type': 'rotation',
        'schedule_file': 'results/rotation_schedules/rotation_30d_full.json',
        'rebalance_mode': 'incremental',
        'trading_cost': 0.003,
        'output_dir': 'experiment/etf/rotation_comparison/results/rotation_30d/'
    },
    'rotation_60d': { ... }
}
```

#### 3.2 回测执行函数
- `run_fixed_pool_backtest()`: 执行固定池回测（调用`run_backtest.sh`）
- `run_rotation_backtest()`: 执行轮动策略回测（调用`run_rotation_strategy.py`）

#### 3.3 结果分析函数
- `load_baseline_results()`: 加载对照组CSV
- `load_rotation_results()`: 加载轮动组CSV + 元数据JSON
- `calculate_statistics()`: 计算对比指标

#### 3.4 报告生成函数
- `generate_comparison_report()`: 自动生成完整Markdown报告
  - 执行摘要（智能判断结论）
  - 详细对比表格
  - 轮动成本分析
  - 结论与建议
  - 附录（复现命令）

**命令行接口**:
```bash
# 执行所有场景并分析
python experiment/etf/rotation_comparison/run_comparison.py --execute all

# 分步执行
python experiment/etf/rotation_comparison/run_comparison.py --execute baseline
python experiment/etf/rotation_comparison/run_comparison.py --execute rotation_30d
python experiment/etf/rotation_comparison/run_comparison.py --execute rotation_60d

# 仅分析已有结果
python experiment/etf/rotation_comparison/run_comparison.py --analyze

# 试运行模式（查看命令但不执行）
python experiment/etf/rotation_comparison/run_comparison.py --execute all --dry-run
```

**输出**: `experiment/etf/rotation_comparison/RESULTS.md`

---

### 4. 创建 `EXPERIMENT_DESIGN.md` 实验设计文档

**内容结构**（11个章节）:
1. 实验目标（假设检验）
2. 实验设计（3场景矩阵）
3. 数据准备（详细命令）
4. 回测执行（完整流程）
5. 结果分析（6大维度）
6. 结果输出（报告结构）
7. 技术实现细节（虚拟ETF合成法）
8. 实验风险与限制
9. 后续扩展方向
10. 检查清单
11. 时间估算

**关键亮点**:
- ✅ 确保公平对比（对照组与实验组筛选规则一致）
- ✅ 避免未来数据泄露（时序严格性）
- ✅ 精确成本计入（增量调整模式节省39%成本）
- ✅ 详细的复现命令（便于后续验证）

---

## 🎯 实验设计核心要点

### 对比方案

| 场景 | ETF池 | 轮动周期 | 回测方式 |
|------|-------|----------|----------|
| Baseline（对照组） | 固定20只（2023-11-01时点） | - | 20次独立回测 |
| Rotation-30d（实验组1） | 动态20只（每30天重筛） | 30天 | 1次虚拟ETF回测 |
| Rotation-60d（实验组2） | 动态20只（每60天重筛） | 60天 | 1次虚拟ETF回测 |

### 关键技术保证

1. **筛选规则一致性** ⭐ 最重要
   - 对照组和实验组都使用：一阶段过滤 + 纯评分排序（无二阶段硬性阈值）
   - 都启用无偏评分（`enable_unbiased_scoring=True`）
   - 动量权重为0（避免动量偏差）

2. **时序严格性**
   - 对照组：使用2023-10-31之前的数据筛选
   - 实验组：每个轮动日使用当日之前的数据筛选
   - 确保无未来数据泄露

3. **虚拟ETF合成法**
   - 等权组合：每只ETF权重 = 1/N
   - 逐期归一化：确保价格连续性
   - 增量调整：基于换手率计算成本（节省39%）

---

## 📂 新增文件清单

| 文件路径 | 文件类型 | 用途 |
|---------|---------|------|
| `scripts/generate_fixed_baseline_pool.py` | Python脚本 | 生成对照组固定池 |
| `experiment/etf/rotation_comparison/run_comparison.py` | Python脚本 | 自动化实验执行和分析 |
| `experiment/etf/rotation_comparison/EXPERIMENT_DESIGN.md` | 文档 | 详细实验设计说明 |
| `experiment/etf/rotation_comparison/PROGRESS_REPORT.md` | 文档 | 本报告 |

**修改文件**:
| 文件路径 | 修改内容 |
|---------|---------|
| `scripts/prepare_rotation_schedule.py` | 添加`--no-score-threshold`参数，启用无偏评分 |

---

## ⏭️ 下一步执行计划（等待用户确认）

### Step 1: 数据准备（预计2-3小时）

```bash
# 1.1 生成固定池（对照组）
python scripts/generate_fixed_baseline_pool.py

# 1.2 生成30天轮动表（实验组1）
python scripts/prepare_rotation_schedule.py \
  --start-date 2023-11-01 \
  --end-date 2025-11-12 \
  --rotation-period 30 \
  --pool-size 20 \
  --data-dir data/chinese_etf \
  --output results/rotation_schedules/rotation_30d_full.json

# 1.3 生成60天轮动表（实验组2）
python scripts/prepare_rotation_schedule.py \
  --start-date 2023-11-01 \
  --end-date 2025-11-12 \
  --rotation-period 60 \
  --pool-size 20 \
  --data-dir data/chinese_etf \
  --output results/rotation_schedules/rotation_60d_full.json

# 1.4 验证轮动表
python scripts/validate_rotation_schedule.py \
  results/rotation_schedules/rotation_30d_full.json

python scripts/validate_rotation_schedule.py \
  results/rotation_schedules/rotation_60d_full.json
```

### Step 2: 执行实验（预计3-4小时）

**方式A: 自动化执行（推荐）**
```bash
python experiment/etf/rotation_comparison/run_comparison.py --execute all
```

**方式B: 分步执行（便于调试）**
```bash
# 执行对照组
python experiment/etf/rotation_comparison/run_comparison.py --execute baseline

# 执行实验组1
python experiment/etf/rotation_comparison/run_comparison.py --execute rotation_30d

# 执行实验组2
python experiment/etf/rotation_comparison/run_comparison.py --execute rotation_60d

# 分析结果
python experiment/etf/rotation_comparison/run_comparison.py --analyze
```

### Step 3: 审查结果（预计1小时）

```bash
# 查看生成的报告
cat experiment/etf/rotation_comparison/RESULTS.md

# 检查数据文件完整性
ls -lh experiment/etf/rotation_comparison/results/*/
```

---

## 🚨 需要注意的事项

1. **数据完整性**
   - 确保`data/chinese_etf`目录包含所有ETF的日线数据
   - 时间跨度需覆盖2023-11-01之前（至少2023-01-01起）

2. **磁盘空间**
   - 对照组回测会生成20个独立结果文件
   - 预留至少500MB空间

3. **执行时间**
   - 固定池回测：约2-3小时（20只ETF，逐个回测）
   - 轮动策略回测：约1-1.5小时/场景（虚拟ETF）
   - 总计：约4-6小时

4. **错误处理**
   - 如果某只ETF数据不足，会跳过该ETF（固定池）
   - 如果轮动表生成失败，检查`data_dir`参数是否正确
   - 如果回测失败，查看详细日志排查问题

---

## 📊 预期结果示例

### 夏普比率对比

| 场景 | 夏普比率 | 相对Baseline变化 |
|------|----------|-----------------|
| Baseline（对照组） | 1.69 | - |
| Rotation-30d | ? | ? |
| Rotation-60d | ? | ? |

**判断标准**:
- 如果轮动策略夏普比率 > 1.77（+5%）：✅ 轮动策略优于固定池
- 如果轮动策略夏普比率 < 1.61（-5%）：❌ 轮动策略劣于固定池
- 如果在1.61-1.77之间：⚖️ 两种策略表现相当

---

## ✅ 开发质量保证

### 代码质量
- ✅ 遵循项目代码规范
- ✅ 添加详细的docstring和注释
- ✅ 错误处理和边界情况检查
- ✅ 支持试运行模式（`--dry-run`）

### 功能完整性
- ✅ 支持多场景灵活执行（all/单场景/仅分析）
- ✅ 自动化生成完整对比报告
- ✅ 智能判断实验结论（优于/劣于/相当）
- ✅ 包含轮动成本分析

### 可维护性
- ✅ 模块化设计（配置、执行、分析分离）
- ✅ 详细的实验设计文档
- ✅ 完整的复现命令和检查清单
- ✅ 便于后续扩展（更多轮动周期、策略）

---

## 🎉 总结

**开发状态**: ✅ 所有开发任务已完成，代码质量经过审查

**交付物**:
1. ✅ 修改后的`prepare_rotation_schedule.py`（支持纯排序模式）
2. ✅ 新增`generate_fixed_baseline_pool.py`（固定池生成）
3. ✅ 新增`run_comparison.py`（自动化实验脚本）
4. ✅ 新增`EXPERIMENT_DESIGN.md`（详细实验设计）
5. ✅ 本开发进展报告

**等待用户确认后，即可开始执行数据准备和实验！**

---

**报告结束**
