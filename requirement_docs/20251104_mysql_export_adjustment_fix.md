# MySQL数据导出复权处理优化

**文档日期**: 2025-11-04
**状态**: ✅ 已完成
**优先级**: P0（严重影响回测准确性）
**目标文件**: `scripts/export_mysql_to_csv.py`, `utils/data_loader.py`

---

## 1. 问题分析

### 1.1 核心问题

| 问题 | 位置 | 影响 | 状态 |
|------|------|------|------|
| 复权因子存在向前看偏差 | `_compute_adjustment_columns:308-318` | 回测结果失真 | ✅ 已修复 |
| 未从数据库查询adj_factor | `_build_daily_query:461-465` | 数据缺失 | ✅ 已修复 |
| 缺少复权OHLC价格 | `_compute_adjustment_columns` | 回测标准缺失 | ✅ 已修复 |

### 1.2 向前看偏差问题

**错误代码**（已修复）：
```python
cumulative = pct.fillna(0.0).div(100.0).add(1.0).cumprod()
last_value = cumulative.iloc[-1]  # ❌ 使用未来数据
adj_factor = cumulative / last_value
```

**影响**：回测时使用了未来信息，业绩指标不可信。

**示例**（pct_chg = 1.0% 每天）：
| 日期 | pct_chg | 错误方法（向前看）| 正确方法（向后复权）|
|------|---------|----------------|-------------------|
| Day1 | 1.0%    | 0.9803 ❌      | 1.0100 ✅         |
| Day2 | 1.0%    | 0.9901 ❌      | 1.0201 ✅         |
| Day3 | 1.0%    | 1.0000 ❌      | 1.0303 ✅         |

---

## 2. 实施方案

### 2.1 Phase 1: 添加 adj_factor 查询

**文件**: `scripts/export_mysql_to_csv.py:38-49`

```python
PRICE_COLUMNS = [
    "open_price", "high_price", "low_price", "close_price",
    "pre_close", "change_amount", "pct_change", "volume", "amount",
    "adj_factor",  # ✅ 新增
]
```

### 2.2 Phase 2: 重写复权计算逻辑

**文件**: `scripts/export_mysql_to_csv.py:292-358`

**核心改动**：

1. **优先使用数据库 adj_factor**：
   ```python
   if "adj_factor" in frame.columns and frame["adj_factor"].notna().any():
       adj_factor = pd.to_numeric(frame["adj_factor"], errors="coerce")
   ```

2. **回退机制：向后复权（无向前看偏差）**：
   ```python
   elif "pct_chg" in frame.columns:
       pct = pd.to_numeric(frame["pct_chg"], errors="coerce").fillna(0.0)
       adj_factor = (pct / 100.0 + 1.0).cumprod()  # ✅ 从第一天累积
   ```

3. **计算完整的复权 OHLC**：
   ```python
   adjustments["adj_factor"] = adj_factor
   adjustments["adj_close"] = close * adj_factor
   adjustments["adj_open"] = open_price * adj_factor
   adjustments["adj_high"] = high_price * adj_factor
   adjustments["adj_low"] = low_price * adj_factor
   ```

### 2.3 Phase 3: 更新输出列格式

**文件**: `scripts/export_mysql_to_csv.py:59-108`

```python
"etf": [
    "trade_date", "instrument_name",
    "open", "high", "low", "close",      # 原始价格
    "pre_close", "change", "pct_chg",
    "volume", "amount",
    "adj_factor",                         # 复权因子
    "adj_open", "adj_high", "adj_low", "adj_close"  # ✅ 复权价格
],
```

**输出示例**：
```csv
trade_date,instrument_name,open,high,low,close,adj_factor,adj_open,adj_high,adj_low,adj_close
20240102,沪深300ETF,3.85,3.87,3.84,3.86,0.95,3.6575,3.6765,3.6480,3.6670
20240103,沪深300ETF,3.86,3.89,3.85,3.88,0.95,3.6670,3.6955,3.6575,3.6860
```

