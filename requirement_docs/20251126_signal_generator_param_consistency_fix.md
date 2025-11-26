# 信号生成器参数一致性修复需求

**日期**: 2025-11-26
**优先级**: 高
**影响范围**: generate_signals.py, backtest_runner, 所有策略

## 1. 问题背景

信号生成器 `generate_signals.py` 与回测系统存在参数默认值不一致的问题，可能导致**回测结果与实盘信号生成行为不一致**。

### 核心原则

用户要求：
1. **所有策略的所有超参，默认都不生效**
2. **必须显式输入选项才能生效**
3. **显式输入的选项，必须通过代码逻辑保存到超参配置JSON中**

## 2. 问题清单

### 2.1 MACD策略Anti-Whipsaw默认值不一致 ⚠️ 严重

**位置**: `generate_signals.py:266-272` 和 `635-641`

**问题代码**:
```python
# 信号生成器中默认值为 True
enable_hysteresis = bool(self.strategy_params.get('enable_hysteresis', True))
enable_zero_axis = bool(self.strategy_params.get('enable_zero_axis', True))
confirm_bars_sell = int(self.strategy_params.get('confirm_bars_sell', 2))
```

**策略类中默认值** (`strategies/macd_cross.py:275,288`):
```python
enable_hysteresis = False  # 策略默认关闭
enable_zero_axis = False   # 策略默认关闭
confirm_bars_sell = 0      # 策略默认关闭
```

**影响**:
- 回测时 `enable_hysteresis=False`（默认）
- 信号生成时 `enable_hysteresis=True`（错误的默认值）
- **导致回测与实盘信号不一致**

### 2.2 配置文件缺少anti_whipsaw节

**位置**: `config/macd_strategy_params.json`

**问题**: 配置文件中 `runtime_config` 没有 `anti_whipsaw` 节，但代码尝试读取它。

**当前配置文件结构**:
```json
{
  "macd_cross": {
    "params": {...},
    "runtime_config": {
      "filters": {...},
      "loss_protection": {...}
      // 缺少 anti_whipsaw 节！
    }
  }
}
```

### 2.3 backtest_runner保存配置时可能遗漏anti_whipsaw

**位置**: 需要检查 `backtest_runner/` 模块中保存配置的逻辑

## 3. 修复方案

### 3.1 修复 generate_signals.py 默认值

将所有 Anti-Whipsaw 参数的默认值改为与策略类一致（**全部默认关闭**）：

| 参数 | 错误默认值 | 正确默认值 |
|------|-----------|-----------|
| `enable_hysteresis` | `True` | `False` |
| `enable_zero_axis` | `True` | `False` |
| `confirm_bars_sell` | `2` | `0` |

### 3.2 确保backtest_runner保存完整的runtime_config

在优化/回测后保存配置时，需要包含所有启用的参数：
- `filters` 节
- `loss_protection` 节
- **`anti_whipsaw` 节**（新增）

### 3.3 生成信号时验证配置完整性

加载配置时，如果发现关键配置节缺失，应打印警告并使用策略默认值。

## 4. 受影响文件

| 文件 | 修改类型 |
|------|---------|
| `generate_signals.py` | 修改默认值 |
| `backtest_runner/io/results_writer.py` | 检查/修改保存逻辑 |
| `utils/strategy_params_manager.py` | 可能需要扩展 |
| `config/macd_strategy_params.json` | 补充anti_whipsaw节 |
| `config/kama_strategy_params.json` | 检查完整性 |

## 5. 验收标准

### 5.1 默认值一致性

运行以下命令，不加载任何配置文件，检查默认值是否全部为关闭状态：

```bash
python generate_signals.py --analyze \
  --portfolio-file /tmp/test_portfolio.json \
  --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross \
  --data-dir data/chinese_etf/daily
```

输出应显示所有增强功能默认关闭。

### 5.2 配置文件加载正确性

```bash
python generate_signals.py --analyze \
  --portfolio-file /tmp/test_portfolio.json \
  --stock-list results/trend_etf_pool.csv \
  --strategy macd_cross \
  --load-params config/macd_strategy_params.json \
  --data-dir data/chinese_etf/daily
```

输出应显示从配置文件加载的参数与配置文件内容一致。

### 5.3 参数保存完整性

运行回测优化后，检查保存的配置文件是否包含完整的 `runtime_config`：
- `filters`
- `loss_protection`
- `anti_whipsaw`（如果启用了相关功能）

## 6. 实施步骤

1. ✅ 创建需求文档
2. ✅ 修复 `generate_signals.py` 中的默认值
   - 修改 `enable_hysteresis` 默认值从 `True` 改为 `False`
   - 修改 `enable_zero_axis` 默认值从 `True` 改为 `False`
   - 修改 `confirm_bars_sell` 默认值从 `2` 改为 `0`
