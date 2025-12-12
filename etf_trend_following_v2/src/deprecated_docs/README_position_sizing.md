# Position Sizing Module

## 概述

`position_sizing.py` 是ETF趋势跟踪系统的仓位管理模块，实现基于**波动率倒数加权**的投资组合构建方法。核心思想是按"风险"而非金额分配资金：波动大的ETF少买，波动小的多买，确保每个持仓对账户的风险贡献一致。

## 核心特性

- **波动率估计**: 支持滚动标准差（STD）和指数加权移动平均（EWMA）两种方法
- **逆波动率加权**: 自动计算每只ETF的目标仓位，使风险贡献均等
- **多层约束系统**:
  - 单标的上限（默认20%）
  - 簇级别上限（默认20%）
  - 总仓位上限（默认100%，无杠杆）
- **A股市场兼容**: 支持100股/手的交易单位，自动取整
- **调仓计算**: 从当前持仓到目标持仓的交易指令生成

## 理论基础

### 波动率倒数加权公式

```
PositionCapital_i = TotalAccountCapital × TargetRisk / DailyVolatility_i
```

**示例**（账户100万，目标风险0.5%）：
- 国债ETF波动率0.1%: 5000/0.001 = 500万（会被20%上限截断到20万）
- 券商ETF波动率2.0%: 5000/0.02 = 25万

### 目标风险推导

假设投资组合年化波动率目标为20%，持有N只ETF：

```
日波动率目标 = 20% / sqrt(252) ≈ 1.25%
单标的风险贡献 = 1.25% / sqrt(N)
```

对于10只ETF：
```
单标的日风险 = 1.25% / sqrt(10) ≈ 0.4% → 设定为0.5%
```

## 快速开始

### 基础用法

```python
from position_sizing import calculate_portfolio_positions

# 准备数据
data_dict = {
    '159915.SZ': df_159915,  # DataFrame with 'close' column
    '512880.SH': df_512880,
}

# 计算仓位
positions = calculate_portfolio_positions(
    data_dict=data_dict,
    symbols=['159915.SZ', '512880.SH'],
    total_capital=1_000_000,
    target_risk_pct=0.005,      # 0.5%日风险
    max_position_pct=0.2,        # 单标的最大20%
    max_cluster_pct=0.2,         # 单簇最大20%
    cluster_assignments={'159915.SZ': 0, '512880.SH': 1},
    volatility_method='ewma'
)

# 查看结果
from position_sizing import get_position_summary
summary = get_position_summary(positions, 1_000_000)
print(summary)
```

### 输出示例

```
      symbol  target_capital  target_weight  volatility  cluster_id
   159915.SZ        200000.0           20.0       1.234           0
   512880.SH        150000.0           15.0       1.678           1
       TOTAL        350000.0           35.0         NaN        None
```

## API 参考

### 核心函数

#### 1. `calculate_volatility()`

计算单个标的的日波动率。

```python
vol = calculate_volatility(
    df,                    # DataFrame with 'close' column
    method='ewma',         # 'std' or 'ewma'
    window=60,             # 仅用于'std'方法
    ewma_lambda=0.94       # RiskMetrics标准值
)
```

**推荐**: EWMA方法对近期数据权重更高，能更快响应市场变化。

#### 2. `calculate_position_size()`

计算单个标的的目标仓位。

```python
capital, weight = calculate_position_size(
    volatility=0.02,           # 日波动率（如2%）
    total_capital=1_000_000,
    target_risk_pct=0.005,     # 0.5%目标风险
    max_position_pct=0.2       # 20%上限
)
```

#### 3. `calculate_portfolio_positions()`

计算整个投资组合的仓位（主入口函数）。

```python
positions = calculate_portfolio_positions(
    data_dict,                 # {symbol: DataFrame}
    symbols,                   # 标的列表
    total_capital,
    target_risk_pct=0.005,
    max_position_pct=0.2,
    max_cluster_pct=0.2,       # 可选，设为None禁用
    cluster_assignments=None,  # 可选，簇分配
    max_total_pct=1.0,
    volatility_method='ewma'
)
```

**返回**:
```python
{
    'symbol': {
        'target_capital': float,   # 目标仓位金额
        'target_weight': float,    # 权重（0-1）
        'volatility': float,       # 日波动率
        'cluster_id': int or None  # 簇ID
    }
}
```

#### 4. `calculate_rebalance_trades()`

计算调仓交易指令。

```python
trades = calculate_rebalance_trades(
    current_positions={'159915.SZ': 50000},  # 当前持仓金额
    target_positions={'159915.SZ': 100000},  # 目标持仓金额
    current_prices={'159915.SZ': 2.5},       # 当前价格
    min_trade_amount=1000,                   # 最小交易金额
    lot_size=100                             # A股100股/手
)
```

