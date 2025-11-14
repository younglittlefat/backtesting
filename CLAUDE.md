# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

Backtesting.py 是一个用于回测交易策略的 Python 库。它提供了一个简单、快速的框架，用于在历史数据上测试算法交易策略，并提供全面的统计数据和交互式可视化。

**项目特色功能**:
- ⭐ **连续止损保护**: 增强版策略支持原生止损保护，经过280次回测验证，可显著提升风险调整后收益（夏普比率+75%，最大回撤-34%）
- 多种信号过滤器：ADX趋势强度、成交量确认、均线斜率等
- 灵活的成本模型：支持中国A股/ETF、美股等不同市场的交易成本配置

## 环境配置

**重要**: 本项目必须在名为 `backtesting` 的 conda 环境中运行。你现在是在wsl里的Ubuntu 24系统中运行，但项目在windows的硬盘上（/mnt/d/git/backtesting），请妥善处理脚本调用、传入的路径

### Conda 环境设置
```bash
# Conda 路径
# /home/zijunliu/miniforge3/condabin/conda

# 激活 backtesting 环境
conda activate backtesting

# 如果环境不存在，创建环境
conda create -n backtesting python=3.9
conda activate backtesting
```

### 安装
```bash
# 确保已激活 backtesting 环境
conda activate backtesting

# 开发安装（包含所有依赖）
pip install -e '.[doc,test,dev]'
```

## 开发命令

### 测试
```bash
# 激活环境
conda activate backtesting

# 运行所有测试
python -m backtesting.test

# 运行带覆盖率的测试
coverage run -m backtesting.test
coverage report
```

### 代码检查和类型检查
```bash
# 代码风格检查
flake8 backtesting setup.py

# 类型检查
mypy --no-warn-unused-ignores backtesting

# 使用 ruff（在 pyproject.toml 中配置）
ruff check backtesting
```

### 文档构建
```bash
# 构建文档（需要 doc 依赖）
cd doc
./build.sh

# 构建脚本处理 Jupyter notebook 转换和 pdoc 生成
```

## 架构概览

### 核心组件

**backtesting/backtesting.py**
- 包含 `Backtest` 和 `Strategy` 类的主框架
- `Strategy`: 用户扩展以定义交易逻辑的抽象基类
  - `init()`: 初始化指标并预计算数据
  - `next()`: 每个 bar 调用以做出交易决策
- `Backtest`: 在历史数据上运行策略的主回测引擎
- `_Broker`: 处理订单执行和持仓管理的内部类

**backtesting/lib.py**
- 工具函数和可组合策略构建块的集合
- 技术分析辅助函数: `crossover()`, `cross()`, `barssince()`
- OHLCV 数据（`OHLCV_AGG`）和交易（`TRADES_AGG`）的数据聚合规则
- 常见模式的基础策略类

**backtesting/_stats.py**
- 回测结果的统计计算
- 性能指标计算（夏普比率、回撤、收益等）
- 风险指标和交易分析

**backtesting/_plotting.py**
- 使用 Bokeh 进行交互式可视化
- 带指标叠加的蜡烛图
- 权益曲线和回撤图
- 可自定义的绘图参数

**backtesting/_util.py**
- 内部工具和辅助函数
- 数据验证和预处理
- 指标管理和内存优化

### 数据流

1. **输入**: 带有 datetime 索引的 OHLCV pandas DataFrame
2. **策略初始化**: `Strategy.init()` 使用 `self.I()` 声明指标
3. **模拟循环**: 对于每个 bar，使用当前数据调用 `Strategy.next()`
4. **订单执行**: 买入/卖出订单由内部 broker 处理
5. **统计**: 从交易和权益曲线计算性能指标
6. **可视化**: 使用 Bokeh 绘制结果进行交互式分析

### 关键设计模式

**指标声明**
- 在 `init()` 中使用 `self.I(func, *args, **kwargs)` 声明指标
- 指标在回测期间逐步显示
- 滚动指标的自动预热期检测

