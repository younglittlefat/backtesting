# ETF轮动策略 vs 固定池策略对比实验设计

**文档版本**: v1.0
**创建日期**: 2025-11-13
**对应Phase**: Phase 4 - 对比实验
**实验ID**: rotation_comparison_phase4

---

## 1. 实验目标

回答核心问题：**定期重新筛选ETF池（如每30天）能否提升风险调整后收益？**

### 1.1 假设

- **H0（零假设）**: 动态轮动与固定池的夏普比率无显著差异
- **H1（备择假设）**: 动态轮动的夏普比率显著优于固定池

### 1.2 成功标准

- **显著优于**: 夏普比率提升 ≥ 5%
- **显著劣于**: 夏普比率下降 ≥ 5%
- **表现相当**: 夏普比率变化 < 5%

---

## 2. 实验设计

### 2.1 实验矩阵

| 场景ID | 类型 | ETF池类型 | 轮动周期 | ETF数量 | 回测数 |
|--------|------|-----------|----------|---------|--------|
| **Baseline** | 对照组 | 固定池 | - | 20 | 20次（逐个） |
| **Rotation-30d** | 实验组1 | 动态轮动 | 30天 | 20（每期） | 1次（虚拟ETF） |
| **Rotation-60d** | 实验组2 | 动态轮动 | 60天 | 20（每期） | 1次（虚拟ETF） |

### 2.2 共同配置

| 参数 | 值 | 说明 |
|------|-----|------|
| **时间跨度** | 2023-11-01 至 2025-11-12 | 2年历史数据 |
| **策略** | KAMA Baseline | 无过滤器、无止损保护 |
| **初始资金** | 100,000元 | 标准配置 |
| **交易成本** | 0.3%单边 | 中国ETF市场标准 |
| **数据频率** | 日线 | 使用`data/chinese_etf` |

**策略参数** (KAMA Baseline):
- `period=20`
- `fast_ema_span=2`
- `slow_ema_span=30`

### 2.3 ETF筛选规则（确保对照组与实验组一致）

**一阶段过滤**（硬性门槛）:
- 日均成交额 ≥ 5万元
- 上市天数 ≥ 60天

**二阶段筛选**（纯评分排序）:
- 跳过百分位过滤（`skip_stage2_percentile_filtering=True`）
- 跳过范围过滤（`skip_stage2_range_filtering=True`）
- 启用无偏评分（`enable_unbiased_scoring=True`）
- 按综合评分排序取top-20

**评分权重**（无偏配置）:
- ADX趋势强度: 40%
- 趋势一致性: 25%
- 价格效率: 20%
- 流动性: 15%
- **动量: 0%** （关键：避免动量偏差）

---

## 3. 数据准备

### 3.1 固定池生成（对照组）

**脚本**: `scripts/generate_fixed_baseline_pool.py`

**关键点**:
- 使用2023-10-31之前的历史数据筛选
- 确保无未来数据泄露
- 与轮动池使用相同的筛选规则

**命令**:
```bash
python scripts/generate_fixed_baseline_pool.py \
  --baseline-date 2023-11-01 \
  --pool-size 20 \
  --data-dir data/chinese_etf \
  --output results/rotation_fixed_pool/baseline_pool.csv
```

**输出**: `results/rotation_fixed_pool/baseline_pool.csv`

### 3.2 轮动表生成（实验组）

**脚本**: `scripts/prepare_rotation_schedule.py`

**关键点**:
- 每个轮动日使用当日之前的历史数据筛选
- 默认已启用`--no-score-threshold`（纯排序模式）
- 输出JSON格式轮动表

**30天轮动表**:
```bash
python scripts/prepare_rotation_schedule.py \
  --start-date 2023-11-01 \
  --end-date 2025-11-12 \
  --rotation-period 30 \
  --pool-size 20 \
  --data-dir data/chinese_etf \
  --output results/rotation_schedules/rotation_30d_full.json
```

**60天轮动表**:
```bash
python scripts/prepare_rotation_schedule.py \
  --start-date 2023-11-01 \
  --end-date 2025-11-12 \
  --rotation-period 60 \
  --pool-size 20 \
  --data-dir data/chinese_etf \
  --output results/rotation_schedules/rotation_60d_full.json
```

**输出**:
- `results/rotation_schedules/rotation_30d_full.json`
- `results/rotation_schedules/rotation_60d_full.json`

---

## 4. 回测执行

### 4.1 固定池回测（对照组）

**脚本**: `run_backtest.sh`

