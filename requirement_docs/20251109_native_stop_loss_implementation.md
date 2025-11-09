# 基于框架原生方法的止损实现

## 背景

LossProtectionFilter 因架构缺陷无法工作（依赖回测期间不可访问的 `strategy.trades` 属性）。改用 backtesting.py 框架原生方法，在 Strategy 内部实现止损控制。

## 实现方案

三种止损策略：
1. **跟踪止损（Trailing Stop）**：价格上涨时动态调整止损线
2. **连续止损保护（Consecutive Loss Protection）**⭐：连续N次亏损后暂停交易
3. **组合方案（Combined）**：跟踪止损 + 连续止损保护

**代码实现**: `strategies/stop_loss_strategies.py`

## 实验结果（280次回测）

**测试配置**：20只中国ETF，2023-11至2025-11

**完整对比结果**：

| 策略 | 平均收益 | 夏普比率 | 最大回撤 | 胜率 |
|------|----------|----------|----------|------|
| Base（无止损） | 51.09% | 0.61 | -21.17% | 48.41% |
| **Loss Protection** ⭐ | **53.91%** | **1.07** | **-13.88%** | **61.42%** |
| Combined | 44.93% | 1.01 | -12.87% | 55.89% |
| Trailing Stop | 40.20% | 0.91 | -12.77% | 57.57% |

**关键结论**：
- 夏普比率提升 **+75%** (0.61 → 1.07)
- 最大回撤降低 **-34%** (-21% → -14%)
- 胜率提升 **+27%** (48% → 61%)
- 最差标的风险降低 **+77%** (-42% → -9%)

## 推荐配置

**Loss Protection（连续止损保护）** ⭐⭐⭐⭐⭐
- `max_consecutive_losses`: 3次（连续亏损阈值）
- `pause_bars`: 10根K线（暂停交易时长）
- **优势**：最高夏普比率，最高胜率，参数不敏感
- **适用**：趋势跟踪策略，追求风险调整后收益

**参数敏感性**：
- Loss Protection 对参数不敏感，2-4次和5-15根K线效果相近
- Trailing Stop 对参数敏感：5%为平衡点，3%过严，7%适合高波动标的

## 使用方法

### 方式1：命令行（推荐）

```bash
# 基本使用
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

# 组合过滤器
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  -t sma_cross_enhanced \
  --enable-loss-protection \
  --enable-adx-filter \
  --enable-volume-filter \
  --data-dir data/chinese_etf/daily \
  -o
```

### 方式2：Python调用

参考 `strategies/stop_loss_strategies.py` 中的策略类：
- `SmaCrossWithLossProtection` - 连续止损保护（推荐）
- `SmaCrossWithTrailingStop` - 跟踪止损
- `SmaCrossWithFullRiskControl` - 组合方案

### 方式3：重现实验

```bash
python experiment/etf/sma_cross/stop_loss_comparison/compare_stop_loss.py \
  --stock-list results/trend_etf_pool.csv \
  --data-dir data/chinese_etf/daily
```

## 相关文件

**实现代码**：
- `strategies/stop_loss_strategies.py` - 三种止损策略实现
- `strategies/sma_cross_enhanced.py:145-168` - SmaCrossEnhanced集成代码
- `backtest_runner.py:76-78,126-129` - 命令行参数支持
- `run_backtest.sh:85-89` - Shell脚本参数

**实验结果**：
- `experiment/etf/sma_cross/stop_loss_comparison/RESULTS.md` - 详细分析报告
- `experiment/etf/sma_cross/stop_loss_comparison/comparison_results.csv` - 280条回测数据
- `experiment/etf/sma_cross/stop_loss_comparison/summary_statistics.csv` - 策略汇总统计
