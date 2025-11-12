# KAMA策略超参数网格搜索实验设计文档

**实验日期**: 2025-11-11
**实验目标**: 通过系统性网格搜索优化KAMA自适应均线策略的信号增强（过滤器）和止损保护参数，提升风险调整后收益
**实验类型**: 超参数优化实验 + 特征组合实验

---

## 📋 目录

1. [背景与动机](#1-背景与动机)
2. [实验设计](#2-实验设计)
3. [评估指标](#3-评估指标)
4. [技术实现](#4-技术实现)
5. [预期成果](#5-预期成果)
6. [风险与缓解](#6-风险与缓解)

---

## 1. 背景与动机

### 1.1 策略概述

**KAMA策略** (`strategies/kama_cross.py`) 基于Kaufman自适应移动平均线，核心特性：
- **自适应性**: 根据市场效率自动调整响应速度
- **趋势期**: 快速跟随价格变化，减少滞后
- **震荡期**: 平滑滤波，减少假信号
- **已实现功能**: Phase 1-3（基础信号、过滤器、止损保护）✅

### 1.2 策略架构

```python
KamaCrossStrategy(BaseEnhancedStrategy):
    # Phase 1: KAMA特有过滤器
    - enable_efficiency_filter: 效率比率过滤（default: True）
    - enable_slope_confirmation: KAMA斜率确认（default: True）

    # Phase 2: 通用信号过滤器
    - enable_slope_filter: 价格斜率过滤
    - enable_adx_filter: ADX趋势强度过滤 ⭐推荐
    - enable_volume_filter: 成交量确认过滤 ⭐推荐
    - enable_confirm_filter: 持续确认过滤

    # Phase 3: 止损保护
    - enable_loss_protection: 连续止损保护 ⭐推荐
    - max_consecutive_losses: 连续亏损阈值（default: 3）
    - pause_bars: 暂停K线数（default: 10）
```

### 1.3 实验必要性

**当前问题**:
1. ❓ **过滤器效果未验证**: 6种过滤器各自对KAMA策略的增益未知
2. ❓ **最优组合未知**: 哪些过滤器组合效果最佳？
3. ❓ **止损参数未优化**: 连续止损保护的参数是否适配KAMA策略？
4. ❓ **协同效应未探索**: 过滤器 + 止损保护的组合效果如何？

**实验目标**:
1. **量化各过滤器的增益**: 相比Baseline，各过滤器对夏普比率/回撤的改进
2. **发现最优过滤器组合**: 基于实验数据选择最佳特征组合
3. **优化止损参数**: 为KAMA策略找到最佳连续止损保护配置
4. **验证协同效应**: 测试过滤器 + 止损的综合表现

### 1.4 跨策略对比实验

| 策略 | 实验 | Baseline夏普 | 止损保护效果 | 核心结论 |
|------|------|-------------|-------------|----------|
| **SMA** | `experiment/etf/sma_cross/stop_loss_comparison/` | 0.61 | **+75.4%** | Loss Protection高效 |
| **MACD** | `experiment/etf/macd_cross/grid_search_stop_loss/` | 0.73 | **+28.8%** | Combined方案最优 |
| **KAMA** | `experiment/etf/kama_cross/hyperparameter_search/` | **1.69** | **-0.7%** | 止损保护无效 |

**关键洞察** ⭐:
- **止损保护效果 ∝ 1/基础信号质量**
- KAMA自适应特性已内置连续亏损保护
- **策略选择比参数优化更重要**

---

## 🎯 实验结果总结 ⭐

### Phase 1结果 ✅ (已完成)
- **Baseline夏普**: 1.69（优异！远超SMA 0.61和MACD 0.6）
- **最佳过滤器**: ADX（夏普1.68，回撤-4.71%）
- **最佳组合**: ADX+Slope（夏普1.58，回撤-4.38%最优）
- **Confirm过滤器**: ❌ 不适用KAMA策略（与自适应特性冲突）

### Phase 2结果 ✅ (已完成)
- **关键发现**: **止损保护对KAMA策略无效**（-0.7%夏普变化）
- **对比**: SMA (+75%)、MACD (+28.8%) vs KAMA (-0.7%)
- **根本原因**: KAMA自适应特性已内置连续亏损保护机制
- **推荐**: 使用Baseline KAMA，**不启用止损保护**

### 最终推荐配置 ⭐
```bash
# ✅ 推荐配置（最优性价比）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  --data-dir data/chinese_etf/daily
# 预期：夏普1.69，收益34.63%，回撤-5.27%

# ❌ 不推荐：--enable-loss-protection (无效果)
```

---

## 2. 实验设计

### 2.1 测试配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **基础策略** | `kama_cross` | KAMA自适应均线交叉策略 |
| **测试标的池** | `results/trend_etf_pool.csv` | 20只趋势型中国ETF |
| **数据目录** | `data/chinese_etf/daily` | 日线级别数据 |
| **测试周期** | 2023-11至2025-11 | 约2年历史数据（与SMA/MACD实验一致） |
| **基准命令** | `./run_backtest.sh --stock-list results/trend_etf_pool.csv -t kama_cross --data-dir data/chinese_etf/daily` | 不启用优化（KAMA默认参数） |

**注意**: KAMA策略**不启用参数优化**（无`--optimize`），使用固定参数：
- `kama_period=20, kama_fast=2, kama_slow=30`（业界标准配置）
- 优化重点：信号增强和止损保护参数

### 2.2 实验架构

```
实验分为2个阶段（已完成）：

✅ Phase 1: 信号过滤器组合优化（200次回测）
✅ Phase 2: 止损保护参数优化（1020次回测）

❌ Phase 3: 跟踪止损（已取消 - 基于Phase 2结论）
```

#### Phase 1: 信号过滤器组合（Signal Filters）
Dimension 3: 交叉验证（Filter + Stop Loss 组合）
```

### 2.3 Dimension 1: 信号过滤器实验

#### Phase 1A: Baseline（对照组）

**配置**: 不启用任何可选过滤器

```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  --data-dir data/chinese_etf/daily
```

**实验次数**: 20只标的 × 1配置 = **20次**
**预期耗时**: ~5-10分钟

---

#### Phase 1B: 单一过滤器测试（Single Filter）

**目标**: 测试每个过滤器的独立效果

| 过滤器 | 启用参数 | 说明 |
|--------|----------|------|
| **ADX趋势强度** | `--enable-adx-filter` | 过滤弱趋势环境 |
| **成交量确认** | `--enable-volume-filter` | 成交量放大确认 |
| **价格斜率** | `--enable-slope-filter` | 过滤震荡信号 |
| **持续确认** | `--enable-confirm-filter` | 多K线持续确认 |

**实验次数**: 20只标的 × 4种过滤器 = **80次**
**预期耗时**: ~20-30分钟

**示例命令**:
```bash
# ADX过滤器
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  --enable-adx-filter \
  --data-dir data/chinese_etf/daily
```

---

#### Phase 1C: 双过滤器组合（Dual Filters）

**目标**: 测试常用的两两组合

**精选组合**（基于经验推荐）:

| 组合 | 过滤器1 | 过滤器2 | 理论优势 |
|------|---------|---------|----------|
| **Combo 1** ⭐ | ADX趋势强度 | 成交量确认 | 趋势+量价配合 |
| **Combo 2** | ADX趋势强度 | 价格斜率 | 双重趋势确认 |
| **Combo 3** | 成交量确认 | 持续确认 | 量价+时间维度 |
| **Combo 4** | 价格斜率 | 持续确认 | 方向+持续性 |

**实验次数**: 20只标的 × 4种组合 = **80次**
**预期耗时**: ~20-30分钟

**示例命令**:
```bash
# Combo 1: ADX + Volume
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  --enable-adx-filter \
  --enable-volume-filter \
  --data-dir data/chinese_etf/daily
```

---

#### Phase 1D: 全组合测试（Full Stack）

**目标**: 测试所有过滤器同时启用的效果

**配置**: 启用全部4个通用过滤器

```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  --enable-adx-filter \
  --enable-volume-filter \
  --enable-slope-filter \
  --enable-confirm-filter \
  --data-dir data/chinese_etf/daily
```

**实验次数**: 20只标的 × 1配置 = **20次**
**预期耗时**: ~5-10分钟

---

**Dimension 1 总计**: 20 + 80 + 80 + 20 = **200次回测**，预期耗时 **~1小时**

---

### 2.4 Dimension 2: 止损保护参数搜索

#### Phase 2A: 无止损对照（Baseline with Best Filter）

**配置**: 使用Dimension 1中表现最佳的过滤器组合，但不启用止损

**目的**: 作为止损实验的对照组

**实验次数**: 20只标的 × 1配置 = **20次**

---

#### Phase 2B: 连续止损保护网格搜索（Loss Protection Grid Search）

**目标**: 优化连续止损保护参数

**搜索空间**:
```python
grid_loss_protection = {
    'max_consecutive_losses': [2, 3, 4, 5],      # 连续亏损次数阈值
    'pause_bars': [5, 10, 15, 20],               # 暂停交易K线数
}
```

**参数组合**: 4 × 4 = **16种**

**实验次数**: 20只标的 × 16组合 = **320次**
**预期耗时**: ~1.5-2小时

**示例命令**:
```bash
# 使用最佳过滤器 + 止损保护（max_loss=3, pause=10）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  <最佳过滤器参数> \
  --enable-loss-protection \
  --max-consecutive-losses 3 \
  --pause-bars 10 \
  --data-dir data/chinese_etf/daily
```

---

**Dimension 2 总计**: 20 + 320 = **340次回测**，预期耗时 **~1.5-2小时**

---

### 2.5 Dimension 3: 交叉验证（Filter + Stop Loss 组合）

#### Phase 3: 顶级组合对比（Top Configurations Showdown）

**目标**: 对比最优配置的综合表现

**测试矩阵**:

| 配置 | 过滤器 | 止损 | 说明 |
|------|--------|------|------|
| **Config 0** | 无 | 无 | Baseline（纯KAMA） |
| **Config 1** | 最佳单一过滤器 | 无 | 最佳Filter Only |
| **Config 2** | 最佳双过滤器组合 | 无 | 最佳Combo Only |
| **Config 3** | 无 | 最佳止损参数 | 最佳Stop Loss Only |
| **Config 4** ⭐ | 最佳单一过滤器 | 最佳止损参数 | Single Filter + Stop Loss |
| **Config 5** ⭐ | 最佳双过滤器组合 | 最佳止损参数 | Combo + Stop Loss |
| **Config 6** | 全组合过滤器 | 最佳止损参数 | Full Stack + Stop Loss |

**实验次数**: 20只标的 × 7配置 = **140次**
**预期耗时**: ~30-40分钟

---

**Dimension 3 总计**: **140次回测**，预期耗时 **~30-40分钟**

---

### 2.6 实验汇总

| 阶段 | 测试内容 | 回测次数 | 预期耗时 |
|------|----------|----------|----------|
| **Phase 1A** | Baseline对照组 | 20 | 5-10分钟 |
| **Phase 1B** | 单一过滤器 | 80 | 20-30分钟 |
| **Phase 1C** | 双过滤器组合 | 80 | 20-30分钟 |
| **Phase 1D** | 全组合过滤器 | 20 | 5-10分钟 |
| **Phase 2A** | 最佳过滤器无止损 | 20 | 5-10分钟 |
| **Phase 2B** | 止损参数网格搜索 | 320 | 1.5-2小时 |
| **Phase 3** | 顶级配置对比 | 140 | 30-40分钟 |
| **总计** | - | **680次** | **~3-4小时** |

---

## 3. 评估指标

### 3.1 主要指标（Primary Metrics）

| 指标 | 权重 | 目标 | 说明 |
|------|------|------|------|
| **夏普比率（Sharpe Ratio）** | 40% | 最大化 | 主要优化目标，风险调整后收益 |
| **最大回撤（Max Drawdown）** | 30% | 最小化 | 风险控制能力 |
| **平均收益率（Avg Return）** | 20% | 保持或提升 | 绝对收益表现 |
| **胜率（Win Rate）** | 10% | 提升 | 策略可靠性 |

### 3.2 次要指标（Secondary Metrics）

| 指标 | 作用 |
|------|------|
| **收益标准差** | 评估不同标的间的稳定性 |
| **夏普比率标准差** | 评估策略鲁棒性 |
| **最差标的收益** | 下行风险评估 |
| **平均交易次数** | 策略活跃度 |
| **触发暂停次数** | 止损保护工作频率（仅适用于止损实验） |

### 3.3 对比维度

#### 对比1: 过滤器增益分析

```
指标计算:
- 增益 = (过滤器配置指标 - Baseline指标) / Baseline指标 × 100%

示例:
- 夏普比率增益 = (1.2 - 0.8) / 0.8 × 100% = +50%
- 最大回撤改进 = (-10% - (-15%)) / (-15%) × 100% = -33%（回撤降低33%）
```

**关键问题**:
1. 哪个单一过滤器增益最大？
2. 哪个双过滤器组合性价比最高？
3. 全组合是否存在过度过滤导致收益下降？

#### 对比2: 止损参数敏感性

**热力图分析**:
- X轴: `pause_bars` (5, 10, 15, 20)
- Y轴: `max_consecutive_losses` (2, 3, 4, 5)
- 颜色: 平均夏普比率

**关键问题**:
1. 最优参数区域在哪里？
2. 参数敏感性如何？（颜色梯度）
3. 是否存在稳定区间？（颜色均匀区域）

#### 对比3: 协同效应验证

**协同效应指标**:
```
Synergy = (Filter+StopLoss夏普) - (Filter夏普 + StopLoss夏普 - Baseline夏普)

解释:
- Synergy > 0: 存在正向协同（1+1>2）
- Synergy = 0: 无协同效应（独立作用）
- Synergy < 0: 负向干扰（相互削弱）
```

---

## 4. 技术实现

### 4.1 目录结构

```
experiment/etf/kama_cross/hyperparameter_search/
├── EXPERIMENT_DESIGN.md          # 本文档
├── README.md                      # 用户快速上手指南
├── REQUIREMENTS.md                # 详细需求文档
├── grid_search.py                 # 主实验脚本
├── generate_visualizations.py    # 可视化生成脚本
├── generate_report.py             # 报告生成脚本
├── results/                       # 结果目录
│   ├── phase1a_baseline.csv
│   ├── phase1b_single_filters.csv
│   ├── phase1c_dual_filters.csv
│   ├── phase1d_full_stack.csv
│   ├── phase2b_loss_protection_grid.csv
│   ├── phase3_top_configs.csv
│   ├── summary_statistics.csv
│   └── RESULTS.md                 # 详细实验报告
└── plots/                         # 可视化图表
    ├── filter_comparison.png
    ├── heatmap_loss_protection.png
    ├── top_configs_comparison.png
    └── synergy_analysis.png
```

### 4.2 核心脚本设计

#### `grid_search.py` 主要功能

```python
import subprocess
import pandas as pd
from pathlib import Path

class KAMAGridSearch:
    def __init__(self, stock_list, data_dir, output_dir):
        self.stock_list = stock_list
        self.data_dir = data_dir
        self.output_dir = Path(output_dir)

    def run_phase_1a_baseline(self):
        """Phase 1A: Baseline实验"""
        pass

    def run_phase_1b_single_filters(self):
        """Phase 1B: 单一过滤器实验"""
        filters = ['adx', 'volume', 'slope', 'confirm']
        for filter_name in filters:
            self._run_backtest(enable_filters=[filter_name])

    def run_phase_1c_dual_filters(self):
        """Phase 1C: 双过滤器组合实验"""
        combos = [
            ['adx', 'volume'],
            ['adx', 'slope'],
            ['volume', 'confirm'],
            ['slope', 'confirm'],
        ]
        for combo in combos:
            self._run_backtest(enable_filters=combo)

    def run_phase_1d_full_stack(self):
        """Phase 1D: 全组合过滤器实验"""
        self._run_backtest(enable_filters=['adx', 'volume', 'slope', 'confirm'])

    def run_phase_2b_loss_protection_grid(self, best_filter_config):
        """Phase 2B: 止损参数网格搜索"""
        for max_losses in [2, 3, 4, 5]:
            for pause_bars in [5, 10, 15, 20]:
                self._run_backtest(
                    enable_filters=best_filter_config,
                    enable_loss_protection=True,
                    max_consecutive_losses=max_losses,
                    pause_bars=pause_bars
                )

    def run_phase_3_top_configs(self, best_filter, best_combo, best_stop_loss):
        """Phase 3: 顶级配置对比"""
        configs = [
            {},  # Config 0: Baseline
            {'filters': best_filter},  # Config 1
            {'filters': best_combo},   # Config 2
            {'stop_loss': best_stop_loss},  # Config 3
            {'filters': best_filter, 'stop_loss': best_stop_loss},  # Config 4
            {'filters': best_combo, 'stop_loss': best_stop_loss},   # Config 5
            {'filters': 'full', 'stop_loss': best_stop_loss},        # Config 6
        ]
        for config in configs:
            self._run_backtest(**config)

    def _run_backtest(self, enable_filters=None, enable_loss_protection=False,
                      max_consecutive_losses=3, pause_bars=10):
        """
        执行单次回测实验

        Args:
            enable_filters: 启用的过滤器列表 ['adx', 'volume', 'slope', 'confirm']
            enable_loss_protection: 是否启用止损保护
            max_consecutive_losses: 连续亏损阈值
            pause_bars: 暂停K线数

        Returns:
            dict: 回测结果统计
        """
        cmd = [
            './run_backtest.sh',
            '--stock-list', self.stock_list,
            '-t', 'kama_cross',
            '--data-dir', self.data_dir,
        ]

        # 添加过滤器参数
        if enable_filters:
            if 'adx' in enable_filters:
                cmd.append('--enable-adx-filter')
            if 'volume' in enable_filters:
                cmd.append('--enable-volume-filter')
            if 'slope' in enable_filters:
                cmd.append('--enable-slope-filter')
            if 'confirm' in enable_filters:
                cmd.append('--enable-confirm-filter')

        # 添加止损参数
        if enable_loss_protection:
            cmd.extend([
                '--enable-loss-protection',
                '--max-consecutive-losses', str(max_consecutive_losses),
                '--pause-bars', str(pause_bars),
            ])

        # 执行回测
        result = subprocess.run(cmd, capture_output=True, text=True)

        # 解析结果（需要解析backtest_runner的输出）
        stats = self._parse_backtest_output(result.stdout)

        return stats

    def _parse_backtest_output(self, output):
        """解析backtest_runner的输出，提取统计指标"""
        # 从汇总CSV文件中读取结果
        # 返回字典: {'sharpe_ratio': ..., 'return': ..., 'max_drawdown': ...}
        pass
```

#### `generate_visualizations.py` 可视化功能

```python
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

def plot_filter_comparison(results_df, output_path):
    """
    生成过滤器对比图

    X轴: 配置名称（Baseline, ADX Only, Volume Only, ...）
    Y轴: 夏普比率
    柱状图 + 误差棒（标准差）
    """
    pass

def plot_loss_protection_heatmap(grid_results_df, output_path):
    """
    生成止损参数热力图

    X轴: pause_bars
    Y轴: max_consecutive_losses
    颜色: 平均夏普比率
    """
    pivot_table = grid_results_df.pivot_table(
        values='sharpe_ratio',
        index='max_consecutive_losses',
        columns='pause_bars',
        aggfunc='mean'
    )

    plt.figure(figsize=(10, 8))
    sns.heatmap(pivot_table, annot=True, fmt='.2f', cmap='RdYlGn', center=0.8)
    plt.title('KAMA Loss Protection Parameter Heatmap')
    plt.savefig(output_path)

def plot_top_configs_radar(top_configs_df, output_path):
    """
    生成顶级配置雷达图

    维度: 夏普比率、收益率、最大回撤、胜率
    配置: Config 0-6
    """
    pass

def plot_synergy_analysis(results_df, output_path):
    """
    生成协同效应分析图

    对比:
    - Filter Only夏普
    - Stop Loss Only夏普
    - Filter + Stop Loss夏普
    - 理论叠加夏普（无协同）
    """
    pass
```

#### `generate_report.py` 报告生成

```python
def generate_markdown_report(results_dict, output_path):
    """
    生成详细的Markdown实验报告

    包含:
    1. 实验概述
    2. Phase 1: 过滤器实验结果
    3. Phase 2: 止损参数优化结果
    4. Phase 3: 顶级配置对比
    5. 核心发现与建议
    6. 附录：完整数据表
    """
    report = []

    report.append("# KAMA策略超参数搜索实验报告\n")
    report.append(f"**实验日期**: {results_dict['experiment_date']}\n")
    report.append(f"**总测试次数**: {results_dict['total_experiments']}\n")

    # Phase 1 结果
    report.append("## Phase 1: 信号过滤器实验结果\n")
    report.append("### 单一过滤器表现\n")
    # 生成表格...

    # Phase 2 结果
    report.append("## Phase 2: 止损参数优化结果\n")
    report.append("### 最佳参数推荐\n")
    # 生成推荐...

    # Phase 3 结果
    report.append("## Phase 3: 顶级配置对比\n")
    # 生成对比表...

    # 写入文件
    with open(output_path, 'w') as f:
        f.write('\n'.join(report))
```

### 4.3 调用方式

**完整实验运行**:
```bash
cd /mnt/d/git/backtesting

# 激活环境
conda activate backtesting

# 运行完整实验（约3-4小时）
python experiment/etf/kama_cross/hyperparameter_search/grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --output-dir experiment/etf/kama_cross/hyperparameter_search/results \
  --phases all
```

**分阶段运行**:
```bash
# Phase 1: 过滤器实验（~1小时）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases phase1

# Phase 2: 止损优化（~2小时）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases phase2

# Phase 3: 顶级对比（~30分钟）
python grid_search.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily \
  --phases phase3
```

---

## 5. 实验成果总结 ✅

### 5.1 完成状态

| 阶段 | 状态 | 回测次数 | 成功率 | 耗时 |
|------|------|----------|--------|------|
| **Phase 1** | ✅ 完成 | 200次 | 100% | 45秒 |
| **Phase 2** | ✅ 完成 | 1020次 | 100% | 1.5小时 |
| **总计** | ✅ 完成 | **1220次** | **100%** | **~2小时** |

### 5.2 输出文件

**数据文件**:
```
results/
├── phase1a_baseline.csv               ✅ (20条)
├── phase1b_single_filters.csv         ✅ (80条)
├── phase1c_dual_filters.csv          ✅ (80条)
├── phase1d_full_stack.csv            ✅ (20条)
├── phase2a_baseline.csv              ✅ (60条)
├── phase2b_loss_protection_grid.csv  ✅ (960条)
└── phase2_summary_statistics.csv     ✅ (51配置)
```

**分析报告**:
- `PHASE1_ACCEPTANCE_REPORT.md` ✅
- `PHASE2_ACCEPTANCE_REPORT.md` ✅
- `PHASE2_EXECUTIVE_SUMMARY.md` ✅
- `PHASE2_QUICK_REFERENCE.md` ✅

### 5.3 关键洞察

1. **KAMA独特性**：自适应特性使其无需额外止损保护
2. **跨策略对比**：止损效果与基础信号质量成反比
3. **实用建议**：专注策略选择，而非复杂参数优化

### 5.1 输出文件

#### 数据文件（CSV）

| 文件名 | 说明 | 行数预估 |
|--------|------|----------|
| `phase1a_baseline.csv` | Baseline回测结果 | 20 |
| `phase1b_single_filters.csv` | 单一过滤器结果 | 80 |
| `phase1c_dual_filters.csv` | 双过滤器组合结果 | 80 |
| `phase1d_full_stack.csv` | 全组合结果 | 20 |
| `phase2b_loss_protection_grid.csv` | 止损网格搜索结果 | 320 |
| `phase3_top_configs.csv` | 顶级配置对比结果 | 140 |
| `summary_statistics.csv` | 汇总统计 | ~30 |

**CSV格式示例**:
```csv
stock_code,config_name,enable_adx,enable_volume,enable_loss_protection,max_consecutive_losses,pause_bars,sharpe_ratio,return_pct,max_drawdown_pct,win_rate,num_trades
159201.SZ,Baseline,False,False,False,,,0.75,45.2,-18.3,52.3,12
159201.SZ,ADX Only,True,False,False,,,0.89,48.1,-14.2,58.7,10
...
```

#### 可视化图表（PNG）

| 文件名 | 图表类型 | 说明 |
|--------|----------|------|
| `filter_comparison.png` | 柱状图 | Phase 1过滤器对比 |
| `heatmap_loss_protection_sharpe.png` | 热力图 | 止损参数vs夏普比率 |
| `heatmap_loss_protection_drawdown.png` | 热力图 | 止损参数vs最大回撤 |
| `top_configs_comparison.png` | 雷达图/柱状图 | 顶级配置多维对比 |
| `synergy_analysis.png` | 柱状图 | 协同效应分析 |
| `parameter_sensitivity.png` | 箱线图 | 参数敏感性分析 |

#### 报告文件（Markdown）

**`RESULTS.md`** 包含：
1. **实验概述**: 配置、时间、总测试次数
2. **Phase 1 结果**: 过滤器增益分析表 + 关键发现
3. **Phase 2 结果**: 止损参数热力图 + 最优推荐
4. **Phase 3 结果**: 顶级配置对比表 + 协同效应分析
5. **核心结论**: 最终推荐配置
6. **附录**: 完整数据表

### 5.2 关键洞察预期

#### 洞察1: 过滤器效果排序

**预期结果示例**:
```
过滤器增益排序（按夏普比率提升）:
1. ADX趋势强度: +35%（最显著）
2. ADX+成交量组合: +45%（协同增强）
3. 成交量确认: +18%
4. 价格斜率: +12%
5. 持续确认: +8%
6. 全组合: +50%（但交易次数降低60%，可能过度过滤）
```

#### 洞察2: 止损最优参数

**预期结果示例**:
```
最佳连续止损保护参数:
- max_consecutive_losses: 3
- pause_bars: 10
- 夏普比率: 1.15
- 相比无止损提升: +28%
- 最大回撤降低: -25%
```

#### 洞察3: 终极配置推荐

**预期结果示例**:
```
⭐ 最优配置（Config 5）:
- 过滤器: ADX + 成交量
- 止损: max_consecutive_losses=3, pause_bars=10
- 夏普比率: 1.35（相比Baseline +80%）
- 最大回撤: -12.5%（相比Baseline -45%）
- 协同效应: +15%（正向协同）
```

---

## 6. 风险与缓解

### 6.1 过拟合风险

**风险**: 参数在历史数据上过度优化，实盘表现差

**缓解措施**:
1. **参数稳定性分析**: 优先选择参数不敏感区域的配置
2. **交叉验证**: 使用不同时间窗口验证参数稳定性
3. **保守选择**: 选择热力图中"平台区域"的参数（颜色均匀区域）
4. **实盘验证**: 使用最优参数进行模拟盘测试

### 6.2 计算资源

**风险**: 680次回测耗时过长

**缓解措施**:
1. **分阶段执行**: 优先完成Phase 1（1小时），验证可行性后继续
2. **并行化**: 未来可考虑多进程并行执行回测
3. **缓存机制**: 相同配置的回测结果缓存，避免重复计算

### 6.3 数据质量

**风险**: 标的数据缺失或异常导致结果不可靠

**缓解措施**:
1. **预验证**: 实验前检查`trend_etf_pool.csv`中标的数据完整性
2. **异常检测**: 脚本中加入数据质量检查（停牌、缺失值处理）
3. **鲁棒性测试**: 对比不同标的池的结果，验证结论一致性

### 6.4 策略过度过滤

**风险**: 启用所有过滤器导致交易次数过低，策略失效

**缓解措施**:
1. **交易频率监控**: 报告中展示平均交易次数变化
2. **阈值设定**: 建议最低交易次数（如≥8次/2年）
3. **过滤器取舍**: 优先选择增益高、交易频率适中的组合

---

## 7. 后续扩展

实验完成后的可选扩展方向：

### 7.1 跟踪止损实验（Optional）

- 测试`trailing_stop_pct`参数（3%, 5%, 7%）
- 对比连续止损保护 vs 跟踪止损
- 测试Combined方案（连续 + 跟踪）

### 7.2 多市场验证

- 在美股ETF池上重复实验
- 验证参数的跨市场通用性

### 7.3 滚动窗口回测

- Walk-forward分析
- 评估参数的时间稳定性

### 7.4 实盘模拟

- 使用最优配置进行模拟盘测试
- 收集实际交易的表现数据

---

## 8. 参考资料

- **KAMA策略文档**: `requirement_docs/20251111_kama_adaptive_strategy_implementation.md`
- **策略实现代码**: `strategies/kama_cross.py`
- **SMA止损实验**: `experiment/etf/sma_cross/stop_loss_comparison/`
- **MACD参数优化**: `experiment/etf/macd_cross/grid_search_stop_loss/`
- **止损实验参考**: `requirement_docs/20251109_native_stop_loss_implementation.md`

---

**最后更新**: 2025-11-11
**作者**: Claude Code
**版本**: v1.0
