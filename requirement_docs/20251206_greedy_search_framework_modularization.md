# 贪心搜索实验框架模块化重构

## 元信息

| 字段 | 值 |
|------|-----|
| 文档编号 | 20251206_greedy_search_framework_modularization |
| 创建日期 | 2025-12-06 |
| 状态 | 📋 待开发 |
| 优先级 | 中 |
| 影响范围 | `mega_test_*_greedy_parallel.sh` 系列脚本 |

---

## 1. 背景

### 1.1 现状描述

当前项目中存在两个贪心搜索实验脚本：
- `mega_test_kama_greedy_parallel.sh` (1107行)
- `mega_test_macd_greedy_parallel.sh` (1118行)

这两个脚本实现了相同的贪心搜索算法：
1. **阶段0**: 测试Baseline（无任何选项）
2. **阶段1**: 单变量筛选（OR逻辑：sharpe_mean > base OR sharpe_median > base）
3. **阶段k**: k变量筛选（严格递增：两指标同时超过所有子组合最优值）
4. **终止条件**: 某阶段无任何组合满足筛选条件

### 1.2 问题分析

| 问题 | 描述 | 影响 |
|------|------|------|
| **大量内嵌Python代码** | 每个脚本包含约400行heredoc内嵌的Python代码 | 无IDE支持、难以调试、无法单独测试 |
| **高度重复** | 两脚本90%代码相同，仅配置和参数映射不同 | 维护成本高、容易不一致 |
| **`extract_metrics_from_summary`重复4次** | 同一函数在每个脚本中出现4次（阶段0、阶段1、阶段k筛选各一次） | 修改需同步多处 |
| **扩展困难** | 添加新策略需复制整个1100行脚本 | 代码膨胀、易出错 |
| **Bash与Python混合** | 业务逻辑分散在两种语言中 | 职责不清、测试困难 |

### 1.3 代码重复分析

```
mega_test_kama_greedy_parallel.sh vs mega_test_macd_greedy_parallel.sh
────────────────────────────────────────────────────────────────────────
相同部分 (~90%):
  - 颜色定义和打印函数 (行 94-133)
  - create_metadata 函数 (行 136-165)
  - run_stage0_baseline 函数框架 (行 268-402)
  - run_stage1_single_var 函数框架 (行 408-599)
  - run_stage_k 函数框架 (行 605-879)
  - collect_only_mode 函数 (行 886-971)
  - main 函数框架 (行 973-1093)
  - Python extract_metrics_from_summary 函数 (重复4次，每次约50行)
  - Python filter_stage1 逻辑 (约100行)
  - Python filter_stage_k 逻辑 (约120行)
  - Python gen_combinations 逻辑 (约40行)

不同部分 (~10%):
  - 策略名称 (kama_cross vs macd_cross)
  - CORE_OPTIONS 数组定义
  - 固定超参变量定义
  - run_single_experiment 中的参数映射逻辑
  - 路径配置 (POOL_PATH, OUTPUT_BASE_DIR 等)
```

---

## 2. 重构目标

### 2.1 核心目标

1. **消除重复**: 将90%的重复代码抽取为共享模块
2. **关注点分离**: Python处理数据逻辑，Bash处理流程控制
3. **配置驱动**: 策略特定配置集中到YAML文件
4. **可测试性**: Python模块可独立单元测试
5. **可扩展性**: 添加新策略只需新增配置文件

### 2.2 量化目标

| 指标 | 重构前 | 重构后目标 |
|------|--------|-----------|
| 总代码行数 | 2225行 | ~850行 |
| 重复代码率 | ~90% | <5% |
| 添加新策略成本 | 复制1100行 | 新增~50行YAML |
| Python代码可测试性 | 无 | 100%可测试 |

---

## 3. 技术方案

### 3.1 目标架构