**命令**:
```bash
./run_backtest.sh \
  --stock-list results/rotation_fixed_pool/baseline_pool.csv \
  --strategy kama_cross \
  --data-dir data/chinese_etf \
  --aggregate-output experiment/etf/rotation_comparison/results/baseline/aggregate_results.csv \
  --output-dir experiment/etf/rotation_comparison/results/baseline/
```

**输出**:
- 20个ETF的独立回测结果
- 汇总文件: `aggregate_results.csv`

**关键指标**:
- 平均夏普比率
- 夏普比率中位数
- 夏普比率标准差（稳定性）
- 平均总收益
- 平均最大回撤

### 4.2 轮动策略回测（实验组）

**脚本**: `scripts/run_rotation_strategy.py`

**30天轮动**:
```bash
python scripts/run_rotation_strategy.py \
  --rotation-schedule results/rotation_schedules/rotation_30d_full.json \
  --strategy kama_cross \
  --rebalance-mode incremental \
  --trading-cost 0.003 \
  --data-dir data/chinese_etf \
  --output experiment/etf/rotation_comparison/results/rotation_30d/
```

**60天轮动**:
```bash
python scripts/run_rotation_strategy.py \
  --rotation-schedule results/rotation_schedules/rotation_60d_full.json \
  --strategy kama_cross \
  --rebalance-mode incremental \
  --trading-cost 0.003 \
  --data-dir data/chinese_etf \
  --output experiment/etf/rotation_comparison/results/rotation_60d/
```

**输出**:
- 虚拟ETF回测结果: `backtest_results.csv`
- 虚拟ETF元数据: `virtual_etf_metadata.json`（包含轮动统计）
- 权益曲线: `equity_curve.csv`

**关键指标**:
- 夏普比率
- 总收益
- 最大回撤
- 交易次数
- 轮动成本

---

## 5. 结果分析

### 5.1 自动化分析脚本

**脚本**: `experiment/etf/rotation_comparison/run_comparison.py`

**功能**:
1. 执行所有场景的回测（或选择性执行）
2. 加载并对比分析结果
3. 自动生成Markdown格式对比报告

**使用方法**:
```bash
# 执行所有场景并分析
python experiment/etf/rotation_comparison/run_comparison.py --execute all

# 仅执行对照组
python experiment/etf/rotation_comparison/run_comparison.py --execute baseline

# 仅分析已有结果（不执行回测）
python experiment/etf/rotation_comparison/run_comparison.py --analyze

# 试运行模式（查看命令但不执行）
python experiment/etf/rotation_comparison/run_comparison.py --execute all --dry-run
```

### 5.2 分析维度

#### 5.2.1 收益性对比
- 总收益率
- 年化收益率
- 收益分布（对照组20只ETF）

#### 5.2.2 风险调整收益对比
- **夏普比率** ⭐ 主要指标
- Sortino比率
- Calmar比率

#### 5.2.3 风险控制对比
- 最大回撤
- 回撤恢复时间
- 波动率
- 下行波动率

#### 5.2.4 稳定性分析
- 夏普比率标准差（对照组）
- ETF间表现差异（对照组）
- 最差标的表现（对照组）

#### 5.2.5 轮动成本分析
- 轮动次数
- 平均换手率
- 平均保留数量
- 累计轮动成本占比

#### 5.2.6 市场环境分析
- 上涨市场表现
- 下跌市场表现
- 震荡市场表现

---

## 6. 结果输出

### 6.1 报告文件

**主报告**: `experiment/etf/rotation_comparison/RESULTS.md`

**内容结构**:
1. 执行摘要（核心结论）
2. 实验设计
3. 详细结果（表格+图表）
4. 轮动成本分析
5. 市场环境分析
6. 结论与建议
7. 附录（数据文件清单、复现命令）

### 6.2 数据文件清单

```
experiment/etf/rotation_comparison/
├── results/
│   ├── baseline/
│   │   ├── aggregate_results.csv          # 20只ETF汇总
│   │   └── individual/*.csv                # 单只ETF详细结果
│   ├── rotation_30d/
│   │   ├── backtest_results.csv           # 虚拟ETF回测结果
│   │   ├── virtual_etf_metadata.json      # 轮动统计
│   │   └── equity_curve.csv               # 权益曲线
│   └── rotation_60d/
│       ├── backtest_results.csv
│       ├── virtual_etf_metadata.json
│       └── equity_curve.csv
├── run_comparison.py                      # 自动化实验脚本
├── EXPERIMENT_DESIGN.md                   # 本文档
└── RESULTS.md                             # 最终报告（实验后生成）
```

---

## 7. 技术实现细节

### 7.1 虚拟ETF合成法

**原理**: 将轮动的N只ETF按等权组合合成单一虚拟ETF

