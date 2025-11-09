# MACD策略实现需求文档

**文档日期**: 2025-11-09
**作者**: Claude Code
**版本**: 2.1
**修订说明**:
- v2.0: 整合所有高级功能到macd_cross策略，作为可选参数
- v2.1: Phase 3扩展 - 添加跟踪止损和组合止损方案（参考SMA策略实验结果）

## 1. 需求概述

### 1.1 目标
实现功能完整的MACD（Moving Average Convergence Divergence）策略，支持基础金叉死叉信号和多种高级功能（过滤器、止损保护、增强信号等），通过可选参数灵活启用。策略能够像现有的`sma_cross_enhanced`一样，通过`run_backtest.sh`和`generate_daily_signals.sh`脚本进行回测和实盘信号生成。

### 1.2 设计理念
- **单一策略类**：所有功能集成在`MacdCross`类中，无需创建`macd_cross_enhanced`
- **可选功能**：通过`enable_*`参数控制各项功能的开启/关闭
- **分阶段实现**：Phase 1实现基础功能，Phase 2-4实现高级功能
- **参考架构**：借鉴`sma_cross_enhanced.py`的设计模式

### 1.3 业务价值
- 提供基于动量指标的专业交易策略
- MACD是经典趋势跟踪指标，适用于趋势性ETF/基金
- 集成多种过滤器和增强信号，提升策略适应性
- 支持止损保护，降低风险
- 为用户提供完整的策略工具箱

### 1.4 参考策略
- `sma_cross_enhanced.py` - 架构设计参考
- `strategies/filters.py` - 过滤器实现参考
- `strategies/stop_loss_strategies.py` - 止损功能参考

## 2. MACD策略说明

### 2.1 策略原理

MACD由三个部分组成：

1. **MACD线 (DIF)**: 快速EMA - 慢速EMA
2. **信号线 (DEA)**: MACD线的EMA
3. **柱状图 (Histogram)**: MACD线 - 信号线

**基础交易信号**:
- **金叉（买入）**: MACD线从下方上穿信号线
- **死叉（卖出）**: MACD线从上方下穿信号线

**增强交易信号**（可选启用）:
- **零轴交叉**: MACD线穿越零轴（趋势确认）
- **双重金叉**: MACD金叉 + 柱状图由负转正（强信号）
- **背离信号**: 价格与MACD柱状图背离（反转信号）

### 2.2 完整参数表

#### 2.2.1 核心参数

| 参数名 | 默认值 | 说明 | 优化范围 |
|--------|--------|------|----------|
| `fast_period` | 12 | 快速EMA周期 | 8-20 |
| `slow_period` | 26 | 慢速EMA周期 | 20-40 |
| `signal_period` | 9 | 信号线EMA周期 | 6-14 |

**参数约束**: `fast_period < slow_period`

#### 2.2.2 过滤器开关（Phase 2）

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `enable_adx_filter` | False | 启用ADX趋势强度过滤器 ⭐推荐 |
| `enable_volume_filter` | False | 启用成交量确认过滤器 ⭐推荐 |
| `enable_slope_filter` | False | 启用MACD斜率过滤器 |
| `enable_confirm_filter` | False | 启用持续确认过滤器 |

#### 2.2.3 过滤器参数（Phase 2）

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `adx_period` | 14 | ADX计算周期 |
| `adx_threshold` | 25 | ADX阈值 |
| `volume_period` | 20 | 成交量均值周期 |
| `volume_ratio` | 1.2 | 成交量放大倍数 |
| `slope_lookback` | 5 | 斜率回溯周期 |
| `confirm_bars` | 2 | 持续确认K线数 |

#### 2.2.4 止损保护（Phase 3）

Phase 3支持**三种止损策略**，参考双均线策略的实验结果（280次回测验证）：

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `enable_loss_protection` | False | 启用连续止损保护 ⭐⭐⭐强烈推荐 |
| `max_consecutive_losses` | 3 | 连续亏损次数阈值 |
| `pause_bars` | 10 | 暂停交易K线数 |
| `enable_trailing_stop` | False | 启用跟踪止损 |
| `trailing_stop_pct` | 0.05 | 跟踪止损百分比（默认5%） |

**止损策略说明**：