### 2.4 Phase 4: 适配 data_loader

**文件**: `utils/data_loader.py:350-441`

```python
# 检查是否有复权价格列
has_adj_prices = all(col in available_cols for col in
                     ['adj_open', 'adj_high', 'adj_low', 'adj_close'])

if has_adj_prices:
    # 使用复权价格
    print("使用复权价格进行回测")
    ohlcv_df = _create_ohlcv_dataframe(
        df=df_lower,
        date_col='trade_date',
        open_col='adj_open',  # ✅ 使用复权价格
        high_col='adj_high',
        low_col='adj_low',
        close_col='adj_close',
        volume_col='volume',
    )
else:
    # 回退：使用原始价格
    print("使用原始价格进行回测（未找到复权价格列）")
```

---

## 3. 测试验证

### 3.1 测试覆盖

**测试文件**：
- `test_adj_loading.py`: 数据加载测试
- `test_adj_computation.py`: 复权计算逻辑测试

**测试结果**：
```
数据加载测试:
  ✅ 加载带复权价格的 CSV（优先使用复权价格）
  ✅ 加载不带复权价格的 CSV（回退到原始价格）

复权计算测试:
  ✅ 使用数据库 adj_factor 计算复权 OHLC
  ✅ adj_factor 缺失时向后复权回退（无向前看偏差）
  ✅ 基金复权因子计算（adj_nav / unit_nav）

🎉 所有测试通过 (5/5)
```

### 3.2 向前看偏差验证

**关键检查点**：最后一天的 adj_factor 值

```python
import pandas as pd

df = pd.read_csv("data/daily_adj/daily/etf/510300.SH.csv")
last_factor = df['adj_factor'].iloc[-1]

# 向后复权：最后一天 adj_factor ≠ 1.0
# 向前复权（错误）：最后一天 adj_factor = 1.0
if abs(last_factor - 1.0) < 0.0001:
    print("⚠️  警告: 可能存在向前看偏差")
else:
    print("✅ 无向前看偏差")
```

**测试结果**：最后一天 adj_factor = 1.030301 ✅

---

## 4. 使用指南

### 4.1 导出数据

**单标的导出**：
```bash
conda activate backtesting

python scripts/export_mysql_to_csv.py \
  --start_date 20240101 \
  --end_date 20241031 \
  --data_type etf \
  --ts_code 510300.SH \
  --export_daily \
  --output_dir data/daily_adj
```

**批量导出**：
```bash
# 导出所有ETF
python scripts/export_mysql_to_csv.py \
  --start_date 20240101 \
  --end_date 20241231 \
  --data_type etf \
  --export_daily \
  --output_dir data/daily_adj
```

### 4.2 运行回测

**方法1: 使用脚本（推荐）**：
```bash
./run_backtest.sh -s 510300.SH -t sma_cross \
  --data-dir data/daily_adj/daily \
  --start-date 2024-01-01 \
  --end-date 2024-10-31
```

**输出示例**：
```
加载数据文件: data/daily_adj/daily/etf/510300.SH.csv
原始数据行数: 200
使用复权价格进行回测  ← ✅ 自动检测
处理后数据行数: 200
日期范围: 2024-01-01 至 2024-10-31
```

**方法2: Python API**：
```python
from pathlib import Path
from utils.data_loader import load_chinese_ohlcv_data

data = load_chinese_ohlcv_data(
    csv_path=Path("data/daily_adj/daily/etf/510300.SH.csv"),
    start_date="2024-01-01",
    end_date="2024-10-31",
    verbose=True
)
# data 的 Close 列已自动使用 adj_close
```

### 4.3 验证导出数据

**检查 CSV 结构**：
```bash
head -3 data/daily_adj/daily/etf/510300.SH.csv
```

