# ETF 趋势跟踪 v2 文档总览

## 适用范围
- 面向 `etf_trend_following_v2` 整体（回测、信号生成、持仓管理）。
- 需求基准：`requirement_docs/20251211_etf_trend_following_v2_requirement.md`。
- 目标：在不修改原框架的前提下，提供独立可配置的 ETF 趋势跟踪与风控链路。

## 系统流程（T+1 假设）
1) **全池扫描**：按配置加载池、清洗数据、可选流动性过滤。  
2) **策略信号**：MACD、KAMA 或 Combo 生成买/卖/持信号，可选 ADX/成交量/斜率等过滤。  
3) **动量评分与缓冲**：多周期波动率归一的动量得分 → 惯性加分 → 迟滞区间（买入 Top N，持有至 Rank M）。  
4) **聚类与分散**：相关性聚类，限制每簇持仓数量/权重。  
5) **仓位与风控**：波动率倒数加权 + 单标/簇/总仓位上限；ATR 跟踪止损、时间止损、熔断、流动性检查。  
6) **持仓与成交**：遵守 T+1，生成/执行交易指令，记录成本与滑点假设。  
7) **输出**：信号、订单、持仓快照、绩效报表与日志。

## 配置结构（缩略版）
- `env`：路径、时区、交易日历。  
- `modes`：运行模式（backtest/signal/live-dryrun）、日期、回看窗口。  
- `universe`：标的池文件/列表、流动性阈值、黑名单。  
- `strategies`：`macd` / `kama` / `combo` 及其过滤开关、核心参数。  
- `scoring`：动量周期与权重、买入/持有阈值、惯性加分、调仓频率。  
- `clustering`：相关性窗口、距离阈值、每簇上限、更新频率。  
- `risk`：ATR/时间止损、熔断、流动性、T+1。  
- `position_sizing`：波动率估计法、单标/簇/总仓位上限、最小现金保留。  
- `execution`：撮合假设、下单时间、滑点/手续费。  
- `io`：信号/持仓/报告/日志路径与格式。

## 快速上手
### 回测（示例）
```python
from etf_trend_following_v2.src.config_loader import load_config
from etf_trend_following_v2.src.backtest_runner import BacktestRunner

config = load_config("etf_trend_following_v2/config/example_config.json")
runner = BacktestRunner(config)
stats = runner.run(
    start_date="2023-01-01",
    end_date="2024-12-31",
    initial_capital=1_000_000
)
runner.generate_report(output_dir="results/")
```

### 日常信号（示例）
```python
from etf_trend_following_v2.src.signal_pipeline import run_daily_signal

result = run_daily_signal(
    config_path="etf_trend_following_v2/config/example_config.json",
    as_of_date="2025-12-11",
    portfolio_snapshot="results/portfolio_latest.json",
    market_data_path="data/index/000300.SH.csv",
    output_dir="results/signals",
    dry_run=False
)
```
输出包含：`signals_{date}.csv`、`orders_{date}.csv`、`portfolio_{date}.json`、`scores_{date}.csv`。

### 常用路径
- 示例配置：`etf_trend_following_v2/config/example_config.json`
- 数据默认：`data/chinese_etf/daily`
- 报告与快照：`results/`（可在配置中覆盖）

## 关键约束与默认值
- **复用 backtesting.py**：回测通过 Strategy 包装器，避免自建撮合偏差。
- **多头/T+1**：默认 long-only，买入当日不可卖出；次日止损优先。  
- **风控优先级**：ATR/时间止损 > 熔断 > 排名劣汰/缓冲。  
- **分散度**：默认每簇最多 2 个标的，单标/总仓位上限可配。  
- **滑点与费用**：从配置读取，默认收盘或次日开盘撮合。

## 文档索引
- 模块/API 速览：`MODULE_GUIDE.md`
- 状态与测试：`STATUS_TESTING.md`
- 需求全文：`requirement_docs/20251211_etf_trend_following_v2_requirement.md`