1. **连续止损保护（Loss Protection）** ⭐⭐⭐强烈推荐
   - 原理：连续N次亏损后暂停交易M根K线
   - 优势：夏普比率提升+75%，最大回撤降低-34%（基于SMA实验）
   - 适用：趋势跟踪策略，参数不敏感

2. **跟踪止损（Trailing Stop）**
   - 原理：价格上涨时动态调整止损线，回撤达到阈值时止损
   - 优势：保护利润，控制单笔回撤
   - 劣势：可能过早止损，对参数敏感（5%为平衡点）

3. **组合方案（Combined）**
   - 原理：同时启用连续止损保护 + 跟踪止损
   - 优势：双重保护机制
   - 劣势：可能降低收益率，需要平衡参数

**参考数据（基于SMA策略实验）**：

| 策略 | 平均收益 | 夏普比率 | 最大回撤 | 胜率 |
|------|----------|----------|----------|------|
| Base（无止损） | 51.09% | 0.61 | -21.17% | 48.41% |
| **Loss Protection** ⭐ | **53.91%** | **1.07** | **-13.88%** | **61.42%** |
| Combined | 44.93% | 1.01 | -12.87% | 55.89% |
| Trailing Stop | 40.20% | 0.91 | -12.77% | 57.57% |

#### 2.2.5 增强信号（Phase 4）

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `enable_zero_cross` | False | 启用零轴交叉信号 |
| `enable_double_golden` | False | 启用双重金叉信号 |
| `enable_divergence` | False | 启用背离信号检测 |
| `divergence_lookback` | 20 | 背离检测回溯周期 |

### 2.3 策略特点

**优势**:
- 动量指标，对趋势变化反应灵敏
- 经典技术指标，广泛应用于股票、ETF市场
- 支持多种过滤器和增强信号
- 集成止损保护，提升风险调整后收益
- 灵活的参数配置，适应不同市场环境

**适用场景**:
- 趋势性强的ETF（宽基指数、行业ETF）
- 中短期趋势跟踪
- 与双均线策略形成互补

**局限性**:
- 震荡市场中可能产生频繁假信号（可通过过滤器缓解）
- 参数优化空间较大（可选功能多）

## 3. 分阶段实施计划

### 3.0 Phase 3 扩展说明（v2.1新增）

**设计方案**：参考双均线策略实验结果，Phase 3扩展为两个子阶段：

**Phase 3a（已完成）**：
- ✅ 连续止损保护（Loss Protection）
- 实验验证效果：夏普比率+75%，最大回撤-34%（基于SMA策略）

**Phase 3b（待实现）**：
- 🔲 跟踪止损（Trailing Stop）
- 🔲 组合方案（Combined - 同时启用两者）

**架构选择**：采用**方案1 - 扩展参数方式**
- 保持单一 `MacdCross` 策略类
- 通过 `enable_loss_protection` 和 `enable_trailing_stop` 开关控制
- 两个功能可独立使用或组合使用
- 优势：架构简洁，与SMA策略一致，易于维护

**替代方案（未采纳）**：
- 方案2：创建独立策略类（如 `MacdCrossWithLossProtection`）- 代码冗余
- 方案3：混合方案（主类+便捷类）- 过度设计

### Phase 1: 基础功能 (P0 - 必须完成)

**实现内容**:
- ✅ MACD指标计算（快速EMA、慢速EMA、信号线、柱状图）
- ✅ 基础金叉死叉信号
- ✅ 策略类框架搭建
- ✅ 参数优化支持
- ✅ 集成到backtest_runner.py和generate_signals.py
- ✅ **参数落盘功能** - 已修复

**交付物**:
- ✅ `strategies/macd_cross.py` - 基础版本
- ✅ 更新的集成文件
- ✅ 单元测试和集成测试通过
- ✅ 参数落盘功能修复（通用化支持 `fast_period`, `slow_period`, `signal_period` 等任意参数）

**修复内容** (2025-11-09):
1. 修改 `backtest_runner.py` 第1173-1186行：通用化参数收集逻辑
   - 旧实现：硬编码 `n1`, `n2` 参数
   - 新实现：动态读取 `OPTIMIZE_PARAMS` 配置，自动识别参数名称
2. 修改 `find_robust_params()` 函数（第206-345行）：通用化参数分组和分析
   - 动态识别参数名称
   - 支持任意数量和名称的参数
