# Signal Generator 模块

实盘交易信号生成器，用于每天收盘后分析股票池中的所有标的，生成买入/卖出信号。

## 目录结构

```
signal_generator/
├── __init__.py          # 包入口，导出公共API
├── __main__.py          # 支持 python -m signal_generator 调用
├── config.py            # 配置常量（费用模型、默认参数）
├── core.py              # SignalGenerator 核心类
├── cli.py               # 命令行接口和模式处理
├── reports.py           # 报告打印函数
├── detectors/           # 信号检测器子包
│   ├── __init__.py
│   ├── base.py          # 信号检测器基类
│   ├── macd.py          # MACD信号检测器
│   ├── sma.py           # SMA信号检测器
│   └── kama.py          # KAMA信号检测器
└── README.md            # 本文档
```

## 模块说明

### config.py - 配置模块
定义费用模型和默认参数：
- `COST_MODELS`: 费用模型配置（cn_etf、cn_stock、us_stock等）
- `DEFAULT_*`: 默认参数（资金、回看天数、持仓数等）

### core.py - 核心模块
`SignalGenerator` 类，负责：
- 数据加载（支持单价格/双价格模式）
- 信号生成（委托给检测器）
- 资金分配计算
- 日期追踪

主要方法：
- `get_signal(ts_code)`: 获取单个标的的信号
- `generate_signals_for_pool(stock_list_file)`: 批量生成信号

### detectors/ - 信号检测器子包
策略无关的信号检测逻辑：

| 检测器 | 文件 | 功能 |
|--------|------|------|
| `BaseSignalDetector` | base.py | 抽象基类，定义检测接口 |
| `MacdSignalDetector` | macd.py | MACD金叉/死叉检测，支持Anti-Whipsaw |
| `SmaSignalDetector` | sma.py | SMA金叉/死叉检测，支持持续确认 |
| `KamaSignalDetector` | kama.py | KAMA信号检测，支持持续确认 |

### reports.py - 报告模块
提供格式化输出函数：
- `print_signal_report()`: 打印信号报告
- `print_portfolio_status()`: 打印持仓状态
- `print_trade_plan()`: 打印交易计划
- `print_execution_summary()`: 打印已执行交易摘要
- `print_snapshot_list()`: 打印快照列表

### cli.py - 命令行模块
处理6种工作模式：
1. `--init`: 初始化持仓文件
2. `--status`: 查看持仓状态
3. `--analyze`: 分析模式（不执行）
4. `--execute`: 执行模式
5. `--list-snapshots`: 列出快照
6. `--restore`: 恢复快照

## 使用方式

### 作为模块导入

```python
from signal_generator import SignalGenerator
from strategies.sma_cross import SmaCross

# 创建信号生成器
generator = SignalGenerator(
    strategy_class=SmaCross,
    strategy_params={'n1': 10, 'n2': 20},
    cash=100000,
    cost_model='cn_etf',
    data_dir='data/csv/daily',
    lookback_days=250
)

# 获取单个标的信号
signal = generator.get_signal('510050.SH')
print(signal['signal'])  # BUY, SELL, HOLD_LONG, HOLD_SHORT, ERROR

# 批量生成信号
signals_df, allocation = generator.generate_signals_for_pool(
    'stocks.csv',
    target_positions=10
)
```

### 命令行使用

```bash
# 方式1：直接运行模块
python -m signal_generator --help

# 方式2：使用原有脚本（保持向后兼容）
python generate_signals.py --help

# 初始化持仓
python -m signal_generator --init 100000 --portfolio-file portfolio.json

# 查看持仓状态
python -m signal_generator --status --portfolio-file portfolio.json

# 分析模式
python -m signal_generator --analyze \
    --stock-list stocks.csv \
    --portfolio-file portfolio.json \
    --strategy macd_cross

# 执行模式
python -m signal_generator --execute \
    --stock-list stocks.csv \
    --portfolio-file portfolio.json \
    --strategy macd_cross

# 无状态模式（快速信号扫描）
python -m signal_generator \
    --stock-list stocks.csv \
    --strategy sma_cross \
    --cash 100000
```

## 信号检测器扩展

如需添加新的策略信号检测器，继承 `BaseSignalDetector`：

```python
from signal_generator.detectors.base import BaseSignalDetector

class MySignalDetector(BaseSignalDetector):
    def detect_signal(self, strategy, result, df=None):
        # 实现信号检测逻辑
        # ...
        result['signal'] = 'BUY'  # or 'SELL', 'HOLD_LONG', 'HOLD_SHORT'
        result['message'] = '信号说明'
        return result
```

然后在 `core.py` 的 `_detect_signal_by_strategy_type()` 方法中添加策略类型判断。

## 与原 generate_signals.py 的对比

| 方面 | 原文件 | 重构后 |
|------|--------|--------|
| 代码行数 | 1866行单文件 | 10个文件，平均~150行/文件 |
| 可维护性 | 职责混杂 | 职责单一，模块化 |
| 可测试性 | 难以单独测试 | 各模块可独立测试 |
| 可扩展性 | 修改影响面大 | 新增策略只需添加检测器 |
| 向后兼容 | - | 100%兼容原CLI参数 |

## 依赖关系

```
cli.py
  ├── core.py (SignalGenerator)
  │     └── detectors/ (信号检测器)
  ├── reports.py (报告打印)
  └── config.py (配置)

外部依赖：
  ├── backtesting (回测框架)
  ├── portfolio_manager (持仓管理)
  ├── utils/data_loader (数据加载)
  ├── utils/strategy_params_manager (参数管理)
  └── strategies/ (策略类)
```

## 注意事项

1. **双价格模式**：默认使用复权价格计算信号，原始价格用于交易
2. **幂等性保护**：执行模式下，同一天不会重复执行（除非使用 `--force`）
3. **快照机制**：执行前自动保存快照，支持恢复
4. **Anti-Whipsaw**：MACD检测器支持滞回阈值、零轴约束、卖出确认等过滤
