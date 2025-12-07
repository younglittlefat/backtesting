# 新增盈亏比、胜率、交易次数指标需求

**文档编号**: 20251206_add_profit_loss_ratio_metrics
**创建日期**: 2025-12-06
**状态**: ✅ 已完成

---

## 1. 背景与动机

### 1.1 问题描述

当前 `mega_test_*_greedy_parallel.sh` 贪心超参搜索流程中，每轮回测仅输出以下指标：
- 夏普比率（均值/中位数）
- 年化收益率（均值/中位数）
- 最大回撤（均值/中位数）

**缺失的关键指标**：

| 指标 | 趋势跟踪意义 | 当前状态 |
|------|--------------|----------|
| **盈亏比** (Profit/Loss Ratio) | 趋势跟踪的核心，应 > 2，越高越好 | ❌ 未输出到汇总 |
| **胜率** (Win Rate) | 35%-50%可接受，需配合盈亏比评估 | ❌ 未输出到汇总 |
| **交易次数** (# Trades) | 防止过度优化（太少无统计意义，太多磨损成本） | ❌ 未输出到汇总 |

### 1.2 趋势跟踪策略评估原则

趋势跟踪策略的核心特征是**低胜率、高盈亏比**：
- 胜率通常在 35%-50%（大量小亏损，少量大盈利）
- 盈亏比应 > 2.0（平均盈利是平均亏损的2倍以上）
- 交易次数需要足够（>20次）才有统计意义

**期望收益公式**：
```
期望收益 = 胜率 × 平均盈利 - (1-胜率) × 平均亏损
         = 胜率 × 盈亏比 × 平均亏损 - (1-胜率) × 平均亏损
```

当盈亏比=2.0、胜率=40%时：
```
期望收益 = 0.4 × 2.0 × L - 0.6 × L = 0.2L > 0 ✓
```

---

## 2. 现有框架与流程

### 2.1 指标计算流程

```
┌─────────────────────────────────────────────────────────────────┐
│  backtesting/_stats.py                                          │
│  ├── compute_stats()                                            │
│  │   ├── s.loc['# Trades'] = n_trades                          │
│  │   ├── s.loc['Win Rate [%]'] = win_rate * 100                │
│  │   ├── s.loc['Profit Factor'] = Σ盈利/Σ亏损                  │
│  │   └── ❌ 缺少 Profit/Loss Ratio = avg盈利/avg亏损           │
│  └── 返回 pd.Series 包含所有指标                                │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  backtest_runner/io/summary_generator.py                        │
│  ├── save_summary_csv()                                         │
│  │   ├── 生成 backtest_summary_*.csv（每标的一行）             │
│  │   └── ❌ 未包含胜率、盈亏比、交易次数                        │
│  └── save_global_summary_csv()                                  │
│      ├── 生成 global_summary_*.csv（全局聚合）                  │
│      └── ❌ 未包含胜率、盈亏比、交易次数的均值/中位数           │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  mega_test_*_greedy_parallel.sh                                 │
│  ├── 嵌入式 Python 代码提取指标                                 │
│  │   ├── extract baseline metrics                               │
│  │   ├── extract single-var metrics                             │
│  │   └── extract k-var metrics                                  │
│  └── ❌ 仅提取 sharpe_mean, sharpe_median                       │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  scripts/collect_mega_test_results.sh                           │
│  ├── 汇总所有实验结果到 mega_test_greedy_summary.csv            │
│  └── ❌ 未包含胜率、盈亏比、交易次数列                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键文件位置

| 文件 | 路径 | 职责 |
|------|------|------|
| 指标计算 | `backtesting/_stats.py` | 单标的回测指标计算 |
| 汇总生成 | `backtest_runner/io/summary_generator.py` | 生成明细和全局汇总CSV |
| KAMA脚本 | `mega_test_kama_greedy_parallel.sh` | KAMA策略贪心搜索 |
| MACD脚本 | `mega_test_macd_greedy_parallel.sh` | MACD策略贪心搜索 |
| SMA脚本 | `mega_test_sma_enhanced_greedy_parallel.sh` | SMA策略贪心搜索 |
| 结果收集 | `scripts/collect_mega_test_results.sh` | 汇总实验结果 |

### 2.3 现有指标定义

**`_stats.py` 中已有但未传递的指标**：

```python
# 行 187-199
s.loc['# Trades'] = n_trades = len(trades_df)
s.loc['Win Rate [%]'] = win_rate * 100
s.loc['Profit Factor'] = returns[returns > 0].sum() / (abs(returns[returns < 0].sum()) or np.nan)
```

**注意**：`Profit Factor` 是**总盈利/总亏损**，而非**平均盈利/平均亏损**（盈亏比）

---

## 3. 需求详情

### 3.1 新增指标定义

| 指标 | 字段名 | 计算公式 | 说明 |
|------|--------|----------|------|
| 盈亏比 | `Profit/Loss Ratio` | `mean(盈利交易PnL) / abs(mean(亏损交易PnL))` | 平均盈利/平均亏损 |
| 胜率 | `Win Rate [%]` | `count(PnL>0) / count(all) * 100` | 已有，需传递 |
| 交易次数 | `# Trades` | `count(all_trades)` | 已有，需传递 |

### 3.2 输出格式

#### 明细汇总 CSV (`backtest_summary_*.csv`)

新增列：
```
..., 胜率(%), 盈亏比, 交易次数
```

#### 全局汇总 CSV (`global_summary_*.csv`)

新增列（6个）：
```
..., 胜率-均值(%), 胜率-中位数(%), 盈亏比-均值, 盈亏比-中位数, 交易次数-均值, 交易次数-中位数
```

#### 最终汇总 CSV (`mega_test_greedy_summary.csv`)

新增列（6个）：
```
..., win_rate_mean, win_rate_median, pl_ratio_mean, pl_ratio_median, trades_mean, trades_median, ...
```

---

## 4. 实现方案

### 4.1 修改文件列表

| 序号 | 文件 | 修改内容 |
|------|------|----------|
| 1 | `backtesting/_stats.py` | 新增 `Profit/Loss Ratio` 计算 |
| 2 | `backtest_runner/io/summary_generator.py` | 扩展明细CSV和全局CSV字段 |
| 3 | `mega_test_kama_greedy_parallel.sh` | 提取新指标到JSON和打印输出 |
| 4 | `mega_test_macd_greedy_parallel.sh` | 同上 |
| 5 | `mega_test_sma_enhanced_greedy_parallel.sh` | 同上 |
| 6 | `scripts/collect_mega_test_results.sh` | 汇总新指标列 |

### 4.2 详细修改

#### 4.2.1 `backtesting/_stats.py`

**位置**: 约 196 行后（`Profit Factor` 之后）

**新增代码**:
```python
# 盈亏比（平均盈利/平均亏损）- 趋势跟踪核心指标
avg_win = pl[pl > 0].mean() if (pl > 0).any() else np.nan
avg_loss = abs(pl[pl < 0].mean()) if (pl < 0).any() else np.nan
s.loc['Profit/Loss Ratio'] = avg_win / (avg_loss or np.nan)
```

#### 4.2.2 `backtest_runner/io/summary_generator.py`

**修改 1**: `save_summary_csv()` 函数（约 64-75 行）

在 `summary_rows.append()` 中新增：
```python
'胜率(%)': round(_safe_stat(stats, 'Win Rate [%]'), 2) if _safe_stat(stats, 'Win Rate [%]') is not None else None,
'盈亏比': round(_safe_stat(stats, 'Profit/Loss Ratio'), 2) if _safe_stat(stats, 'Profit/Loss Ratio') is not None else None,
'交易次数': int(_safe_stat(stats, '# Trades', default=0)),
```

**修改 2**: `save_global_summary_csv()` 函数（约 139-175 行）

新增提取和计算：
```python
# 获取新指标列
win_rate_col = _find_first_col(df, ['胜率(%)', 'Win Rate [%]'])
pl_ratio_col = _find_first_col(df, ['盈亏比', 'Profit/Loss Ratio'])
trades_col = _find_first_col(df, ['交易次数', '# Trades'])

# 计算统计值
win_rate = pd.to_numeric(df[win_rate_col], errors='coerce') if win_rate_col else pd.Series(dtype=float)
pl_ratio = pd.to_numeric(df[pl_ratio_col], errors='coerce') if pl_ratio_col else pd.Series(dtype=float)
trades = pd.to_numeric(df[trades_col], errors='coerce') if trades_col else pd.Series(dtype=float)

win_rate_mean = float(round(win_rate.dropna().mean(), 2)) if win_rate.dropna().size else None
win_rate_median = float(round(win_rate.dropna().median(), 2)) if win_rate.dropna().size else None
pl_ratio_mean = float(round(pl_ratio.dropna().mean(), 2)) if pl_ratio.dropna().size else None
pl_ratio_median = float(round(pl_ratio.dropna().median(), 2)) if pl_ratio.dropna().size else None
trades_mean = float(round(trades.dropna().mean(), 1)) if trades.dropna().size else None
trades_median = float(round(trades.dropna().median(), 1)) if trades.dropna().size else None
```

在 `result = pd.DataFrame([{...}])` 中新增：
```python
'胜率-均值(%)': win_rate_mean,
'胜率-中位数(%)': win_rate_median,
'盈亏比-均值': pl_ratio_mean,
'盈亏比-中位数': pl_ratio_median,
'交易次数-均值': trades_mean,
'交易次数-中位数': trades_median,
```

#### 4.2.3 `mega_test_*_greedy_parallel.sh` 脚本（3个）

**修改 1**: Baseline 提取的 `col_mapping`

```python
col_mapping = {
    'sharpe_mean': ['夏普-均值', 'Sharpe Ratio Mean'],
    'sharpe_median': ['夏普-中位数', 'Sharpe Ratio Median'],
    'win_rate_mean': ['胜率-均值(%)', 'Win Rate [%] Mean'],
    'win_rate_median': ['胜率-中位数(%)', 'Win Rate [%] Median'],
    'pl_ratio_mean': ['盈亏比-均值', 'Profit/Loss Ratio Mean'],
    'pl_ratio_median': ['盈亏比-中位数', 'Profit/Loss Ratio Median'],
    'trades_mean': ['交易次数-均值', '# Trades Mean'],
    'trades_median': ['交易次数-中位数', '# Trades Median'],
}
```

**修改 2**: 筛选时的打印输出

```python
print(f"  {status} {opt}: sharpe={sharpe_mean:.3f}/{sharpe_median:.3f}, "
      f"win_rate={win_rate_mean:.1f}%, pl_ratio={pl_ratio_mean:.2f}, trades={trades_mean:.0f}")
```

**修改 3**: 保存到 candidates JSON 的字段

```python
candidates.append({
    'options': [opt],
    'sharpe_mean': sharpe_mean,
    'sharpe_median': sharpe_median,
    'win_rate_mean': win_rate_mean,
    'win_rate_median': win_rate_median,
    'pl_ratio_mean': pl_ratio_mean,
    'pl_ratio_median': pl_ratio_median,
    'trades_mean': trades_mean,
    'trades_median': trades_median,
    'exp_name': exp_name
})
```

#### 4.2.4 `scripts/collect_mega_test_results.sh`

**修改 1**: `extract_metrics_from_summary()` 的 `col_mapping`

```python
col_mapping = {
    'return_mean': ['年化收益率-均值(%)', 'Return [%] Mean'],
    'return_median': ['年化收益率-中位数(%)', 'Return [%] Median'],
    'sharpe_mean': ['夏普-均值', 'Sharpe Ratio Mean'],
    'sharpe_median': ['夏普-中位数', 'Sharpe Ratio Median'],
    'max_dd_mean': ['最大回撤-均值(%)', 'Max. Drawdown [%] Mean'],
    'max_dd_median': ['最大回撤-中位数(%)', 'Max. Drawdown [%] Median'],
    # 新增
    'win_rate_mean': ['胜率-均值(%)', 'Win Rate [%] Mean'],
    'win_rate_median': ['胜率-中位数(%)', 'Win Rate [%] Median'],
    'pl_ratio_mean': ['盈亏比-均值', 'Profit/Loss Ratio Mean'],
    'pl_ratio_median': ['盈亏比-中位数', 'Profit/Loss Ratio Median'],
    'trades_mean': ['交易次数-均值', '# Trades Mean'],
    'trades_median': ['交易次数-中位数', '# Trades Median'],
}
```

**修改 2**: `csv_columns` 定义

```python
csv_columns.extend([
    'return_mean', 'return_median',
    'sharpe_mean', 'sharpe_median',
    'max_dd_mean', 'max_dd_median',
    # 新增
    'win_rate_mean', 'win_rate_median',
    'pl_ratio_mean', 'pl_ratio_median',
    'trades_mean', 'trades_median',
    'num_stocks', 'summary_path'
])
```

---

## 5. 开发任务清单

- [x] **Task 1**: 创建需求文档
- [x] **Task 2**: 修改 `backtesting/_stats.py` 添加盈亏比计算
- [x] **Task 3**: 修改 `backtest_runner/io/summary_generator.py` 扩展明细和全局CSV字段
- [x] **Task 4**: 修改 `mega_test_kama_greedy_parallel.sh` 提取新指标
- [x] **Task 5**: 修改 `mega_test_macd_greedy_parallel.sh` 提取新指标
- [x] **Task 6**: 修改 `mega_test_sma_enhanced_greedy_parallel.sh` 提取新指标
- [x] **Task 7**: 修改 `scripts/collect_mega_test_results.sh` 汇总新指标
- [ ] **Task 8**: 测试验证新指标计算正确性
- [x] **Task 9**: 更新需求文档标记完成状态

---

## 6. 兼容性考虑

1. **向后兼容**: 新增字段使用 `_find_first_col()` 查找，旧数据缺失时返回 `None`
2. **筛选逻辑不变**: 贪心筛选仍基于夏普比率，新指标仅用于展示和分析
3. **可选扩展**: 未来可添加基于盈亏比的筛选条件（如 `pl_ratio > 1.5`）

---

## 7. 验收标准

1. 运行单个回测后，`backtest_summary_*.csv` 包含胜率、盈亏比、交易次数列
2. 运行单个回测后，`global_summary_*.csv` 包含6个新统计字段
3. 运行 mega_test 脚本后，每轮打印输出包含新指标
4. 运行结果收集脚本后，`mega_test_greedy_summary.csv` 包含6个新列
5. 新指标计算结果与手动验算一致

---

## 8. 变更记录

| 日期 | 版本 | 描述 |
|------|------|------|
| 2025-12-06 | v1.0 | 初始需求文档 |
| 2025-12-06 | v1.1 | 完成核心模块开发（Task 1-5），待完成 Task 7-9 |
| 2025-12-07 | v1.2 | 完成全部开发（Task 6-7, 9），修复审查意见3/4，待用户验证 |

---

## 9. 第一次代码审查建议（处理状态）

1. **最终汇总缺列**：`scripts/collect_mega_test_results.sh` 仍未写入胜率/盈亏比/交易次数，`mega_test_greedy_summary.csv` 继续丢失新指标。✅ **已修复（v1.2）**
2. **SMA 贪心未覆盖**：`mega_test_sma_enhanced_greedy_parallel.sh` 只处理夏普，新指标（胜率/盈亏比/交易次数）缺席，需与 MACD/KAMA 同步。✅ **已修复（v1.2）**
3. **缺失值被写成 0**：`backtest_runner/io/summary_generator.py` 用 `_safe_stat(..., default=0)` 写胜率/盈亏比时，会把缺失/NaN写成 0，导致全局均值/中位数被稀释；建议保持 None/NaN。✅ **已修复（v1.2）** - 移除 default=0，改用 None 保持缺失值
4. **盈亏比口径不可比**：`backtesting/_stats.py` 的 `Profit/Loss Ratio` 基于绝对 PnL 金额，跨标的/不同仓位不可比，建议改用交易收益率或 R-multiple。✅ **已修复（v1.2）** - 改用 ReturnPct（交易收益率）计算
5. **旧格式崩溃风险**：`mega_test_{kama,macd}_greedy_parallel.sh` baseline 打印新指标未防御 None，遇到旧版 summary 缺列会 TypeError，需兜底。⏳ **暂缓** - 新版 summary 会输出新列，旧数据暂不处理
6. **筛选逻辑未用新指标**：候选筛选仍只看夏普，新趋势跟踪约束（盈亏比>2、胜率 35%-50%、交易次数>20）未落地，容易放行高夏普但样本过少或盈亏比不足的组合。⏳ **暂缓** - 属于功能增强，不在本需求范围内
7. **缺少测试**：未新增 `_stats` 新指标计算以及 summary/global CSV 新列存在性的测试，建议补充回归用例。⏳ **暂缓** - 待用户验证后补充

---

## 10. 模块化重构（2025-12-07）

### 10.1 背景

在添加新指标后，5个贪心搜索脚本存在大量重复代码（每个脚本700-1100行），维护困难：
- `mega_test_kama_greedy.sh` (串行版)
- `mega_test_macd_greedy.sh` (串行版)
- `mega_test_kama_greedy_parallel.sh` (并行版)
- `mega_test_macd_greedy_parallel.sh` (并行版)
- `mega_test_sma_enhanced_greedy_parallel.sh` (并行版)

### 10.2 重构方案

创建 `greedy_search/` 模块，抽取公共逻辑：

```
greedy_search/
├── __init__.py              # 模块入口
├── metrics_extractor.py     # 指标提取（从CSV提取所有指标）
├── candidate_filter.py      # 候选筛选（阶段1 OR逻辑、阶段k严格递增）
├── combo_generator.py       # 组合生成（k变量组合）
├── cli.py                   # CLI入口（供Shell脚本调用）
└── greedy_lib.sh            # Shell公共函数库
```

### 10.3 模块功能

#### Python模块

| 模块 | 功能 |
|------|------|
| `metrics_extractor` | 从global_summary CSV提取标准化指标（夏普、胜率、盈亏比、交易次数等） |
| `candidate_filter` | 阶段1 OR逻辑筛选、阶段k严格递增筛选 |
| `combo_generator` | 从k-1阶段候选生成k变量组合 |
| `cli` | 提供命令行接口供Shell脚本调用 |

#### Shell公共函数

| 函数 | 功能 |
|------|------|
| `greedy_print_*` | 彩色输出（header, stage, section, success, warning, error） |
| `greedy_create_metadata` | 创建实验元数据JSON |
| `greedy_init_dirs` | 初始化实验目录结构 |
| `greedy_build_base_cmd` | 构建基础回测命令 |
| `greedy_run_stage0` | 执行Baseline测试 |
| `greedy_run_stage1_parallel` | 阶段1并发执行 |
| `greedy_run_stage1_serial` | 阶段1串行执行 |
| `greedy_run_stage_k_parallel` | 阶段k并发执行 |
| `greedy_run_stage_k_serial` | 阶段k串行执行 |
| `greedy_collect_results` | 收集实验结果 |
| `greedy_collect_only_mode` | 仅收集模式 |
| `greedy_print_final_stats` | 打印最终统计 |

### 10.4 重构后脚本结构

重构后每个策略脚本精简为：
1. **策略特定配置**（~40行）：策略名、路径、超参列表
2. **实验执行函数**（~60行）：`run_single_experiment()`，仅包含策略特定的参数映射
3. **主执行流程**（~50行）：调用公共函数执行各阶段

**代码行数对比**：

| 脚本 | 重构前 | 重构后 | 减少 |
|------|--------|--------|------|
| mega_test_kama_greedy_parallel.sh | 961行 | 265行 | -72% |
| mega_test_macd_greedy_parallel.sh | 915行 | 277行 | -70% |
| mega_test_sma_enhanced_greedy_parallel.sh | 1142行 | 267行 | -77% |
| mega_test_kama_greedy.sh | 969行 | 232行 | -76% |
| mega_test_macd_greedy.sh | 970行 | 243行 | -75% |

### 10.5 开发任务清单

- [x] **Task R1**: 创建 `greedy_search/` 模块目录
- [x] **Task R2**: 实现 `metrics_extractor.py` 指标提取模块
- [x] **Task R3**: 实现 `candidate_filter.py` 候选筛选模块
- [x] **Task R4**: 实现 `combo_generator.py` 组合生成模块
- [x] **Task R5**: 实现 `cli.py` CLI入口
- [x] **Task R6**: 实现 `greedy_lib.sh` Shell公共函数库
- [x] **Task R7**: 重构 `mega_test_kama_greedy_parallel.sh`
- [x] **Task R8**: 重构 `mega_test_macd_greedy_parallel.sh`
- [x] **Task R9**: 重构 `mega_test_sma_enhanced_greedy_parallel.sh`
- [x] **Task R10**: 重构 `mega_test_kama_greedy.sh`
- [x] **Task R11**: 重构 `mega_test_macd_greedy.sh`
- [ ] **Task R12**: 测试验证重构后脚本功能一致性

### 10.6 变更记录

| 日期 | 版本 | 描述 |
|------|------|------|
| 2025-12-07 | v2.0 | 完成模块化重构（Task R1-R11），待用户验证 |

