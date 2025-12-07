# 贪心搜索实验框架模块化重构

## 元信息

| 字段 | 值 |
|------|-----|
| 文档编号 | 20251206_greedy_search_framework_modularization |
| 创建日期 | 2025-12-06 |
| 状态 | ✅ 已完成 |
| 优先级 | 中 |
| 影响范围 | `mega_test_*_greedy*.sh` 系列脚本 |

---

## 1. 背景

### 1.1 现状描述

当前项目中存在5个贪心搜索实验脚本：
- `mega_test_kama_greedy_parallel.sh` (并行版)
- `mega_test_macd_greedy_parallel.sh` (并行版)
- `mega_test_sma_enhanced_greedy_parallel.sh` (并行版)
- `mega_test_kama_greedy.sh` (串行版)
- `mega_test_macd_greedy.sh` (串行版)

这些脚本实现了相同的贪心搜索算法：
1. **阶段0**: 测试Baseline（无任何选项）
2. **阶段1**: 单变量筛选（OR逻辑：sharpe_mean > base OR sharpe_median > base）
3. **阶段k**: k变量筛选（严格递增：两指标同时超过所有子组合最优值）
4. **终止条件**: 某阶段无任何组合满足筛选条件

### 1.2 问题分析

| 问题 | 描述 | 影响 |
|------|------|------|
| **大量内嵌Python代码** | 每个脚本包含约400行heredoc内嵌的Python代码 | 无IDE支持、难以调试、无法单独测试 |
| **高度重复** | 脚本90%代码相同，仅配置和参数映射不同 | 维护成本高、容易不一致 |
| **`extract_metrics_from_summary`重复4次** | 同一函数在每个脚本中出现4次 | 修改需同步多处 |
| **扩展困难** | 添加新策略需复制整个1100行脚本 | 代码膨胀、易出错 |

---

## 2. 重构目标与成果

### 2.1 核心目标

1. **消除重复**: 将90%的重复代码抽取为共享模块 ✅
2. **关注点分离**: Python处理数据逻辑，Bash处理流程控制 ✅
3. **可测试性**: Python模块可独立单元测试 ✅
4. **可扩展性**: 添加新策略只需新增策略脚本（~250行） ✅

### 2.2 量化成果

| 指标 | 重构前 | 重构后 | 改进 |
|------|--------|--------|------|
| mega_test_kama_greedy_parallel.sh | 961行 | 265行 | -72% |
| mega_test_macd_greedy_parallel.sh | 915行 | 277行 | -70% |
| mega_test_sma_enhanced_greedy_parallel.sh | 1142行 | 267行 | -77% |
| mega_test_kama_greedy.sh | 969行 | 232行 | -76% |
| mega_test_macd_greedy.sh | 970行 | 243行 | -75% |
| **重复代码率** | ~90% | <10% | -80%+ |

---

## 3. 实现架构

### 3.1 目录结构

```
greedy_search/                    # Python模块（项目根目录下）
├── __init__.py                   # 模块入口
├── metrics_extractor.py          # 指标提取（从CSV提取标准化指标）
├── candidate_filter.py           # 候选筛选（阶段1 OR逻辑、阶段k严格递增）
├── combo_generator.py            # 组合生成（k变量组合）
├── cli.py                        # CLI入口（供Shell脚本调用）
└── greedy_lib.sh                 # Shell公共函数库

# 策略脚本（项目根目录下）
mega_test_kama_greedy_parallel.sh     # KAMA策略并行版
mega_test_macd_greedy_parallel.sh     # MACD策略并行版
mega_test_sma_enhanced_greedy_parallel.sh  # SMA策略并行版
mega_test_kama_greedy.sh              # KAMA策略串行版
mega_test_macd_greedy.sh              # MACD策略串行版
```

### 3.2 模块职责

#### Python模块

| 模块 | 职责 | 主要函数 |
|------|------|----------|
| `metrics_extractor.py` | 从global_summary CSV提取标准化指标 | `extract_metrics_from_csv()`, `find_global_summary()` |
| `candidate_filter.py` | 阶段1 OR逻辑筛选、阶段k严格递增筛选 | `filter_stage1_candidates()`, `filter_stage_k_candidates()` |
| `combo_generator.py` | 从k-1阶段候选生成k变量组合 | `generate_k_combinations()` |
| `cli.py` | 提供命令行接口供Shell脚本调用 | `extract_baseline`, `filter_stage1`, `filter_stage_k`, `gen_combos` |

