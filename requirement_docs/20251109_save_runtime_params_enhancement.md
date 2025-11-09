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

#### 方案A：扩展配置文件结构 + 策略契约机制（推荐）✅

**设计原则**:
1. **分离关注点**: 区分优化参数、过滤器配置、止损保护配置
2. **策略契约**: 强制所有策略实现参数导出接口
3. **可扩展性**: 新增策略时自动检查是否实现必要接口
4. **向后兼容**: 支持旧配置文件格式

---

##### 1. 配置文件新格式

```json
{
  "sma_cross_enhanced": {
    "optimized": true,
    "optimization_date": "2025-11-09 21:18:19",
    "strategy_version": "1.0",  // 新增：策略版本标识
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
  },
  "macd_cross": {
    "optimized": true,
    "optimization_date": "2025-11-09 22:00:00",
    "strategy_version": "1.0",
    "params": {
      "fast_period": 12,
      "slow_period": 26,
      "signal_period": 9
    },
    "runtime_config": {
      "filters": { ... },
      "loss_protection": {
        "enable_loss_protection": true,
        "max_consecutive_losses": 4,  // MACD 可能需要不同默认值
        "pause_bars": 12
      }
    },
    "performance": { ... }
  }
}
```

---

##### 2. 策略契约机制（核心设计）

**问题**: 如何强制新策略实现运行时参数导出？

**解决方案**: 在策略基类中定义抽象方法，新策略必须实现。

**新增策略基类接口**:

在 `strategies/base_strategy.py` (需新建) 中定义:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class RuntimeConfigurable(ABC):
    """
    强制策略实现运行时参数导出接口

    所有支持止损保护的策略必须继承此类
    """

    @abstractmethod
    def get_runtime_config(self) -> Dict[str, Any]:
        """
        导出当前策略的运行时配置

        返回格式:
        {
            "filters": {
                "enable_adx_filter": bool,
                "adx_threshold": int,
                ...
            },
            "loss_protection": {
                "enable_loss_protection": bool,
                "max_consecutive_losses": int,
                "pause_bars": int
            },
            # 策略特有的运行时参数
            "strategy_specific": {}
        }
        """
        pass

    @abstractmethod
    def get_runtime_config_schema(self) -> Dict[str, Any]:
        """
        返回运行时配置的结构定义（用于验证）

        返回格式:
        {
            "filters": {
                "enable_adx_filter": {"type": "bool", "default": False},
                "adx_threshold": {"type": "int", "default": 25, "range": [10, 50]},
                ...
            },
            "loss_protection": {
                "enable_loss_protection": {"type": "bool", "default": False},
                "max_consecutive_losses": {"type": "int", "default": 3, "range": [1, 10]},
                "pause_bars": {"type": "int", "default": 10, "range": [1, 50]}
            }
        }
        """
        pass


class BaseEnhancedStrategy(Strategy, RuntimeConfigurable):
    """
    增强型策略基类，所有新策略应该继承此类

    自动集成：
    - 过滤器支持
    - 止损保护
    - 运行时参数导出
    """

    # 过滤器参数（子类可覆盖默认值）
    enable_adx_filter = False
    enable_volume_filter = False
    enable_slope_filter = False
    enable_confirm_filter = False

    # 止损保护参数（子类可覆盖默认值）
    enable_loss_protection = False
    max_consecutive_losses = 3
    pause_bars = 10

    def get_runtime_config(self) -> Dict[str, Any]:
        """默认实现：导出所有运行时参数"""
        return {
            "filters": {
                "enable_adx_filter": self.enable_adx_filter,
                "enable_volume_filter": self.enable_volume_filter,
                "enable_slope_filter": self.enable_slope_filter,
                "enable_confirm_filter": self.enable_confirm_filter,
                "adx_threshold": getattr(self, 'adx_threshold', 25),
                "adx_period": getattr(self, 'adx_period', 14),
                "volume_ratio": getattr(self, 'volume_ratio', 1.2),
                "volume_period": getattr(self, 'volume_period', 20),
                "slope_lookback": getattr(self, 'slope_lookback', 5),
                "confirm_bars": getattr(self, 'confirm_bars', 3),
            },
            "loss_protection": {
                "enable_loss_protection": self.enable_loss_protection,
                "max_consecutive_losses": self.max_consecutive_losses,
                "pause_bars": self.pause_bars,
            }
        }

    def get_runtime_config_schema(self) -> Dict[str, Any]:
        """默认 schema（子类可扩展）"""
        return {
            "filters": {
                "enable_adx_filter": {"type": "bool", "default": False},
                "adx_threshold": {"type": "int", "default": 25},
                # ... 其他过滤器参数
            },
            "loss_protection": {
                "enable_loss_protection": {"type": "bool", "default": False},
                "max_consecutive_losses": {"type": "int", "default": 3},
                "pause_bars": {"type": "int", "default": 10},
            }
        }