**策略继承**
- 扩展 `Strategy` 类并实现 `init()` 和 `next()`
- 通过 `self.data` 访问当前数据（Close, Open, High, Low, Volume）
- 使用 `self.buy()`, `self.sell()`, `self.position` 进行交易

**优化支持**
- 定义为类变量的参数可以被优化
- 内置参数网格并行优化
- 支持自定义优化指标

## 依赖和兼容性

- **Python**: 需要 3.9+
- **核心**: numpy, pandas, bokeh
- **可选**: matplotlib（额外绘图）, scikit-learn（机器学习示例）
- **开发**: flake8, mypy, coverage
- **文档**: pdoc3, jupytext, nbconvert

## 发布和 CI

- CI 管道运行在 GitHub Actions
- 在多个 Python 版本（3.12, 3.13+）上测试
- 使用 flake8 进行代码检查和 mypy 进行类型检查
- 测试文档构建
- 验证 Windows 兼容性
- 使用 setuptools_scm 从 git 标签进行版本管理

## 已实现需求文档索引

本节索引了 `requirement_docs/` 目录中的所有需求文档，按实现时间顺序排列，便于快速了解系统演进历程和已实现功能。

### 📁 2024年10月 - 系统基础设计

#### `1031_backtesting_design.md`
**核心回测系统架构设计文档**
系统的奠基文档，定义了整个回测框架的核心架构，包括策略接口、数据处理流程、性能指标计算等基础设施。为后续所有功能开发提供了技术基础。

#### `1103_etf_adj_factor_integration.md`
**ETF复权因子集成需求**
解决ETF价格计算准确性问题，集成复权因子确保历史价格数据的准确性。对回测结果的可靠性至关重要。

### 📁 2024年11月 - 数据处理与成本模型

#### `1105_trading_cost_configuration.md`
**交易成本配置系统**
实现灵活的交易成本模型，支持中国A股/ETF、美股等不同市场的费率配置。提高回测结果的真实性。

#### `20251103_tushare_fetcher_refactoring.md`
**TuShare数据获取系统重构**
优化数据获取管道，重构TuShare接口调用逻辑，提升数据获取效率和稳定性。

#### `20251104_mysql_export_adjustment_fix.md`
**MySQL数据导出调整修复**
修复数据库集成中的数据导出问题，确保数据一致性和完整性。

### 📁 2024年11月 - ETF筛选与投资组合优化

#### `20251106_china_etf_filter_for_trend_following.md` ⭐ **核心系统**
**中国ETF趋势跟踪筛选系统（1532行）**
实现完整的三层漏斗模型ETF筛选系统：
- **初筛层**: 基础流动性和规模筛选（1600+只ETF → 300+只）
- **核心筛选层**: 趋势性、流动性、基本面等7个维度评分筛选（300+只 → 50+只）
- **投资组合优化层**: 基于现代投资组合理论的最优配置（50+只 → 20+只最终池）

**关键代码**: `etf_selector/` 模块架构，包含完整的评分算法和筛选流程。

#### `20251108_fix_portfolio_greedy_selection_for_unbiased_scoring.md`
**投资组合贪心选择算法兼容性修复**
修复投资组合优化中的贪心算法初始化失败问题，确保无偏评分系统的正常运行。

#### `20251108_fund_dividend_full_lifecycle_fetch.md`
**基金分红数据全生命周期获取**
实现基金分红数据的完整获取流程，支持历史分红数据的全面采集和处理。

### 📁 2024年11月8日 - 信号一致性与参数管理

#### `20251108_backtest_signal_parameter_consistency.md`
**回测信号参数一致性保障**
确保回测和实盘信号生成使用相同的参数配置，解决参数不一致导致的策略表现差异问题。

### 📁 2024年11月9日 - 策略增强与系统重构