```
scripts/greedy_search/
├── greedy_runner.sh              # 主入口脚本 (~200行)
├── lib/
│   ├── utils.sh                  # 打印/颜色函数 (~50行)
│   └── parallel.sh               # 并发执行逻辑 (~100行)
├── python/
│   ├── __init__.py
│   ├── metrics.py                # 指标提取 (~80行)
│   ├── filters.py                # 候选筛选 (~150行)
│   ├── combinations.py           # 组合生成 (~50行)
│   ├── config_loader.py          # YAML配置加载 (~100行)
│   └── cli.py                    # CLI入口 (~70行)
└── configs/
    ├── kama.yaml                 # KAMA策略配置 (~80行)
    └── macd.yaml                 # MACD策略配置 (~80行)

# 向后兼容wrapper
mega_test_kama_greedy_parallel.sh  → 调用 scripts/greedy_search/greedy_runner.sh --config configs/kama.yaml
mega_test_macd_greedy_parallel.sh  → 调用 scripts/greedy_search/greedy_runner.sh --config configs/macd.yaml
```

### 3.2 YAML配置格式设计

```yaml
# configs/kama.yaml
strategy:
  name: kama_cross
  description: "KAMA策略贪心筛选超参组合测试"

experiment:
  type: "mega_test_greedy"
  version: "2.0"
  pool_path: "experiment/etf/selector_score/single_primary/single_liquidity_score_pool_2019_2021.csv"
  data_dir: "data/chinese_etf/daily"
  temp_params_path: "config/test/kama_single_liquidity_score_strategy_params.json"
  output_base_dir: "experiment/etf/selector_score/single_primary/mega_test_kama_{timestamp}"
  start_date: "20220102"
  end_date: "20240102"
  parallel_jobs: 8

core_options:
  - enable-efficiency-filter
  - enable-slope-confirmation
  - enable-slope-filter
  - enable-adx-filter
  - enable-volume-filter
  - enable-confirm-filter
  - enable-loss-protection
  - enable-trailing-stop
  - enable-atr-stop

fixed_params:
  adx_period: 14
  adx_threshold: 25.0
  volume_period: 20
  volume_ratio: 1.2
  slope_lookback: 5
  confirm_bars: 2
  max_consecutive_losses: 3
  pause_bars: 10
  trailing_stop_pct: 0.05
  atr_period: 14
  atr_multiplier: 2.5
  min_efficiency_ratio: 0.3
  min_slope_periods: 3

# 选项到CLI参数的映射规则
option_param_mapping:
  enable-adx-filter:
    - "--adx-period {adx_period}"
    - "--adx-threshold {adx_threshold}"
  enable-volume-filter:
    - "--volume-period {volume_period}"
    - "--volume-ratio {volume_ratio}"
  enable-slope-filter:
    - "--slope-lookback {slope_lookback}"
  enable-loss-protection:
    - "--max-consecutive-losses {max_consecutive_losses}"
    - "--pause-bars {pause_bars}"
  enable-trailing-stop:
    - "--trailing-stop-pct {trailing_stop_pct}"
  enable-atr-stop:
    - "--atr-period {atr_period}"
    - "--atr-multiplier {atr_multiplier}"
  enable-confirm-filter:
    - "--confirm-bars {confirm_bars}"
  enable-efficiency-filter:
    - "--min-efficiency-ratio {min_efficiency_ratio}"
  enable-slope-confirmation:
    - "--min-slope-periods {min_slope_periods}"
```

### 3.3 Python模块设计

#### 3.3.1 metrics.py - 指标提取模块

```python
"""指标提取模块 - 统一处理global_summary的指标提取逻辑"""

from typing import Dict, Optional
import pandas as pd

# 列名映射（支持中英文）
COLUMN_MAPPING = {
    'sharpe_mean': ['夏普-均值', 'Sharpe Ratio Mean'],
    'sharpe_median': ['夏普-中位数', 'Sharpe Ratio Median'],
    'win_rate_mean': ['胜率-均值(%)', 'Win Rate [%] Mean'],
    'win_rate_median': ['胜率-中位数(%)', 'Win Rate [%] Median'],
    'pl_ratio_mean': ['盈亏比-均值', 'Profit/Loss Ratio Mean'],
    'pl_ratio_median': ['盈亏比-中位数', 'Profit/Loss Ratio Median'],
    'trades_mean': ['交易次数-均值', '# Trades Mean'],
    'trades_median': ['交易次数-中位数', '# Trades Median'],
}

def extract_metrics_from_summary(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """从global_summary DataFrame提取所有指标（当前重复4次的函数，统一实现）"""
    # ... 实现逻辑
    pass

def extract_metrics_from_path(summary_path: str) -> Dict[str, Optional[float]]:
    """从文件路径提取指标"""
    df = pd.read_csv(summary_path, encoding='utf-8-sig')
    return extract_metrics_from_summary(df)
```

