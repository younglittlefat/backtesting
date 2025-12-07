# 不同打分体系ETF池回测对比实验

## 1. 概述

使用固定的KAMA策略配置，对比不同打分体系筛选出的ETF池的回测表现，评估哪种打分维度选出的标的更适合趋势跟踪策略。

**策略配置**: `k3_enable-adx-filter_enable-atr-stop_enable-slope-confirmation`（固定参数，无优化）

## 2. 快速开始

```bash
# 激活环境
conda activate backtesting

# 运行所有已发现的 pool（自动发现机制）
cd /mnt/d/git/backtesting
python -m experiment.etf.selector_score.pool_comparison.cli

# 指定特定 pool
python -m experiment.etf.selector_score.pool_comparison.cli \
  --pools single_adx_score single_liquidity_score

# 包含基准池对比
python -m experiment.etf.selector_score.pool_comparison.cli --include-baseline

# 并行执行（4个worker）
python -m experiment.etf.selector_score.pool_comparison.cli --max-workers 4

# 仅收集已有结果（跳过回测）
python -m experiment.etf.selector_score.pool_comparison.cli \
  --collect-only --output-dir results/pool_comparison_xxx
```

## 3. Pool 扩展性设计

### 3.1 自动发现机制（推荐，零配置）

系统会自动扫描 `pool/` 目录，发现符合命名约定的 CSV 文件：

```
命名约定: single_{dimension}_pool*.csv（不含 _all_scores）

示例:
  single_volatility_pool_2019_2021.csv  → dimension = volatility
  single_rsi_score_pool.csv             → dimension = rsi_score
```

**添加新 Pool 的步骤**:
1. 将 CSV 文件放入 `pool/` 目录
2. 确保命名符合 `single_{dimension}_pool*.csv` 格式
3. 完成！系统自动发现

**可选**: 在 `config.py` 的 `DIMENSION_LABELS` 中添加中文描述：
```python
DIMENSION_LABELS = {
    'volatility': '波动率',
    'rsi_score': 'RSI强度',
    # ...
}
```

### 3.2 当前可用 Pool

| Pool名称 | 打分维度 | 来源 |
|---------|---------|------|
| single_adx_score | ADX趋势强度 | 静态配置 |
| single_liquidity_score | 流动性 | 静态配置 |
| single_price_efficiency | 价格效率 | 静态配置 |
| single_trend_consistency | 趋势一致性 | 静态配置 |
| single_momentum_3m | 3个月动量 | 静态配置 |
| single_momentum_12m | 12个月动量 | 静态配置 |
| single_core_trend_excess_return_20d | 20日核心趋势超额收益 | 自动发现 |
| single_core_trend_excess_return_60d | 60日核心趋势超额收益 | 自动发现 |
| single_idr | 日内波动比率(IDR) | 自动发现 |
| single_trend_quality | 趋势质量 | 自动发现 |
| single_volume | 成交量 | 自动发现 |
| baseline_composite | 综合评分基准 | 需 `--include-baseline` |

### 3.3 运行时注册（非标准命名）

```python
from experiment.etf.selector_score.pool_comparison import register_custom_pool

register_custom_pool(
    name='my_custom_pool',
    file_path='/path/to/custom_pool.csv',
    dimension='自定义维度'
)
```

### 3.4 优先级

`runtime > static > discovered`

## 4. 配置详情

### 4.1 固定 KAMA 策略参数

```python
STRATEGY_CONFIG = {
    'strategy': 'kama_cross',
    'kama_period': 20,
    'kama_fast': 2,
    'kama_slow': 30,
    'enable_adx_filter': True,
    'adx_period': 14,
    'adx_threshold': 25.0,
    'enable_atr_stop': True,
    'atr_period': 14,
    'atr_multiplier': 2.5,
    'enable_slope_confirmation': True,
    'min_slope_periods': 3,
}
```

### 4.2 回测时间段

- **开始日期**: 2022-01-02
- **结束日期**: 2024-01-02
- **数据目录**: `data/chinese_etf/daily`

### 4.3 评估指标

| 指标 | 说明 | 列名 |
|------|------|------|
| 收益率 | 年化收益率 | `return_mean`, `return_median` |
| 夏普比率 | 风险调整收益 | `sharpe_mean`, `sharpe_median` |
| 最大回撤 | 最大资金回撤 | `max_dd_mean`, `max_dd_median` |
| 胜率 | 盈利交易占比 | `win_rate_mean`, `win_rate_median` |
| 盈亏比 | 平均盈利/平均亏损 | `pl_ratio_mean`, `pl_ratio_median` |
| 交易次数 | 总交易次数 | `trades_mean`, `trades_median` |

