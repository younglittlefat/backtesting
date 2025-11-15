# 趋势ETF筛选系统（精简版）

创建日期: 2025-11-06  
最后更新: 2025-11-15  
项目: Backtesting.py 趋势标的筛选

---

## 1. 目标与方法
- 目标：从全市场ETF中筛出适合趋势跟踪的标的池，用于后续回测与实盘轮换。
- 方法：三级漏斗，默认以“无偏评分”替代基于收益的阈值筛选，最后做去重与分散。
```
[全量ETF]
  → 初级筛选（流动性、上市天数）
    → 核心筛选（无偏评分：ADX/趋势一致性/价格效率/流动性 + 动量低权重）
      → 组合优化（智能去重 + 低相关性贪心 + 行业平衡）
        → [目标池 10-30只]
```
- 统一原则：以命令行 CLI 参数为“单一事实来源”（source of truth）。

---

## 2. 实现要点（与代码对齐）

说明仅保留关键事实与入口，详细推导与阶段性过程已删除。代码锚点用于溯源。

- 入口与默认
  - CLI 入口：`etf_selector/main.py`（默认参数以此为准） etf_selector/main.py:90
  - 核心流程：`TrendETFSelector.run_pipeline()` etf_selector/selector.py:120
  - 组合优化：`PortfolioOptimizer.optimize_portfolio()` etf_selector/portfolio.py:392

### 2.1 第一级：初级筛选
- 条件：最小日均成交额、最小上市天数；数据源为 CSV（basic_info + daily/etf）
- 默认（以 CLI 为准）：
  - `--min-turnover` 默认 1e8 元 etf_selector/main.py:90
  - `--min-listing-days` 默认 180 天 etf_selector/main.py:94
- 说明：`FilterConfig` 与一体化脚本存在不同默认值（见 5. TODO），已决定以 CLI 为准。

实现锚点：
- 初筛实现：`_stage1_basic_filter()`（加载basic_info、rolling成交额均值） etf_selector/selector.py:145
- 成交额计算：`ETFDataLoader.calculate_avg_turnover()` etf_selector/data_loader.py:194

### 2.2 第二级：核心筛选（无偏评分为默认主线）
- 计算指标：
  - ADX 均值（滚动窗口） etf_selector/indicators.py:140
  - 波动率（年化，基于日收益率std） etf_selector/indicators.py:73
  - 动量（3M/12M） etf_selector/indicators.py:105
  - 无偏指标：趋势一致性、价格效率、流动性评分 etf_selector/unbiased_indicators.py:18
- 默认行为（重要）：
  - 跳过“百分位阈值筛选”（ADX/收益回撤比），改为评分排序 etf_selector/selector.py:367
  - 启用“无偏评分系统”，主要指标占 80%，动量仅 20% etf_selector/selector.py:392, etf_selector/scoring.py:18
  - 双均线回测过滤默认禁用（避免引入收益偏差） etf_selector/config.py:25
  - 波动率/动量“区间过滤”默认跳过（专注排序，不做硬阈值） etf_selector/config.py:36
- 可选开关（按需启用）：
  - 启用双均线过滤：`--enable-ma-filter`（将引入收益相关偏差，谨慎） etf_selector/main.py:109
  - 启用第二级“百分位阈值筛选”：当前 CLI 未暴露“取消跳过”的开关（默认跳过），如需启用，请用配置文件将 `skip_stage2_percentile_filtering=False`。
  - 启用“区间过滤”（波动率、动量>0）：当前 CLI 未暴露，需配置文件设置 `skip_stage2_range_filtering=False`。

实现锚点：
- 第二级主流程：`_stage2_trend_filter()`（指标计算→评分排序） etf_selector/selector.py:207
- 综合评分：`UnbiasedScorer` / `calculate_etf_scores()` etf_selector/scoring.py:54

### 2.3 第三级：组合优化
- 目标：去重相近ETF、控制平均相关性、保持行业分散。
- 规则：
  - 智能去重：相关性阈值自 0.98 → 0.95 → 0.92 → 0.90 逐步放宽 etf_selector/portfolio.py:198
  - 低相关性组合：`max_correlation` 默认 0.7（CLI 参数在选择器内透传） etf_selector/portfolio.py:392
  - 贪心选择并保留原排序偏好，行业均衡作为后处理 etf_selector/portfolio.py:468, etf_selector/portfolio.py:476