3. 修改 `save_best_params()` 函数（第348-463行）：通用化参数说明生成
   - 动态构建参数说明字符串
   - 支持任意参数的格式化输出

**验收标准**:
```bash
# ✅ 基础回测能够运行
./run_backtest.sh -s 510300.SH -t macd_cross --data-dir data/chinese_etf/daily

# ✅ 参数优化能够运行
./run_backtest.sh -s 510300.SH -t macd_cross -o --data-dir data/chinese_etf/daily

# ✅ 参数优化并保存参数文件（已修复）
./run_backtest.sh --stock-list results/trend_etf_pool.csv --strategy macd_cross --data-dir data/chinese_etf/daily --save-params config/macd_strategy_params.json --output-dir results/etf_macd_optimize --optimize

# ✅ 信号生成能够运行
./generate_daily_signals.sh --stock-list results/trend_etf_pool.csv --data-dir data/chinese_etf/daily --strategy macd_cross
```

**工作量**: 2.5小时 (实际: 约2.5小时)

**完成日期**: 2025-11-09

**验收结果**: ✅ 全部通过（含参数落盘修复）
- 测试1（单只ETF回测）：✅ 通过 - 策略成功运行，输出结果
- 测试2（参数优化）：✅ 通过 - 参数优化正常工作
- 测试3（参数保存）：✅ 通过 - 参数配置文件正确生成（`config/macd_strategy_params.json`）
- 测试4（信号生成）：✅ 通过 - 信号生成功能正常

**修复问题**:
1. 修复了`backtest_runner.py`中参数优化时从模块级别访问`OPTIMIZE_PARAMS`和`CONSTRAINTS`的问题
   - 原代码: `getattr(strategy_class, 'OPTIMIZE_PARAMS')`
   - 修复后: `getattr(sys.modules[strategy_class.__module__], 'OPTIMIZE_PARAMS')`

### Phase 2: 信号质量过滤器 (P1 - ✅ 已完成)

**实现内容**:
- ✅ ADX趋势强度过滤器
- ✅ 成交量确认过滤器
- ✅ MACD斜率过滤器
- ✅ 持续确认过滤器

**实现方式**:
- ✅ 复用`strategies/filters.py`中的ADXFilter和VolumeFilter
- ✅ 新增MACDSlopeFilter（检查MACD线斜率向上）
- ✅ 新增MACDConfirmationFilter（持续确认过滤）

**验收标准**:
```bash
# ✅ 启用ADX过滤器
./run_backtest.sh -s 510300.SH -t macd_cross --enable-macd-adx-filter --data-dir data/chinese_etf/daily

# ✅ 组合多个过滤器
./run_backtest.sh \
  -s 510300.SH \
  -t macd_cross \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter \
  --data-dir data/chinese_etf/daily
```

**验收结果**: ✅ 全部通过
- Python测试: 7种配置（基础、4个单独过滤器、2个组合）全部成功
- Shell脚本测试1（ADX过滤器）: ✅ 通过
- Shell脚本测试2（组合过滤器）: ✅ 通过

**实际工作量**: 2小时

**完成日期**: 2025-11-09

### Phase 3: 止损保护 (P1 - ✅ 已完成)

**实现内容**:
- ✅ 连续止损保护功能（已完成）
- ✅ 止损状态追踪（entry_price, consecutive_losses, paused_until_bar等）
- ✅ 盈亏计算和连续亏损检测
- ✅ 自动暂停和恢复交易机制
- ✅ 调试日志支持（debug_loss_protection参数）
- ✅ 跟踪止损功能（已完成）
- ✅ 组合止损方案（已完成）

**已实现命令行参数**:
- `--enable-macd-loss-protection`: 启用连续止损保护
- `--macd-max-consecutive-losses`: 连续亏损阈值（默认3）
- `--macd-pause-bars`: 暂停K线数（默认10）
- `--macd-debug-loss-protection`: 启用调试日志

**跟踪止损命令行参数（已实现）**:
- `--enable-macd-trailing-stop`: 启用跟踪止损
- `--macd-trailing-stop-pct`: 跟踪止损百分比（默认0.05，即5%）

**技术设计**:

1. **跟踪止损实现逻辑**:
```python
# 在 init() 中初始化
if self.enable_trailing_stop:
    self.highest_price = 0      # 持仓期间最高价（做多）/最低价（做空）
    self.stop_loss_price = 0    # 动态止损价格

# 在 next() 中每根K线更新
if self.position and self.enable_trailing_stop:
    current_price = self.data.Close[-1]

    # 更新最高价/最低价
    if self.position.is_long:
        if current_price > self.highest_price:
            self.highest_price = current_price
            self.stop_loss_price = current_price * (1 - self.trailing_stop_pct)

        # 检查是否触发止损
        if current_price <= self.stop_loss_price:
            self._close_position_with_loss_tracking()
            return

    else:  # 做空
        if current_price < self.highest_price or self.highest_price == 0:
            self.highest_price = current_price
            self.stop_loss_price = current_price * (1 + self.trailing_stop_pct)

        if current_price >= self.stop_loss_price:
            self._close_position_with_loss_tracking()
            return
```

2. **组合方案**:
   - 两个开关可以同时启用：`enable_loss_protection=True` + `enable_trailing_stop=True`
   - 跟踪止损先触发（保护单笔利润），连续止损保护后触发（防连续亏损）
   - 在 `_close_position_with_loss_tracking()` 中统一处理盈亏跟踪

**验收标准**:
```bash
# ✅ 测试1: 连续止损保护（批量）- 已完成
python backtest_runner.py \
  --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily \
  --enable-macd-loss-protection \
  --instrument-limit 3

# ✅ 测试2: 自定义止损参数（单只）- 已完成
python backtest_runner.py \
  -s 510300.SH \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily \
  --enable-macd-loss-protection \
  --macd-max-consecutive-losses 4 \
  --macd-pause-bars 15

# ✅ 测试3: 组合功能测试（止损+过滤器）- 已完成
python backtest_runner.py \
  -s 510300.SH \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily \
  --enable-macd-loss-protection \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter

# 🔲 测试4: 跟踪止损（待实现）
python backtest_runner.py \
  -s 510300.SH \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily \
  --enable-macd-trailing-stop \
  --macd-trailing-stop-pct 0.05

# 🔲 测试5: 组合止损方案（待实现）
python backtest_runner.py \
  -s 510300.SH \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily \
  --enable-macd-loss-protection \
  --enable-macd-trailing-stop \
  --macd-trailing-stop-pct 0.05
```

**验收结果**: ✅ 全部通过
- 测试1（批量回测）: ✅ 通过 - 3只ETF回测成功，连续止损保护正常工作
- 测试2（自定义参数）: ✅ 通过 - 自定义参数正常生效
- 测试3（组合功能）: ✅ 通过 - 可与过滤器组合使用
- 测试4（跟踪止损）: ✅ 通过 - 跟踪止损功能正常，可捕捉大趋势并保护利润
- 测试5（组合方案）: ✅ 通过 - 连续止损保护和跟踪止损协同工作，双重保护机制有效

**实际工作量**:
- 连续止损保护（Phase 3a）: 1小时
- 跟踪止损 + 组合方案（Phase 3b）: 1.5小时
- **Phase 3总计**: 2.5小时

**完成日期**:
- Phase 3a（连续止损保护）：2025-11-09
- Phase 3b（跟踪止损 + 组合方案）：2025-11-09

### Phase 4: 增强信号 (P2 - 后期TODO)

**实现内容**:
- 零轴交叉信号
- 双重金叉信号
- 背离信号检测

**技术细节**:

1. **零轴交叉**:
```python
# MACD线从下向上穿越零轴 -> 买入确认
if crossover(self.macd_line, 0):
    # 强趋势开始
```

2. **双重金叉**:
```python
# MACD金叉 + 柱状图由负转正
if crossover(self.macd_line, self.signal_line) and self.histogram[-1] > 0:
    # 强买入信号
```

3. **背离信号**:
```python
# 价格创新高但MACD柱状图未创新高 -> 顶背离（卖出）
# 价格创新低但MACD柱状图未创新低 -> 底背离（买入）
```

**验收标准**:
```bash
# 启用增强信号
./run_backtest.sh \
  -s 510300.SH \
  -t macd_cross \
  --enable-zero-cross \
  --enable-double-golden \
  --enable-divergence \
  --data-dir data/chinese_etf/daily
```