#### `20251109_signal_quality_optimization.md` ⭐ **策略增强**
**双均线策略信号质量优化**
为双均线策略实现5种信号过滤器：
- **ADX趋势强度过滤器**: 过滤弱趋势环境中的假信号
- **成交量确认过滤器**: 用成交量变化确认价格突破的有效性
- **均线斜率过滤器**: 过滤震荡市中的噪音信号
- **持续确认过滤器**: 要求信号持续多根K线才执行
- **低波动过滤器**: 过滤低活跃度的标的

经过详细回测验证，可显著提升策略稳定性。

#### `20251109_native_stop_loss_implementation.md` ⭐⭐⭐ **核心功能**
**原生止损保护实现**
基于backtesting.py框架实现三种止损策略：
- **连续止损保护** ⭐ 推荐：连续N次亏损后暂停交易
- **跟踪止损**: 价格上涨时动态调整止损线
- **组合方案**: 跟踪止损 + 连续止损保护

**实验验证**: 基于20只中国ETF、280次回测，连续止损保护策略实现：
- 夏普比率提升 **+75%** (0.61 → 1.07)
- 最大回撤降低 **-34%** (-21% → -14%)
- 胜率提升 **+27%** (48% → 61%)

#### `20251109_macd_cross_strategy_implementation.md`
**MACD交叉策略实现（391行）**
基于MACD指标的专业交易策略实现：
- **Phase 1-3** ✅: 基础功能、信号过滤器、止损保护（已完成）
- **Phase 4** 🔲: 增强信号（零轴交叉、双重金叉、背离检测 - 待实现）

集成多种过滤器和三种止损保护方案，提供单一策略类通过`enable_*`参数灵活控制功能。

#### `20251109_backtest_runner_refactoring_plan.md` & `20251109_backtest_runner_refactoring_report.md`
**系统架构重构计划与报告**
将单一1457行的`backtest_runner.py`重构为模块化包结构：
- **重构前**: 单文件1457行，职责不清，难以维护
- **重构后**: 18个Python模块，职责清晰，高内聚低耦合
- **兼容性**: 100%向后兼容，所有现有脚本无需修改

**新架构**: `backtest_runner/`包含config、core、processing、io、utils等模块，每个模块平均115行，便于理解和维护。

#### `20251109_save_runtime_params_enhancement.md` ⭐ **参数管理增强**
**运行时参数保存功能增强（1399行）**
解决回测和实盘信号生成参数不一致的关键问题：
- **问题**: 命令行启用的功能（过滤器、止损保护）不会保存到配置文件
- **解决方案**: 扩展配置文件结构，实现策略契约机制
- **核心设计**: 强制策略实现`RuntimeConfigurable`接口，自动保存完整运行时配置

**技术实现**:
- 新增`BaseEnhancedStrategy`基类，自动集成运行时参数导出
- 配置文件新增`runtime_config`字段，保存过滤器和止损保护配置
- 向后兼容旧策略和配置文件，支持参数验证和错误处理

### 📁 2025年11月11日 - KAMA自适应策略开发

#### `20251111_kama_adaptive_strategy_implementation.md` ⭐ **策略设计完成**
**KAMA自适应均线策略设计与实现**
设计基于Kaufman自适应移动平均线的智能交易策略：
- **核心优势**: 根据市场效率自动调整响应速度，趋势期快速跟随，震荡期平滑滤波
- **技术创新**: 效率比率动态计算，自适应平滑常数调整，减少假信号和滞后
- **系统集成**: 基于`BaseEnhancedStrategy`架构，复用现有过滤器和止损保护功能

**实现状态**: Phase 1-3全部完成 ✅

#### `experiment/etf/kama_cross/hyperparameter_search/` ⭐⭐ **完整实验验证**
**KAMA策略超参数网格搜索实验（已完成）**
通过1220次回测系统验证KAMA策略的过滤器和止损保护效果：

**Phase 1发现**（200次回测）:
- **Baseline夏普**: 1.69（远超SMA 0.61和MACD 0.6）
- **最佳过滤器**: ADX（夏普1.68，回撤-4.71%）
- **不适用**: Confirm过滤器（与自适应特性冲突）

