# ETF筛选器单维度效果验证实验

## 实验概述

本实验旨在验证ETF筛选系统中各个评分维度对KAMA自适应策略收益的单独贡献效果，从而为权重优化提供科学依据。

## 实验设计

### 测试维度
1. **主要指标**（无偏技术指标）：
   - `adx_mean` - ADX趋势强度
   - `trend_consistency` - 趋势一致性
   - `price_efficiency` - 价格发现效率
   - `liquidity_score` - 流动性评分

2. **次要指标**（动量指标）：
   - `momentum_3m` - 3个月动量
   - `momentum_12m` - 12个月动量

3. **基准对比**：
   - `comprehensive` - 综合评分（当前系统）

### 实验参数
- **池子规模**: 20只ETF
- **回测策略**: KAMA自适应均线策略
- **时间窗口**: 2023-11-01 至 2025-11-12
- **数据路径**: `data/chinese_etf/daily`

## 文件结构

```
experiment/etf/selector_dimension_analysis/
├── EXPERIMENT_DESIGN.md           # 详细实验设计文档
├── README.md                      # 本文件
├── single_dimension_selector.py   # 单维度筛选器
├── dimension_analysis.py          # 主实验脚本
├── config/                        # 配置文件（待需要时创建）
├── results/                       # 实验结果
│   ├── stock_lists/              # 各维度筛选的ETF列表
│   ├── backtest_results/         # 回测结果
│   └── analysis/                 # 分析报告
└── RESULTS.md                     # 最终实验结果（实验完成后生成）
```

## 使用方法

### 推荐运行方式（正确设置环境）

```bash
# 进入实验目录
cd /mnt/d/git/backtesting/experiment/etf/selector_dimension_analysis

# 激活conda环境并设置PYTHONPATH
source /home/zijunliu/miniforge3/etc/profile.d/conda.sh
conda activate backtesting
export PYTHONPATH="/mnt/d/git/backtesting:$PYTHONPATH"

# 运行完整实验（记录日志）
python dimension_analysis.py 2>&1 | tee experiment_$(date +%Y%m%d_%H%M%S).log
```

### 简化运行（如果环境已配置）
```bash
# 进入实验目录
cd experiment/etf/selector_dimension_analysis/

# 运行完整实验
python dimension_analysis.py
```

### 单独测试筛选器
```bash
# 测试单维度筛选器（从项目根目录运行）
cd /mnt/d/git/backtesting
python -c "
from experiment.etf.selector_dimension_analysis.single_dimension_selector import SingleDimensionSelector
from etf_selector.config import FilterConfig
selector = SingleDimensionSelector(FilterConfig())
result = selector.select_by_dimension('adx_mean', target_size=5)
print(f'测试成功: {len(result)}只ETF')
"
```

## 预期输出

### 1. ETF池文件
- `results/stock_lists/dimension_{name}_etf_pool.csv`
- 每个维度生成20只ETF的池子
- 包含字段：`ts_code`, `name`, `dimension`, `dimension_value`

### 2. 回测结果
- `results/backtest_results/dimension_{name}/`
- 每个维度的详细回测结果（权益曲线、交易记录等）
- 汇总指标：夏普比率、总收益、最大回撤、胜率等

### 3. 分析报告
- `results/DIMENSION_ANALYSIS_REPORT_{timestamp}.md`
- 维度表现排名、关键发现、假设验证、实用建议

### 4. 数据文件
- `results/analysis/dimension_comparison_{timestamp}.csv`
- 各维度详细对比数据，用于后续分析
- `results/selection_stats.csv` - 筛选阶段统计信息

## 核心假设

**H1**: ADX趋势强度维度对KAMA策略效果最好
**H2**: 动量维度表现良好但存在选择性偏差风险
**H3**: 趋势一致性和价格效率作为无偏指标，稳健性更强
**H4**: 流动性维度对收益影响较小，但对风险控制有帮助

## 技术依赖

- Python 3.9+
- backtesting conda环境
- ETF筛选系统 (`etf_selector`)
- KAMA策略回测系统

## 注意事项

1. **数据依赖**: 确保`data/chinese_etf/daily`目录存在且包含完整的ETF数据
2. **环境要求**: 必须在`backtesting` conda环境中运行
3. **计算时间**: 完整实验预计需要30-60分钟（7个维度 × 20只ETF = 140次回测）
4. **存储空间**: 确保有足够的磁盘空间存储回测结果
5. **流动性阈值**: 默认使用5万元流动性阈值（初筛通过率约27%，约376只ETF）

## 已知问题与修复

本实验在开发过程中发现并修复了以下关键问题（详见`PROBLEM_REPORT_20251115.md`）：

### ✅ P0-1: 数据加载接口错误（已修复）
**问题**: `single_dimension_selector.py:227` 调用了不存在的 `load_etf_data()` 方法
**修复**: 改为 `load_etf_daily(ts_code, use_adj=True)`

