# MACD策略实现需求文档

**文档日期**: 2025-11-09
**作者**: Claude Code
**版本**: 2.2 (精简版)
**修订说明**:
- v2.0: 整合所有高级功能到macd_cross策略,作为可选参数
- v2.1: Phase 3扩展 - 添加跟踪止损和组合止损方案
- v2.2: 精简文档 - 已完成内容简化为代码引用

## 1. 需求概述

**实现状态**:
- Phase 1-3: ✅ 已完成（基础功能 + 过滤器 + 止损保护）
- Phase 4: 🔲 待实现（增强信号）

**核心代码**: `strategies/macd_cross.py` (约500行)

### 1.1 业务价值
- 基于动量指标的专业交易策略
- MACD是经典趋势跟踪指标，适用于趋势性ETF/基金
- 集成多种过滤器和三种止损保护方案
- 单一策略类，通过`enable_*`参数灵活控制功能

## 2. MACD策略说明

### 2.1 策略原理

MACD由三个部分组成：
1. **MACD线 (DIF)**: 快速EMA - 慢速EMA
2. **信号线 (DEA)**: MACD线的EMA
3. **柱状图 (Histogram)**: MACD线 - 信号线

**基础交易信号**:
- **金叉（买入）**: MACD线从下方上穿信号线
- **死叉（卖出）**: MACD线从上方下穿信号线

### 2.2 完整参数表

#### 2.2.1 核心参数

| 参数名 | 默认值 | 说明 | 优化范围 |
|--------|--------|------|----------|
| `fast_period` | 12 | 快速EMA周期 | 8-20 |
| `slow_period` | 26 | 慢速EMA周期 | 20-40 |
| `signal_period` | 9 | 信号线EMA周期 | 6-14 |

**参数约束**: `fast_period < slow_period`

#### 2.2.2 过滤器开关（Phase 2 - ✅ 已完成）

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `enable_adx_filter` | False | 启用ADX趋势强度过滤器 ⭐推荐 |
| `enable_volume_filter` | False | 启用成交量确认过滤器 ⭐推荐 |
| `enable_slope_filter` | False | 启用MACD斜率过滤器 |
| `enable_confirm_filter` | False | 启用持续确认过滤器 |

**代码位置**: `strategies/macd_cross.py:90-140`

#### 2.2.3 止损保护（Phase 3 - ✅ 已完成）

三种止损策略支持：

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `enable_loss_protection` | False | 启用连续止损保护 ⭐⭐⭐强烈推荐 |
| `max_consecutive_losses` | 3 | 连续亏损次数阈值 |
| `pause_bars` | 10 | 暂停交易K线数 |
| `enable_trailing_stop` | False | 启用跟踪止损 |
| `trailing_stop_pct` | 0.05 | 跟踪止损百分比（默认5%） |

**止损策略说明**（参考SMA实验结果）：

| 策略 | 平均收益 | 夏普比率 | 最大回撤 | 胜率 |
|------|----------|----------|----------|------|
| Base（无止损） | 51.09% | 0.61 | -21.17% | 48.41% |
| **Loss Protection** ⭐ | **53.91%** | **1.07** | **-13.88%** | **61.42%** |
| Combined | 44.93% | 1.01 | -12.87% | 55.89% |
| Trailing Stop | 40.20% | 0.91 | -12.77% | 57.57% |

**代码位置**:
- 连续止损保护: `strategies/macd_cross.py:150-200`
- 跟踪止损: `strategies/macd_cross.py:280-350`

#### 2.2.4 增强信号（Phase 4 - 🔲 待实现）

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `enable_zero_cross` | False | 启用零轴交叉信号 |
| `enable_double_golden` | False | 启用双重金叉信号 |
| `enable_divergence` | False | 启用背离信号检测 |
| `divergence_lookback` | 20 | 背离检测回溯周期 |

## 3. 已完成功能总结

### Phase 1: 基础功能 ✅
- MACD指标计算
- 基础金叉死叉信号
- 参数优化支持
- 集成到backtest_runner.py和generate_signals.py
- 参数落盘功能

