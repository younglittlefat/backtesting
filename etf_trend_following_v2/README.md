# ETF趋势跟踪系统 v2

基于绝对趋势信号与相对动量排名的ETF投资组合管理系统。

## 项目概述

本系统是ETF趋势跟踪策略的第二代实现，核心思想是：
- **绝对趋势信号**：使用技术指标（MACD/KAMA）判断ETF是否处于趋势状态
- **相对动量排名**：在趋势标的中选择动量最强的Top N进行投资
- **缓冲带机制**：减少频繁换仓，降低交易成本
- **风险管理**：ATR止损、时间止损、熔断保护、波动率倒数加权

### 核心特色

1. **多策略支持**
   - KAMA自适应均线（推荐，夏普1.69）
   - MACD交叉策略
   - 组合策略（MACD + KAMA共识）

2. **科学选股**
   - 多周期动量评分（20/60/120日）
   - 层次聚类去相关性
   - 缓冲带减少换仓频率

3. **完善风控**
   - 3倍ATR动态止损
   - 20日时间止损
   - 单日5%熔断保护
   - 波动率倒数加权仓位

4. **灵活配置**
   - JSON配置文件
   - 策略参数可调
   - 风控规则可定制

## 快速开始

### 1. 环境准备

```bash
# 激活conda环境
conda activate backtesting

# 确保在项目根目录
cd /mnt/d/git/backtesting

# 检查依赖（如未安装）
pip install -e '.[doc,test,dev]'
```

### 2. 配置文件设置

复制示例配置并根据需要修改：

```bash
cd etf_trend_following_v2
cp config/config.json config/my_config.json
# 编辑 my_config.json 根据需要调整参数
```

关键配置项说明：
- `strategy.type`: 选择策略类型（macd/kama/combo）
- `scoring.lookback_periods`: 动量评分周期
- `buffer.buy_top_n`: 买入前N名
- `buffer.hold_until_rank`: 持有至排名跌出此阈值
- `risk.atr_multiplier`: ATR止损倍数

### 3. 运行回测

```bash
# 使用默认配置运行回测
python backtest_runner.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2023-11-01 \
  --end-date 2025-11-30 \
  --output results/backtest_report.json

# 查看回测结果
cat results/backtest_report.json
```

### 4. 生成每日信号

```bash
# 生成今日信号（用于实盘）
python signal_pipeline.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --portfolio-file positions/my_portfolio.json \
  --output signals/signal_$(date +%Y%m%d).json

# 查看信号
cat signals/signal_$(date +%Y%m%d).json
```

## 核心概念

### 绝对趋势信号 + 相对动量排名

系统采用两阶段选股逻辑：

1. **第一阶段：趋势过滤**
   - 使用技术指标（MACD/KAMA）判断每只ETF是否处于上升趋势
   - 只有趋势信号为"看多"的标的才进入候选池

2. **第二阶段：动量排序**
   - 计算候选池中每只ETF的动量评分（多周期ROC加权）
   - 按评分排序，选择Top N买入

**为什么这样设计？**
- 趋势信号控制"何时能买"（风险控制）
- 动量排名决定"买哪个"（收益优化）
- 两者结合，既控制回撤又捕捉强势标的

### 缓冲带机制

传统策略每天都重新排名，可能导致频繁换仓：
```
Day 1: 持有 [A, B, C]，排名 A(1), B(2), C(3)
Day 2: D上涨到第3名，C跌到第4名 → 卖C买D → 交易成本
Day 3: C又涨回第3名，D跌到第4名 → 卖D买C → 又一次成本
```

**缓冲带解决方案**：
- 买入规则：只买排名前`buy_top_n`的标的（例如前10名）
- 持有规则：持仓标的只要排名不跌出`hold_until_rank`（例如前15名）就继续持有
- 效果：标的在10-15名之间波动时不触发交易，减少无效换仓

参数示例：
```json
{
  "buffer": {
    "buy_top_n": 10,          // 买入前10名
    "hold_until_rank": 15     // 持有至跌出前15名
  }
}
```

### ATR止损