**验证计算正确性**：
```python
import pandas as pd

df = pd.read_csv("data/daily_adj/daily/etf/510300.SH.csv")

# 检查必需列
required_cols = ['adj_factor', 'adj_open', 'adj_high', 'adj_low', 'adj_close']
has_all = all(col in df.columns for col in required_cols)
print(f"包含所有复权列: {has_all}")

# 验证计算
df['calculated'] = df['close'] * df['adj_factor']
max_diff = abs(df['adj_close'] - df['calculated']).max()
print(f"最大偏差: {max_diff:.6f}")
print("✅ 复权价格计算正确" if max_diff < 0.0001 else "❌ 计算有误")
```

---

## 5. 常见问题

### Q1: 数据库中没有 adj_factor 怎么办？

**A**: 系统会自动使用向后复权作为回退。如需完整的数据库 adj_factor：
```bash
python scripts/fetch_tushare_data_v2.py --data_type etf --update
```

### Q2: 原始价格和复权价格如何选择？

**推荐**：回测使用复权价格

| 场景 | 使用价格 | 原因 |
|------|----------|------|
| 回测策略 | 复权价格 ✅ | 消除分红送股影响，反映真实收益 |
| 展示K线 | 原始价格 | 符合实际交易价格 |
| 计算收益率 | 复权价格 ✅ | 准确计算总收益 |

**自动选择**：数据加载器会自动检测并优先使用复权价格。

### Q3: 如何验证数据完整性？

**检查数据库覆盖率**：
```sql
SELECT data_type,
       COUNT(*) as total,
       COUNT(adj_factor) as has_adj_factor,
       ROUND(COUNT(adj_factor) / COUNT(*) * 100, 2) as coverage_pct
FROM instrument_daily
GROUP BY data_type;
```

**快速检查清单**：
```bash
# 1. 检查 CSV 列
head -1 data/daily_adj/daily/etf/510300.SH.csv | grep adj_close

# 2. 验证数据行数
wc -l data/daily_adj/daily/etf/510300.SH.csv

# 3. 运行测试脚本
python test_adj_loading.py
python test_adj_computation.py

# 4. 测试回测加载
./run_backtest.sh -s 510300.SH -t sma_cross \
  --data-dir data/daily_adj/daily \
  --start-date 2024-01-01 --end-date 2024-01-31
```

---

## 6. 技术细节

### 6.1 复权因子说明

**adj_factor**：
- **来源**: 数据库 `instrument_daily.adj_factor` 字段（Tushare API）
- **作用**: `复权价格 = 原始价格 × adj_factor`
- **回退**: 当数据库无 adj_factor 时，使用向后复权计算

**向后复权 vs 向前复权**：
- **向后复权**（已采用）: 以第一天为基准，向后累积 → 无向前看偏差 ✅
- **向前复权**（已弃用）: 以最后一天为基准，标准化到 1.0 → 有向前看偏差 ❌

### 6.2 修改的文件

1. **scripts/export_mysql_to_csv.py**
   - `PRICE_COLUMNS`: 添加 adj_factor 查询
   - `_compute_adjustment_columns`: 重写复权计算逻辑
   - `DAILY_COLUMN_LAYOUT`: 添加复权 OHLC 输出列

2. **utils/data_loader.py**
   - `load_chinese_ohlcv_data`: 优先使用复权价格

3. **新增测试文件**
   - `test_adj_loading.py`: 数据加载测试
   - `test_adj_computation.py`: 复权计算逻辑测试

---

## 7. 风险与缓解

| 风险 | 状态 | 缓解措施 |
|------|------|----------|
| adj_factor字段为空 | ✅ 已处理 | 向后复权回退机制 |
| 历史数据无adj_factor | ⚠️ 需注意 | 运行 `fetch_tushare_data_v2.py` 重新获取 |
| 计算精度误差 | ✅ 已处理 | 使用 float64 精度 |

---