3. ✅ 检查并修复 `backtest_runner` 的配置保存逻辑
   - 新增 `anti_whipsaw` 节到 `runtime_config`
   - 添加9个Anti-Whipsaw参数的保存逻辑
4. ✅ 运行验收测试（5个测试全部通过）
5. 🔲 更新 CLAUDE.md 文档（可选）

## 7. 修复记录

### 修复内容

**文件1: `generate_signals.py`**
- 行266-272, 635-641: 修改Anti-Whipsaw参数默认值
  - `enable_hysteresis`: `True` → `False`
  - `enable_zero_axis`: `True` → `False`
  - `confirm_bars_sell`: `2` → `0`

**文件2: `backtest_runner/core/optimization.py`**
- 行253-257: 新增 `anti_whipsaw` 节到 `runtime_config` 结构
- 行277-283: 新增Anti-Whipsaw参数列表
- 行298-304: 新增Anti-Whipsaw参数保存逻辑（仅对MACD策略生效）

### 验收测试结果

| 测试 | 描述 | 结果 |
|------|------|------|
| 测试1 | 无配置文件时的默认值 | ✅ 通过 |
| 测试2 | 从配置文件加载参数 | ✅ 通过 |
| 测试3 | 配置文件无anti_whipsaw时的行为 | ✅ 通过 |
| 测试4 | CLI参数覆盖配置文件 | ✅ 通过 |
| 测试5 | 策略类默认值一致性检查 | ✅ 通过 |
| 测试6 | MACD策略信号生成（实际运行） | ✅ 通过 |
| 测试7 | KAMA策略信号生成（实际运行） | ✅ 通过 |

## 8. 回归风险

**低风险**: 此修复将默认值改为更保守的设置（全部关闭），不会影响显式指定参数的用户。

**潜在影响**:
- 如果用户之前依赖错误的默认值（如自动启用 hysteresis），需要显式在配置文件或命令行中启用
- 建议在修复后通知用户检查其配置

## 9. 补充修复（2025-11-26 第二轮）

### 9.1 新发现问题

在检查 `run_backtest.sh` 和参数落盘完整性时，发现以下遗漏：

| 问题ID | 严重程度 | 问题描述 |
|--------|---------|---------|
| P1 | ⚠️ 中等 | 跟踪止损参数 (`enable_trailing_stop`, `trailing_stop_pct`) 未保存到JSON |
| P2 | ⚠️ 中等 | ATR止损参数 (`enable_atr_stop`, `atr_period`, `atr_multiplier`) 未保存到JSON |

### 9.2 run_backtest.sh 检查结果

**结论：✅ 符合要求**

所有增强功能在 shell 脚本中默认关闭（FLAG=0 或 VALUE=""），仅在用户显式传入时启用。

### 9.3 补充修复内容

**文件1: `backtest_runner/core/optimization.py`**
- 行252-259: 新增 `trailing_stop` 和 `atr_stop` 节到 `runtime_config` 结构
- 行287-295: 新增跟踪止损和ATR止损参数列表
- 行318-330: 新增跟踪止损和ATR止损参数保存逻辑（所有策略通用）

**文件2: `generate_signals.py`**
- 行1420-1432: 新增 `trailing_stop` 和 `atr_stop` 配置读取逻辑

**文件3: `backtest_runner/cli.py`**
- 行85-92: 新增 `trailing_stop` 和 `atr_stop` 配置加载逻辑

### 9.4 修复后的 runtime_config 完整结构

```json
{
  "strategy_name": {
    "params": {...},
    "runtime_config": {
      "filters": {
        "enable_slope_filter": false,
        "enable_adx_filter": false,
        "enable_volume_filter": false,
        "enable_confirm_filter": false,
        "slope_lookback": 5,
        "adx_period": 14,
        "adx_threshold": 25.0,
        "volume_period": 20,
        "volume_ratio": 1.2,
        "confirm_bars": 2
      },
      "loss_protection": {
        "enable_loss_protection": false,
        "max_consecutive_losses": 3,
        "pause_bars": 10
      },
      "anti_whipsaw": {
        "enable_hysteresis": false,
        "hysteresis_mode": "std",
        "hysteresis_k": 0.5,
        "hysteresis_window": 20,
        "hysteresis_abs": 0.001,
        "confirm_bars_sell": 0,
        "min_hold_bars": 0,
        "enable_zero_axis": false,
        "zero_axis_mode": "symmetric"
      },
      "trailing_stop": {
        "enable_trailing_stop": false,
        "trailing_stop_pct": 0.05
      },
      "atr_stop": {
        "enable_atr_stop": false,
        "atr_period": 14,
        "atr_multiplier": 2.5
      }
    }
  }
}
```
