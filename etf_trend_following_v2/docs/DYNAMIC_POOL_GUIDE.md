# 动态ETF池功能使用指南

## 功能概述

动态ETF池功能允许系统在每个调仓日（rebalance day）动态扫描全市场ETF，仅保留满足流动性条件的标的进入可交易池。这实现了Gemini讨论中提出的"广撒网"设计理念。

## 核心特性

1. **不再依赖预先筛选的ETF池文件** - 不需要 `pool_file` 或 `pool_list`
2. **每个调仓日动态计算** - 在每个rebalance day实时计算哪些ETF满足流动性条件
3. **新上市的ETF自动纳入** - 一旦满足条件（上市天数 + 流动性）就自动进入可交易池
4. **退市/流动性恶化的ETF自动移除** - 不满足条件的ETF会被从可交易池移除，持仓会被强制卖出

## 配置方法

### 1. 配置文件设置

在JSON配置文件中，设置以下参数：

```json
{
  "universe": {
    "dynamic_pool": true,                          // 启用动态池
    "all_etf_data_dir": "data/chinese_etf/daily",  // 全量ETF数据目录
    "liquidity_threshold": {
      "min_avg_volume": 500000,   // 最小平均成交量（股）- MA5
      "min_avg_amount": 5000000   // 最小平均成交额（元）- MA5
    },
    "min_listing_days": 60,       // 最小上市天数
    "blacklist": []                // 黑名单（可选）
  }
}
```

### 2. 流动性阈值配置

推荐的三种配置方案：

#### 保守配置（约200只ETF）
```json
"liquidity_threshold": {
  "min_avg_volume": 1000000,   // 100万股
  "min_avg_amount": 10000000   // 1000万元
}
```

#### 平衡配置（约300-400只ETF）
```json
"liquidity_threshold": {
  "min_avg_volume": 500000,    // 50万股
  "min_avg_amount": 5000000    // 500万元
}
```

#### 激进配置（约600-800只ETF）
```json
"liquidity_threshold": {
  "min_avg_volume": 300000,    // 30万股
  "min_avg_amount": 3000000    // 300万元
}
```

### 3. 数据目录结构

确保数据目录包含所有ETF CSV文件：

```
data/chinese_etf/daily/
└── etf/
    ├── 159915.SZ.csv
    ├── 510050.SH.csv
    ├── 512880.SH.csv
    └── ... (1700+ ETF文件)
```

每个CSV文件格式：
- 包含 `trade_date`, `open`, `high`, `low`, `close`, `volume`, `amount` 列
- `trade_date` 格式: YYYYMMDD (如 '20240102')
- `volume` 单位: hands (1 hand = 100 shares)
- `amount` 单位: k_yuan (1 unit = 1000 yuan)

## 使用示例

### Python API

```python
from etf_trend_following_v2.src.config_loader import load_config
from etf_trend_following_v2.src.portfolio_backtest_runner import PortfolioBacktestRunner

# 加载配置
config = load_config('config/example_dynamic_pool_config.json')

# 创建回测运行器
runner = PortfolioBacktestRunner(config)

# 运行回测
results = runner.run(
    start_date='2023-01-01',
    end_date='2024-12-31',
    initial_capital=1_000_000,
    output_dir='results/dynamic_pool_backtest'
)

print(f"Final Equity: {results['stats']['equity_final']:,.2f}")
print(f"Sharpe Ratio: {results['stats']['sharpe_ratio']:.2f}")
```

### 命令行

```bash
# 使用动态池配置运行回测
python -m etf_trend_following_v2.run_backtest \
    --config config/example_dynamic_pool_config.json \
    --start-date 2023-01-01 \
    --end-date 2024-12-31 \
    --output-dir results/dynamic_pool_backtest
```

## 工作原理

### 1. 数据加载阶段

```python
# 系统扫描全量ETF数据目录
all_symbols = scan_all_etfs('data/chinese_etf/daily')
# 结果: ['159915.SZ', '510050.SH', ..., '512880.SH']  (1700+ symbols)

# 加载所有ETF的历史数据
data_dict = load_universe(all_symbols, ...)
```

### 2. 每个调仓日动态过滤

```python
# 在每个rebalance day (如 2024-01-02)
dynamic_pool = filter_by_dynamic_liquidity(
    symbols=all_symbols,
    as_of_date='2024-01-02',
    min_amount=5_000_000,    # MA5 平均成交额
    min_volume=500_000,      # MA5 平均成交量
    lookback_days=5,         # 使用5日均值
    min_listing_days=60      # 至少上市60天
)
# 结果: 约300-400只ETF满足条件
```

