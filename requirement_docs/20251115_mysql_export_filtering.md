# MySQL 导出筛选规则扩展（ETF/Fund）

文档日期: 2025-11-15  
适用范围: `scripts/export_mysql_to_csv.py`（仅对 etf、fund 应用筛选）

---

## 1. 背景与目标
- 当前脚本会将 MySQL 中的 etf、fund、index 的日线数据落地到本地 CSV。实际使用中，etf、fund 并非全部需要，需加入筛选规则，剔除不满足要求的标的，避免无效数据落地。
- 本次仅对 `etf` 与 `fund` 两类导出引入筛选，`index` 不受影响。

参考文档:
- 初版设计: `requirement_docs/1031_backtesting_design.md`
- 导出复权修复: `requirement_docs/20251104_mysql_export_adjustment_fix.md`

---

## 2. 筛选规则（AND 关系）
不满足任一条件则不落地 CSV；边界值也视为不满足（即边界失败）。

记：
- `N`: 最小历史样本交易日数（默认 180）
- `x`: 区间年化波动率阈值（默认 0.02）
- `y`: 区间日均成交额阈值，单位元（默认 5000）

定义“回测准入日期”:
- `admission_start_date = max(--start_date, instrument_daily 中该标的的最早 trade_date)`
- 实际实现采用“样本交易日数”口径，即统计 [admission_start_date, --end_date] 区间内该标的的有效交易日数量。

三条规则（仅对 etf、fund）:
1) 历史样本长度不足  
   - 判定口径: 样本交易日数 `sample_trading_days`  
   - 规则: `sample_trading_days > N` 才通过；否则剔除（等于 N 也视为不通过）
2) 区间年化波动率不足  
   - 区间: [admission_start_date, --end_date]  
   - 日收益率: 使用算术收益率  
     - ETF: 优先 `pct_chg / 100`; 缺失时回退为 `close` 简单收益率  
     - Fund: 优先 `adj_nav`，缺失回退 `unit_nav` 计算简单收益率  
   - 年化因子: 252  
   - 规则: `annual_volatility > x` 才通过；否则剔除（等于 x 也视为不通过）  
   - 最少样本天数: 与 N 一致（隐含在规则1中）
3) 区间日均成交额不足（仅 ETF 生效）  
   - 区间: 同上  
   - 口径: `amount` 单位为千元；空值按 0 计入平均；计算后 ×1000 转换为元  
   - 规则: `avg_turnover_yuan > y` 才通过；否则剔除（等于 y 也视为不通过）  
   - Fund 不应用此条

注:
- “仍以数据库内 <= end_date 的最近数据为准”：若 `end_date` 非交易日，则按 `<= end_date` 的最后一个交易日止。
- 规则为 AND 关系：三条均满足才落地（Fund 只应用前两条）。

---

## 3. 命令行参数
新增三个参数，无独立开关:
- `--min_history_days`（int，默认 180）: 样本交易日数阈值 N，严格大于 N 才通过
- `--min_annual_vol`（float，默认 0.02）: 年化波动率阈值 x，严格大于 x 才通过
- `--min_avg_turnover_yuan`（float，默认 5000）: 日均成交额阈值 y（元），严格大于 y 才通过；仅对 ETF 生效

示例:
```bash
python scripts/export_mysql_to_csv.py \
  --start_date 20240101 --end_date 20241031 \
  --data_type etf,fund \
  --export_daily \
  --output_dir data/csv \
  --min_history_days 180 \
  --min_annual_vol 0.02 \
  --min_avg_turnover_yuan 5000
```

---

## 4. 计算细节
- Admission起点: 取 `max(--start_date, 该标的在 instrument_daily 的最早 trade_date)` 的“样本交易起点”。实现采用区间内实际可得的首个交易日作为起点，样本交易日数为区间内的有效行数。
- 日收益率:
  - ETF: `pct_chg/100` 优先；缺失回退为 `close` 简单收益率
  - Fund: `adj_nav` 优先，回退 `unit_nav`
- 年化标准差: `std(returns, ddof=1) * sqrt(252)`
- 日均成交额（ETF）: `mean(amount.fillna(0)) * 1000`（将“千元”换算为“元”）
- 边界策略: 等于阈值视为不通过（inclusive-as-fail）

---

## 5. 工程实现
实现文件: `scripts/export_mysql_to_csv.py`

实现方式: 两阶段导出（性能友好、逻辑清晰）
1) Phase 1（统计）：按 `ts_code` 聚合统计下列指标，形成白名单  
   - `sample_trading_days`、`first_trade_date`、`last_trade_date`  
   - `annual_volatility`（见上）  
   - `avg_turnover_yuan`（ETF 专属）  
   - 判定是否通过，并记录失败原因集合：`insufficient_history | low_volatility | low_turnover`
2) Phase 2（写出）：仅对白名单内的标的写出 CSV；其余不落地

可观测性与产出:
- 生成 `filtered_out.csv`（位于 `--output_dir` 根路径）
  - 字段: `data_type, ts_code, instrument_name, admission_start_date, end_date, sample_trading_days, annual_volatility, avg_turnover_yuan, fail_reasons, threshold_*`
- `export_metadata.json` 增补:
  - `filters`: 配置与应用类型
  - `filter_statistics`: 分类型统计（候选总数、通过数、过滤数、各原因计数）
- 单标导出（带 `--ts_code`）若被过滤:
  - 不生成 CSV，退出码 0
  - 日志输出未通过原因

统计与日志:
- 每类完成后输出：通过标的数、导出记录数、时间范围
- 对未查询到数据的类型发出 warning

---

## 6. 与历史逻辑的关系
- 不改变 index 的导出行为
- 保持已修复的复权逻辑（参考 20251104 文档）；筛选仅用于“是否写出”，不改变已导出的列结构与复权列计算
- `--export_basic` 也按筛选白名单导出（仅 etf、fund 受影响；index 仍导出全量）

---

## 7. 验收要点
- 参数默认值符合预期：N=180, x=0.02, y=5000（元）
- etf、fund 导出仅包含满足三条（fund 两条）条件的标的
- `filtered_out.csv` 正确记录剔除标的与原因
- `export_metadata.json` 包含过滤配置与分类型统计
- 指定单标被过滤时脚本退出码为 0 且日志包含原因

---

## 8. 后续扩展（可选）
- 添加绘图/报表脚本，展示过滤前后标的数量、分布（波动率、成交额）与阈值敏感性