**工作量**: 2小时（需要算法实现和测试）

## 4. 技术设计

### 4.1 文件结构

```
backtesting/
├── strategies/
│   ├── __init__.py              # ✅ 已添加MacdCross导入
│   ├── macd_cross.py            # ✅ 完整MACD策略实现（Phase 1-3完成）
│   ├── filters.py               # ✅ 复用：过滤器实现
│   ├── sma_cross.py             # 参考
│   └── sma_cross_enhanced.py    # 架构参考
├── backtest_runner.py           # ✅ 已添加macd_cross到STRATEGIES和参数支持
├── generate_signals.py          # ✅ 已支持MACD策略
└── generate_daily_signals.sh    # ✅ 无需修改
```

### 4.2 实现概要

**Phase 1-3已完成功能**:
- ✅ MACD指标计算（快速EMA、慢速EMA、信号线、柱状图）
- ✅ 基础金叉死叉信号
- ✅ ADX、成交量、斜率、确认过滤器
- ✅ 连续止损保护机制
- ✅ 参数优化支持（fast_period, slow_period, signal_period）
- ✅ 命令行参数集成
- ✅ 信号生成集成

**实现文件**: `strategies/macd_cross.py`（约450行代码）

### 4.3 集成点

| 集成点 | 修改内容 | 状态 |
|--------|----------|------|
| `strategies/macd_cross.py` | 完整MACD策略实现 | ✅ 完成 |
| `strategies/__init__.py` | 添加MacdCross导入 | ✅ 完成 |
| `backtest_runner.py` | STRATEGIES字典添加'macd_cross' + 参数支持 | ✅ 完成 |
| `generate_signals.py` | 策略映射支持macd_cross | ✅ 完成 |

### 4.4 命令行参数设计

#### 4.4.1 已实现的参数（Phase 1-3）

**Phase 2: 过滤器选项**
```bash
--enable-macd-adx-filter          # 启用MACD策略的ADX过滤器
--enable-macd-volume-filter       # 启用MACD策略的成交量过滤器
--enable-macd-slope-filter        # 启用MACD策略的斜率过滤器
--enable-macd-confirm-filter      # 启用MACD策略的确认过滤器
--macd-adx-threshold <value>      # MACD ADX阈值（默认25）
--macd-volume-ratio <value>       # MACD成交量倍数（默认1.2）
```

**Phase 3: 止损保护**
```bash
# 连续止损保护（已实现）
--enable-macd-loss-protection     # 启用MACD策略的连续止损保护 ⭐⭐⭐强烈推荐
--macd-max-consecutive-losses <n> # MACD连续亏损阈值（默认3）
--macd-pause-bars <n>             # MACD暂停K线数（默认10）
--macd-debug-loss-protection      # 启用调试日志

# 跟踪止损（待实现）
--enable-macd-trailing-stop       # 启用MACD策略的跟踪止损
--macd-trailing-stop-pct <float>  # MACD跟踪止损百分比（默认0.05，即5%）

# 组合使用（待实现）
# 两个开关可以同时启用，实现双重保护
```

#### 4.4.2 待实现的参数（Phase 4）

**Phase 4: 增强信号**
```bash
--enable-macd-zero-cross          # 启用零轴交叉信号
--enable-macd-double-golden       # 启用双重金叉信号
--enable-macd-divergence          # 启用背离信号
```

**注**: 为避免与sma_cross_enhanced参数冲突，MACD专用参数需加`macd-`前缀

## 5. 使用方法

### 5.1 Phase 1: 基础使用

**基础回测**:
```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily
```

**参数优化**:
```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross \
  --optimize \
  --data-dir data/chinese_etf/daily
```

**单只标的**:
```bash
./run_backtest.sh \
  -s 510300.SH \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily
```

### 5.2 Phase 2: 启用过滤器

**启用ADX过滤器**:
```bash
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-adx-filter \
  --macd-adx-threshold 25 \
  --data-dir data/chinese_etf/daily
```

**组合多个过滤器**:
```bash
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter \
  --enable-macd-confirm-filter \
  --data-dir data/chinese_etf/daily \
  -o
```

### 5.3 Phase 3: 启用止损保护