### 3. 强制卖出不合格持仓

```python
# 如果持仓不在当前dynamic_pool中，强制卖出
for symbol in portfolio.positions:
    if symbol not in dynamic_pool:
        force_sell(symbol, reason='dynamic_pool_excluded')
```

## 性能验证

### 测试结果（2024-01-02）

使用平衡配置在真实数据上的测试结果：

```
Total ETFs scanned: 1749
ETFs passing filter: 597 (34.1%)

Sample passed symbols:
- 159501.SZ, 159503.SZ, 159506.SZ, ...
```

### 时间变化验证（2022-01-04 vs 2024-01-02）

```
2022-01-04: 164/1749 ETFs (9.4%)
2024-01-02: 597/1749 ETFs (34.1%)

差异: +433 ETFs
```

证明动态池随市场演进正确变化：
- 新上市ETF自动加入
- 流动性改善的ETF自动加入

## 性能注意事项

### 1. 数据加载时间

首次加载全量ETF数据（1700+ symbols）需要一定时间：
- 预计时间: 2-5分钟（取决于磁盘速度）
- 优化建议: 使用SSD存储数据目录

### 2. 动态过滤时间

每个调仓日的动态过滤：
- 预计时间: 5-10秒（已加载的数据中切片）
- 不影响回测速度（仅在rebalance day执行）

### 3. 内存使用

- 全量加载1700+ ETF: 约2-4 GB内存
- 推荐配置: 8GB+ 系统内存

## 与静态池对比

| 特性 | 静态池 (pool_file) | 动态池 (dynamic_pool) |
|------|-------------------|----------------------|
| 配置复杂度 | 需要预先筛选 | 仅需配置阈值 |
| 新上市ETF | 需要手动更新 | 自动纳入 |
| 退市ETF | 需要手动移除 | 自动移除 |
| 流动性变化 | 不响应 | 自动响应 |
| 回测真实性 | 略低（前视偏差） | 高（无前视偏差） |
| 性能 | 更快（小池子） | 略慢（大池子） |

## 常见问题

### Q1: 动态池大小是否稳定？

A: 动态池大小会随市场变化：
- 牛市/流动性充裕: 池子变大
- 熊市/流动性枯竭: 池子变小
- 这正是动态池的设计初衷

### Q2: 如何调整池子大小？

A: 调整 `liquidity_threshold` 参数：
- 池子太大(>800) → 提高阈值
- 池子太小(<200) → 降低阈值

### Q3: 动态池与rotation模式兼容吗？

A: 不兼容。两者都是"动态选择池子"的方案：
- `dynamic_pool=true` → 基于流动性过滤
- `rotation.enabled=true` → 基于预计算轮动表

只能选择其一。

### Q4: 性能影响如何？

A: 对回测速度影响很小：
- 动态过滤仅在rebalance day执行（如每5天一次）
- 主要时间消耗在数据加载（一次性）

## 技术实现细节

### 代码架构

1. **config_loader.py**:
   - 新增 `UniverseConfig.dynamic_pool` 配置项
   - 新增 `UniverseConfig.all_etf_data_dir` 配置项
   - 新增 `UniverseConfig.min_listing_days` 配置项

2. **data_loader.py**:
   - `scan_all_etfs()`: 扫描数据目录获取所有ETF
   - `filter_by_dynamic_liquidity()`: 动态流动性过滤

3. **portfolio_backtest_runner.py**:
   - `_load_data()`: 支持动态池模式加载
   - `_apply_dynamic_pool_filter()`: 每个rebalance日调用
   - `_eligible_symbols()`: 支持动态池参数

### 单元测试

运行测试验证功能：

```bash
# 运行所有动态池测试
python -m pytest etf_trend_following_v2/tests/test_dynamic_pool.py -v

# 运行功能测试（真实数据）
python etf_trend_following_v2/test_dynamic_pool_functional.py
```

## 参考资料

- [需求文档](/mnt/d/git/backtesting/requirement_docs/20251112_dynamic_pool_rotation_strategy.md)
- [CLAUDE.md](/mnt/d/git/backtesting/CLAUDE.md)
- [配置示例](/mnt/d/git/backtesting/etf_trend_following_v2/config/example_dynamic_pool_config.json)