**Phase 2关键发现**（1020次回测）⭐:
- **止损保护无效**: 对KAMA策略仅-0.7%夏普变化
- **根本原因**: KAMA自适应特性已内置连续亏损保护
- **对比**: SMA (+75%)、MACD (+28.8%) vs KAMA (-0.7%)

**最终推荐**: 使用Baseline KAMA，不启用止损保护（夏普1.69，收益34.63%）

### 📁 2025年11月12日 - 动态投资组合管理

#### `20251112_dynamic_pool_rotation_strategy.md` ⭐ **投资组合轮动策略**
**动态ETF池轮动策略实现**
研究定期重新筛选ETF池（如每30天）能否提升收益，突破固定池子的局限性：
- **核心思路**: 预计算轮动表 + 虚拟ETF组合回测
- **技术创新**: 等权组合法解决backtesting.py单标的假设
- **实现状态**: Phase 1-2完成 ✅（轮动表生成 + 虚拟ETF数据生成器）
- **待验证**: 动态轮动 vs 固定池的收益对比实验

### 📊 功能完成度总结

| 功能模块 | 状态 | 核心文档 | 说明 |
|---------|------|----------|------|
| **ETF筛选系统** | ✅ 95%完成 | 20251106_china_etf_filter_for_trend_following.md | 三层漏斗模型完整实现 |
| **止损保护** | ✅ 完成 | 20251109_native_stop_loss_implementation.md | 经实验验证，对SMA/MACD显著提升 |
| **信号过滤器** | ✅ 完成 | 20251109_signal_quality_optimization.md | 5种过滤器增强信号质量 |
| **MACD策略** | ✅ 75%完成 | 20251109_macd_cross_strategy_implementation.md | Phase 1-3完成，Phase 4待实现 |
| **KAMA策略** | ✅ 100%完成 | 20251111_kama_adaptive_strategy_implementation.md | 完整实现+实验验证，性能卓越 |
| **动态轮动池** | 🟡 60%完成 | 20251112_dynamic_pool_rotation_strategy.md | Phase 1-2完成，待回测实验验证 |
| **参数管理** | ✅ 完成 | 20251109_save_runtime_params_enhancement.md | 解决回测/实盘参数一致性问题 |
| **系统重构** | ✅ 完成 | 20251109_backtest_runner_refactoring_*.md | 模块化架构，易维护扩展 |
| **数据管道** | ✅ 完成 | 20251103_tushare_fetcher_refactoring.md | 数据获取稳定可靠 |

### 🎯 系统能力

经过这些需求的实现，系统现在具备：
1. **专业级ETF筛选**: 基于现代投资组合理论的科学筛选
2. **风险控制**: 原生止损保护，对SMA/MACD实验验证有效
3. **信号增强**: 多维度过滤器提升策略稳定性
4. **参数一致性**: 回测和实盘使用相同配置
5. **模块化架构**: 易于维护和功能扩展
6. **多策略支持**: SMA、MACD、**KAMA**等不同技术指标策略
7. **策略优选**: KAMA自适应特性实现卓越表现（夏普1.69）

### 📖 使用建议

**对于新用户**:
1. **优先推荐KAMA策略**（夏普1.69，收益34.63%，回撤-5.27%）
2. 使用ETF筛选系统选择优质标的
3. 对于SMA/MACD策略启用连续止损保护

**对于开发者**:
1. 遵循`BaseEnhancedStrategy`基类开发新策略
2. 利用模块化架构进行功能扩展
3. 参考KAMA实验进行策略验证

**策略性能对比**:
| 策略 | 推荐配置 | 夏普比率 | 止损保护 |
|------|---------|----------|----------|
| **KAMA** | Baseline | **1.69** | ❌ 不需要 |
| SMA | Loss Protection | 1.07 | ✅ 必需(+75%) |
| MACD | Combined | 0.94 | ✅ 推荐(+28%) |

## 实验索引

本节记录 `experiment/` 目录中的关键实验，按策略分类，展示实验验证的核心结论和参数建议。

### 📊 SMA双均线策略实验