```

**策略实现示例**:

```python
# strategies/sma_cross_enhanced.py
from strategies.base_strategy import BaseEnhancedStrategy

class SmaCrossEnhanced(BaseEnhancedStrategy):
    """继承 BaseEnhancedStrategy，自动获得运行时参数导出能力"""

    n1 = 10
    n2 = 20

    # 可选：覆盖默认止损保护参数
    max_consecutive_losses = 3  # SMA 策略推荐值
    pause_bars = 10

    def init(self):
        # 策略初始化
        pass

    def next(self):
        # 策略逻辑
        pass

    # 可选：扩展 runtime_config（如果有策略特有参数）
    def get_runtime_config(self) -> Dict[str, Any]:
        config = super().get_runtime_config()
        config["strategy_specific"] = {
            "use_exponential_ma": getattr(self, 'use_exponential_ma', False),
        }
        return config


# strategies/macd_cross.py
class MacdCross(BaseEnhancedStrategy):
    """MACD 策略，继承基类获得止损保护"""

    fast_period = 12
    slow_period = 26
    signal_period = 9

    # MACD 策略可能需要不同的止损参数
    max_consecutive_losses = 4  # MACD 波动性更大
    pause_bars = 12

    def init(self):
        # MACD 指标初始化
        pass

    def next(self):
        # MACD 交易逻辑
        pass
```

---

##### 3. 强制检查机制

**在回测启动时检查策略契约**:

在 `backtest_runner/core/optimization.py` 或 `backtest_runner/cli.py` 中添加:

```python
def validate_strategy_contract(strategy_class):
    """
    验证策略是否实现了必要的接口

    如果策略不符合契约，抛出异常并给出明确提示
    """
    from strategies.base_strategy import RuntimeConfigurable

    if not issubclass(strategy_class, RuntimeConfigurable):
        raise TypeError(
            f"策略 {strategy_class.__name__} 必须继承 RuntimeConfigurable 接口！\n"
            f"请修改策略定义为:\n"
            f"  class {strategy_class.__name__}(BaseEnhancedStrategy):\n"
            f"      ...\n"
            f"\n"
            f"或手动实现以下方法:\n"
            f"  - get_runtime_config()\n"
            f"  - get_runtime_config_schema()\n"
            f"\n"
            f"参考文档: requirement_docs/20251109_save_runtime_params_enhancement.md"
        )

    # 验证方法实现
    if not hasattr(strategy_class, 'get_runtime_config'):
        raise NotImplementedError(
            f"策略 {strategy_class.__name__} 未实现 get_runtime_config() 方法"
        )

    if not hasattr(strategy_class, 'get_runtime_config_schema'):
        raise NotImplementedError(
            f"策略 {strategy_class.__name__} 未实现 get_runtime_config_schema() 方法"
        )


# 在回测执行前调用
def run_backtest(strategy_class, data, ...):
    # 验证策略契约
    validate_strategy_contract(strategy_class)

    # 执行回测
    bt = Backtest(data, strategy_class, ...)
    stats = bt.run(...)

    # 保存参数时调用策略的 get_runtime_config()
    if args.save_params:
        runtime_config = strategy_class().get_runtime_config()  # 获取运行时配置
        params_manager.save_optimization_results_with_runtime_config(
            optimized_params=best_params,
            runtime_config=runtime_config,  # 传入运行时配置
            ...
        )
