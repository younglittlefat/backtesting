# 增强参数保存功能：保存运行时参数

**日期**: 2025-11-09
**类型**: Bug修复 + 功能增强
**优先级**: 高（影响实盘信号生成准确性）

## 问题描述

### 现状
回测时通过命令行启用的功能（过滤器、止损保护等）**不会保存到配置文件**，导致实盘信号生成时无法复现回测配置。

### 具体案例
```bash
# 回测时启用止损保护
./run_backtest.sh \
  --strategy sma_cross_enhanced \
  --enable-loss-protection \
  --max-consecutive-losses 3 \
  --pause-bars 10 \
  --optimize \
  --save-params config/sma_strategy_params.json

# 保存的配置文件只有：
{
  "params": {
    "n1": 10,   # ✓ 保存了
    "n2": 20    # ✓ 保存了
    # ❌ enable_loss_protection 未保存
    # ❌ max_consecutive_losses 未保存
    # ❌ pause_bars 未保存
  }
}

# 实盘信号生成时
python generate_signals.py \
  --load-params config/sma_strategy_params.json \
  --strategy sma_cross_enhanced
  # ❌ 止损保护不会生效（使用默认值 False）
```

## 根因分析

**代码位置**: `backtest_runner/core/optimization.py:227-234`

```python
# 当前逻辑：只保存 bt.optimize() 返回的参数
params_manager.save_optimization_results(
    optimized_params=best_params,  # 只有 {n1: 10, n2: 20}
    ...
)
```

**原因**:
1. `bt.optimize()` 只返回参数网格中的参数（n1, n2）
2. 运行时参数（enable_loss_protection等）不在优化网格中
3. `save_optimization_results()` 只保存 `best_params`

## 解决方案

### 目标
保存**完整的运行时配置**，确保实盘信号生成能复现回测环境。

### 需要保存的参数

#### 1. 优化参数（已保存）
- `n1`, `n2` 等策略核心参数

#### 2. 过滤器配置（未保存）⚠️
- `enable_adx_filter`, `enable_volume_filter`, `enable_slope_filter`, `enable_confirm_filter`
- `adx_threshold`, `adx_period`, `volume_ratio`, `volume_period`, `slope_lookback`, `confirm_bars`

#### 3. 止损保护配置（未保存）⚠️
- `enable_loss_protection`
- `max_consecutive_losses`
- `pause_bars`

### 实现方案

#### 方案A：扩展配置文件结构（推荐）

**配置文件新格式**:
```json
{
  "sma_cross_enhanced": {
    "optimized": true,
    "optimization_date": "2025-11-09 21:18:19",
    "params": {
      "n1": 10,
      "n2": 20
    },
    "runtime_config": {
      "filters": {
        "enable_adx_filter": false,
        "enable_volume_filter": false,
        "enable_slope_filter": false,
        "enable_confirm_filter": false,
        "adx_threshold": 25,
        "adx_period": 14,
        "volume_ratio": 1.2,
        "volume_period": 20,
        "slope_lookback": 5,
        "confirm_bars": 3
      },
      "loss_protection": {
        "enable_loss_protection": true,
        "max_consecutive_losses": 3,
        "pause_bars": 10
      }
    },
    "performance": { ... }
  }
}
```

**修改点**:

1. **backtest_runner/core/optimization.py:save_best_params()**
   - 传入额外参数 `filter_params`
   - 调用新方法 `params_manager.save_optimization_results_with_runtime_config()`

2. **utils/strategy_params_manager.py:StrategyParamsManager**
   - 添加方法 `save_optimization_results_with_runtime_config()`
   - 添加方法 `get_runtime_config(strategy_name)`

3. **generate_signals.py:main()**
   - 加载参数时同时加载 `runtime_config`
   - 合并到 `strategy_params`

#### 方案B：generate_signals.py 支持命令行参数（临时方案）

添加与 `run_backtest.sh` 相同的命令行参数：
```python
parser.add_argument('--enable-loss-protection', action='store_true')
parser.add_argument('--max-consecutive-losses', type=int, default=3)
parser.add_argument('--pause-bars', type=int, default=10)
# ... 其他过滤器参数
```

## 实现检查清单

- [ ] 扩展 `StrategyParamsManager` 支持 `runtime_config`
- [ ] 修改 `save_best_params()` 收集并保存运行时参数
- [ ] 修改 `generate_signals.py` 加载运行时参数
- [ ] 更新配置文件格式版本（向后兼容）
- [ ] 添加单元测试验证参数完整性
- [ ] 更新文档说明新的配置文件格式

## 影响范围

**文件修改**:
- `utils/strategy_params_manager.py` - 新增 runtime_config 支持
- `backtest_runner/core/optimization.py` - 保存时传入运行时参数
- `backtest_runner/cli.py` 或 `backtest_runner.py.backup` - 传递 filter_params
- `generate_signals.py` - 加载时读取 runtime_config

**向后兼容性**:
- 旧配置文件无 `runtime_config` 字段时，使用策略默认值
- 不影响现有功能

## 验证方法

### 测试用例1：止损保护参数保存和加载
```bash
# 1. 回测并保存参数
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy sma_cross_enhanced \
  --enable-loss-protection \
  --optimize \
  --save-params config/test_params.json

# 2. 检查配置文件
cat config/test_params.json | grep "enable_loss_protection"
# 预期：应该有 "enable_loss_protection": true

# 3. 实盘信号生成
python generate_signals.py \
  --load-params config/test_params.json \
  --strategy sma_cross_enhanced \
  --stock-list results/trend_etf_pool.csv \
  --analyze \
  --portfolio-file positions/test.json

# 4. 验证：信号生成时应该看到止损保护相关日志
```

### 测试用例2：多过滤器组合
```bash
./run_backtest.sh \
  --strategy sma_cross_enhanced \
  --enable-adx-filter \
  --enable-volume-filter \
  --enable-loss-protection \
  --adx-threshold 30 \
  --optimize \
  --save-params config/test_params.json

# 验证配置文件包含所有过滤器参数
```

## 参考资料

- 止损保护实现文档: `requirement_docs/20251109_native_stop_loss_implementation.md`
- 过滤器实现: `strategies/filters.py`
- 策略定义: `strategies/sma_cross_enhanced.py:80-106`
- 现有参数管理: `utils/strategy_params_manager.py`