**代码位置**: `strategies/macd_cross.py:1-80`
**集成位置**:
- `backtest_runner.py:1173-1186` (参数保存)
- `backtest_runner.py:206-345` (参数优化)

**验收命令**:
```bash
# 基础回测
./run_backtest.sh -s 510300.SH -t macd_cross --data-dir data/chinese_etf/daily

# 参数优化并保存
./run_backtest.sh --stock-list results/trend_etf_pool.csv --strategy macd_cross \
  --data-dir data/chinese_etf/daily --save-params config/macd_strategy_params.json --optimize
```

### Phase 2: 信号质量过滤器 ✅
- ADX趋势强度过滤器（复用`strategies/filters.py`）
- 成交量确认过滤器（复用`strategies/filters.py`）
- MACD斜率过滤器（新增）
- 持续确认过滤器（新增）

**代码位置**: `strategies/macd_cross.py:90-140`

**验收命令**:
```bash
# 组合多个过滤器
./run_backtest.sh -s 510300.SH -t macd_cross \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter \
  --data-dir data/chinese_etf/daily
```

### Phase 3: 止损保护 ✅
- 连续止损保护功能（Phase 3a）
- 跟踪止损功能（Phase 3b）
- 组合止损方案（Phase 3b）
- 止损状态追踪和调试日志支持

**代码位置**:
- 连续止损: `strategies/macd_cross.py:150-200`
- 跟踪止损: `strategies/macd_cross.py:280-350`

**命令行参数**:
```bash
# 连续止损保护
--enable-macd-loss-protection
--macd-max-consecutive-losses <n>
--macd-pause-bars <n>

# 跟踪止损
--enable-macd-trailing-stop
--macd-trailing-stop-pct <float>

# 组合方案（同时启用）
--enable-macd-loss-protection --enable-macd-trailing-stop
```

**验收命令**:
```bash
# 测试连续止损保护
python backtest_runner.py -s 510300.SH --strategy macd_cross \
  --data-dir data/chinese_etf/daily --enable-macd-loss-protection

# 测试跟踪止损
python backtest_runner.py -s 510300.SH --strategy macd_cross \
  --data-dir data/chinese_etf/daily --enable-macd-trailing-stop

# 测试组合方案
python backtest_runner.py -s 510300.SH --strategy macd_cross \
  --data-dir data/chinese_etf/daily \
  --enable-macd-loss-protection --enable-macd-trailing-stop
```

## 4. 待实现功能 - Phase 4: 增强信号 🔲

### 4.1 实现内容

1. **零轴交叉信号**:
```python
# MACD线从下向上穿越零轴 -> 买入确认
if crossover(self.macd_line, 0):
    # 强趋势开始
```

2. **双重金叉信号**:
```python
# MACD金叉 + 柱状图由负转正
if crossover(self.macd_line, self.signal_line) and self.histogram[-1] > 0:
    # 强买入信号
```

3. **背离信号检测**:
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

### 4.2 命令行参数设计

```bash
--enable-macd-zero-cross          # 启用零轴交叉信号
--enable-macd-double-golden       # 启用双重金叉信号
--enable-macd-divergence          # 启用背离信号
--macd-divergence-lookback <n>    # 背离检测回溯周期（默认20）
```

### 4.3 验收标准

```bash
# 启用增强信号
./run_backtest.sh -s 510300.SH -t macd_cross \
  --enable-macd-zero-cross \
  --enable-macd-double-golden \
  --enable-macd-divergence \
  --data-dir data/chinese_etf/daily
```

### 4.4 实施计划

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| 实现零轴交叉信号 | 30min | P2 |
| 实现双重金叉信号 | 30min | P2 |
| 实现背离信号检测 | 1h | P2 |
| 测试和文档更新 | 30min | P2 |

**总计**: 2.5小时

### 4.5 技术挑战

- 背离信号检测需要实现可靠的局部极值识别算法
- 需要平衡信号灵敏度和假信号过滤

## 5. 使用方法

### 5.1 基础使用