实现锚点：
- 收益率/相关矩阵：`calculate_returns_matrix()` / `calculate_correlation_matrix()` etf_selector/portfolio.py:48
- 去重与分散：`adaptive_deduplication()` / `_greedy_selection()` / `_balance_industries()` etf_selector/portfolio.py:166, etf_selector/portfolio.py:505
- 导出：`export_results()`（CSV） etf_selector/selector.py:452

---

## 3. 使用方式

最小可用（默认参数，评分主线）
```bash
python -m etf_selector.main \
  --target-size 20 \
  --output results/trend_etf_pool_$(date +%Y%m%d).csv \
  --with-analysis
```

联动回测（注意数据目录差异）
```bash
# 筛选器使用 data/csv
python -m etf_selector.main --output results/trend_etf_pool_$(date +%Y%m%d).csv

# 回测脚本使用 data/csv/daily（需包含etf子目录数据）
./run_backtest.sh \
  --stock-list results/trend_etf_pool_20251107.csv \
  --strategy sma_cross \
  --data-dir data/csv/daily
```

导出CSV字段（最小约定）
- 必需：`ts_code`, `name`
- 常见分析字段：`industry`, `adx_mean`, `volatility`, `momentum_3m`, `trend_consistency`, `price_efficiency`, `liquidity_score`, `final_score`, `stage2_rank`

---

## 4. 参数食谱（CLI 优先）

- 平衡（推荐，适配中国市场成交额分布）
```bash
python -m etf_selector.main \
  --target-size 20 \
  --min-turnover 500000 \
  --max-correlation 0.7 \
  --with-analysis
```
要点：维持“无偏评分”默认；仅适度下调成交额阈值以保留可交易样本。

- 探索（更多候选，后续由第三级去重/分散约束）
```bash
python -m etf_selector.main \
  --target-size 30 \
  --min-turnover 100000 \
  --max-correlation 0.7
```
要点：放宽流动性以扩大候选，保持相关性约束；不引入收益相关过滤。

- 可选（启用双均线过滤，可能引入偏差）
```bash
python -m etf_selector.main \
  --target-size 20 \
  --min-turnover 500000 \
  --enable-ma-filter
```
要点：将产生`return_dd_ratio`并按收益回撤比排序；不再是“无偏评分”主线，谨慎用于验证。

---

## 5. TODO（精简版）
- 统一默认参数源到 CLI
  - 对齐 `FilterConfig` 与一体化脚本：`min_turnover` 等默认值（建议采用 CLI 值）  
    - etf_selector/main.py:90（1e8）  
    - etf_selector/config.py:13（5万）  
    - run_selector_backtest.py:97（5千万）
- CLI 参数补齐
  - 暴露“取消跳过第二级阈值筛选”的开关（当前仅支持“跳过”的选项） etf_selector/selector.py:367
  - 暴露“区间过滤开关”（波动率、动量>0） etf_selector/config.py:36
- 输出与自检
  - 固定导出字段顺序与含义注释；新增轻量一致性校验（字段/数量/日期范围）
- 行业分类配置化
  - 从关键词匹配升级为可配置映射（YAML/JSON），保留默认回退 etf_selector/config.py:75
- 稳定性与回归
  - 去重与相关矩阵的降级路径用例（缺列/空矩阵/重复索引） etf_selector/portfolio.py:260, etf_selector/portfolio.py:449

---

## 6. 参考（最小）
- 算法与实现入口
  - 入口与默认：etf_selector/main.py:1
  - 选择器主流程：etf_selector/selector.py:25
  - 指标计算：etf_selector/indicators.py:12
  - 无偏指标：etf_selector/unbiased_indicators.py:1
  - 评分系统：etf_selector/scoring.py:18
  - 组合优化：etf_selector/portfolio.py:23
- 回测联动
  - 一体化脚本：run_selector_backtest.py:1
  - 回测脚本（支持 --stock-list）：run_backtest.sh:1

（本精简版以“能跑、与实现一致、便于维护”为目标；已移除冗长的阶段性数据分布、模式对比与历史案例表。）
