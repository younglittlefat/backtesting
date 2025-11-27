# MySQL数据导出复权处理优化

**日期**: 2025-11-04
**状态**: ✅ 已完成

---

## 1. 问题描述

| 问题 | 影响 |
|------|------|
| 复权因子存在向前看偏差 | 回测结果失真（使用了未来数据） |
| 未从数据库查询adj_factor | 数据缺失 |
| 缺少复权OHLC价格 | 回测标准缺失 |

**向前看偏差示例**（pct_chg = 1.0%/天）：

| 日期 | 错误方法（向前看）| 正确方法（向后复权）|
|------|------------------|-------------------|
| Day1 | 0.9803 ❌ | 1.0100 ✅ |
| Day2 | 0.9901 ❌ | 1.0201 ✅ |
| Day3 | 1.0000 ❌ | 1.0303 ✅ |

---

## 2. 解决方案

### 2.1 复权计算逻辑

1. **优先使用数据库 adj_factor**
2. **回退机制**：向后复权（无向前看偏差）
3. **输出完整复权 OHLC**：adj_open, adj_high, adj_low, adj_close

### 2.2 输出CSV格式

```csv
trade_date,instrument_name,open,high,low,close,adj_factor,adj_open,adj_high,adj_low,adj_close
20240102,沪深300ETF,3.85,3.87,3.84,3.86,0.95,3.6575,3.6765,3.6480,3.6670
```

---

## 3. 使用方法

### 3.1 导出数据

```bash
# 单标的导出
python scripts/export_mysql_to_csv.py \
  --start_date 20240101 --end_date 20241031 \
  --data_type etf --ts_code 510300.SH \
  --export_daily --output_dir data/daily_adj

# 批量导出所有ETF
python scripts/export_mysql_to_csv.py \
  --start_date 20240101 --end_date 20241231 \
  --data_type etf --export_daily --output_dir data/daily_adj
```

### 3.2 运行回测

```bash
./run_backtest.sh -s 510300.SH -t sma_cross \
  --data-dir data/daily_adj/daily \
  --start-date 2024-01-01 --end-date 2024-10-31
```

输出示例：
```
使用复权价格进行回测  ← 自动检测
```

### 3.3 验证向前看偏差

```python
import pandas as pd
df = pd.read_csv("data/daily_adj/daily/etf/510300.SH.csv")
last_factor = df['adj_factor'].iloc[-1]

# 向后复权：最后一天 adj_factor ≠ 1.0 ✅
# 向前复权（错误）：最后一天 adj_factor = 1.0 ❌
print("✅ 无向前看偏差" if abs(last_factor - 1.0) > 0.0001 else "⚠️ 可能存在偏差")
```

---

## 4. 关键代码位置

| 模块 | 文件路径 | 行号 | 说明 |
|------|----------|------|------|
| 价格列定义 | `scripts/export_mysql_to_csv.py` | 38-49 | PRICE_COLUMNS 添加 adj_factor |
| 复权计算 | `scripts/export_mysql_to_csv.py` | 292-358 | `_compute_adjustment_columns` |
| 输出列格式 | `scripts/export_mysql_to_csv.py` | 59-108 | DAILY_COLUMN_LAYOUT |
| 数据加载 | `utils/data_loader.py` | 350-441 | 自动检测复权价格列 |
| 类别推断 | `utils/data_loader.py` | 253-290 | `_infer_category` |

---

## 5. 常见问题

### Q1: 数据库中没有 adj_factor？

系统自动使用向后复权回退。如需完整数据：
```bash
python scripts/fetch_tushare_data_v2.py --data_type etf --update
```

### Q2: 原始价格 vs 复权价格？

| 场景 | 使用价格 |
|------|----------|
| 回测策略 | 复权价格 ✅ |
| 展示K线 | 原始价格 |
| 计算收益率 | 复权价格 ✅ |

数据加载器**自动优先使用复权价格**。

### Q3: 验证数据完整性

```bash
# 检查CSV列
head -1 data/daily_adj/daily/etf/510300.SH.csv | grep adj_close

# 运行测试
python test_adj_loading.py
python test_adj_computation.py
```

---

## 6. 附加功能

### 6.1 回测结果CSV汇总

**位置**: `backtest_runner.py:647-709`

自动生成 `results/summary/backtest_summary_YYYYMMDD_HHMMSS.csv`

### 6.2 中文名称映射

**位置**: `backtest_runner.py:53-108`

从数据库获取标的中文名称，显示在终端和CSV中。

### 6.3 CSV格式优化

- 数字保留3位小数
- 显示实际回测起止日期

**输出示例**：
```csv
代码,标的名称,类型,策略,回测开始日期,回测结束日期,收益率(%),夏普比率,最大回撤(%)
510300.SH,沪深300ETF,etf,sma_cross,2023-01-03,2024-10-31,-28.689,-0.602,-35.549
```

---

## 7. 参考资料

- Tushare数据获取: `requirement_docs/20251103_tushare_fetcher_refactoring.md`
- 数据加载: `utils/data_loader.py`
