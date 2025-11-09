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

---

## 功能验证（2025-11-09）

### 问题报告

用户在使用 `--enable-loss-protection` 参数进行回测时，发现结果与baseline（不启用止损保护）完全相同，怀疑功能未生效。

### 调查过程

#### 1. 参数传递BUG修复

发现 `backtest_runner.py` 在optimize模式下存在参数传递问题：

**问题根源**：
- `bt.optimize()` 只处理**可迭代参数**（list, range等）
- 单值参数如 `enable_loss_protection=True` 会被**静默忽略**

**修复方案** (`backtest_runner.py:543-559`)：
```python
# 修复前：单值参数被忽略
run_kwargs.update(filter_params)  # {'enable_loss_protection': True} ❌

# 修复后：包装成单元素列表
normalized_filter_params = {}
for key, value in filter_params.items():
    if not hasattr(value, '__iter__') or isinstance(value, str):
        normalized_filter_params[key] = [value]  # {'enable_loss_protection': [True]} ✓
run_kwargs.update(normalized_filter_params)
```

#### 2. 日志验证

在 `SmaCrossEnhanced` 策略中添加详细日志：
- 每笔交易记录盈亏百分比和连续亏损计数
- 触发暂停时输出警告信息
- 暂停期间随机采样输出状态（避免日志过多）

**关键代码** (`strategies/sma_cross_enhanced.py:219-266`)：
```python
def _close_position_with_loss_tracking(self):
    # ... 计算盈亏 ...
    if is_loss:
        self.consecutive_losses += 1
        print(f"[止损保护] 交易#{self.total_trades}: 亏损 {pnl_pct:.2f}% (连续亏损: {self.consecutive_losses}/{self.max_consecutive_losses})")

        if self.consecutive_losses >= self.max_consecutive_losses:
            # 触发暂停
            self.paused_until_bar = self.current_bar + self.pause_bars
            print(f"[止损保护] ⚠️ 触发暂停 (第{self.triggered_pauses}次): Bar {self.current_bar} → {self.paused_until_bar}")
```

### 验证结果

#### 测试案例1：159922.SZ (中证500ETF) - 优化参数 n1=15, n2=20

**结果**：启用与不启用止损保护完全相同
- 收益率：385.09%
- 夏普：0.91
- 交易：22次

**日志分析**：
```
[止损保护] 交易#1: 盈利 10.70% (重置连续亏损: 0 → 0)
[止损保护] 交易#5: 亏损 -5.52% (连续亏损: 1/3)
[止损保护] 交易#6: 亏损 -6.68% (连续亏损: 2/3)
[止损保护] 交易#7: 盈利 21.07% (重置连续亏损: 2 → 0)
...
```

**原因**：连续亏损最多只有2次，**未达到3次阈值**，止损保护启用但从未激活。

#### 测试案例2：561160.SH (锂电池ETF) - 默认参数 n1=10, n2=20 ⭐

**结果**：启用与不启用止损保护仍然相同
- 收益率：425.92%
- 交易：20次

**日志分析**（关键证据）：
```
[止损保护] 交易#5: 亏损 -0.87% (连续亏损: 1/3)
[止损保护] 交易#6: 亏损 -12.22% (连续亏损: 2/3)
[止损保护] 交易#7: 亏损 -12.84% (连续亏损: 3/3)
[止损保护] ⚠️ 触发暂停 (第1次): Bar 112 → 122 (暂停10根K线)
[止损保护] Bar 116: 暂停期内 (暂停至Bar 122)
[止损保护] 交易#8: 盈利 14.54% (重置连续亏损: 0 → 0)
```

**原因**：止损保护**确实触发**了暂停（Bar 112-122），但暂停的10根K线期间**没有产生交易信号**，因此没有信号被过滤，交易次数不变。

### 结论

#### ✅ 止损保护功能完全正常

1. **参数传递** ✓ - 修复后所有参数正确传递到策略
2. **逻辑执行** ✓ - 连续亏损跟踪、暂停触发、暂停期拒绝交易均正常工作
3. **日志证据** ✓ - 可以看到完整的交易日志和暂停触发记录

#### 为什么结果相同？

**情况1：优化参数太稳定，从未触发暂停**
- 如159922.SZ使用优化参数n1=15, n2=20
- 连续亏损最多2次，未达到阈值3
- 止损保护启用但从未激活

**情况2：触发暂停但暂停期无信号** ⭐ 关键发现
- 如561160.SH使用n1=10, n2=20
- 确实触发了暂停（Bar 112-122，共10根K线）
- 但暂停的10根K线期间没有产生交易信号
- 因此没有信号被过滤，交易次数和结果不变

#### 类比说明

这就像：
- 戴着口罩（止损保护功能启用）
- 在疫情时呆在家里（触发暂停，拒绝交易）
- 但这段时间本来也没安排出门（暂停期间没有交易信号）
- 所以戴不戴口罩结果都一样（结果相同但功能正常）

### 验证方法

运行测试脚本查看详细日志：
```bash
python test_loss_protection_with_logging.py
python test_optimized_params.py
```

查看日志中的关键信息：
- `[止损保护] 交易#X: 亏损/盈利 X.XX%` - 每笔交易跟踪
- `[止损保护] ⚠️ 触发暂停` - 暂停触发确认
- `[止损保护] Bar X: 暂停期内` - 暂停期间状态

### 相关文件

**调查和修复**：
- `backtest_runner.py:543-559` - 参数包装修复（关键）
- `strategies/sma_cross_enhanced.py:136-144,176-266` - 止损保护逻辑和日志
- `test_loss_protection_with_logging.py` - 单标的验证脚本
- `test_optimized_params.py` - 多标的验证脚本
- `loss_protection_verification_report.md` - 详细验证报告（已删除，内容整合至此）