**返回**:
```python
{
    '159915.SZ': {
        'action': 'buy',       # 'buy' or 'sell'
        'amount': 50000.0,     # 交易金额
        'shares': 20000,       # 股数（已取整到100的倍数）
        'delta_pct': 50.0      # 相对目标仓位的变化百分比
    }
}
```

### 辅助函数

#### `normalize_positions()`
归一化仓位，确保总仓位不超上限。

#### `apply_cluster_limits()`
应用簇级别的仓位上限。

#### `validate_portfolio_constraints()`
验证投资组合是否满足所有约束。

```python
is_valid, errors = validate_portfolio_constraints(
    positions,
    max_position_pct=0.2,
    max_cluster_pct=0.2,
    max_total_pct=1.0,
    cluster_assignments=cluster_map
)

if not is_valid:
    for error in errors:
        print(f"Constraint violation: {error}")
```

#### `get_position_summary()`
生成投资组合摘要表（pandas DataFrame）。

## 完整使用示例

### 场景1: 无簇约束的基础组合

```python
import pandas as pd
from position_sizing import (
    calculate_portfolio_positions,
    get_position_summary,
    validate_portfolio_constraints
)

# 加载数据（假设已有）
data_dict = load_etf_data(['159915.SZ', '512880.SH', '511010.SH'])

# 计算仓位
positions = calculate_portfolio_positions(
    data_dict=data_dict,
    symbols=list(data_dict.keys()),
    total_capital=1_000_000,
    target_risk_pct=0.005,
    max_position_pct=0.2,
    max_cluster_pct=None,        # 禁用簇约束
    volatility_method='ewma'
)

# 验证约束
is_valid, errors = validate_portfolio_constraints(
    positions,
    max_position_pct=0.2,
    max_total_pct=1.0
)
print(f"Portfolio valid: {is_valid}")

# 生成报告
summary = get_position_summary(positions, 1_000_000)
print(summary.to_string(index=False))
```

### 场景2: 带簇约束的组合（推荐）

```python
# 簇分配（来自ETF筛选模块）
cluster_map = {
    '159915.SZ': 0,  # 创业板ETF - 簇0
    '512880.SH': 1,  # 券商ETF - 簇1
    '512690.SH': 1,  # 证券ETF - 簇1（同一簇）
    '511010.SH': 2,  # 国债ETF - 簇2
}

positions = calculate_portfolio_positions(
    data_dict=data_dict,
    symbols=list(cluster_map.keys()),
    total_capital=1_000_000,
    target_risk_pct=0.005,
    max_position_pct=0.2,        # 单标的最大20%
    max_cluster_pct=0.3,         # 单簇最大30%
    cluster_assignments=cluster_map,
    max_total_pct=1.0
)

# 验证簇约束
is_valid, errors = validate_portfolio_constraints(
    positions,
    max_position_pct=0.2,
    max_cluster_pct=0.3,
    cluster_assignments=cluster_map
)
```

### 场景3: 调仓执行

```python
from position_sizing import calculate_rebalance_trades

# 假设当前持仓（从broker获取）
current_holdings = {
    '159915.SZ': 80000,   # 8万
    '512880.SH': 120000,  # 12万
    '511010.SH': 0        # 无持仓
}

# 目标仓位（从上面计算得出）
target_holdings = {
    symbol: pos['target_capital']
    for symbol, pos in positions.items()
}

# 当前价格（从行情获取）
current_prices = {
    '159915.SZ': 2.50,
    '512880.SH': 1.80,
    '511010.SH': 101.50
}

# 计算交易指令
trades = calculate_rebalance_trades(
    current_positions=current_holdings,
    target_positions=target_holdings,
    current_prices=current_prices,
    min_trade_amount=1000,
    lot_size=100
)

# 打印交易指令
for symbol, trade in trades.items():
    print(f"{symbol}: {trade['action'].upper()} {trade['shares']} shares "
          f"(≈{trade['amount']:,.0f} CNY)")
```

**输出示例**:
```
159915.SZ: BUY 8000 shares (≈20,000 CNY)
512880.SH: SELL 11200 shares (≈20,160 CNY)
511010.SH: BUY 1000 shares (≈101,500 CNY)
```

## 参数调优建议

### `target_risk_pct` - 目标风险

| 风格 | 建议值 | 说明 |
|------|--------|------|
| 保守 | 0.003 (0.3%) | 低风险，适合稳健投资者 |
| **中性** | **0.005 (0.5%)** | **推荐默认值** |
| 激进 | 0.008 (0.8%) | 高风险高收益 |

### `max_position_pct` - 单标的上限

| 策略 | 建议值 | 说明 |
|------|--------|------|
| 高度分散 | 0.10 (10%) | 10只以上标的 |
| **平衡分散** | **0.20 (20%)** | **推荐，5-10只标的** |
| 集中持仓 | 0.30 (30%) | 3-5只标的 |

### `max_cluster_pct` - 簇上限

建议设为 `1.5 × max_position_pct`，例如：
- 单标的20% → 簇上限30%
- 单标的15% → 簇上限20-25%