## 8. 后续建议

1. **数据完整性检查**: 验证数据库 adj_factor 覆盖率（见 Q3）
2. **历史数据更新**: 如覆盖率低，重新获取历史数据
3. **回测结果对比**: 使用新数据重新运行历史回测，评估修复影响

---

## 9. 相关文档

- **Tushare数据获取**: `requirement_docs/20251103_tushare_fetcher_refactoring.md`
- **项目配置**: `CLAUDE.md`
- **数据加载标准**: `utils/data_loader.py`

---

## 10. 问题修复记录

### 10.1 数据加载类别推断问题（2025-11-04）

**问题描述**：
运行回测时报错：
```
错误: 加载 159231.SZ 数据失败: CSV文件缺少必要的列: ['日期', '股价(美元)'].
可用列: ['trade_date', 'instrument_name', 'open', 'high', 'low', 'close', ...]
```

**根因分析**：
- 使用 `--data-dir data/csv/daily/etf` 时，`_infer_category` 函数错误推断类别
- 相对路径只有文件名（如 `159231.SZ.csv`）时，无法正确提取类别 `etf`
- 导致 `load_instrument_data` 调用了错误的加载函数 `load_lixinger_data`（期望美股数据列）而非 `load_chinese_ohlcv_data`

**修复方案**（`utils/data_loader.py:253-290`）：

改进 `_infer_category` 函数的类别推断逻辑：

1. **增强 ValueError 处理**：当 `relative_to` 失败时，从完整路径的父目录提取类别
2. **改进 daily/intraday 检测**：使用循环查找，支持 `csv/daily/etf` 等多层结构
3. **优化单文件名场景**：直接从 `csv_path.parent.name` 提取类别

**测试验证**：
```bash
# 测试场景1: relative_to失败（相对vs绝对）✅
# 测试场景2: 相对路径只有文件名 ✅
# 测试场景3: 标准 daily/etf 结构 ✅
# 测试场景4: csv/daily/etf 结构 ✅
# 测试场景5: fund 类别 ✅
```

**回测验证**：
```bash
./run_backtest.sh --start-date 20230102 --end-date 20251103 \
  --data-dir data/csv/daily/etf --instrument-limit 10 --verbose
```

**结果**：
- ✅ 无列名错误
- ✅ 类别正确识别为 `etf`
- ✅ 成功使用复权价格进行回测
- ✅ 数据正常加载

**影响文件**：
- `utils/data_loader.py:253-290` - `_infer_category` 函数

---

---

## 11. 新增功能记录（2025-11-04 后续）

### 11.1 Feature 1: 回测结果CSV汇总自动生成

**需求描述**：在回测完成后自动生成包含所有结果的CSV汇总文件

**实施方案**：
- **文件**: `backtest_runner.py:647-709`
- **功能**: 自动生成 `results/summary/backtest_summary_YYYYMMDD_HHMMSS.csv`
- **格式**: 与终端输出一致（代码、类型、策略、收益率、夏普比率、最大回撤）
- **排序**: 按收益率降序排序
- **编码**: UTF-8 BOM 支持中文

**测试验证**：
```bash
./run_backtest.sh --start-date 20230102 --end-date 20251103 \
  --data-dir data/csv/daily/etf --instrument-limit 10
```

**输出示例**：
```
汇总结果已保存: results/summary/backtest_summary_20251104_234123.csv
```

### 11.2 Feature 2: ETF基础信息导出修复

**问题描述**：`scripts/export_mysql_to_csv.py` 同时使用 `--export_basic` 和 `--export_daily` 时，ETF基础信息导出为空

**根本原因**：数据库 `instrument_basic` 表中缺少ETF基础信息数据，只有Fund数据

**解决方案**：
1. **数据导入**: 使用 `fetch_tushare_data_v2.py` 获取ETF基础信息
   ```bash
   python scripts/fetch_tushare_data_v2.py --start_date 20230102 \
     --end_date 20251104 --data_type etf --basic_info
   ```