**Average True Range (ATR)** 是衡量波动率的指标：
- 高波动标的ATR大 → 止损距离宽松
- 低波动标的ATR小 → 止损距离严格

**止损触发条件**：
```
当前价格 < 成本价 - (ATR × 倍数)
```

参数示例（3倍ATR）：
- 某ETF成本价10元，当前ATR=0.2元
- 止损价 = 10 - (0.2 × 3) = 9.4元
- 当价格跌破9.4元时触发止损

**优势**：
- 自适应：波动大的标的自动放宽止损
- 科学：基于统计特征而非固定百分比
- 灵活：通过`atr_multiplier`调整激进/保守程度

### 波动率倒数加权

**目标**：让高波动标的占用较少仓位，低波动标的占用较多仓位，实现组合风险均衡。

**计算步骤**：
1. 计算每只标的的ATR（波动率）
2. 取倒数作为初始权重：`weight = 1 / ATR`
3. 归一化权重和为1
4. 应用约束：
   - 单标的上限（如20%）
   - 总仓位上限（如100%）
   - 目标风险水平（如单标的风险0.5%）

**示例**：
```
标的A: ATR=0.3, weight=1/0.3=3.33
标的B: ATR=0.1, weight=1/0.1=10.0
归一化: A=25%, B=75%（B波动小，占比高）
```

参数示例：
```json
{
  "position_sizing": {
    "target_risk_per_position": 0.005,  // 单标的目标风险0.5%
    "max_position_size": 0.20,          // 单标的上限20%
    "max_total_exposure": 1.0           // 总仓位上限100%
  }
}
```

### 层次聚类

**问题**：动量Top 10可能包含高度相关的标的（如多只券商ETF），降低分散效果。

**层次聚类方案**：
1. 计算候选标的的价格相关性矩阵
2. 使用层次聚类算法将相似标的分组
3. 每个簇最多选择N只（如2只）
4. 优先选择簇内动量最高的标的

**效果**：
- 自动识别相关性强的标的（如券商、地产、科技板块）
- 强制分散到不同板块
- 在保持动量优势的同时提升组合分散度

参数示例：
```json
{
  "clustering": {
    "correlation_threshold": 0.5,  // 相关性>0.5视为同一簇
    "max_per_cluster": 2           // 每簇最多2只
  }
}
```

## 目录结构

```
etf_trend_following_v2/
├── README.md                    # 本文档
├── config/
│   └── config.json             # 示例配置文件
├── strategies/
│   ├── __init__.py
│   ├── macd.py                 # MACD策略信号生成器
│   ├── kama.py                 # KAMA策略信号生成器
│   └── combo.py                # 组合策略（MACD + KAMA共识）
├── config_loader.py            # 配置加载和验证
├── data_loader.py              # OHLCV数据加载
├── scoring.py                  # 动量评分和缓冲带
├── clustering.py               # 层次聚类去相关性
├── position_sizing.py          # 波动率倒数加权仓位计算
├── risk.py                     # ATR止损、时间止损、熔断
├── portfolio.py                # 持仓管理（更新成本、收益等）
├── signal_pipeline.py          # 信号生成主流程
├── backtest_runner.py          # 回测引擎
└── io_utils.py                 # JSON读写、持仓序列化
```

## 配置说明

完整配置文件结构（见 `config/config.json`）：

```json
{
  "strategy": {
    "type": "kama",              // 策略类型: macd/kama/combo
    "kama": {...},               // KAMA参数
    "macd": {...}                // MACD参数
  },
  "scoring": {
    "lookback_periods": [20, 60, 120],  // 动量评分周期
    "weights": [0.4, 0.3, 0.3]         // 周期权重
  },
  "buffer": {
    "buy_top_n": 10,             // 买入前N名
    "hold_until_rank": 15        // 持有至跌出此排名
  },
  "clustering": {
    "enabled": true,
    "correlation_threshold": 0.5,
    "max_per_cluster": 2
  },
  "position_sizing": {
    "method": "inverse_volatility",
    "target_risk_per_position": 0.005,
    "max_position_size": 0.20,
    "max_total_exposure": 1.0
  },
  "risk": {
    "atr_period": 14,
    "atr_multiplier": 3.0,
    "time_stop_days": 20,
    "circuit_breaker_threshold": 0.05
  }
}
```