#### 3.3.2 filters.py - 筛选逻辑模块

```python
"""筛选逻辑模块 - 实现阶段1和阶段k的候选筛选"""

from typing import List, Dict
from .metrics import extract_metrics_from_path

def filter_stage1(
    backtest_dir: str,
    candidates_dir: str,
    core_options: List[str],
    baseline_metrics: Dict
) -> List[Dict]:
    """阶段1筛选：OR逻辑"""
    pass

def filter_stage_k(
    backtest_dir: str,
    candidates_dir: str,
    k: int,
    prev_candidates: List[Dict]
) -> List[Dict]:
    """阶段k筛选：严格递增"""
    pass
```

#### 3.3.3 cli.py - 命令行入口

```python
"""CLI入口 - 提供Bash调用的命令行接口"""

import click

@click.group()
def cli():
    pass

@cli.command()
@click.option('--backtest-dir', required=True)
@click.option('--candidates-dir', required=True)
def extract_baseline(backtest_dir, candidates_dir):
    """提取Baseline指标"""
    pass

@cli.command()
@click.option('--backtest-dir', required=True)
@click.option('--candidates-dir', required=True)
@click.option('--core-options', required=True)
def filter_stage1(backtest_dir, candidates_dir, core_options):
    """执行阶段1筛选"""
    pass

@cli.command()
@click.option('--config', required=True)
def load_config(config):
    """加载配置并输出为Bash变量"""
    pass

if __name__ == '__main__':
    cli()
```

### 3.4 Bash框架设计

#### 3.4.1 lib/utils.sh - 工具函数库

```bash
#!/bin/bash
# 颜色定义和打印函数

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

print_header() { echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n${BLUE}  $1${NC}\n${BLUE}═══════════════════════════════════════════════════════════════════${NC}"; }
print_stage() { echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n${MAGENTA}  $1${NC}\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }
print_section() { echo -e "\n${CYAN}▶ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
```

#### 3.4.2 greedy_runner.sh - 主入口脚本

```bash
#!/bin/bash
# 贪心搜索实验框架 - 通用入口

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/utils.sh"
source "${SCRIPT_DIR}/lib/parallel.sh"

# 解析参数
CONFIG_FILE=""
PARALLEL_JOBS=""
COLLECT_ONLY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --config) CONFIG_FILE="$2"; shift 2 ;;
        -j|--jobs) PARALLEL_JOBS="$2"; shift 2 ;;
        --collect-only) COLLECT_ONLY="$2"; shift 2 ;;
        *) print_error "未知参数: $1"; exit 1 ;;
    esac
done

# 加载配置（Python输出Bash变量）
eval $(python3 -m scripts.greedy_search.python.cli load-config "$CONFIG_FILE")

# 覆盖并发度（如果命令行指定）
[ -n "$PARALLEL_JOBS" ] && PARALLEL_JOBS_CONFIG=$PARALLEL_JOBS

# 执行流程
if [ -n "$COLLECT_ONLY" ]; then
    collect_only_mode "$COLLECT_ONLY"
else
    run_full_experiment
fi
```

### 3.5 调用方式对比

```bash
# 重构前：直接运行策略特定脚本
./mega_test_kama_greedy_parallel.sh -j 8
./mega_test_macd_greedy_parallel.sh -j 5

# 重构后：通过配置驱动
./scripts/greedy_search/greedy_runner.sh --config configs/kama.yaml -j 8
./scripts/greedy_search/greedy_runner.sh --config configs/macd.yaml -j 5

# 重构后：向后兼容wrapper（可选保留）
./mega_test_kama_greedy_parallel.sh -j 8  # 内部转发到 greedy_runner.sh
```

---

## 4. 实现计划

### Phase 1: Python模块抽取 (预计 ~300行新增)

**任务**:
1. 创建 `scripts/greedy_search/python/` 目录结构
2. 实现 `metrics.py` - 统一指标提取逻辑
3. 实现 `filters.py` - 阶段1和阶段k筛选逻辑
4. 实现 `combinations.py` - 组合生成逻辑
5. 实现 `cli.py` - 命令行入口

**验收标准**:
- [ ] 所有Python模块可独立运行
- [ ] 单元测试覆盖核心函数
- [ ] 输出与原heredoc代码一致