**关键技术**:
1. **逐期归一化**: 每次轮动后重新归一化价格，确保连续性
2. **再平衡模式**:
   - **全平仓** (full_liquidation): 双边成本0.6%
   - **增量调整** (incremental): 基于换手率0.24-0.39%（节省39%成本）✅ 推荐
3. **成本精确计入**: 根据换手率计算实际交易成本

### 7.2 避免未来数据泄露

**对照组**:
- 使用2023-10-31之前的历史数据筛选
- 筛选日期: 2023-10-31（固定）
- 使用日期: 2023-11-01 至 2025-11-12

**实验组**:
- 每个轮动日严格使用当日之前的历史数据
- 评分窗口: 全部历史数据 至 `rotation_date - 1天`
- 确保时序严格性

### 7.3 公平对比保证

| 维度 | 对照组 | 实验组 | 是否一致 |
|------|--------|--------|----------|
| 筛选规则 | 一阶段+纯排序 | 一阶段+纯排序 | ✅ 一致 |
| 评分权重 | 无偏配置 | 无偏配置 | ✅ 一致 |
| 策略参数 | KAMA Baseline | KAMA Baseline | ✅ 一致 |
| 交易成本 | 0.3%单边 | 0.3%单边 | ✅ 一致 |
| 时间跨度 | 2023-11至2025-11 | 2023-11至2025-11 | ✅ 一致 |

---

## 8. 实验风险与限制

### 8.1 已知限制

1. **样本期限制**: 仅2年数据，可能无法覆盖完整市场周期
2. **虚拟ETF近似**: 等权组合假设，实际可能存在流动性限制
3. **交易成本模型**: 假设固定0.3%，实际可能因市场冲击而变化
4. **筛选指标时效性**: 历史有效的指标未来可能失效

### 8.2 潜在风险

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 数据不足 | 中 | 高 | 延长回测周期（需更多历史数据） |
| 筛选偏差 | 低 | 中 | 已启用无偏评分，避免动量偏差 |
| 成本模型偏差 | 中 | 中 | 敏感性分析（测试0.2%、0.4%成本） |
| 过拟合风险 | 低 | 高 | 使用固定参数，无优化 |

---

## 9. 后续扩展方向

### 9.1 轮动周期扩展

测试更多轮动周期以找到最优值：
- 15天（更频繁）
- 90天（更稳定）
- 180天（季度轮动）

### 9.2 策略扩展

测试其他策略的轮动效果：
- SMA + Loss Protection（夏普1.07，+75%提升）
- MACD + Combined（夏普0.94，+28.8%提升）

### 9.3 筛选指标优化

改进ETF筛选规则：
- 加入市场环境判断（牛熊市分离）
- 动态调整评分权重
- 引入机器学习预测

### 9.4 成本优化

降低轮动成本：
- 部分轮动（仅调整表现最差的5只）
- 动态轮动频率（根据市场波动率调整）
- 成本阈值触发（仅当预期收益>成本时才轮动）

---

## 10. 检查清单

### 10.1 开发阶段 ✅

- [x] 修改`prepare_rotation_schedule.py`添加`--no-score-threshold`参数
- [x] 开发`generate_fixed_baseline_pool.py`脚本
- [x] 开发`run_comparison.py`自动化实验脚本
- [x] 创建实验设计文档（本文档）

### 10.2 数据准备阶段（待执行）

- [ ] 生成固定池（对照组）
- [ ] 生成30天轮动表（实验组1）
- [ ] 生成60天轮动表（实验组2）
- [ ] 验证轮动表完整性（使用`validate_rotation_schedule.py`）

### 10.3 实验执行阶段（待执行）

- [ ] 执行对照组回测（20只ETF）
- [ ] 执行30天轮动回测（虚拟ETF）
- [ ] 执行60天轮动回测（虚拟ETF）
- [ ] 验证所有结果文件完整性

### 10.4 分析阶段（待执行）

- [ ] 运行`run_comparison.py --analyze`
- [ ] 审查生成的`RESULTS.md`报告
- [ ] 验证结论的合理性
- [ ] 补充市场环境分析（如需要）

---

## 11. 时间估算

| 阶段 | 预计耗时 | 说明 |
|------|----------|------|
| 数据准备 | 2-3小时 | 生成池子+轮动表 |
| 回测执行 | 3-4小时 | 取决于回测速度 |
| 结果分析 | 1小时 | 自动化脚本 |
| 报告审查 | 1小时 | 人工审查和补充 |
| **总计** | **7-9小时** | 约1个工作日 |

---

**文档结束**

下一步：执行数据准备阶段命令，等待用户确认后开始实验