### 关键参数调优建议

| 参数 | 保守 | 中性（推荐） | 激进 | 说明 |
|------|------|-------------|------|------|
| `buy_top_n` | 5 | 10 | 15 | 持仓数量 |
| `hold_until_rank` | 8 | 15 | 20 | 缓冲带宽度 |
| `atr_multiplier` | 2.0 | 3.0 | 4.0 | 止损距离 |
| `max_position_size` | 0.15 | 0.20 | 0.25 | 单标的上限 |
| `correlation_threshold` | 0.4 | 0.5 | 0.6 | 聚类敏感度 |

## 使用示例

### 回测命令

```bash
# 基础回测
python backtest_runner.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2023-11-01 \
  --end-date 2025-11-30 \
  --output results/backtest_report.json

# 使用MACD策略回测
python backtest_runner.py \
  --config config/config_macd.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output results/macd_backtest.json

# 比较不同缓冲带参数
for buy_n in 5 10 15; do
  for hold_rank in 10 15 20; do
    # 修改配置文件中的参数
    # 运行回测
    # 保存结果
  done
done
```

### 信号生成命令

```bash
# 生成今日信号（实盘使用）
python signal_pipeline.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --portfolio-file positions/my_portfolio.json \
  --output signals/signal_$(date +%Y%m%d).json

# 查看买入信号
cat signals/signal_$(date +%Y%m%d).json | jq '.buy'

# 查看卖出信号
cat signals/signal_$(date +%Y%m%d).json | jq '.sell'

# 查看持仓状态
cat positions/my_portfolio.json | jq '.positions'
```

### Python API 使用

```python
from config_loader import load_config
from data_loader import DataLoader
from signal_pipeline import SignalPipeline
from portfolio import Portfolio

# 加载配置
config = load_config('config/config.json')

# 初始化数据加载器
data_loader = DataLoader('../data/chinese_etf/daily')
etf_pool = ['510300.SH', '510500.SH', '159915.SZ']  # 示例ETF池

# 加载数据
data_dict = data_loader.load_multiple(etf_pool, start_date='2024-01-01')

# 初始化投资组合
portfolio = Portfolio.load('positions/my_portfolio.json')

# 初始化信号管线
pipeline = SignalPipeline(config, data_loader)

# 生成信号
signals = pipeline.generate_signals(
    etf_pool=etf_pool,
    current_date='2024-12-11',
    portfolio=portfolio
)

# 处理信号
print(f"买入: {signals['buy']}")
print(f"卖出: {signals['sell']}")
print(f"持有: {signals['hold']}")

# 保存更新的投资组合
portfolio.save('positions/my_portfolio.json')
```

## 策略选择指南

### MACD vs KAMA vs Combo

| 策略 | 优势 | 劣势 | 适用场景 | 推荐指数 |
|------|------|------|----------|----------|
| **KAMA** | 夏普1.69，自适应，信号质量高 | 参数较多 | 通用，强推荐 | ⭐⭐⭐⭐⭐ |
| **MACD** | 经典，直观，参数少 | 夏普0.94，震荡市假信号多 | 趋势明显的市场 | ⭐⭐⭐ |
| **Combo** | 高置信度，假信号少 | 信号较少，可能错过机会 | 保守投资者 | ⭐⭐⭐⭐ |

### 参数建议

#### KAMA策略（推荐）
```json
{
  "strategy": {
    "type": "kama",
    "kama": {
      "period": 20,
      "fast_sc": 2,
      "slow_sc": 30,
      "lookback": 3
    }
  }
}
```

**调参建议**：
- `period`: 趋势周期，建议10-30，默认20
- `fast_sc`: 快速平滑常数，建议2-5，默认2
- `slow_sc`: 慢速平滑常数，建议20-40，默认30
- `lookback`: 信号确认周期，建议1-5，默认3

#### MACD策略
```json
{
  "strategy": {
    "type": "macd",
    "macd": {
      "fast_period": 12,
      "slow_period": 26,
      "signal_period": 9
    }
  }
}
```