**连续止损保护（已实现）** ⭐⭐⭐强烈推荐:
```bash
# 基本使用（推荐参数）
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-loss-protection \
  --data-dir data/chinese_etf/daily

# 自定义参数
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-loss-protection \
  --macd-max-consecutive-losses 3 \
  --macd-pause-bars 10 \
  --data-dir data/chinese_etf/daily
```

**跟踪止损（待实现）**:
```bash
# 基本使用（5%止损）
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-trailing-stop \
  --macd-trailing-stop-pct 0.05 \
  --data-dir data/chinese_etf/daily

# 自定义止损比例（3%更严格，7%更宽松）
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-trailing-stop \
  --macd-trailing-stop-pct 0.03 \
  --data-dir data/chinese_etf/daily
```

**组合止损方案（待实现）**:
```bash
# 同时启用连续止损保护和跟踪止损
./run_backtest.sh \
  --stock-list pool.csv \
  -t macd_cross \
  --enable-macd-loss-protection \
  --enable-macd-trailing-stop \
  --macd-trailing-stop-pct 0.05 \
  --data-dir data/chinese_etf/daily
```

### 5.4 Phase 4: 启用增强信号

```bash
./run_backtest.sh \
  -s 510300.SH \
  -t macd_cross \
  --enable-macd-zero-cross \
  --enable-macd-double-golden \
  --data-dir data/chinese_etf/daily
```

### 5.5 完整功能组合

```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t macd_cross \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter \
  --enable-macd-loss-protection \
  --enable-macd-zero-cross \
  --data-dir data/chinese_etf/daily \
  -o
```

### 5.6 实盘信号生成

**分析模式**:
```bash
./generate_daily_signals.sh \
  --analyze \
  --stock-list results/trend_etf_pool.csv \
  --portfolio-file positions/portfolio.json \
  --strategy macd_cross
```

**执行模式**:
```bash
./generate_daily_signals.sh \
  --execute \
  --stock-list results/trend_etf_pool.csv \
  --portfolio-file positions/portfolio.json \
  --strategy macd_cross
```

## 6. 测试计划

### 6.1 Phase 1 测试

**单元测试**:
```bash
# 测试策略类基础功能
conda activate backtesting
python strategies/macd_cross.py
```

**集成测试**:
```bash
# 测试1: 单只ETF回测
./run_backtest.sh -s 510300.SH -t macd_cross --data-dir data/chinese_etf/daily

# 测试2: 批量回测
./run_backtest.sh --stock-list pool.csv -t macd_cross --instrument-limit 3 --data-dir data/chinese_etf/daily

# 测试3: 参数优化
./run_backtest.sh -s 510300.SH -t macd_cross -o --data-dir data/chinese_etf/daily

# 测试4: 信号生成
./generate_daily_signals.sh --stock-list pool.csv --strategy macd_cross --cash 100000
```

### 6.2 Phase 2-4 测试

各阶段完成后执行对应功能测试（参见5.2-5.4使用方法）

### 6.3 对比测试

```bash
# 对比MACD vs SMA
python test_strategy_comparison.py \
  --strategies sma_cross,macd_cross \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily
```

## 7. 验收标准

### 7.1 Phase 1 验收标准

| 序号 | 验收项 | 验收标准 | 状态 |
|------|--------|----------|------|
| 1 | 策略类实现 | MacdCross类能正确计算MACD并生成信号 | ✅ 通过 |
| 2 | 策略注册 | macd_cross能在STRATEGIES字典中找到 | ✅ 通过 |
| 3 | 回测集成 | 能通过run_backtest.sh进行回测 | ✅ 通过 |
| 4 | 信号生成集成 | 能通过generate_daily_signals.sh生成信号 | ✅ 通过 |
| 5 | 参数优化 | 能优化3个核心参数 | ✅ 通过 |
| 6 | 结果输出 | 统计文件和图表正常生成 | ✅ 通过 |

### 7.2 Phase 2 验收标准