```

---

##### 4. 修改点总结

**新增文件**:
1. `strategies/base_strategy.py` - 定义 `RuntimeConfigurable` 和 `BaseEnhancedStrategy`

**修改文件**:
1. **strategies/sma_cross_enhanced.py**
   - 继承 `BaseEnhancedStrategy`
   - (可选) 覆盖默认止损参数

2. **strategies/macd_cross.py**
   - 继承 `BaseEnhancedStrategy`
   - (可选) 定义 MACD 特有的止损参数

3. **backtest_runner/core/optimization.py**
   - 添加 `validate_strategy_contract()` 函数
   - 修改 `save_best_params()`:
     ```python
     runtime_config = strategy_instance.get_runtime_config()
     params_manager.save_optimization_results_with_runtime_config(
         optimized_params=best_params,
         runtime_config=runtime_config,
         ...
     )
     ```

4. **utils/strategy_params_manager.py**
   - 添加方法 `save_optimization_results_with_runtime_config()`
   - 添加方法 `get_runtime_config(strategy_name)`
   - 添加方法 `validate_runtime_config(config, schema)` - 验证配置完整性

5. **generate_signals.py**
   - 加载参数时同时加载 `runtime_config`
   - 应用到策略实例:
     ```python
     params = params_manager.load_strategy_params(strategy_name)
     runtime_config = params_manager.get_runtime_config(strategy_name)

     # 合并到策略参数
     strategy_params = {**params, **flatten_runtime_config(runtime_config)}
     ```

---

##### 5. 新策略开发工作流

**开发者视角**:

```python
# Step 1: 继承 BaseEnhancedStrategy（自动获得止损保护）
from strategies.base_strategy import BaseEnhancedStrategy

class MyNewStrategy(BaseEnhancedStrategy):
    # Step 2: 定义优化参数
    param1 = 10
    param2 = 20

    # Step 3: (可选) 覆盖止损保护默认值
    max_consecutive_losses = 5  # 根据策略特点调整
    pause_bars = 15

    def init(self):
        # 策略初始化
        pass

    def next(self):
        # 策略逻辑
        pass

    # Step 4: (可选) 如果有策略特有的运行时参数，扩展 get_runtime_config()
    def get_runtime_config(self):
        config = super().get_runtime_config()
        config["strategy_specific"] = {
            "my_special_param": self.my_special_param,
        }
        return config
```

**强制检查**:
- 如果忘记继承 `BaseEnhancedStrategy` 或 `RuntimeConfigurable`，回测启动时会报错并给出明确提示
- 报错信息会包含修复指引和文档链接

---

##### 6. 优势

✅ **强制性**: 新策略如果不实现接口，无法通过回测启动时的检查
✅ **灵活性**: 不同策略可以有不同的止损保护默认值
✅ **可扩展性**: 新策略可以扩展 `runtime_config` 添加特有参数
✅ **向后兼容**: 旧配置文件无 `runtime_config` 时使用策略默认值
✅ **可维护性**: 通过基类统一管理通用功能（过滤器、止损保护）
✅ **自文档化**: Schema 定义提供参数说明和验证规则

#### 方案B：generate_signals.py 支持命令行参数（临时方案）

添加与 `run_backtest.sh` 相同的命令行参数：
```python
parser.add_argument('--enable-loss-protection', action='store_true')
parser.add_argument('--max-consecutive-losses', type=int, default=3)
parser.add_argument('--pause-bars', type=int, default=10)
# ... 其他过滤器参数
```

---

##### 7. 边界情况处理

**场景1: 旧策略不支持 RuntimeConfigurable**

```python
# 旧策略（不继承 BaseEnhancedStrategy）
class OldStrategy(Strategy):
    def init(self):
        pass

    def next(self):
        pass