#### `experiment/etf/sma_cross/stop_loss_comparison/` ⭐⭐⭐ **止损方案对比**
**实验目标**: 对比3种止损方案在20只中国ETF上的表现（2023-11至2025-11，280次回测）

**核心结论**:
| 方案 | 收益 | 夏普 | 最大回撤 | 胜率 | 评价 |
|------|------|------|----------|------|------|
| Base（无止损） | 51.09% | 0.61 | -21.17% | 48.41% | ❌ 不推荐 |
| **Loss Protection** | **53.91%** | **1.07** (+75%) | **-13.88%** (-34%) | **61.42%** | ⭐ 最优 |
| Combined | 44.93% | 1.01 | **-12.87%** | 55.89% | ✅ 最稳健 |
| Trailing Stop | 40.20% | 0.91 | -12.77% | 57.57% | ⚠️ 单独效果有限 |

**推荐配置**: `max_consecutive_losses=3, pause_bars=10`（参数不敏感，鲁棒性强）

**关键文档**: `experiment/etf/sma_cross/stop_loss_comparison/RESULTS.md`

### 📈 KAMA自适应均线策略实验 ⭐⭐⭐

#### `experiment/etf/kama_cross/hyperparameter_search/` **完整超参数网格搜索**
**实验目标**: 系统验证KAMA策略的过滤器和止损保护效果（2023-11至2025-11）

**Phase 1核心发现**（200次回测）:
- **Baseline夏普**: 1.69（远超SMA 0.61、MACD 0.6）
- **最佳过滤器**: ADX（夏普1.68，回撤-4.71%）
- **最佳组合**: ADX+Slope（夏普1.58，回撤-4.38%）
- **不适用**: Confirm过滤器（与KAMA自适应特性冲突）

**Phase 2关键发现**（1020次回测）⭐:
- **止损保护无效**: 对KAMA策略仅-0.7%夏普变化
- **跨策略对比**: SMA (+75%)、MACD (+28.8%) vs **KAMA (-0.7%)**
- **根本原因**: KAMA自适应特性已内置连续亏损保护机制
- **科学洞察**: **止损保护效果 ∝ 1/基础信号质量**

**最终推荐**: 使用Baseline KAMA，不启用止损保护
```bash
# ✅ 推荐配置（最佳性价比）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t kama_cross \
  --data-dir data/chinese_etf/daily
# 预期：夏普1.69，收益34.63%，回撤-5.27%
```

**关键文档**:
- `experiment/etf/kama_cross/hyperparameter_search/results/PHASE2_ACCEPTANCE_REPORT.md`
- `experiment/etf/kama_cross/hyperparameter_search/EXPERIMENT_DESIGN.md`

### 📈 MACD交叉策略实验

#### `experiment/etf/macd_cross/grid_search_stop_loss/` ⭐⭐ **止损超参网格搜索**
**实验目标**: 通过960次回测优化MACD策略止损参数（48组合×20只ETF）

**核心结论**:
- **最佳方案**: Combined（夏普0.94，回撤-15.82%，相比Baseline夏普+28.8%，回撤-21.4%）
- **最优参数**: `max_consecutive_losses=2, pause_bars=5, trailing_stop_pct=0.03`
- **Loss Protection独立表现**: 夏普0.85（`max_losses=3, pause_bars=20`）
- **协同效应**: Loss Protection(0.85) + Trailing(0.83) → Combined(0.94)，显著增强

**关键文档**: `experiment/etf/macd_cross/grid_search_stop_loss/RESULTS.md`

#### `experiment/etf/macd_cross/selector_weights_grid_search/` ⭐ **选择器权重优化**
**实验目标**: 验证无偏ETF筛选器权重配置（去除动量偏差，22次实验）

**核心发现**:
1. **参数不敏感性** ⭐ 最重要：22个权重配置结果几乎相同（夏普σ=0.000039，收益差<2.32%）
2. **策略主导效应**: 回测结果80%由MACD策略质量决定，筛选权重优化空间<5%
3. **无偏验证成功**: 动量权重严格为0仍获年化198%，纯技术指标筛选有效