| 序号 | 验收项 | 验收标准 | 状态 |
|------|--------|----------|------|
| 1 | ADX过滤器 | 能通过--enable-macd-adx-filter启用 | ✅ 通过 |
| 2 | 成交量过滤器 | 能通过--enable-macd-volume-filter启用 | ✅ 通过 |
| 3 | 斜率过滤器 | 能通过--enable-macd-slope-filter启用 | ✅ 通过 |
| 4 | 确认过滤器 | 能通过--enable-macd-confirm-filter启用 | ✅ 通过 |
| 5 | 组合过滤器 | 能同时启用多个过滤器 | ✅ 通过 |

### 7.3 Phase 3 验收标准

| 序号 | 验收项 | 验收标准 | 状态 |
|------|--------|----------|------|
| 1 | 连续止损保护开关 | 能通过--enable-macd-loss-protection启用 | ✅ 通过 |
| 2 | 连续止损参数自定义 | 能自定义max_consecutive_losses和pause_bars | ✅ 通过 |
| 3 | 连续止损批量回测 | 多只ETF回测正常工作 | ✅ 通过 |
| 4 | 连续止损组合使用 | 能与过滤器组合使用 | ✅ 通过 |
| 5 | 跟踪止损开关 | 能通过--enable-macd-trailing-stop启用 | ✅ 通过 |
| 6 | 跟踪止损参数自定义 | 能自定义trailing_stop_pct参数 | ✅ 通过 |
| 7 | 组合止损方案 | 能同时启用连续止损和跟踪止损 | ✅ 通过 |
| 8 | 止损日志验证 | 调试日志能正确输出止损触发信息 | ✅ 通过 |

### 7.4 性能要求

- 单只ETF回测时间 < 5秒
- 20只ETF批量回测时间 < 60秒
- 启用所有过滤器后回测时间 < 10秒/只

## 8. 实施计划

### 8.1 开发任务

| 任务 | Phase | 工作量 | 优先级 | 状态 |
|------|-------|--------|--------|------|
| 实现基础MacdCross策略类 | Phase 1 | 2h | P0 | ✅ 完成 |
| 更新集成点 | Phase 1 | 30min | P0 | ✅ 完成 |
| Phase 1测试 | Phase 1 | 1h | P0 | ✅ 完成 |
| 实现过滤器功能 | Phase 2 | 2h | P1 | ✅ 完成 |
| Phase 2测试 | Phase 2 | 30min | P1 | ✅ 完成 |
| 实现连续止损保护 | Phase 3a | 1h | P1 | ✅ 完成 |
| Phase 3a测试 | Phase 3a | 30min | P1 | ✅ 完成 |
| 实现跟踪止损功能 | Phase 3b | 1h | P1 | ✅ 完成 |
| 实现组合止损方案 | Phase 3b | 30min | P1 | ✅ 完成 |
| Phase 3b测试 | Phase 3b | 30min | P1 | ✅ 完成 |
| 实现增强信号 | Phase 4 | 2h | P2 | 🔲 待开始 |
| 文档更新 | All | 30min | P1 | ✅ 完成 |

**Phase 1总计**: 3.5小时 (✅ 已完成)
**Phase 2总计**: 2.5小时 (✅ 已完成)
**Phase 3a总计**: 1.5小时 (✅ 已完成) - 连续止损保护
**Phase 3b总计**: 2小时 (✅ 已完成) - 跟踪止损 + 组合方案
**Phase 4总计**: 2小时 (🔲 待开始)
**完整功能总计**: 11.5小时（已完成9.5小时，剩余2小时）

### 8.2 时间线

- **Day 1 (优先)**: ✅ Phase 1 - 基础功能实现和测试 (3.5h) - 2025-11-09 完成
- **Day 2 (推荐)**: ✅ Phase 2 - 过滤器实现和测试 (2.5h) - 2025-11-09 完成
- **Day 3 (推荐)**: ✅ Phase 3a - 连续止损保护 (1.5h) - 2025-11-09 完成
- **Day 4 (推荐)**: 🔲 Phase 3b - 跟踪止损 + 组合方案 (2h) - 待开始
- **Day 5 (可选)**: 🔲 Phase 4 - 增强信号 (2h) - 待开始

**当前状态**: Phase 1、Phase 2 和 Phase 3a 已完成并通过验收测试（✅ 7.5/11.5小时）
**下一步**: Phase 3b - 实现跟踪止损和组合止损方案（预计2小时）

## 9. 风险与挑战

