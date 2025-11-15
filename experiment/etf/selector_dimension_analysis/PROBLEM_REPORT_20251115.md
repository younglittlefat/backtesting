# ETF 单维度筛选实验重跑问题总结（2025-11-15）

本文汇总了在降低流动性门槛（5万元）后，对 `experiment/etf/selector_dimension_analysis` 实验重跑所暴露的问题与根因，并给出修复建议与验证步骤。

## 结论概览
- 维度筛选阶段仍未产出任何有效 ETF 池，所有维度被判定为空，回测阶段全部跳过；分析报告显示“Empty selection”。
- 核心阻塞来自代码与 `etf_selector` 模块接口/函数签名不匹配：
  - 使用了不存在的数据加载接口 `ETFDataLoader.load_etf_data`；
  - 指标函数参数传递错误（ADX/动量/波动率/无偏指标均应传 Series 而非整表 DataFrame）；
  - 综合评分路径将 `run_pipeline()` 的 List[Dict] 返回值当作 DataFrame 使用。
- 降低流动性阈值后，第一级筛选已能通过约 376 只 ETF，说明数据面无系统性短板，问题集中在单维度计算与综合路径的实现缺陷。

## 日志与现象
- 第一批（流动性阈值过严，历史问题，已知）
  - 所有维度为空，回测 0/7 成功  
    - experiment/etf/selector_dimension_analysis/experiment_execution.log:299
    - experiment/etf/selector_dimension_analysis/experiment_execution_v2.log:19

- 降低阈值后（当前关注）
  - 第一级筛选通过数约 376 只（阈值 5万元；上市≥180 天）：  
    - experiment/etf/selector_dimension_analysis/experiment_final.log:774-776, 872-875
  - 单维度路径报错 “string indices must be integers”（列表元素被当作字典使用）：  
    - adx_mean: experiment/etf/selector_dimension_analysis/experiment_final.log:779  
    - trend_consistency: experiment/etf/selector_dimension_analysis/experiment_final.log:795  
    - price_efficiency: experiment/etf/selector_dimension_analysis/experiment_final.log:811  
    - liquidity_score: experiment/etf/selector_dimension_analysis/experiment_final.log:827  
    - momentum_3m: experiment/etf/selector_dimension_analysis/experiment_final.log:843  
    - momentum_12m: experiment/etf/selector_dimension_analysis/experiment_final.log:859
  - 综合评分路径报错 “list indices must be integers or slices, not str”（将 list 当 DataFrame 用）：  
    - experiment/etf/selector_dimension_analysis/experiment_final.log:1565
  - 另一轮重跑明确暴露错误接口调用：`'ETFDataLoader' object has no attribute 'load_etf_data'`（指标计算阶段全量失败，成功计算 0 只）：  
    - experiment/etf/selector_dimension_analysis/experiment_success.log:28-82（多行类似报错）
    - 各维度汇总：“成功计算0只ETF的...指标”：experiment/etf/selector_dimension_analysis/experiment_success.log:411, 812, 1213, 1614, 2015
  - 结果产物侧证据：筛选统计均为 0；对比分析为“Empty selection”  
    - experiment/etf/selector_dimension_analysis/results/selection_stats.csv  
    - experiment/etf/selector_dimension_analysis/results/analysis/dimension_comparison_*.csv
  - 数据层面额外提示（非阻塞）：收益率矩阵存在重复日期索引，已自动去重（PortfolioOptimizer 内部处理，非根因）  
    - 多处告警源于 etf_selector/portfolio.py:94

## 根因定位（按严重度排序）
1) 错误的数据加载接口（P0）  
   - 现状：调用 `self.data_loader.load_etf_data(ts_code)`，该方法不存在。  
   - 证据：experiment/etf/selector_dimension_analysis/experiment_success.log:28 起多行“no attribute 'load_etf_data'”。  
   - 代码位置：experiment/etf/selector_dimension_analysis/single_dimension_selector.py:227
   - 正确接口：`ETFDataLoader.load_etf_daily(ts_code, start_date=None, end_date=None, use_adj=True)`

2) 指标函数参数签名不匹配（P0）  
   - ADX/动量/波动率/无偏指标应传入 Series，而非整表 DataFrame：
     - ADX 期望 `(high: Series, low: Series, close: Series)`  
       - etf_selector/indicators.py:12-44
     - 波动率期望 `returns: Series`（日收益率序列）  
       - etf_selector/indicators.py:47-80
     - 动量期望 `close: Series`  
       - etf_selector/indicators.py:83-121
     - 无偏指标期望 `close/volume: Series`  
       - etf_selector/unbiased_indicators.py:18-58, 188-236
   - 现状代码直接传 `data`（DataFrame），或动量/波动率未先构造 `adj_close` 的收益率序列。  
   - 代码位置（示例）：  
     - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:240（ADX 传参错误）  
     - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:259-263（动量返回结构与当前实现不匹配）  
     - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:265-268（波动率传参错误）
   - 直接后果：单维度指标列表构建失败，触发 “string indices must be integers”等类型错误，最终各维度为空。

3) 综合评分路径返回类型误用（P0）  
   - `TrendETFSelector.run_pipeline()` 返回的是 `List[Dict]`（而非 DataFrame）。  
   - 现状代码将 `results` 当作 DataFrame 索引赋值（`results['dimension'] = ...`），导致 `list indices must be integers or slices, not str`。  
   - 代码位置：experiment/etf/selector_dimension_analysis/single_dimension_selector.py:128-136

