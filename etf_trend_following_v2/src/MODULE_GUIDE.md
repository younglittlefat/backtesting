# 模块与 API 导航

面向开发/维护的精简版入口，详细参数以源码 docstring 与测试为准。

## 配置与数据
- **config_loader.py**：加载/校验层级化 `config.json`，返回 dataclass；支持默认值与交叉校验。  
- **data_loader.py**：单标/多标加载、日期过滤、流动性过滤、数据质量验证，支持调整后价格。  

## 策略信号
- **strategies/**：独立信号生成器（MACD/KAMA/Combo），可选 ADX/成交量/斜率/确认/零轴/迟滞等过滤。  
- **backtest_wrappers.py**：将信号封装为 `backtesting.py` Strategy，复用撮合与指标。  

## 评分与排序
- **scoring.py**：多周期波动率归一的动量得分；惯性加分；买入 Top N / 持有至 Rank M 迟滞；历史滚动得分以避免前视。主要入口：  
  - `calculate_universe_scores`、`apply_inertia_bonus`、`get_trading_signals`、`calculate_historical_scores`。  

## 聚类与分散
- **clustering.py**：相关性→距离→层次聚类；簇内竞争（风险调整动量）；每簇持仓上限与替换逻辑。主要入口：  
  - `get_cluster_assignments`、`filter_by_cluster_limit`、`calculate_risk_adjusted_momentum`。  

## 仓位管理
- **position_sizing.py**：波动率倒数加权，支持 STD/EWMA；单标/簇/总仓位上限；A 股 100 股/手取整；调仓指令生成。  

## 风控
- **risk.py**：ATR（SMA/EMA/Wilder）跟踪止损、时间止损、熔断（市场/账户）、流动性检查、T+1 校验；`RiskManager` 汇总接口。  

## 组合与持仓
- **portfolio.py**：Position/TradeOrder/Portfolio 三类；生成调仓指令、执行订单（成本/印花税/T+1），权益与持仓摘要、快照持久化。  

## 管线与回测
- **signal_pipeline.py**：日常信号管线（加载→聚类→信号→评分→风控→仓位→订单）；入口 `run_daily_signal`。  
- **backtest_runner.py**：基于 `backtesting.Backtest` 的回测执行与结果聚合。  

## I/O 工具
- **io_utils.py**：日志配置、信号/持仓/订单读写（CSV/JSON）、绩效报告生成、路径工具与数据/配置校验。  

## 示例与测试
- 示例脚本：`etf_trend_following_v2/examples/`（与模块同名示例）。  
- 单测：`etf_trend_following_v2/tests/`（与模块同名文件）可作为用法参考。  

## 贡献建议
- 新增模块的文档放在本文件对应小节，保持一句话定位 + 主要入口函数。  
- 详尽流程/示例请更新 `README.md` 的“快速上手”或补充 tests/examples，而非新增平行 README。  