### Phase 2: Bash库函数抽取 (预计 ~150行新增)

**任务**:
1. 创建 `scripts/greedy_search/lib/` 目录
2. 抽取 `utils.sh` - 打印和颜色函数
3. 抽取 `parallel.sh` - 并发执行逻辑
4. 抽取 `experiment.sh` - 实验执行函数模板

**验收标准**:
- [ ] 库函数可被source引入
- [ ] 保持原有功能不变

### Phase 3: YAML配置系统 (预计 ~200行新增)

**任务**:
1. 设计YAML配置schema
2. 实现 `config_loader.py` - 配置加载和验证
3. 创建 `configs/kama.yaml`
4. 创建 `configs/macd.yaml`
5. 实现配置到Bash变量的转换

**验收标准**:
- [ ] 配置文件可正确加载
- [ ] 参数映射逻辑正确
- [ ] 支持配置验证

### Phase 4: 主框架重构 (预计 ~200行)

**任务**:
1. 实现 `greedy_runner.sh` 主入口
2. 集成Python CLI调用
3. 实现阶段流程控制
4. 实现结果收集逻辑

**验收标准**:
- [ ] 完整实验流程可运行
- [ ] 输出结果与原脚本一致
- [ ] 支持 `--collect-only` 模式

### Phase 5: 向后兼容与清理

**任务**:
1. 创建兼容wrapper脚本
2. 更新文档和CLAUDE.md
3. 添加使用示例
4. 可选：移除旧脚本或标记deprecated

**验收标准**:
- [ ] 原有命令行调用方式仍然有效
- [ ] 文档更新完整
- [ ] 无功能回归

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Python CLI调用开销 | 每阶段额外启动Python进程 | 可接受，每阶段仅调用1-2次 |
| YAML解析依赖 | 需要PyYAML | 项目已有该依赖 |
| 向后兼容性 | 现有自动化脚本可能失效 | 保留wrapper脚本 |
| 配置格式演进 | 未来可能需要扩展 | 设计时预留扩展字段 |

---

## 6. 测试策略

### 6.1 单元测试

```python
# tests/test_greedy_search/test_metrics.py
def test_extract_metrics_summary_format():
    """测试汇总格式的指标提取"""
    pass

def test_extract_metrics_detail_format():
    """测试详细格式的指标提取"""
    pass

# tests/test_greedy_search/test_filters.py
def test_filter_stage1_or_logic():
    """测试阶段1的OR逻辑筛选"""
    pass

def test_filter_stage_k_strict_increasing():
    """测试阶段k的严格递增筛选"""
    pass
```

### 6.2 集成测试

```bash
# 使用小规模测试数据验证完整流程
./scripts/greedy_search/greedy_runner.sh \
    --config configs/test_small.yaml \
    -j 2
```

### 6.3 回归测试

对比重构前后的输出：
- Baseline指标提取结果
- 各阶段候选池JSON
- 最终汇总CSV

---

## 7. 附录

### 7.1 当前重复代码统计

| 代码块 | KAMA脚本位置 | MACD脚本位置 | 行数 |
|--------|-------------|-------------|------|
| 颜色定义 | 94-101 | 99-106 | 8 |
| print_* 函数 | 107-133 | 111-138 | 27 |
| create_metadata | 136-161 | 140-165 | 26 |
| extract_metrics (阶段0) | 315-392 | 326-403 | 78 |
| extract_metrics (阶段1) | 466-513 | 477-524 | 48 |
| filter_stage1 逻辑 | 453-591 | 464-602 | 139 |
| gen_combinations | 627-670 | 638-681 | 44 |
| extract_metrics (阶段k) | 722-780 | 733-791 | 59 |
| filter_stage_k 逻辑 | 708-869 | 719-880 | 162 |
| collect_only_mode | 886-971 | 897-982 | 86 |
| main函数框架 | 973-1093 | 984-1104 | 121 |

**总重复行数**: ~798行 × 2 = ~1596行（占总代码72%）

### 7.2 参考资料

- 原脚本: `mega_test_kama_greedy_parallel.sh`, `mega_test_macd_greedy_parallel.sh`
- 结果收集脚本: `scripts/collect_mega_test_results.sh`
- 回测入口: `run_backtest.sh`