# 解决方案：提供向后兼容的包装器
def get_strategy_runtime_config(strategy_instance):
    """
    安全获取策略运行时配置，支持旧策略

    如果策略不支持 RuntimeConfigurable，返回空配置
    """
    if hasattr(strategy_instance, 'get_runtime_config'):
        return strategy_instance.get_runtime_config()
    else:
        # 旧策略，返回默认值
        return {
            "filters": {},
            "loss_protection": {
                "enable_loss_protection": False,
                "max_consecutive_losses": 3,
                "pause_bars": 10,
            }
        }
```

**场景2: 配置文件中没有 runtime_config 字段（向后兼容）**

```python
def load_strategy_params_with_runtime_config(strategy_name):
    """加载参数，支持旧配置文件格式"""
    params = params_manager.load_strategy_params(strategy_name)

    # 检查是否有 runtime_config
    if "runtime_config" not in params:
        # 旧配置文件，使用策略默认值
        strategy_class = get_strategy_class(strategy_name)
        if hasattr(strategy_class, 'get_runtime_config_schema'):
            # 从 schema 中提取默认值
            schema = strategy_class.get_runtime_config_schema()
            runtime_config = extract_defaults_from_schema(schema)
        else:
            # 完全旧策略，使用硬编码默认值
            runtime_config = get_default_runtime_config()

        params["runtime_config"] = runtime_config

    return params
```

**场景3: 命令行参数覆盖配置文件**

```python
def merge_runtime_config(config_from_file, config_from_cli):
    """
    合并配置，命令行参数优先级更高

    用例：用户想临时测试不同的止损参数，不修改配置文件
    """
    merged = config_from_file.copy()

    # CLI 参数覆盖配置文件参数
    if config_from_cli.get('enable_loss_protection') is not None:
        merged['loss_protection']['enable_loss_protection'] = config_from_cli['enable_loss_protection']

    if config_from_cli.get('max_consecutive_losses') is not None:
        merged['loss_protection']['max_consecutive_losses'] = config_from_cli['max_consecutive_losses']

    # ... 其他参数
    return merged
```

**场景4: 配置验证失败处理**

```python
def validate_runtime_config(config, schema):
    """
    验证配置完整性和参数范围

    失败时给出明确的错误提示
    """
    errors = []

    for section, params in schema.items():
        if section not in config:
            errors.append(f"缺少配置节: {section}")
            continue

        for param_name, param_spec in params.items():
            if param_name not in config[section]:
                errors.append(
                    f"缺少参数: {section}.{param_name} "
                    f"(默认值: {param_spec.get('default')})"
                )
                continue

            value = config[section][param_name]
            param_type = param_spec.get('type')
            param_range = param_spec.get('range')

            # 类型检查
            if param_type == 'int' and not isinstance(value, int):
                errors.append(f"{section}.{param_name} 应该是整数，实际: {type(value)}")

            # 范围检查
            if param_range and (value < param_range[0] or value > param_range[1]):
                errors.append(
                    f"{section}.{param_name} 超出范围 {param_range}，实际: {value}"
                )

    if errors:
        raise ValueError(
            "运行时配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors)
        )
```

---

##### 8. 分阶段实现计划

**Phase 1: 基础架构（必须）**
- [ ] 创建 `strategies/base_strategy.py`
- [ ] 实现 `RuntimeConfigurable` 和 `BaseEnhancedStrategy`
- [ ] 扩展 `StrategyParamsManager` 支持 `runtime_config`

**Phase 2: 策略迁移（必须）**
- [ ] 修改 `SmaCrossEnhanced` 继承 `BaseEnhancedStrategy`
- [ ] 修改 `MacdCross` 继承 `BaseEnhancedStrategy`
- [ ] 验证现有策略功能不受影响

**Phase 3: 保存和加载（必须）**
- [ ] 修改 `save_best_params()` 调用 `get_runtime_config()`
- [ ] 修改 `generate_signals.py` 加载 `runtime_config`
- [ ] 实现配置验证函数

**Phase 4: 强制检查（推荐）**
- [ ] 添加 `validate_strategy_contract()` 函数
- [ ] 在回测启动时检查策略契约
- [ ] 添加友好的错误提示

**Phase 5: 测试和文档（必须）**
- [ ] 添加单元测试验证参数完整性
- [ ] 测试向后兼容性（旧配置文件、旧策略）
- [ ] 更新 CLAUDE.md 说明新的策略开发规范

---

##### 9. 测试策略

**单元测试**:

```python
# tests/test_runtime_config.py