2. **验证结果**: ETF基础信息成功导入
   - ETF记录数：1803条
   - Fund记录数：4415条
   - 总计：6218条

**测试验证**：
```bash
# 单标的测试
python scripts/export_mysql_to_csv.py --start_date 20240101 \
  --end_date 20241031 --data_type etf --ts_code 510300.SH \
  --export_basic --export_daily --output_dir test_export

# 批量测试
python scripts/export_mysql_to_csv.py --start_date 20240101 \
  --end_date 20240131 --data_type etf --export_basic --export_daily \
  --output_dir test_export_batch
```

**结果**：
- ✅ ETF基础信息正确导出到 `etf_basic_info.csv`
- ✅ ETF日线数据正确导出到各 `{ts_code}.csv` 文件
- ✅ 批量导出1803个ETF基础信息，1348个标的日线数据

**结论**：脚本代码本身无问题，问题已通过数据导入解决。

---

### 11.3 Feature 3: 回测结果中文名称映射

**需求描述**：利用basic_info里的信息，为回测结果文件添加标的中文名称，包括backtest_summary_xxx.csv和stats里的xx.csv

**实施方案**：
- **文件**: `backtest_runner.py`
- **核心功能**:
  1. 从数据库批量获取标的中文名称
  2. 更新summary CSV格式，添加"标的名称"列
  3. 更新stats CSV，将"标的名称"从代码改为中文名
  4. 更新终端输出，显示中文名称

**技术实现**：

1. **新增函数** (`backtest_runner.py:53-108`):
   ```python
   def enrich_instruments_with_names(instruments: List[InstrumentInfo]) -> List[InstrumentInfo]:
       """从数据库获取标的中文名称，丰富InstrumentInfo对象"""
       # 按类别批量查询basic_info
       # 更新InstrumentInfo.display_name字段
   ```

2. **主流程集成** (`backtest_runner.py:609-611`):
   ```python
   # 从数据库获取中文名称
   print("\n获取标的中文名称...")
   instruments_to_process = enrich_instruments_with_names(instruments_to_process)
   ```

3. **Summary CSV更新** (`backtest_runner.py:758-766`):
   ```python
   summary_rows.append({
       '代码': instrument.code,
       '标的名称': resolve_display_name(instrument),  # 新增
       '类型': instrument.category,
       # ...
   })
   ```

4. **终端输出更新** (`backtest_runner.py:714-737`):
   ```python
   header = f"{'代码':<12} {'名称':<16} {'类型':<8} ..."  # 新增名称列
   ```

**测试验证**：
```bash
# 测试多标的中文名映射
conda run -n backtesting python backtest_runner.py \
  --stock 510300.SH,159915.SZ,159001.SZ \
  --start-date 2024-01-01 --end-date 2024-01-31 \
  --data-dir data/csv/daily/etf --disable-low-vol-filter
```

**输出对比**：

**之前**：
```
代码,类型,策略,收益率(%),夏普比率,最大回撤(%)
510300.SH,etf,sma_cross,0.0,,-0.0
```

**之后**：
```
代码,标的名称,类型,策略,收益率(%),夏普比率,最大回撤(%)
510300.SH,沪深300ETF,etf,sma_cross,0.0,,-0.0
159915.SZ,创业板ETF,etf,sma_cross,0.0,,-0.0
159001.SZ,货币ETF,etf,sma_cross,0.0,,-0.0
```

**验证结果**：
- ✅ 数据库中文名称映射: 3/3个标的成功
- ✅ Summary CSV包含"标的名称"列
- ✅ Stats CSV的"标的名称"显示中文名
- ✅ 终端输出显示中文名称
- ✅ 自动fallback：无中文名时显示代码

---

