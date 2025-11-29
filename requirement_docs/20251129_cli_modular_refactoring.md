# CLI 模块化重构需求文档

## 文档信息

- **创建日期**: 2025-11-29
- **状态**: ✅ 已完成
- **影响范围**: `backtest_runner/cli.py` → `backtest_runner/cli/` 子模块

---

## 一、背景与问题

### 1.1 问题描述

在前一次模块化重构后，`backtest_runner/cli.py` 仍然有 **1032 行**代码，占整个 `backtest_runner/` 包代码量的 27%，成为新的代码膨胀点。

### 1.2 代码职责分布（重构前）

| 函数/区块 | 行数 | 职责 |
|----------|-----|------|
| `main()` | ~110 | 主流程编排 |
| `_print_system_info()` | ~30 | 系统信息输出 |
| `_configure_*` 系列 | ~60 | 配置构建 |
| `_get_*/process_*` 系列 | ~80 | 标的处理 |
| `_run_batch_backtests()` | ~100 | 批量回测执行 |
| `_process_results()` / `_save_summary_csv()` | ~120 | 结果处理与保存 |
| `_save_global_summary_csv()` | ~100 | 全局统计汇总 |
| **轮动模式相关** | **~430** | `_run_rotation_mode()` 及子函数 |

### 1.3 核心问题

1. **轮动模式代码膨胀** - 占 cli.py 的 42%，与标准回测模式耦合
2. **职责边界模糊** - 配置加载、标的处理、结果保存等逻辑混杂
3. **重复代码模式** - `_build_strategy_instance()` 中大量重复的 `hasattr/getattr`
4. **测试困难** - 函数通过 `args` 对象隐式传参，难以单元测试

---

## 二、重构目标

### 2.1 量化目标

| 指标 | 重构前 | 目标 |
|-----|-------|-----|
| cli.py 行数 | 1032 | < 50 |
| 最大单文件行数 | 1032 | < 450 |
| 可测试性 | 低 | 高 |
| 代码重复 | hasattr 重复 20+ 次 | 0 重复 |

### 2.2 设计目标

- 模式分离：标准模式与轮动模式独立
- 可复用组件：抽取通用逻辑为独立模块
- 声明式配置：消除重复的条件判断代码
- 向后兼容：现有调用方式不变

---

## 三、技术方案

### 3.1 目标架构

```
backtest_runner/
├── cli.py                    # 薄包装层（向后兼容）
├── cli/
│   ├── __init__.py           # 导出 main()
│   ├── main.py               # 主入口、参数验证、模式分发
│   ├── standard_mode.py      # 标准回测模式
│   └── rotation_mode.py      # 轮动策略模式
├── config/
│   ├── argparser.py          # (已有) 参数定义
│   ├── strategy_registry.py  # (已有) 策略注册
│   ├── runtime_loader.py     # 🆕 运行时配置加载
│   └── strategy_builder.py   # 🆕 策略实例构建器
├── io/
│   ├── result_writer.py      # (已有)
│   └── summary_generator.py  # 🆕 CSV 汇总生成
└── ...
```

### 3.2 模块职责划分

#### cli/main.py (~120行)
- 命令行参数解析
- 参数验证
- 运行时配置加载
- 模式分发（标准 vs 轮动）

#### cli/standard_mode.py (~400行)
- 标准回测流程控制
- 标的筛选和处理
- 批量回测执行
- 结果处理调用

#### cli/rotation_mode.py (~320行)
- 轮动策略回测流程
- 虚拟 ETF 数据构建调用
- 轮动统计计算
- 轮动结果输出

#### config/runtime_loader.py (~50行)
- 从配置文件加载运行时参数
- 支持 filters/loss_protection/anti_whipsaw/trailing_stop/atr_stop

#### config/strategy_builder.py (~100行)
- 声明式参数映射表
- 动态构建策略子类

#### io/summary_generator.py (~300行)
- 回测汇总 CSV 生成
- 全局统计概括生成
- 轮动策略汇总生成

### 3.3 关键设计改进

#### 3.3.1 策略构建器（消除重复代码）

**重构前** - 大量重复的 hasattr/setattr：
```python
def _build_strategy_instance(strategy_class, args):
    strategy_params = {}
    if hasattr(strategy_class, 'enable_slope_filter') and hasattr(args, 'enable_slope_filter'):
        strategy_params['enable_slope_filter'] = args.enable_slope_filter
    if hasattr(strategy_class, 'enable_adx_filter') and hasattr(args, 'enable_adx_filter'):
        strategy_params['enable_adx_filter'] = args.enable_adx_filter
    # ... 重复 20+ 次 ...
```

**重构后** - 声明式配置：
```python
# config/strategy_builder.py
STRATEGY_PARAM_MAPPING = {
    'enable_slope_filter': 'enable_slope_filter',
    'enable_adx_filter': 'enable_adx_filter',
    'enable_volume_filter': 'enable_volume_filter',
    # ... 完整映射表 ...
}

def build_strategy_instance(strategy_class, args):
    params = {}
    for strategy_attr, args_attr in STRATEGY_PARAM_MAPPING.items():
        if hasattr(strategy_class, strategy_attr) and hasattr(args, args_attr):
            params[strategy_attr] = getattr(args, args_attr)
    return type('ParameterizedStrategy', (strategy_class,), params)
```

#### 3.3.2 运行时配置加载器