def test_base_strategy_get_runtime_config():
    """测试基类默认实现"""
    strategy = BaseEnhancedStrategy()
    config = strategy.get_runtime_config()

    assert "filters" in config
    assert "loss_protection" in config
    assert config["loss_protection"]["enable_loss_protection"] == False


def test_strategy_override_defaults():
    """测试子类覆盖默认值"""
    class CustomStrategy(BaseEnhancedStrategy):
        max_consecutive_losses = 5
        pause_bars = 15

    strategy = CustomStrategy()
    config = strategy.get_runtime_config()

    assert config["loss_protection"]["max_consecutive_losses"] == 5
    assert config["loss_protection"]["pause_bars"] == 15


def test_validate_strategy_contract():
    """测试契约检查"""
    class InvalidStrategy(Strategy):
        pass

    with pytest.raises(TypeError) as exc_info:
        validate_strategy_contract(InvalidStrategy)

    assert "必须继承 RuntimeConfigurable" in str(exc_info.value)


def test_save_and_load_runtime_config():
    """测试配置保存和加载"""
    # 保存配置
    runtime_config = {
        "loss_protection": {
            "enable_loss_protection": True,
            "max_consecutive_losses": 4,
            "pause_bars": 12
        }
    }
    params_manager.save_optimization_results_with_runtime_config(
        strategy_name="test_strategy",
        optimized_params={"n1": 10, "n2": 20},
        runtime_config=runtime_config,
        ...
    )

    # 加载配置
    loaded_config = params_manager.get_runtime_config("test_strategy")
    assert loaded_config == runtime_config


def test_backward_compatibility():
    """测试向后兼容性"""
    # 创建旧格式配置文件（无 runtime_config）
    old_config = {
        "test_strategy": {
            "params": {"n1": 10, "n2": 20}
        }
    }

    # 加载应该成功，使用默认值
    params = load_strategy_params_with_runtime_config("test_strategy")
    assert "runtime_config" in params
    assert params["runtime_config"]["loss_protection"]["enable_loss_protection"] == False
