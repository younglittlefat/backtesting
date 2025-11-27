# Tushare数据获取脚本重构

**日期**: 2025-11-04
**状态**: ✅ 重构完成

---

## 1. 重构目标

将单一大文件（1914行）拆分为模块化架构，提升可维护性和可测试性。

---

## 2. 目录结构

```
scripts/
├── fetch_tushare_data.py          # 原文件（保留）
├── fetch_tushare_data_v2.py       # 新主入口 (336行)
└── tushare_fetcher/               # 核心模块包
    ├── __init__.py                # 包初始化 (21行)
    ├── base_fetcher.py            # 基础抓取器 (148行)
    ├── etf_fetcher.py             # ETF数据抓取 (381行)
    ├── index_fetcher.py           # 指数数据抓取 (185行)
    ├── fund_fetcher.py            # 基金数据抓取 (709行)
    ├── strategy_selector.py       # 策略选择器 (96行)
    ├── rate_limiter.py            # 频率控制 (62行)
    └── data_processor.py          # 数据处理工具 (127行)
```

---

## 3. 模块职责

| 模块 | 职责 | 核心方法 |
|------|------|----------|
| `base_fetcher.py` | 公共基础功能 | `get_trading_calendar()`, `_clean_data()` |
| `etf_fetcher.py` | ETF数据获取 | `fetch_basic_info()`, `fetch_daily_by_date()` |
| `index_fetcher.py` | 指数数据获取 | `fetch_basic_info()`, `fetch_daily_optimized()` |
| `fund_fetcher.py` | 基金数据获取 | `fetch_nav_by_date()`, `fetch_dividend_data()` |
| `strategy_selector.py` | 策略决策 | `determine_fetch_strategy()` |
| `rate_limiter.py` | API频率控制 | `check_and_wait()` |
| `data_processor.py` | 数据批量处理 | `add_data()`, `flush()` |

### 继承关系

```
BaseFetcher (基类)
    ├── ETFFetcher
    ├── IndexFetcher
    └── FundFetcher
```

---

## 4. 使用方法

### 4.1 ETF数据获取

```bash
# 单标的
python scripts/fetch_tushare_data_v2.py \
  --start_date 20240102 --end_date 20240131 \
  --daily_data --ts_code 510300.SH --mode replace

# 批量（自动选择by_date或by_instrument策略）
python scripts/fetch_tushare_data_v2.py \
  --start_date 20240102 --end_date 20240103 \
  --daily_data --data_type etf --mode replace
```

### 4.2 基金数据获取

```bash
python scripts/fetch_tushare_data_v2.py \
  --start_date 20240109 --end_date 20240110 \
  --basic_info --daily_data --fetch_dividend \
  --data_type fund --mode replace
```

### 4.3 指数数据获取

```bash
python scripts/fetch_tushare_data_v2.py \
  --start_date 20240101 --end_date 20240131 \
  --basic_info --daily_data --data_type index
```

---

## 5. 关键代码位置

| 功能 | 文件路径 | 行号 | 说明 |
|------|----------|------|------|
| 主入口 | `scripts/fetch_tushare_data_v2.py` | 全文件 | 命令行解析、流程协调 |
| 基类定义 | `scripts/tushare_fetcher/base_fetcher.py` | 1-148 | 公共方法、白名单过滤 |
| ETF日线获取 | `scripts/tushare_fetcher/etf_fetcher.py` | 150-250 | `fetch_daily_by_date()` |
| ETF复权因子 | `scripts/tushare_fetcher/etf_fetcher.py` | 280-350 | 复权因子合并逻辑 |
| 基金净值获取 | `scripts/tushare_fetcher/fund_fetcher.py` | 100-200 | `fetch_nav_by_date()` |
| 基金分红获取 | `scripts/tushare_fetcher/fund_fetcher.py` | 300-400 | `fetch_dividend_data()` |
| 策略选择 | `scripts/tushare_fetcher/strategy_selector.py` | 40-80 | `determine_fetch_strategy()` |
| 频率控制 | `scripts/tushare_fetcher/rate_limiter.py` | 20-50 | `check_and_wait()` |

---

## 6. 策略选择机制

系统根据时间范围和数据量自动选择最优获取策略：

| 条件 | 策略 | 说明 |
|------|------|------|
| 天数 ≤ 工具数 | `by_date` | 按日期遍历，每天1次API调用 |
| 天数 > 工具数 | `by_instrument` | 按标的遍历，分块获取 |

**示例**：2天 vs 1794个ETF → 选择 `by_date`

---

## 7. 重构收益

| 指标 | 重构前 | 重构后 | 改进 |
|------|--------|--------|------|
| 单文件行数 | 1914行 | 336行(主入口) | **82%减少** |
| 模块数量 | 1个 | 8个 | 模块化 |
| 最大模块行数 | 1914行 | 709行 | **63%减少** |
| 可测试性 | 低 | 高 | 独立模块可单测 |
| 可维护性 | 低 | 高 | 单一职责 |

---

## 8. 白名单配置

基金数据默认只获取以下公司的产品：

```python
WHITELISTED_FUND_COMPANIES = [
    "易方达基金", "华夏基金", "南方基金", "嘉实基金",
    "博时基金", "广发基金", "招商基金", "富国基金",
    "汇添富基金", "中欧基金", "银河基金"
]
```

**位置**: `scripts/tushare_fetcher/base_fetcher.py:15-25`

---

## 9. 参考资料

- MySQL数据导出: `requirement_docs/20251104_mysql_export_adjustment_fix.md`
- 数据加载: `utils/data_loader.py`
