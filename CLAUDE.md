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

## 止损保护功能（连续止损保护）⭐ 强烈推荐

增强版双均线策略（`SmaCrossEnhanced`）支持原生止损保护功能，经过280次回测验证，显著提升风险调整后收益。

### 核心优势
- **夏普比率提升 +75%**（0.61 → 1.07）
- **最大回撤降低 -34%**（-21% → -14%）
- **胜率提升 +27%**（48% → 61%）
- **最差标的风险降低 +77%**（-42% → -9%）

### 实现原理
连续止损保护通过跟踪连续亏损次数，在策略失效时自动暂停交易，避免在不利市场环境中连续亏损。

### 快速开始

```bash
# 最简单的使用方式（使用推荐参数）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t sma_cross_enhanced \
  --enable-loss-protection \
  --data-dir data/chinese_etf/daily

# 自定义参数
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t sma_cross_enhanced \
  --enable-loss-protection \
  --max-consecutive-losses 4 \
  --pause-bars 15 \
  --data-dir data/chinese_etf/daily

# 组合使用多种过滤器（推荐）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t sma_cross_enhanced \
  --enable-loss-protection \
  --enable-adx-filter \
  --enable-volume-filter \
  --data-dir data/chinese_etf/daily \
  -o
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--enable-loss-protection` | False | 启用连续止损保护 |
| `--max-consecutive-losses` | 3 | 连续亏损次数阈值（推荐值，基于实验结果） |
| `--pause-bars` | 10 | 触发保护后暂停的K线数（推荐值，基于实验结果） |

### 实验验证

基于20只中国ETF、280次回测（2023-11至2025-11）的完整实验结果：

| 策略 | 平均收益 | 夏普比率 | 最大回撤 | 胜率 |
|------|----------|----------|----------|------|
| Base（无止损） | 51.09% | 0.61 | -21.17% | 48.41% |
| **Loss Protection** | **53.91%** | **1.07** | **-13.88%** | **61.42%** |

详细实验报告：`requirement_docs/20251109_native_stop_loss_implementation.md`

### 注意事项
- 默认参数（max_consecutive_losses=3, pause_bars=10）是基于实验优化的推荐值
- 参数对结果不敏感，大部分情况下使用默认值即可
- 可以与ADX过滤器、成交量过滤器等组合使用，可能获得更好效果
- 适用于趋势跟踪策略，震荡市场中效果可能不明显

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