**调参建议**：
- 经典参数（12/26/9）适用大多数市场
- 快速响应：8/17/9
- 平滑信号：19/39/9

#### 组合策略
```json
{
  "strategy": {
    "type": "combo",
    "kama": {...},  // 使用KAMA默认参数
    "macd": {...}   // 使用MACD默认参数
  }
}
```

**特点**：只有KAMA和MACD同时看多才产生买入信号，信号少但质量高。

## FAQ / 故障排除

### Q1: 回测报错 "KeyError: '510300.SH'"
**原因**：数据目录中缺少该ETF的数据文件。

**解决方案**：
```bash
# 检查数据文件是否存在
ls ../data/chinese_etf/daily/510300.SH.csv

# 如果缺失，使用数据获取脚本下载
python ../scripts/fetch_etf_data.py --code 510300.SH
```

### Q2: 信号生成为空
**可能原因**：
1. 所有ETF都没有趋势信号（市场整体弱势）
2. 数据未更新到最新日期
3. 配置参数过于严格

**排查步骤**：
```bash
# 检查最新数据日期
python -c "
from data_loader import DataLoader
dl = DataLoader('../data/chinese_etf/daily')
df = dl.load_single('510300.SH')
print(df.index[-1])
"

# 检查有多少标的有趋势信号
python signal_pipeline.py --config config/config.json --debug
```

### Q3: 内存不足
**原因**：加载大量ETF的历史数据占用内存过多。

**解决方案**：
```python
# 在 data_loader.py 中限制数据时间范围
data_dict = data_loader.load_multiple(
    etf_pool,
    start_date='2024-01-01',  # 只加载最近一年
    end_date='2024-12-31'
)
```

### Q4: ATR止损过于频繁
**原因**：`atr_multiplier`设置过小，或市场波动剧烈。

**解决方案**：
```json
{
  "risk": {
    "atr_multiplier": 4.0  // 从3.0放宽到4.0
  }
}
```

### Q5: 层次聚类后持仓数量不足
**原因**：`max_per_cluster`设置过小，或ETF池本身相关性太高。

**解决方案**：
1. 增加`max_per_cluster`：
```json
{
  "clustering": {
    "max_per_cluster": 3  // 从2增加到3
  }
}
```

2. 或者放宽相关性阈值：
```json
{
  "clustering": {
    "correlation_threshold": 0.6  // 从0.5放宽到0.6
  }
}
```

3. 或者禁用聚类：
```json
{
  "clustering": {
    "enabled": false
  }
}
```

### Q6: 如何验证配置文件正确性？
```bash
# 使用配置加载器的验证功能
python -c "
from config_loader import load_config
config = load_config('config/my_config.json')
print('配置加载成功！')
print(f'策略类型: {config[\"strategy\"][\"type\"]}')
print(f'买入前N名: {config[\"buffer\"][\"buy_top_n\"]}')
"
```

### Q7: 回测结果与预期差异大
**可能原因**：
1. 数据质量问题（复权因子错误、缺失值）
2. 交易成本未考虑
3. 策略参数不匹配历史实验

**排查步骤**：
1. 检查数据质量：
```python
df = data_loader.load_single('510300.SH')
print(df.isnull().sum())  # 检查缺失值
print(df['Close'].describe())  # 检查异常值
```

2. 添加交易成本（在backtest_runner.py中添加滑点和手续费）

3. 对比配置文件与需求文档中的推荐参数

## 进一步阅读

- **需求文档**: `/mnt/d/git/backtesting/requirement_docs/20251211_etf_trend_following_v2_requirement.md`
- **KAMA策略实验**: `/mnt/d/git/backtesting/experiment/etf/kama_cross/hyperparameter_search/`
- **MACD策略实验**: `/mnt/d/git/backtesting/experiment/etf/macd_cross/grid_search_stop_loss/`
- **ETF筛选系统**: `/mnt/d/git/backtesting/etf_selector/`

## 贡献与反馈

如有问题或建议，请在项目Issue中提交。

## 许可证

与主项目 `backtesting.py` 保持一致。