4)（信息性）重复日期索引告警（P2）  
   - 多只 ETF 的收益率序列存在重复日期索引，`PortfolioOptimizer` 已做去重，不阻塞流程：  
     - etf_selector/portfolio.py:94
   - 建议保留日志但降噪，不作为当前阻塞修复项。

## 修复建议
以下修改集中在 `experiment/etf/selector_dimension_analysis/single_dimension_selector.py`：

1) 正确加载数据并使用复权列
- 将 `load_etf_data` 改为 `load_etf_daily`，启用复权价格：
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:227
  - 修改为：`data = self.data_loader.load_etf_daily(ts_code, use_adj=True)`

2) 指标计算按函数签名传入 Series
- ADX：使用 `adj_high/adj_low/adj_close`，建议复用 `calculate_rolling_adx_mean` 的思路或保持现有 `calculate_adx` + 均值：
  - 将 240 行替换为：  
    - `adx_values = calculate_adx(data['adj_high'], data['adj_low'], data['adj_close'], period=self.config.adx_period)`  
    - `metrics['adx_mean'] = float(pd.Series(adx_values).tail(self.config.adx_lookback_days).mean())`
- 趋势一致性/价格效率/流动性评分：传入正确的 Series 顺序：  
  - trend_consistency: `calculate_trend_consistency(data['adj_close'], window=...)`（single_dimension_selector.py:245-247）  
  - price_efficiency: `calculate_price_efficiency(data['adj_close'], data['volume'], window=...)`（single_dimension_selector.py:249-252）  
  - liquidity_score: `calculate_liquidity_score(data['volume'], data['adj_close'], window=...)`（single_dimension_selector.py:254-257）
- 动量：传入 `adj_close`，并使用当前实现的返回键：  
  - single_dimension_selector.py:259-263, 277-281  
  - 建议：  
    - `mom = calculate_momentum(data['adj_close'], self.config.momentum_periods)`  
    - `metrics['momentum_3m'] = mom.get('63d')`  
    - `metrics['momentum_12m'] = mom.get('252d')`
- 波动率：先构造收益率再计算：  
  - single_dimension_selector.py:265-268  
  - 建议：  
    - `rets = data['adj_close'].pct_change().dropna()`  
    - `vol = calculate_volatility(rets, window=self.config.volatility_lookback_days)`  
    - `metrics['volatility'] = vol`

3) 综合评分路径将 List 转为 DataFrame 再附加列
- single_dimension_selector.py:128-136  
  - 建议修改为：  
    - `results_list = standard_selector.run_pipeline()`  
    - `results = pd.DataFrame(results_list)`  
    - `results['dimension'] = 'comprehensive'`  
    - `if 'final_score' in results.columns: results['dimension_value'] = results['final_score']`  
      `else: results['dimension_value'] = np.nan`

4) 保持本实验的二级“范围过滤”开关一致性
- 当前实验构造中 `skip_stage2_range_filtering=False`，意味着会执行波动率/动量范围过滤；在指标计算修复前提下该设置可保留。若后续仍显著收缩样本，可临时置 `True` 以验证总体链路，再回归合理阈值。

## 验证步骤（修复后）
1) 运行单维度小样本自检（确保指标产出非空）
   - `python experiment/etf/selector_dimension_analysis/single_dimension_selector.py`  
   - 期望：各维度“成功计算X只ETF的...指标”且 TopN 输出非空。
2) 批量实验复跑
   - `python experiment/etf/selector_dimension_analysis/dimension_analysis.py`  
   - 期望：`results/stock_lists/` 下生成 `dimension_*_etf_pool.csv`（7 个）；回测阶段至少 1/7 成功；`analysis/` 生成维度对比表。
3) 快速健康度检查
   - 查看 `results/selection_stats.csv` 各维度 `count>0`；检查 `experiment.log` 中不再出现上述三类报错。

## 相关代码与文件引用
- 错误接口与传参与类型误用：
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:227  
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:240  
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:259  
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:265  
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:271  
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:277
- 综合评分路径返回类型误用：
  - experiment/etf/selector_dimension_analysis/single_dimension_selector.py:128
- 正确的指标函数签名：
  - etf_selector/indicators.py:12  
  - etf_selector/indicators.py:47  
  - etf_selector/indicators.py:83
  - etf_selector/unbiased_indicators.py:18  
  - etf_selector/unbiased_indicators.py:188
- 日志证据：
  - experiment/etf/selector_dimension_analysis/experiment_final.log:774  
  - experiment/etf/selector_dimension_analysis/experiment_final.log:779  
  - experiment/etf/selector_dimension_analysis/experiment_final.log:1565  
  - experiment/etf/selector_dimension_analysis/experiment_success.log:28  
  - experiment/etf/selector_dimension_analysis/results/selection_stats.csv

## 备注
- 重复日期索引的告警已在组合优化中自动去重（非阻塞）；若后续需要降噪，可在 `PortfolioOptimizer.calculate_returns_matrix` 中将该告警降为 `INFO` 或按样本规模间隔性打印。
- 回测阶段目前 0/7，系于筛选产出为空导致；待筛选修复后再评估回测链路（含结果解析字段命名与列对齐）。

