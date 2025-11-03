# ETF复权因子集成设计文档

**日期**: 2025-11-03
**作者**: Claude Code
**版本**: v1.0

## 1. 需求概述

为ETF数据增加复权因子(adj_factor)支持，实现日线数据与复权数据的联合获取和存储。

### 1.1 核心目标
- 同时获取ETF日线行情(fund_daily)和复权因子(fund_adj)
- 将两类数据join后统一存储到MySQL表
- 支持前复权和后复权价格计算

### 1.2 验收标准
- 使用159300.SZ作为测试标的（2024年6月24日分红）
- 获取2024年1年数据
- 验证复权因子在分红日前后的变化

## 2. 技术方案

### 2.1 数据结构设计

#### 现有表结构
```sql
instrument_daily (
    ts_code, data_type, trade_date,
    open_price, high_price, low_price, close_price,
    pre_close, change_amount, pct_change,
    volume, amount,
    ...
)
```

#### 新增字段
```sql
ALTER TABLE instrument_daily ADD COLUMN:
    adj_factor DECIMAL(12,6) DEFAULT NULL COMMENT '复权因子'
```

### 2.2 数据获取流程

```
1. 获取ETF列表
2. 对每个ETF:
   a. 调用fund_daily获取日线数据
   b. 调用fund_adj获取复权因子
   c. 按(ts_code, trade_date)进行LEFT JOIN
   d. 批量写入MySQL
```

### 2.3 API调用

#### fund_daily接口
- 限制: 单次最大2000条
- 返回字段: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount

#### fund_adj接口
- 限制: 单次最大2000条
- 返回字段: ts_code, trade_date, adj_factor
- 计算公式:
  - 后复权价格 = 当日价格 × 复权因子
  - 前复权价格 = 当日价格 ÷ 最新复权因子

### 2.4 代码实现要点

#### 修改点1: 更新MySQL表结构
- 位置: `common/mysql_manager.py:_create_instrument_daily_table()`
- 操作: 增加adj_factor字段

#### 修改点2: 扩展数据获取方法
- 位置: `scripts/fetch_tushare_data.py:fetch_etf_daily_data_by_instrument_chunked()`
- 操作:
  1. 在获取fund_daily后立即获取fund_adj
  2. 使用pandas.merge进行LEFT JOIN
  3. 将adj_factor添加到data字典

#### 修改点3: 更新批量插入逻辑
- 位置: `common/mysql_manager.py:_insert_batch_data()`
- 操作: 在INSERT和UPDATE语句中加入adj_factor字段

## 3. 实现步骤

### 3.1 数据库准备
```sql
-- 检查现有表是否有adj_factor字段
SHOW COLUMNS FROM instrument_daily LIKE 'adj_factor';

-- 如果没有该字段，需要删除表重建
DROP TABLE IF EXISTS instrument_daily;
```

### 3.2 代码修改

#### Step 1: 修改_create_instrument_daily_table
```python
# 在close_price后添加
adj_factor DECIMAL(12,6) DEFAULT NULL COMMENT '复权因子',
```

#### Step 2: 修改fetch_etf_daily_data_by_instrument_chunked
```python
# 获取日线数据后
df_daily = self.pro.fund_daily(ts_code=ts_code, start_date=chunk_start, end_date=chunk_end)
# 获取复权数据
df_adj = self.pro.fund_adj(ts_code=ts_code, start_date=chunk_start, end_date=chunk_end)
# 合并
df = pd.merge(df_daily, df_adj[['trade_date', 'adj_factor']],
              on='trade_date', how='left')
```

#### Step 3: 修改data字典构建
```python
data = {
    'data_type': 'etf',
    'ts_code': row['ts_code'],
    'trade_date': row['trade_date'],
    ...
    'adj_factor': row.get('adj_factor'),  # 新增
}
```

#### Step 4: 修改_insert_batch_data的SQL
```python
INSERT INTO instrument_daily (
    ..., adj_factor, ...
) VALUES (
    ..., %s, ...
)
ON DUPLICATE KEY UPDATE
    ...
    adj_factor = VALUES(adj_factor),
```

## 4. 测试验证

### 4.1 验收测试
```bash
# 1. 删除现有ETF数据表
python -c "from common.mysql_manager import MySQLManager; \
  mgr = MySQLManager(); \
  mgr.clear_all_instrument_data('etf')"

# 2. 重新创建表结构（自动包含adj_factor）
# 代码启动时会自动初始化表结构

# 3. 获取159300.SZ的2024年数据
python scripts/fetch_tushare_data.py \
  --start_date 20240101 \
  --end_date 20241231 \
  --data_type etf \
  --daily_data \
  --mode clean_append

# 4. 验证数据
python scripts/export_mysql_to_csv.py --ts_code 159300.SZ --output_dir ./test_output
```

### 4.2 验证点
1. adj_factor字段是否存在且有值
2. 2024年6月24日前后adj_factor是否发生变化
3. adj_factor为1.0的日期应该是最近的交易日
4. 计算后复权价格 = close_price × adj_factor，验证连续性

### 4.3 预期结果
- 159300.SZ在2024年6月24日发生分红
- 分红日前adj_factor > 1.0
- 分红日后adj_factor会跳变（除权）
- 最新交易日adj_factor = 1.0

## 5. 注意事项

### 5.1 频率控制
- fund_adj接口每分钟最多400次调用
- 在分块获取时需要累计请求次数
- 与fund_daily的请求次数合并计算

### 5.2 数据完整性
- fund_adj可能在某些日期无数据（非交易日）
- 使用LEFT JOIN确保日线数据完整
- adj_factor为NULL的记录保留，不影响原有逻辑

### 5.3 兼容性
- 旧数据可能没有adj_factor字段
- 新增字段默认为NULL
- 不影响不使用复权的策略

## 6. 后续扩展

### 6.1 复权价格计算
在backtesting框架中添加复权价格支持:
```python
# 后复权
adj_close = close * adj_factor

# 前复权
adj_close_forward = close / latest_adj_factor
```

### 6.2 数据导出
在export_mysql_to_csv.py中:
- 默认导出后复权价格
- 提供参数选择原始价格/前复权/后复权

### 6.3 其他标的支持
- 基金(fund)也可能需要复权因子
- 股票需要使用不同的复权接口(adj_factor)