```

**集成测试**:

见下文「验证方法」章节。

---

## 实现检查清单

### Phase 1: 基础架构
- [ ] 创建 `strategies/base_strategy.py`
  - [ ] 定义 `RuntimeConfigurable` 抽象类
  - [ ] 实现 `BaseEnhancedStrategy` 基类
  - [ ] 实现 `get_runtime_config()` 默认方法
  - [ ] 实现 `get_runtime_config_schema()` 默认方法

### Phase 2: 参数管理器增强
- [ ] 扩展 `utils/strategy_params_manager.py`
  - [ ] 添加 `save_optimization_results_with_runtime_config()`
  - [ ] 添加 `get_runtime_config(strategy_name)`
  - [ ] 添加 `validate_runtime_config(config, schema)`
  - [ ] 添加向后兼容逻辑

### Phase 3: 策略迁移
- [ ] 修改 `strategies/sma_cross_enhanced.py`
  - [ ] 继承 `BaseEnhancedStrategy`
  - [ ] 验证现有功能不受影响
- [ ] 修改 `strategies/macd_cross.py`（如果存在）
  - [ ] 继承 `BaseEnhancedStrategy`
  - [ ] 定义 MACD 特有的止损参数

### Phase 4: 保存逻辑
- [ ] 修改 `backtest_runner/core/optimization.py`
  - [ ] 添加 `validate_strategy_contract()` 函数
  - [ ] 修改 `save_best_params()` 调用 `get_runtime_config()`
  - [ ] 在回测启动时检查策略契约

### Phase 5: 加载逻辑
- [ ] 修改 `generate_signals.py`
  - [ ] 加载 `runtime_config` 字段
  - [ ] 合并到策略参数
  - [ ] 应用到策略实例

### Phase 6: 测试
- [ ] 添加单元测试
  - [ ] 测试基类默认实现
  - [ ] 测试子类覆盖
  - [ ] 测试契约验证
  - [ ] 测试配置保存和加载
  - [ ] 测试向后兼容性
- [ ] 运行集成测试（见验证方法）

### Phase 7: 文档
- [ ] 更新 `CLAUDE.md`
  - [ ] 添加新策略开发规范
  - [ ] 说明 `BaseEnhancedStrategy` 使用方法
- [ ] 更新配置文件格式说明

## 影响范围

**新增文件**:
- `strategies/base_strategy.py` - 策略契约定义和基类实现

**修改文件**:
- `utils/strategy_params_manager.py` - 新增 runtime_config 支持
- `backtest_runner/core/optimization.py` - 保存时传入运行时参数
- `strategies/sma_cross_enhanced.py` - 继承 BaseEnhancedStrategy
- `strategies/macd_cross.py` - 继承 BaseEnhancedStrategy
- `generate_signals.py` - 加载时读取 runtime_config

**向后兼容性**:
- ✅ 旧配置文件无 `runtime_config` 字段时，使用策略默认值
- ✅ 旧策略不继承 `RuntimeConfigurable` 时，使用包装器提供默认配置
- ✅ 不影响现有功能

**风险评估**:
- 🟢 **低风险**: 新增功能不修改现有逻辑
- 🟢 **低风险**: 向后兼容确保旧代码可正常运行
- 🟡 **中风险**: 策略迁移需要测试验证（可通过充分测试降低）

---

## 方案对比与决策

### 方案A vs 方案B

| 维度 | 方案A（配置文件） | 方案B（命令行参数） |
|------|------------------|---------------------|
| **核心思想** | 扩展配置文件结构保存运行时参数 | generate_signals.py 支持命令行参数 |
| **强制性** | ✅ 通过抽象类强制实现 | ❌ 依赖人工记忆和文档 |
| **可维护性** | ✅ 参数集中管理，易追溯 | ❌ 参数分散在配置文件和命令行 |
| **用户体验** | ✅ 自动复现回测环境，无需记忆参数 | ❌ 需要手动复制回测时的命令行参数 |
| **扩展性** | ✅ 新策略自动检查是否实现接口 | ❌ 新策略需要人工添加参数支持 |
| **错误风险** | 🟢 低（自动保存和加载） | 🔴 高（参数遗漏导致信号错误） |
| **实现复杂度** | 🟡 中等（需要策略基类和契约） | 🟢 低（只需添加命令行参数） |

### 决策：选择方案A ✅

**理由**:

1. **根本解决问题**
   - 方案A从根源上解决参数保存问题，确保回测和实盘环境一致
   - 方案B治标不治本，依然需要人工记忆和复制参数

2. **强制性和安全性**
   - 通过策略契约机制，新策略如果不实现接口会在开发时就发现问题
   - 避免因为遗漏参数导致实盘信号错误

3. **可扩展性**
   - 支持未来新增更多运行时参数（如新的过滤器、风险控制逻辑）
   - 不需要修改 `generate_signals.py` 的命令行参数

4. **用户体验**
   - 用户只需一次保存配置，后续实盘信号生成自动使用正确参数
   - 降低操作复杂度和出错概率

**方案B的适用场景**:
- ✅ 作为临时方案快速验证（开发周期短）
- ✅ 作为方案A的补充，支持命令行临时覆盖配置文件参数
- ❌ 不适合作为长期解决方案

### 实施建议

**短期（1-2天）**:
- 实现方案A的核心功能（Phase 1-3）
- 确保现有 SMA 和 MACD 策略迁移成功

**中期（3-5天）**:
- 添加强制检查和测试（Phase 4-6）
- 完善文档和示例

**长期（可选）**:
- 考虑添加方案B作为补充，允许命令行参数覆盖配置文件
- 实现配置版本管理和迁移工具

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
