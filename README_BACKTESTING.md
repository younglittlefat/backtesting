## ETF标的预筛选
python -m etf_selector.main --output results/trend_etf_pool.csv --target-size 10 --min-turnover 100000 --min-volatility 0.15 --max-volatility 0.80 --adx-percentile 70 --ret-dd-percentile 70 --momentum-min-positive

## 根据筛选标的回测得出最佳超参
./run_backtest.sh  --stock-list results/trend_etf_pool.csv --strategy sma_cross --optimize --data-dir data/csv/daily --save-params config/strategy_params.json

## 根据超参获取今天信号
./generate_daily_signals.sh --analyze --stock-list results/trend_etf_pool.csv --portfolio-file positions/portfolio.json

---

## 优化点：未平仓交易警告的处理

### 问题现象
执行脚本时出现大量日志输出：
- 进度条: `Backtest.run:   0%|          | 0/120 [00:00<?, ?bar/s]`
- 警告: `UserWarning: Some trades remain open at the end of backtest. Use Backtest(..., finalize_trades=True)...`

### 调查结论

#### 1. 未平仓交易产生原因
- 回测结束时，策略仍持有仓位（最后一天没有触发平仓信号）
- 未设置 `finalize_trades=True` 参数
- **这是正常现象**，尤其在双均线策略中（最后持有多头/空头）

#### 2. 对实盘信号的影响
**结论：✅ 不影响实盘信号生成的准确性**

原因：
- `generate_signals.py` 信号生成完全基于指标值（均线交叉）
- 不依赖于 `position` 状态或 `trades` 持仓
- 验证测试显示：finalize_trades=False/True 下信号100%一致

关键代码（generate_signals.py:196-227）：
```python
# 只使用指标值判断信号
sma_short = strategy.sma1[-1]
sma_long = strategy.sma2[-1]

if sma_short_prev <= sma_long_prev and sma_short > sma_long:
    result['signal'] = 'BUY'  # 金叉
elif sma_short_prev >= sma_long_prev and sma_short < sma_long:
    result['signal'] = 'SELL'  # 死叉
```

#### 3. finalize_trades 参数说明

| 参数值 | 行为 | 适用场景 |
|--------|------|----------|
| False（默认） | 不强制平仓，未平仓交易不计入统计 | 实盘信号生成 |
| True | 自动平仓所有未平仓交易，完整统计 | 回测分析、参数优化 |

#### 4. 实施的解决方案

**方案A：实盘信号生成（generate_signals.py）**
```python
import os
import warnings

# 禁用进度条（在导入backtesting之前）
os.environ['BACKTESTING_DISABLE_PROGRESS'] = 'true'

# 过滤未平仓警告
warnings.filterwarnings('ignore', message='.*Some trades remain open.*')
warnings.filterwarnings('ignore', category=UserWarning, module='backtesting')
```

- ✅ 减少日志噪音，不影响信号准确性
- ✅ 减少计算开销（不需要强制平仓）

**方案B：回测统计分析（backtest_runner.py）**
```python
bt = Backtest(
    data,
    strategy_class,
    cash=cash,
    commission=cost_calculator,
    finalize_trades=True,  # ✅ 确保统计准确
)
```

- ✅ 获得完整的交易统计（包含最后一笔交易）
- ✅ 确保参数优化基于准确数据

#### 5. 验证测试
创建了测试脚本验证方案：
```bash
# 测试日志抑制
python test_quiet_backtest.py

# 验证信号一致性（GOOG数据 + 合成数据）
python investigate_open_trades.py
```

结果：
- ✅ 无进度条和警告输出
- ✅ 信号在 finalize_trades=False/True 下完全一致
- ✅ 未平仓交易不影响指标计算

#### 6. 最佳实践

| 用途 | finalize_trades | 抑制日志 | 原因 |
|------|----------------|---------|------|
| 实盘信号生成 | False | ✅ 是 | 信号基于指标，不需要完整统计 |
| 回测统计分析 | True | ❌ 否 | 需要准确的性能指标 |
| 参数优化 | True | ❌ 否 | 避免优化结果偏差 |

#### 7. 风险评估
- **实盘风险**：✅ 无风险（信号准确性验证通过）
- **回测风险**：✅ 已缓解（backtest_runner.py 正确使用 finalize_trades=True）

参考测试脚本：`test_quiet_backtest.py`、`investigate_open_trades.py`