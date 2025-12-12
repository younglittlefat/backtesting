# 状态与测试快照

## 总体状态
- 一期/二期需求已完成功能：MACD、KAMA、Combo 信号；评分/聚类/仓位/风控/持仓；回测包装；信号管线与 I/O。  
- 与 `backtesting.py` 结果对齐（baseline 偏差 0.00%，详见验收报告）。  
- 依赖：Python 3.9+；需要 pandas/numpy/scipy 等科学计算包。  

## 模块测试摘要
- **config_loader**：47 个测试通过（配置校验/序列化）。  
- **data_loader**：覆盖数据质量/流动性过滤（见 `tests/test_data_loader.py`）。  
- **strategies / backtest_wrappers**：MACD/KAMA/Combo 包装器 48 个测试通过。  
- **scoring**：13 个测试通过（动量、惯性、迟滞、历史得分）。  
- **clustering**：20 个测试通过（相关性、聚类、簇过滤、风险调整动量）。  
- **position_sizing**：核心函数单测，含取整/上限（见 `tests/test_position_sizing.py`）。  
- **risk**：36 个测试通过（ATR、时间止损、熔断、流动性、T+1）。  
- **portfolio**：20 个测试通过（订单生成/执行、成本、T+1、防误卖）。  
- **io_utils**：23 个测试通过（信号/持仓/订单/报告/日志/校验）。  
- **backtest_runner**：33 个测试通过（单标/多标回测、聚合统计、报告生成）。  

> 详细执行与日志可用 `python -m pytest etf_trend_following_v2/tests -v`。

## 已知问题 / 风险提示
- **ADX 过滤器（旧策略）**：`strategies/macd_cross.py` 中 ADX 未生效；v2 包装器实现正确。  
- **Combo 策略简化**：当前组合逻辑为简化版，未覆盖所有子账户合并细节。  
- **组合级回测缺口**：backtesting 包装器按单标运行，TopN/簇限额/波动率权重在信号端实现；如需组合级回测需额外设计。  

## 参考文档
- 需求：`requirement_docs/20251211_etf_trend_following_v2_requirement.md`  
- 验收报告：`etf_trend_following_v2/PHASE2_ACCEPTANCE_REPORT.md`  
- 诊断：`etf_trend_following_v2/tests/ADX_FILTER_ROOT_CAUSE_ANALYSIS.md`（ADX 问题）  

## 维护建议
- 版本对齐：新增功能先更新配置与模块注释，再补测试，用本文件刷新状态。  
- 兼容性：保持 `backtesting.py` 复用，避免自建撮合回归。  
- 路径：统一使用 POSIX 路径（WSL 环境），确保快照/报告路径可配置。  