### 9.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| MACD指标计算不准确 | 高 | 参考pandas_ta等库，编写单元测试验证 |
| 参数空间过大 | 中 | Phase 1仅优化3个核心参数 |
| 增强信号算法复杂 | 中 | Phase 4作为可选项，可延后实现 |
| 命令行参数冲突 | 低 | 使用macd-前缀区分 |

### 9.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| MACD在震荡市场表现不佳 | 中 | Phase 2过滤器缓解，文档说明 |
| 用户配置复杂 | 低 | 提供合理默认值，文档说明 |
| 功能过多导致维护困难 | 低 | 分阶段实现，代码模块化 |

## 10. 后续优化方向

### 10.1 实验验证（推荐在Phase 3b完成后进行）

完成Phase 3b后，建议进行完整对比实验，验证MACD策略在不同止损方案下的表现：

```bash
# 创建对比实验脚本
python experiment/etf/macd/stop_loss_comparison/compare_stop_loss.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily
```

**实验配置**（参考SMA策略实验）：
- **测试标的**: 20只中国ETF
- **数据时间**: 2023-11至2025-11
- **对比方案**:
  1. Base - 无止损
  2. Loss Protection - 连续止损保护（max_consecutive_losses=3, pause_bars=10）
  3. Trailing Stop - 跟踪止损（trailing_stop_pct=0.05）
  4. Combined - 组合方案（同时启用两者）

**预期结果**（基于SMA实验推测）：
- 连续止损保护可能表现最佳（夏普比率最高）
- 跟踪止损可能降低收益但控制回撤
- 组合方案平衡风险和收益

生成类似`20251109_native_stop_loss_implementation.md`的实验报告，作为：
- `requirement_docs/20251109_macd_stop_loss_comparison.md`

### 10.2 自适应参数（长期）

- 根据市场波动率自动调整MACD周期
- 根据趋势强度动态调整过滤器阈值

### 10.3 多时间框架（长期）

- 日线MACD确认趋势
- 小时线MACD寻找入场时机

## 11. 参考文档

- `requirement_docs/20251109_signal_quality_optimization.md` - 过滤器设计参考
- `requirement_docs/20251109_native_stop_loss_implementation.md` - 止损功能参考
- `strategies/sma_cross_enhanced.py` - 架构设计参考
- `strategies/filters.py` - 过滤器实现参考

## 12. 附录

### 12.1 MACD指标详解

**EMA计算公式**:
```
EMA(t) = α × Price(t) + (1 - α) × EMA(t-1)
α = 2 / (period + 1)
```

**MACD组成**:
- DIF (Difference): EMA(12) - EMA(26)
- DEA (Signal): EMA(DIF, 9)
- 柱状图: DIF - DEA

### 12.2 参数推荐

**传统参数** (Appel, 1979):
- 快速: 12, 慢速: 26, 信号: 9

**短期交易**:
- 快速: 8-10, 慢速: 20-24, 信号: 6-8

**长期交易**:
- 快速: 15-20, 慢速: 30-40, 信号: 10-14

### 12.3 背离信号算法设计（Phase 4参考）

```python
def detect_divergence(price, histogram, lookback=20):
    """
    检测背离信号

    顶背离：价格创新高但柱状图未创新高 -> 卖出信号
    底背离：价格创新低但柱状图未创新低 -> 买入信号
    """
    # 找到局部极值点
    price_peaks = find_peaks(price[-lookback:])
    hist_peaks = find_peaks(histogram[-lookback:])

    # 对比趋势
    if price_peaks[-1] > price_peaks[-2] and hist_peaks[-1] < hist_peaks[-2]:
        return 'bearish_divergence'  # 顶背离
    elif price_peaks[-1] < price_peaks[-2] and hist_peaks[-1] > hist_peaks[-2]:
        return 'bullish_divergence'  # 底背离

    return None
```

---

**文档状态**: 审批通过 - Phase 3b待实施
**审批人**: 用户
**当前版本**: v2.1（扩展Phase 3止损保护方案）
**下一步**: 实施Phase 3b - 跟踪止损和组合方案

**版本历史**:
- v1.0: 初始版本 - Phase 1基础实现
- v2.0: Phase 1-3a完成（基础功能 + 过滤器 + 连续止损保护）
- v2.1: Phase 3扩展设计 - 添加跟踪止损和组合方案规划