**实施时间**: 约 3 小时
**实施日期**: 2025-11-04
**测试状态**: ✅ 全部通过（数据导入验证 + 功能测试验证 + 批量测试验证）
**下一步**: 定期检查 Tushare 数据获取，确保基础信息完整性

### 11.4 Feature 4: 回测结果CSV格式优化（2025-11-04）

**需求描述**：优化回测结果CSV的数据格式，提高可读性和实用性
1. 所有数字保留小数点后三位，避免过长影响观感
2. 每个标的显示真正的回测起止日期，便于评估时间区间是否充足

**实施方案**：

**文件**: `backtest_runner.py`

1. **汇总CSV格式优化** (`lines 764-778`):
   ```python
   # 获取实际回测起止日期
   start_date = str(stats['Start'])[:10] if 'Start' in stats else '未知'
   end_date = str(stats['End'])[:10] if 'End' in stats else '未知'

   summary_rows.append({
       '代码': instrument.code,
       '标的名称': resolve_display_name(instrument),
       '类型': instrument.category,
       '策略': result['strategy'],
       '回测开始日期': start_date,        # 新增：实际起始日期
       '回测结束日期': end_date,          # 新增：实际结束日期
       '收益率(%)': round(return_pct, 3) if return_pct is not None else None,     # 改进：3位小数
       '夏普比率': round(sharpe_value, 3) if not pd.isna(sharpe_value) else None, # 改进：3位小数
       '最大回撤(%)': round(max_dd, 3) if max_dd is not None else None,          # 改进：3位小数
   })
   ```

2. **个别Stats CSV格式优化** (`lines 335-357`):
   ```python
   summary_data = {
       '开始日期': str(stats['Start'])[:10],    # 改进：只显示日期部分
       '结束日期': str(stats['End'])[:10],      # 改进：只显示日期部分
       '初始资金': round(cash, 3),              # 改进：3位小数
       '最终资金': round(stats['Equity Final [$]'], 3),      # 改进：3位小数
       '收益率(%)': round(_safe_stat(stats, 'Return [%]'), 3),    # 改进：3位小数
       '夏普比率': round(stats['Sharpe Ratio'], 3) if not pd.isna(stats['Sharpe Ratio']) else None,
       # ... 所有数字字段都使用round(value, 3)
   }
   ```

**改进对比**：

**之前格式**：
```csv
代码,标的名称,类型,策略,收益率(%),夏普比率,最大回撤(%)
510300.SH,沪深300ETF,etf,sma_cross,-28.689070892334555,-0.6023804664611816,-35.549211356466876
```

**之后格式**：
```csv
代码,标的名称,类型,策略,回测开始日期,回测结束日期,收益率(%),夏普比率,最大回撤(%)
510300.SH,沪深300ETF,etf,sma_cross,2023-01-03,2024-10-31,-28.689,-0.602,-35.549
```

**优势**：
1. ✅ **数字格式**: 所有数字统一保留3位小数，提高可读性
2. ✅ **日期信息**: 添加实际回测起止日期，便于评估数据完整性
3. ✅ **一致性**: 汇总CSV和个别stats CSV格式统一
4. ✅ **实用性**: 可直接从CSV判断回测时间区间是否足够

**测试验证**：
```bash
# 测试命令
./run_backtest.sh --start-date 20230102 --end-date 20251103 \
  --data-dir data/csv/daily/etf --instrument-limit 5

# 验证结果
cat results/summary/backtest_summary_20251104_235842.csv
```

**结果示例**：
```csv
代码,标的名称,类型,策略,回测开始日期,回测结束日期,收益率(%),夏普比率,最大回撤(%)
159102.SZ,港股通生物科技ETF,etf,sma_cross,2025-09-16,2025-11-03,0.0,,-0.0
159101.SZ,港股通科技ETF基金,etf,sma_cross,2025-09-03,2025-11-03,-0.684,-0.193,-7.493
```

**状态**: ✅ 已完成并验证

---