**重构前** - 手动处理每个配置块：
```python
if getattr(args, 'load_params', None):
    filters_cfg = runtime_config.get('filters', {})
    for k, v in filters_cfg.items():
        setattr(args, k, v)
    loss_cfg = runtime_config.get('loss_protection', {})
    for k, v in loss_cfg.items():
        setattr(args, k, v)
    # ... 重复 5 次 ...
```

**重构后** - 统一配置加载：
```python
# config/runtime_loader.py
CONFIG_SECTIONS = ['filters', 'loss_protection', 'anti_whipsaw', 'trailing_stop', 'atr_stop']

def load_runtime_config(args, config_path, strategy_name):
    manager = StrategyParamsManager(config_path)
    runtime_config = manager.get_runtime_config(strategy_name) or {}
    for section in CONFIG_SECTIONS:
        for key, value in runtime_config.get(section, {}).items():
            setattr(args, key, value)
```

#### 3.3.3 模式分离

**重构前** - main() 中混合处理：
```python
def main():
    # ... 参数解析 ...
    if args.enable_rotation:
        return _run_rotation_mode(args)  # 轮动模式
    # ... 标准模式代码 ...
```

**重构后** - 清晰的模式分发：
```python
# cli/main.py
def main():
    args = parser.parse_args()
    if args.load_params:
        load_runtime_config(args, args.load_params, args.strategy)
    if error := _validate_args(args):
        return 1

    if args.enable_rotation:
        from .rotation_mode import run_rotation_mode
        return run_rotation_mode(args)
    else:
        from .standard_mode import run_standard_mode
        return run_standard_mode(args)
```

---

## 四、实现结果

### 4.1 新增文件

| 文件 | 行数 | 职责 |
|-----|-----|------|
| `cli/__init__.py` | 12 | 导出 main() |
| `cli/main.py` | 112 | 主入口、参数验证 |
| `cli/standard_mode.py` | 392 | 标准回测模式 |
| `cli/rotation_mode.py` | 317 | 轮动策略模式 |
| `config/runtime_loader.py` | 50 | 运行时配置加载 |
| `config/strategy_builder.py` | 98 | 策略实例构建器 |
| `io/summary_generator.py` | 301 | CSV 汇总生成 |

### 4.2 修改文件

| 文件 | 变化 | 说明 |
|-----|-----|------|
| `cli.py` | 1032 → 23 行 | 改为薄包装层 |
| `config/__init__.py` | +4 行 | 导出新模块 |
| `io/__init__.py` | +8 行 | 导出新模块 |
| `__init__.py` | +10 行 | 版本号 2.0.0，导出 main |

### 4.3 效果对比

| 指标 | 重构前 | 重构后 | 改进 |
|-----|-------|-------|-----|
| cli.py 行数 | 1032 | 23 | **-97.8%** |
| 最大单文件行数 | 1032 | 405 | **-60.8%** |
| CLI 模块文件数 | 1 | 4 | 职责分离 |
| 新增可复用组件 | 0 | 3 | 提升复用性 |
| hasattr 重复次数 | 20+ | 0 | **消除重复** |

---

## 五、向后兼容性

### 5.1 兼容性保证

- `backtest_runner/cli.py` 保留为薄包装层
- 所有现有调用方式不变：
  - `python backtest_runner/cli.py ...`
  - `./run_backtest.sh ...`
  - `from backtest_runner.cli import main`

### 5.2 测试验证

```bash
# 测试 CLI help
python backtest_runner/cli.py --help  # ✅ 通过

# 测试标准回测
python backtest_runner/cli.py -s 510300.SH -t sma_cross \
    --data-dir data/chinese_etf/daily \
    --start-date 2024-01-01 --end-date 2024-06-30  # ✅ 通过

# 测试 shell 脚本调用
./run_backtest.sh -s 510300.SH -t kama_cross \
    --data-dir data/chinese_etf/daily \
    --start-date 2024-01-01 --end-date 2024-06-30  # ✅ 通过
```

---

## 六、后续开发指南

### 6.1 新增回测模式

如需添加新的回测模式（如组合回测、多策略对比等）：

1. 在 `cli/` 目录下创建新模块，如 `portfolio_mode.py`
2. 实现 `run_portfolio_mode(args)` 函数
3. 在 `cli/main.py` 中添加模式分发逻辑

### 6.2 新增策略参数

如需支持新的策略参数：

1. 在 `config/argparser.py` 中添加参数定义
2. 在 `config/strategy_builder.py` 的 `STRATEGY_PARAM_MAPPING` 中添加映射

### 6.3 新增配置块

如需支持新的运行时配置块：

1. 在 `config/runtime_loader.py` 的 `CONFIG_SECTIONS` 中添加块名称

---

## 七、文件清单

### 7.1 新增文件

```
backtest_runner/cli/__init__.py
backtest_runner/cli/main.py
backtest_runner/cli/standard_mode.py
backtest_runner/cli/rotation_mode.py
backtest_runner/config/runtime_loader.py
backtest_runner/config/strategy_builder.py
backtest_runner/io/summary_generator.py
```

### 7.2 修改文件

```
backtest_runner/cli.py
backtest_runner/__init__.py
backtest_runner/config/__init__.py
backtest_runner/io/__init__.py
```

---

## 八、总结

本次重构将 1032 行的 `cli.py` 拆分为 7 个模块，实现了：

1. **模式分离** - 标准模式和轮动模式独立维护
2. **职责清晰** - 每个模块职责单一，便于理解和修改
3. **代码复用** - 策略构建器、配置加载器、汇总生成器可复用
4. **消除重复** - 声明式配置替代重复的条件判断
5. **向后兼容** - 现有脚本无需任何修改
