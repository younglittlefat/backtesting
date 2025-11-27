# 运行时参数保存功能增强

**日期**: 2025-11-09
**状态**: ✅ 已完成实现

---

## 1. 问题与解决方案

### 1.1 问题描述

回测时通过命令行启用的功能（过滤器、止损保护等）**不会保存到配置文件**，导致实盘信号生成时无法复现回测配置。

```bash
# 回测时启用止损保护
./run_backtest.sh --strategy sma_cross_enhanced \
  --enable-loss-protection --max-consecutive-losses 3 --pause-bars 10 \
  --save-params config/params.json

# 旧配置文件只保存优化参数，不保存运行时配置
{ "params": { "n1": 10, "n2": 20 } }
# ❌ enable_loss_protection、max_consecutive_losses、pause_bars 丢失
```

### 1.2 解决方案

**扩展配置文件结构 + 策略契约机制**：
- 配置文件新增 `runtime_config` 字段保存过滤器和止损保护配置
- 策略继承 `BaseEnhancedStrategy` 自动获得参数导出能力
- `generate_signals.py` 加载时自动应用运行时配置

---

## 2. 配置文件格式

```json
{
  "sma_cross_enhanced": {
    "optimized": true,
    "optimization_date": "2025-11-09",
    "params": {
      "n1": 10,
      "n2": 20
    },
    "runtime_config": {
      "filters": {
        "enable_adx_filter": true,
        "adx_threshold": 30,
        "enable_volume_filter": false,
        ...
      },
      "loss_protection": {
        "enable_loss_protection": true,
        "max_consecutive_losses": 3,
        "pause_bars": 10
      }
    }
  }
}
```

---

## 3. 使用方法

### 3.1 保存运行时配置

```bash
./run_backtest.sh \
  --strategy sma_cross_enhanced \
  --enable-loss-protection \
  --max-consecutive-losses 3 \
  --enable-adx-filter \
  --adx-threshold 30 \
  --optimize \
  --save-params config/strategy_params.json
```

### 3.2 加载运行时配置

```bash
python generate_signals.py \
  --load-params config/strategy_params.json \
  --strategy sma_cross_enhanced \
  --stock-list results/trend_etf_pool.csv \
  --analyze
```

输出示例：
```
✓ 从配置文件加载参数: {'n1': 10, 'n2': 20}
✓ 从配置文件加载运行时配置
  过滤器: adx_filter=ON, volume_filter=OFF
  止损保护: ON (连续亏损=3, 暂停=10)
```

---

## 4. 核心架构

### 4.1 策略契约机制

| 组件 | 说明 |
|------|------|
| `RuntimeConfigurable` | 抽象接口，定义 `get_runtime_config()` 方法 |
| `BaseEnhancedStrategy` | 基类实现，继承 Strategy + RuntimeConfigurable |
| 子类策略 | 继承 `BaseEnhancedStrategy`，自动获得参数导出能力 |

### 4.2 参数优先级

```
命令行参数 > 配置文件 runtime_config > 策略类默认值
```

---

## 5. 关键代码位置

| 模块 | 文件路径 | 行号 | 说明 |
|------|----------|------|------|
| RuntimeConfigurable接口 | `strategies/base_strategy.py` | 16-73 | 抽象接口定义 |
| BaseEnhancedStrategy | `strategies/base_strategy.py` | 76-258 | 基类实现，默认 `get_runtime_config()` |
| validate_strategy_contract | `strategies/base_strategy.py` | 260+ | 策略契约验证函数 |
| save_optimization_results | `utils/strategy_params_manager.py` | 136-186 | 保存优化结果+runtime_config |
| get_runtime_config | `utils/strategy_params_manager.py` | 188-202 | 读取策略的runtime_config |
| validate_runtime_config | `utils/strategy_params_manager.py` | 204+ | 配置验证 |
| 参数加载逻辑 | `generate_signals.py` | 1388-1430 | 加载并应用runtime_config |

---

## 6. 新策略开发规范

### 6.1 基本要求

继承 `BaseEnhancedStrategy` 即可自动获得运行时参数导出能力：

```python
from strategies.base_strategy import BaseEnhancedStrategy

class MyStrategy(BaseEnhancedStrategy):
    # 定义优化参数
    param1 = 10
    param2 = 20

    def init(self):
        # 初始化指标
        pass

    def next(self):
        # 交易逻辑
        pass
```

### 6.2 扩展运行时配置（可选）

如需保存策略特有参数，覆盖 `get_runtime_config()` 方法：

```python
def get_runtime_config(self):
    config = super().get_runtime_config()
    config['my_strategy_specific'] = {
        'custom_param': self.custom_param,
    }
    return config
```

---

## 7. 向后兼容性

| 场景 | 处理方式 |
|------|---------|
| 旧策略不继承 RuntimeConfigurable | 不报错，使用默认值 |
| 旧配置文件无 runtime_config | 返回 None，使用策略默认值 |
| 命令行参数覆盖配置文件 | 命令行优先 |

---

## 8. 参数命名统一原则

所有策略共享统一的参数名，通过 `--strategy` 决定应用到哪个策略：

```bash
# 统一参数适用于所有策略
--enable-loss-protection      # 统一开关（非 --enable-macd-loss-protection）
--max-consecutive-losses      # 统一参数名
--enable-adx-filter           # 统一开关
--adx-threshold               # 统一参数名
```

---

## 9. 参考资料

- 止损保护实现: `requirement_docs/20251109_native_stop_loss_implementation.md`
- 策略基类: `strategies/base_strategy.py`
- 参数管理器: `utils/strategy_params_manager.py`
