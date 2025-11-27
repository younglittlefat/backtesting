# KAMA自适应均线策略需求文档

**文档日期**: 2025-11-11
**状态**: ✅ 已完成实现

---

## 1. KAMA指标原理

### 1.1 核心思想

KAMA（Kaufman's Adaptive Moving Average）是一种自适应均线，通过**效率比率（ER）**自动调整响应速度：
- **趋势期（高ER）**: 快速响应，减少滞后
- **震荡期（低ER）**: 平滑滤波，减少假信号

### 1.2 计算步骤

**Step 1: 效率比率（ER）**
```
Change = abs(Close - Close[n])        # n期净变化
Volatility = sum(abs(Close[i] - Close[i-1]))  # n期波动总和
ER = Change / Volatility              # 范围 0~1
```

**Step 2: 平滑常数（SC）**
```
FastSC = 2 / (fast_period + 1)
SlowSC = 2 / (slow_period + 1)
SC = [ER × (FastSC - SlowSC) + SlowSC]²
```

**Step 3: KAMA值**
```
KAMA[t] = KAMA[t-1] + SC × (Price - KAMA[t-1])
```

### 1.3 自适应特性

| ER值 | 市场状态 | KAMA响应 |
|------|---------|---------|
| 接近1 | 强趋势 | 接近FastEMA |
| 接近0 | 震荡 | 接近SlowEMA |

---

## 2. 交易信号

- **金叉买入**: 价格从下方突破KAMA线
- **死叉卖出**: 价格从上方跌破KAMA线
- **增强过滤**: 效率比率阈值、KAMA斜率确认

---

## 3. 完整超参数列表

### 3.1 KAMA核心参数

| CLI参数 | 策略参数 | 默认值 | 说明 |
|---------|---------|--------|------|
| `--kama-period` | `kama_period` | 20 | 效率比率计算周期 |
| `--kama-fast` | `kama_fast` | 2 | 快速平滑周期 |
| `--kama-slow` | `kama_slow` | 30 | 慢速平滑周期 |

### 3.2 KAMA特有过滤器

| CLI参数 | 策略参数 | 默认值 | 说明 |
|---------|---------|--------|------|
| `--enable-efficiency-filter` | `enable_efficiency_filter` | False | 启用效率比率过滤 |
| `--min-efficiency-ratio` | `min_efficiency_ratio` | 0.3 | 最小效率比率阈值 |
| `--enable-slope-confirmation` | `enable_slope_confirmation` | False | 启用KAMA斜率确认 |
| `--min-slope-periods` | `min_slope_periods` | 3 | 斜率确认周期 |

### 3.3 通用过滤器（继承自BaseEnhancedStrategy）

| CLI参数 | 策略参数 | 默认值 | 说明 |
|---------|---------|--------|------|
| `--enable-adx-filter` | `enable_adx_filter` | False | ADX趋势强度过滤 ⭐推荐 |
| `--adx-period` | `adx_period` | 14 | ADX计算周期 |
| `--adx-threshold` | `adx_threshold` | 25 | ADX阈值 |
| `--enable-volume-filter` | `enable_volume_filter` | False | 成交量确认过滤 |
| `--volume-period` | `volume_period` | 20 | 成交量均值周期 |
| `--volume-ratio` | `volume_ratio` | 1.2 | 成交量放大倍数 |
| `--enable-slope-filter` | `enable_slope_filter` | False | 价格斜率过滤 |
| `--slope-lookback` | `slope_lookback` | 5 | 斜率回溯期 |
| `--enable-confirm-filter` | `enable_confirm_filter` | False | 持续确认过滤（⚠️不推荐） |
| `--confirm-bars` | `confirm_bars` | 0 | 确认K线数 |

### 3.4 止损保护参数

| CLI参数 | 策略参数 | 默认值 | 说明 |
|---------|---------|--------|------|
| `--enable-loss-protection` | `enable_loss_protection` | False | 连续止损保护（⚠️对KAMA无效） |
| `--max-consecutive-losses` | `max_consecutive_losses` | 3 | 连续亏损阈值 |
| `--pause-bars` | `pause_bars` | 10 | 暂停K线数 |
| `--debug-loss-protection` | `debug_loss_protection` | False | 调试日志 |

---

## 4. 使用方法

### 4.1 基础用法（推荐）

```bash
# ✅ 最佳配置：纯KAMA（实验验证夏普1.69）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy kama_cross \
  --data-dir data/chinese_etf/daily
```

### 4.2 带ADX过滤器

```bash
# ADX过滤器（夏普1.68，回撤-4.71%）
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy kama_cross \
  --enable-adx-filter \
  --data-dir data/chinese_etf/daily
```

### 4.3 参数优化

```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy kama_cross \
  --optimize \
  --data-dir data/chinese_etf/daily
```

### 4.4 调试模式

```bash
python backtest_runner.py -s 159922.SZ -t kama_cross \
  --enable-loss-protection \
  --debug-loss-protection \
  --data-dir data/chinese_etf/daily/etf
```

---

## 5. 关键代码位置

| 模块 | 文件路径 | 行号 | 说明 |
|------|----------|------|------|
| KAMA计算函数 | `strategies/kama_cross.py` | 30-80 | `calculate_kama()` |
| 效率比率计算 | `strategies/kama_cross.py` | 83-130 | `calculate_efficiency_ratio()` |
| 斜率计算 | `strategies/kama_cross.py` | 133-200 | `calculate_slope()` |
| 策略类定义 | `strategies/kama_cross.py` | 204-256 | `KamaCrossStrategy` |
| 策略参数声明 | `strategies/kama_cross.py` | 258-291 | 类变量定义 |
| init方法 | `strategies/kama_cross.py` | 293-352 | 指标初始化、止损状态 |
| next方法 | `strategies/kama_cross.py` | 354-430 | 交易逻辑 |
| 止损跟踪方法 | `strategies/kama_cross.py` | 434-473 | `_close_position_with_loss_tracking()` |
| CLI参数定义 | `backtest_runner/config/argparser.py` | 324-335 | KAMA专属参数 |
| 参数构建 | `backtest_runner/processing/filter_builder.py` | 118-158 | `_build_kama_filter_params()` |

---

## 6. 实验验证结论

### 6.1 性能对比

| 策略 | Baseline夏普 | 最佳止损后 | 止损效果 |
|------|-------------|-----------|---------|
| **KAMA** | **1.69** | 1.68 | ❌ 无效(-0.7%) |
| SMA | 0.61 | 1.07 | ✅ +75% |
| MACD | 0.73 | 0.94 | ✅ +28.8% |

### 6.2 关键发现

1. **止损保护对KAMA无效**：KAMA自适应特性已内置风险控制
2. **最佳配置**：纯Baseline KAMA（不启用止损）
3. **可选ADX**：几乎不损失收益，略改善回撤
4. **避免Confirm过滤器**：与KAMA自适应特性冲突

### 6.3 推荐配置

```bash
# 生产环境推荐
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy kama_cross \
  --data-dir data/chinese_etf/daily
# 预期：夏普1.69，收益34.63%，回撤-5.27%
```

---

## 7. 参考资料

- Kaufman, P. (2013). "Trading Systems and Methods" - KAMA原始论文
- 实验报告: `experiment/etf/kama_cross/hyperparameter_search/results/PHASE2_ACCEPTANCE_REPORT.md`
- 基础策略类: `strategies/base_strategy.py`