#### Shell公共函数库 (`greedy_lib.sh`)

| 函数 | 职责 |
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
| `greedy_parallel_run_tasks` | 并发任务执行框架 |
| `greedy_collect_results` | 收集实验结果 |
| `greedy_collect_only_mode` | 仅收集模式 |
| `greedy_print_final_stats` | 打印最终统计 |

### 3.3 CLI调用方式

```bash
# 提取Baseline指标
python3 -m greedy_search.cli extract_baseline <backtest_dir> <output_json>

# 阶段1筛选
python3 -m greedy_search.cli filter_stage1 <backtest_dir> <candidates_dir> <core_options...>

# 阶段k筛选
python3 -m greedy_search.cli filter_stage_k <backtest_dir> <candidates_dir> <k>

# 生成k变量组合
python3 -m greedy_search.cli gen_combos <candidates_dir> <k>
```

### 3.4 策略脚本结构

重构后每个策略脚本精简为3部分：

```bash
#!/bin/bash
# 1. 加载公共函数库
source "${SCRIPT_DIR}/greedy_search/greedy_lib.sh"

# 2. 策略特定配置（~40行）
STRATEGY_NAME="kama_cross"
POOL_PATH="..."
declare -a CORE_OPTIONS=(...)
# 固定超参定义...

# 3. 策略特定实验执行函数（~60行）
run_single_experiment() {
    local exp_name=$1
    local options_str=$2
    # 构建命令行，添加策略特定参数映射
    ...
}

# 4. 主执行流程（~50行）
main() {
    greedy_init_dirs "$OUTPUT_BASE_DIR"
    greedy_run_stage0 "$STRATEGY_NAME"
    greedy_run_stage1_parallel "$PARALLEL_JOBS" CORE_OPTIONS
    # 循环执行阶段k...
    greedy_collect_results
}
```

---

## 4. 调用方式

```bash
# 并行版本（推荐）
./mega_test_kama_greedy_parallel.sh -j 8      # KAMA策略，8并发
./mega_test_macd_greedy_parallel.sh -j 5      # MACD策略，5并发
./mega_test_sma_enhanced_greedy_parallel.sh   # SMA策略，默认3并发

# 串行版本
./mega_test_kama_greedy.sh                    # KAMA策略串行
./mega_test_macd_greedy.sh                    # MACD策略串行

# 仅收集模式
./mega_test_kama_greedy_parallel.sh --collect-only <实验目录>
```

---

## 5. Code Review 修复记录

### 5.1 第一次 Code Review（2025-12-07）

| 问题 | 状态 | 修复方案 |
|------|------|----------|
| 并发任务分发组合拆分bug | ✅ 已修复 | 使用 `xargs -0`（NUL分隔符）避免空格导致的拆分问题 |
| baseline缺列会报错 | ✅ 已修复 | 对缺失值兜底为 `-inf` 并打印警告 |
| 并发失败未阻断流程 | ✅ 已修复 | 检测 `greedy_parallel_run_tasks` 返回值，失败时终止 |
| 重构未验证 | ⏳ 待验证 | 等待用户验证 |

---

## 6. 测试验证

### 6.1 验证要点

1. **并发执行正确性**: 多选项组合（如 `k2_enable-adx-filter_enable-slope-filter`）应作为整体执行
2. **筛选逻辑正确性**: 阶段1 OR逻辑、阶段k严格递增逻辑
3. **失败处理**: 回测失败时应终止流程，不在不完整数据上继续筛选
4. **结果一致性**: 重构后输出与原脚本一致

### 6.2 回归测试

对比重构前后的输出：
- Baseline指标提取结果
- 各阶段候选池JSON (`candidates_k1.json`, `candidates_k2.json`, ...)
- 最终汇总CSV (`mega_test_greedy_summary.csv`)

---

## 7. 附录

### 7.1 指标列名映射

```python
STANDARD_COL_MAPPING = {
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

### 7.2 参考资料

- 策略脚本: `mega_test_*_greedy*.sh`
- 结果收集脚本: `scripts/collect_mega_test_results.sh`
- 回测入口: `run_backtest.sh`