**最优配置**: ADX 40% + 趋势一致性 25% + 价格效率 20% + 流动性 15%（夏普0.654，年化198%）

**建议**: 使用推荐权重即可，优化重点应转向策略参数而非筛选器

**关键文档**:
- `experiment/etf/macd_cross/selector_weights_grid_search/FINAL_SUMMARY.md`
- `experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/EXECUTIVE_SUMMARY.md`

#### `experiment/etf/kama_cross/hyperparameter_search/` ⭐⭐ **KAMA过滤器网格搜索**
**实验目标**: 测试4种信号过滤器对KAMA策略的影响（Phase 1已完成）

**Phase 1结果** (2025-11-11, 200次回测):
- **Baseline夏普**: 1.69（卓越！远超SMA 0.61和MACD 0.6）
- **最佳过滤器**: ADX（夏普1.68，回撤-4.71%，几乎无性能损失）
- **次优**: Slope（夏普1.59，胜率88.54%最高）
- **最佳组合**: ADX+Slope（夏普1.58，回撤-4.38%最优）
- **关键发现**: KAMA自适应特性强，过滤器边际效应递减
- **已知问题**: Confirm过滤器与KAMA策略架构不兼容（需要sma_short/sma_long属性）

**实验文件**:
- `grid_search_phase1.py` - Phase 1信号过滤器实验脚本
- `results/PHASE1_ACCEPTANCE_REPORT.md` - 详细验收报告
- `DEVELOPMENT_PLAN.md` - 开发进度跟踪

**待开发**: Phase 2止损参数搜索、Phase 3顶级配置对比

### 🔬 多策略对比实验

#### `experiment/etf/strategy_comparison/` ⭐⭐⭐ **三策略横向对比**
**实验目标**: 对比SMA、MACD、KAMA三种均线策略在相同ETF池上的综合表现（2023-11至2025-11）

**实验设计**:
- **测试矩阵**: 3策略 × 2配置（Baseline + BestStopLoss）= 6场景，120次回测
- **评估维度**:
  - 稳健性：平均夏普、夏普中位数、夏普标准差
  - 盈利能力：总收益、平均收益、收益中位数
  - 风险控制：平均回撤、胜率、交易频率

**策略配置**:
| 策略 | 基础参数 | 最佳止损 | 数据来源 |
|------|---------|---------|----------|
| SMA | n1=10, n2=20 | Loss Protection (3次, 10bars) | 280次回测验证 |
| MACD | 优化参数 | Combined (2次, 5bars, 3%跟踪) | 960次回测优化 |
| KAMA | period=20, fast=2, slow=30 | Loss Protection (3次, 10bars) | 默认参数 |

**实验假设**:
1. H1: 止损保护对所有策略都有正向增益
2. H2: KAMA因自适应特性稳健性最优（夏普标准差最小）
3. H3: MACD经优化后盈利能力最强（总收益最高）

**关键文档**:
- `experiment/etf/strategy_comparison/EXPERIMENT_DESIGN.md` - 详细实验设计
- `experiment/etf/strategy_comparison/DEVELOPMENT_PLAN.md` - 开发任务分解
- `experiment/etf/strategy_comparison/RESULTS.md` - 实验结果报告（待生成）

**开发状态**: 📋 规划完成，待执行

### 🎯 实验总结与应用建议

| 策略类型 | 推荐止损方案 | 推荐参数 | 预期效果 |
|---------|-------------|---------|---------|
| **SMA** | Loss Protection | `max_losses=3, pause=10` | 夏普+75%，回撤-34% |
| **MACD** | Combined | `max_losses=2, pause=5, trail=3%` | 夏普+28.8%，回撤-21.4% |

**关键洞察**:
- 连续止损保护对所有趋势策略都有显著效果
- Combined方案在MACD上效果更好（协同增强），在SMA上Loss Protection独立使用最优
- 止损参数普遍不敏感，使用推荐值即可
- ETF筛选器权重不敏感，策略质量才是核心