```bash
# 基础回测
./run_backtest.sh --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross --data-dir data/chinese_etf/daily

# 参数优化
./run_backtest.sh --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross --optimize --data-dir data/chinese_etf/daily
```

### 5.2 启用过滤器

```bash
./run_backtest.sh --stock-list pool.csv -t macd_cross \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter \
  --data-dir data/chinese_etf/daily -o
```

### 5.3 启用止损保护（强烈推荐）

```bash
# 连续止损保护（推荐）
./run_backtest.sh --stock-list pool.csv -t macd_cross \
  --enable-macd-loss-protection \
  --data-dir data/chinese_etf/daily

# 跟踪止损
./run_backtest.sh --stock-list pool.csv -t macd_cross \
  --enable-macd-trailing-stop \
  --macd-trailing-stop-pct 0.05 \
  --data-dir data/chinese_etf/daily

# 组合方案
./run_backtest.sh --stock-list pool.csv -t macd_cross \
  --enable-macd-loss-protection \
  --enable-macd-trailing-stop \
  --data-dir data/chinese_etf/daily
```

### 5.4 完整功能组合

```bash
./run_backtest.sh --stock-list results/trend_etf_pool.csv -t macd_cross \
  --enable-macd-adx-filter \
  --enable-macd-volume-filter \
  --enable-macd-loss-protection \
  --data-dir data/chinese_etf/daily -o
```

### 5.5 实盘信号生成

```bash
# 分析模式
./generate_daily_signals.sh --analyze \
  --stock-list results/trend_etf_pool.csv \
  --portfolio-file positions/portfolio.json \
  --strategy macd_cross

# 执行模式
./generate_daily_signals.sh --execute \
  --stock-list results/trend_etf_pool.csv \
  --portfolio-file positions/portfolio.json \
  --strategy macd_cross
```

## 6. 后续优化方向

### 6.1 实验验证（推荐在Phase 4完成后进行）

建议进行完整对比实验，验证MACD策略在不同配置下的表现：

```bash
# 创建对比实验
python experiment/etf/macd/stop_loss_comparison/compare_stop_loss.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily
```

**实验配置**：
- **测试标的**: 20只中国ETF
- **数据时间**: 2023-11至2025-11
- **对比方案**: Base, Loss Protection, Trailing Stop, Combined

### 6.2 长期优化方向

- **自适应参数**: 根据市场波动率自动调整MACD周期
- **多时间框架**: 日线+小时线MACD组合
- **机器学习**: 动态优化过滤器阈值

## 7. 附录

### 7.1 MACD指标详解

**EMA计算公式**:
```
EMA(t) = α × Price(t) + (1 - α) × EMA(t-1)
α = 2 / (period + 1)
```

**MACD组成**:
- DIF (Difference): EMA(12) - EMA(26)
- DEA (Signal): EMA(DIF, 9)
- 柱状图: DIF - DEA

### 7.2 参数推荐

**传统参数** (Appel, 1979):
- 快速: 12, 慢速: 26, 信号: 9

**短期交易**:
- 快速: 8-10, 慢速: 20-24, 信号: 6-8

**长期交易**:
- 快速: 15-20, 慢速: 30-40, 信号: 10-14

## 8. 参考文档

- `requirement_docs/20251109_signal_quality_optimization.md` - 过滤器设计参考
- `requirement_docs/20251109_native_stop_loss_implementation.md` - 止损功能参考（SMA实验）
- `strategies/sma_cross_enhanced.py` - 架构设计参考
- `strategies/filters.py` - 过滤器实现参考

---

**文档状态**: Phase 1-3 已完成 ✅ | Phase 4 待实施 🔲
**当前版本**: v2.2（精简版）
**下一步**: 实施Phase 4 - 增强信号（可选，优先级P2）

**版本历史**:
- v1.0: 初始版本 - Phase 1基础实现
- v2.0: Phase 1-3a完成（基础功能 + 过滤器 + 连续止损保护）
- v2.1: Phase 3扩展设计 - 添加跟踪止损和组合方案规划
- v2.2: 精简版 - 已完成内容简化为代码引用