## 5. 模块结构

```
experiment/etf/selector_score/
├── POOL_COMPARISON_PLAN.md          # 本文档
├── pool/                             # Pool CSV 文件目录
│   ├── single_adx_score_pool_2019_2021.csv
│   ├── single_xxx_pool_*.csv        # 自动发现
│   └── ...
├── pool_comparison/                  # 核心模块
│   ├── __init__.py                  # 模块导出
│   ├── config.py                    # 配置管理 + 自动发现
│   ├── runner.py                    # 回测执行器
│   ├── collector.py                 # 结果收集器
│   ├── analyzer.py                  # 统计分析
│   └── cli.py                       # 命令行入口
├── run_pool_comparison.sh           # Shell 入口脚本
└── results/                         # 实验结果
    └── pool_comparison_<timestamp>/
        ├── backtests/               # 各 pool 的回测结果
        ├── pool_comparison_summary.csv
        ├── pool_comparison_detail.csv
        └── .experiment_metadata.json
```

## 6. CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--pools` | 指定 pool 名称列表 | 所有已发现 pool |
| `--include-baseline` | 包含基准池对比 | False |
| `--output-dir` | 输出目录 | 自动生成时间戳目录 |
| `--collect-only` | 仅收集结果，跳过回测 | False |
| `--max-workers` | 并行执行数 | 1（串行） |
| `--timeout` | 单个 pool 超时（秒） | 1800 |
| `--retry` | 失败重试次数 | 1 |
| `--skip-existing` | 跳过已有结果的 pool | False |
| `--verbose` | 详细输出 | False |
| `--validate-only` | 仅验证配置 | False |

## 7. 输出文件

### pool_comparison_summary.csv

每个 pool 一行的汇总统计：

```csv
pool_name,scoring_dimension,return_mean,return_median,sharpe_mean,sharpe_median,...
single_adx_score,ADX趋势强度,15.76,13.48,0.65,0.76,...
```

### pool_comparison_detail.csv

每只 ETF 一行的详细结果：

```csv
pool_name,ts_code,name,return,sharpe,max_dd,win_rate,pl_ratio,trades
single_adx_score,159752.SZ,新能源龙头ETF,25.3,1.2,-8.5,65.0,3.2,5
```

### .experiment_metadata.json

实验元数据（可复现性）：

```json
{
  "timestamp": "2024-12-07T10:00:00",
  "git_commit": "abc12345",
  "strategy_config": {...},
  "pools": {
    "single_adx_score": {
      "file": "pool/single_adx_score_pool_2019_2021.csv",
      "md5": "abc123...",
      "dimension": "ADX趋势强度"
    }
  }
}
```

## 8. API 参考

```python
from experiment.etf.selector_score.pool_comparison import (
    # 配置
    STRATEGY_CONFIG,          # 策略参数
    DIMENSION_LABELS,         # 维度中文标签
    get_pool_configs,         # 获取所有 pool 配置
    get_all_pool_names,       # 获取所有 pool 名称
    discover_pools,           # 手动触发自动发现
    register_custom_pool,     # 运行时注册
    validate_config,          # 配置验证

    # 执行
    run_single_pool,          # 执行单个 pool 回测
    run_all_pools,            # 批量执行

    # 收集
    collect_pool_results,     # 收集单个 pool 结果
    collect_all_results,      # 收集所有结果

    # 分析
    compute_pool_stats,       # 计算统计量
    compare_pools,            # 跨 pool 对比
    generate_reports,         # 生成报告
)
```

## 9. 设计决策记录

| 决策 | 说明 | 来源 |
|------|------|------|
| 不使用 `--optimize` | 固定 KAMA 参数确保公平对比 | 评审意见 |
| 复用 `greedy_search.metrics_extractor` | 避免重复解析逻辑 | 评审意见 |
| BOM 编码处理 | `encoding='utf-8-sig'` 读取中文 CSV | 评审意见 |
| 基准池对比 | `--include-baseline` 启用 | 评审意见 |
| 元数据记录 | git commit、文件 MD5 | 评审意见 |
| 并行执行 | `--max-workers` 支持 | 评审意见 |
| 自动发现机制 | 零配置扩展新 pool | 扩展性需求 |