### `volatility_method` - 波动率方法

| 方法 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **EWMA** (推荐) | 响应快，捕捉近期变化 | 对短期波动敏感 | **趋势跟踪系统** |
| STD | 稳定，不易受异常值影响 | 反应慢 | 长期配置策略 |

## 特殊情况处理

### 1. 波动率极低的标的（如国债ETF）

模块会自动应用 `min_volatility=0.0001` (0.01%) 的下限，防止除零错误和过度配置。

### 2. 总仓位不满仓

如果所有标的风险调整后的仓位总和 < 100%，系统会**保留现金**，不会强制满仓。这是合理的风险管理行为。

### 3. 数据不足

如果某只ETF历史数据不足（少于`window`天），STD方法会返回NaN，该标的会被自动跳过。EWMA方法对数据长度要求更宽松。

### 4. 价格跳空

调仓计算时，如果价格数据缺失（`prices[symbol]`为None），该标的会被自动跳过。

## 测试

运行单元测试：

```bash
# 确保在backtesting环境
conda activate backtesting

# 运行测试
python -m pytest etf_trend_following_v2/tests/test_position_sizing.py -v

# 查看覆盖率
python -m pytest etf_trend_following_v2/tests/test_position_sizing.py --cov=etf_trend_following_v2.src.position_sizing
```

**测试覆盖**:
- 波动率计算（STD/EWMA）
- 仓位计算逻辑
- 多层约束执行
- 调仓交易生成
- 边界条件处理

## 与系统其他模块的集成

### 上游模块

1. **ETF筛选模块** → 提供 `symbols` 和 `cluster_assignments`
2. **数据加载模块** → 提供 `data_dict` (OHLCV数据)

### 下游模块

1. **交易执行模块** ← 接收 `trades` 执行调仓
2. **监控报告模块** ← 接收 `positions` 生成报表

### 集成示例

```python
# 1. 从筛选模块获取标的池
from etf_selector import select_top_etfs
symbols, clusters = select_top_etfs(n=20)

# 2. 从数据模块加载数据
from data_loader import load_etf_data
data_dict = load_etf_data(symbols)

# 3. 计算仓位
from position_sizing import calculate_portfolio_positions
positions = calculate_portfolio_positions(
    data_dict, symbols, total_capital=1_000_000,
    cluster_assignments=clusters
)

# 4. 生成交易指令
from position_sizing import calculate_rebalance_trades
trades = calculate_rebalance_trades(current, target, prices)

# 5. 执行交易（交由执行模块）
from trade_executor import execute_trades
execute_trades(trades)
```

## 性能优化

### 计算效率

- **批量计算**: `calculate_portfolio_positions()` 一次性计算所有标的
- **向量化**: 使用pandas/numpy向量运算，避免循环
- **惰性评估**: 仅在需要时计算约束调整

### 内存管理

- 仅保留必要的历史数据（默认60天窗口）
- 使用字典而非DataFrame存储仓位，减少内存开销

## 常见问题

### Q1: 为什么总仓位只有60%，没有满仓？

**A**: 这是正常现象。逆波动率加权确保每只ETF的风险贡献相同，而不是金额相同。如果所有标的都在单标的上限（如20%）以下，总仓位可能低于100%。可以：
- 降低 `target_risk_pct`（但会降低整体风险）
- 增加标的数量
- 调整 `max_position_pct` 上限

### Q2: EWMA和STD方法有多大差异？

**A**: 在稳定市场中差异<5%，但在波动率剧变时（如暴跌后）EWMA会更快调整仓位。对于趋势跟踪系统，推荐EWMA。

### Q3: 簇约束和单标的约束冲突怎么办？

**A**: 系统会按顺序应用约束：
1. 先应用单标的上限
2. 再应用簇上限（等比例缩放簇内标的）
3. 最后应用总仓位上限

### Q4: 如何处理分红对波动率的影响？

**A**: 使用**后复权价格**计算收益率，分红会自动包含在复权因子中。系统假设输入数据已完成复权处理。

## 版本历史

- **v1.0** (2025-12-11): 初始版本
  - 实现EWMA/STD波动率计算
  - 逆波动率加权仓位计算
  - 多层约束系统
  - A股市场调仓支持
  - 完整单元测试覆盖

## 参考文献

1. **RiskMetrics Technical Document** (J.P. Morgan, 1996)
   - EWMA波动率估计方法
   - λ=0.94的理论依据

2. **Volatility-Based Tactical Asset Allocation** (Andrew Clare et al., 2016)
   - 逆波动率加权在资产配置中的应用

3. **中国A股交易规则**
   - 100股/手的交易单位
   - T+1交易制度（本模块不涉及）

## 许可证

本模块是ETF趋势跟踪系统的一部分，遵循项目统一许可证。

## 作者

Claude (Anthropic) - 2025年12月11日