### ✅ P0-2: 指标函数参数类型错误（已修复）
**问题**: 多个指标计算函数接收错误的参数类型（DataFrame vs Series）
**影响**: ADX、波动率等6个指标计算失败
**修复**:
- ADX: 传入 `data['adj_high'], data['adj_low'], data['adj_close']` 而非整个DataFrame
- 波动率: 先构建returns序列 `data['adj_close'].pct_change().dropna()`
- 其他指标: 传入正确的Series列

### ✅ P0-3: 数据结构转换错误（已修复）
**问题**: `comprehensive`维度的`run_pipeline()`返回List[Dict]，但代码期望DataFrame
**修复**: 添加转换 `results = pd.DataFrame(results_list)`

### ⚠️ P1: 回测执行环境问题（待解决）
**问题**: 通过`subprocess.run()`调用`conda run`执行回测时返回exit code 2
**现状**: 手动执行相同命令成功，仅subprocess环境下失败
**临时方案**: 可以在筛选阶段完成后，手动执行单个维度的回测验证

## 故障排除

### 常见问题

1. **导入错误**: 确保在项目根目录下运行，或正确设置PYTHONPATH
   ```bash
   export PYTHONPATH="/mnt/d/git/backtesting:$PYTHONPATH"
   ```

2. **数据缺失**: 检查ETF数据文件是否完整
   ```bash
   ls -la data/chinese_etf/daily/*.csv | wc -l  # 应该有1400+个文件
   ```

3. **权限错误**: 确保有写入`results/`目录的权限
   ```bash
   mkdir -p experiment/etf/selector_dimension_analysis/results
   ```

4. **内存不足**: 大规模回测可能需要较多内存，建议关闭其他应用

5. **回测失败（exit code 2）**: 如果自动回测失败，可以手动执行单个维度测试
   ```bash
   # 手动测试单个维度的回测
   /home/zijunliu/miniforge3/condabin/conda run -n backtesting \
     python backtest_runner.py \
     --stock-list experiment/etf/selector_dimension_analysis/results/stock_lists/dimension_adx_mean_etf_pool.csv \
     --strategy kama_cross \
     --data-dir data/chinese_etf/daily \
     --output /tmp/test_backtest
   ```

### 调试模式

```bash
# 开启详细日志
export PYTHONPATH="/mnt/d/git/backtesting:$PYTHONPATH"
python dimension_analysis.py 2>&1 | tee debug_output.log

# 查看日志文件
tail -f experiment/etf/selector_dimension_analysis/results/experiment.log
```

### 分阶段运行

如果完整实验出错，可以分阶段验证：

```python
# 阶段1: 仅测试筛选器
from single_dimension_selector import SingleDimensionSelector
from etf_selector.config import FilterConfig

selector = SingleDimensionSelector(FilterConfig())
result = selector.select_by_dimension('adx_mean', target_size=5)
print(f"筛选测试成功: {len(result)}只ETF")

# 阶段2: 测试批量筛选
results = selector.batch_select_all_dimensions(target_size=10)
print(f"批量筛选完成: {len(results)}个维度")

# 阶段3: 保存结果
saved = selector.save_results(results, "results/test_stock_lists")
print(f"已保存{len(saved)}个文件")
```

## 实验验证

运行前建议先执行小规模测试，验证环境和数据完整性：

```python
# 从项目根目录运行
cd /mnt/d/git/backtesting

# 快速验证测试（Python交互式）
python -c "
from experiment.etf.selector_dimension_analysis.single_dimension_selector import SingleDimensionSelector
from etf_selector.config import FilterConfig
selector = SingleDimensionSelector(FilterConfig())
result = selector.select_by_dimension('adx_mean', target_size=5)
print(f'✅ 测试成功: 筛选了{len(result)}只ETF')
for _, row in result.iterrows():
    print(f'  - {row[\"ts_code\"]}: {row[\"name\"]} (ADX={row[\"dimension_value\"]:.2f})')
"
```

### 预期测试输出
```
✅ 测试成功: 筛选了5只ETF
  - 513360.SH: 双创ETF (ADX=49.68)
  - 159606.SZ: 创业ETF (ADX=49.02)
  - ...
```

## 实验成果

### 筛选阶段成果（已验证）
- ✅ 初筛通过率：27%（376/1403只ETF）
- ✅ 7个维度独立筛选：各20只ETF池
- ✅ 指标计算准确性：100%成功
- ✅ 输出文件完整性：7个CSV + 统计文件

### 实验报告示例
完成后可查看 `results/DIMENSION_ANALYSIS_REPORT_{timestamp}.md`，包含：
- 维度表现排名表格（按夏普比率、总收益排序）
- 关键发现（最优维度、最佳配置）
- 假设验证结果（H1-H4检验）
- 实用建议（权重优化、配置调整）

---

**实验负责人**: Claude Code
**创建时间**: 2025-11-14
**最后更新**: 2025-11-15
**版本**: v1.1（修复P0问题后）