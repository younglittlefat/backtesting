# 基金分红数据全生命周期获取

**日期**: 2025-11-08
**版本**: v1.1 (已完成)
**状态**: ✓ 开发完成、验收通过、bug已修复

---

## 1. 需求背景

### 1.1 问题描述
基金复权价格计算需要全生命周期分红数据，但原有逻辑按日期范围获取，导致历史分红数据缺失。

### 1.2 业务需求
修改基金分红数据获取逻辑，忽略起止日期限制，获取每个基金从成立至今的全部分红记录。

---

## 2. 实现方案

### 2.1 代码修改

#### **scripts/tushare_fetcher/fund_fetcher.py**
- **第 294-307 行**: 修改方法签名，参数改为可选（默认 None），保持向后兼容
- **第 374-380 行**: 移除日期范围过滤逻辑
- **第 411 行**: 更新日志消息

```python
# 关键修改
def fetch_dividend_data(self, start_date: str = None, end_date: str = None) -> int:
    """获取基金分红数据（按基金代码循环获取，获取全生命周期数据）"""

    # 调用 API 获取全部分红数据
    df = self.pro.fund_div(ts_code=ts_code)

    # 不再执行日期过滤（已移除）
    # df = df[(df['ex_date'] >= start_date) & (df['ex_date'] <= end_date)]
```

#### **scripts/fetch_tushare_data_v2.py**
- **第 190-211 行**: 更新文档字符串和日志，明确说明获取全生命周期数据

```python
def fetch_fund_dividend(self, start_date: str, end_date: str) -> int:
    """获取基金分红数据（全生命周期）"""
    self.logger.info("获取基金分红数据（全生命周期，忽略日期范围限制，用于复权计算）")
```

#### **common/mysql_manager.py**
- **第 798 行**: 修复 `base_year` 字段长度问题

```python
# 修改前
base_year VARCHAR(4) DEFAULT NULL

# 修改后
base_year VARCHAR(20) DEFAULT NULL
```

### 2.2 数据库迁移

**问题**: 字段 `base_year VARCHAR(4)` 长度不足，导致插入失败
**错误**: `(1406, "Data too long for column 'base_year' at row 1")`

**解决**: 创建迁移脚本 `scripts/fix_fund_dividend_base_year_v2.py`

```sql
ALTER TABLE fund_dividend
MODIFY COLUMN base_year VARCHAR(20) DEFAULT NULL COMMENT '份额基准年度';
```

**执行结果**: ✓ 迁移成功

---

## 3. 验收结果

### 3.1 代码验证
| 检查项 | 状态 | 说明 |
|--------|------|------|
| 语法检查 | ✓ | Python 编译通过 |
| 方法签名兼容 | ✓ | 参数可选，保持向后兼容 |
| 日期过滤移除 | ✓ | 第376-377行代码已移除 |
| 文档字符串 | ✓ | 明确说明获取全生命周期数据 |
| 日志信息 | ✓ | 显示"全生命周期，忽略日期范围限制" |
| 数据库字段 | ✓ | base_year 扩展至 VARCHAR(20) |

### 3.2 功能验证
```bash
# 测试命令
python scripts/fetch_tushare_data_v2.py \
  --start_date 20241101 \
  --end_date 20241107 \
  --fetch_dividend \
  --data_type fund
```

**预期行为**:
- ✓ 日志显示"获取基金分红数据（全生命周期...）"
- ✓ 获取每个基金从成立至今的全部分红记录
- ✓ 不再出现 base_year 字段长度错误
- ✓ 其他数据类型（净值、规模）仍遵循日期范围

---

## 4. 风险与影响

### 4.1 风险评估
| 风险 | 影响 | 结果 |
|------|------|------|
| 数据量增大 | 低 | 单个基金历史分红记录有限（通常几十条） |
| 获取时间略增 | 低 | API调用次数不变，影响可忽略 |
| 数据库重复 | 无 | 唯一索引自动去重 |
| 字段长度不足 | 已修复 | base_year 扩展至 VARCHAR(20) |

### 4.2 影响范围
- **修改功能**: 基金分红数据获取
- **无影响**: ETF、指数、基金净值、基金规模数据获取

---

## 5. 使用说明

### 5.1 命令示例
```bash
# 获取基金分红数据（实际获取全生命周期）
python scripts/fetch_tushare_data_v2.py \
  --start_date 20241101 \
  --end_date 20241107 \
  --fetch_dividend \
  --data_type fund

# 同时获取分红和净值数据
python scripts/fetch_tushare_data_v2.py \
  --start_date 20241101 \
  --end_date 20241107 \
  --daily_data \
  --fetch_dividend \
  --data_type fund
```

**注意**:
- 分红数据获取全生命周期（忽略日期参数）
- 净值数据仍按指定日期范围获取

---

## 6. 后续优化建议

### 6.1 增量更新机制（可选）
- 首次运行：获取全生命周期数据
- 后续运行：查询数据库最新分红日期，只获取之后的新记录
- 减少重复数据传输和处理

### 6.2 监控建议
- 监控单次运行的分红数据总量
- 监控 `fund_dividend` 表增长速度
- 监控 API 调用频率

### 6.3 数据验证SQL
```sql
-- 检查 base_year 字段实际数据长度分布
SELECT
    LENGTH(base_year) as len,
    COUNT(*) as count,
    GROUP_CONCAT(DISTINCT base_year ORDER BY base_year LIMIT 5) as examples
FROM fund_dividend
WHERE base_year IS NOT NULL
GROUP BY LENGTH(base_year)
ORDER BY len DESC;
```

---

## 7. 附录

### 7.1 修改文件清单
- `scripts/tushare_fetcher/fund_fetcher.py` - 核心逻辑修改
- `scripts/fetch_tushare_data_v2.py` - 日志和文档更新
- `common/mysql_manager.py` - 表结构定义修改
- `scripts/fix_fund_dividend_base_year_v2.py` - 数据库迁移脚本（已执行，可删除）

### 7.2 表结构（最终版）
```sql
CREATE TABLE fund_dividend (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '基金代码',
    ann_date VARCHAR(8) DEFAULT NULL COMMENT '公告日期',
    imp_anndate VARCHAR(8) DEFAULT NULL COMMENT '分红实施公告日',
    base_date VARCHAR(8) DEFAULT NULL COMMENT '分配收益基准日',
    div_proc VARCHAR(20) DEFAULT NULL COMMENT '方案进度',
    record_date VARCHAR(8) DEFAULT NULL COMMENT '权益登记日',
    ex_date VARCHAR(8) DEFAULT NULL COMMENT '除息日',
    pay_date VARCHAR(8) DEFAULT NULL COMMENT '派息日',
    earpay_date VARCHAR(8) DEFAULT NULL COMMENT '收益支付日',
    net_ex_date VARCHAR(8) DEFAULT NULL COMMENT '净值除权日',
    div_cash DECIMAL(10,6) DEFAULT NULL COMMENT '每份派息(元)',
    base_unit DECIMAL(15,4) DEFAULT NULL COMMENT '基准基金份额(万份)',
    ear_distr DECIMAL(15,2) DEFAULT NULL COMMENT '可分配收益(元)',
    ear_amount DECIMAL(15,2) DEFAULT NULL COMMENT '收益分配金额(元)',
    account_date VARCHAR(8) DEFAULT NULL COMMENT '红利再投资到账日',
    base_year VARCHAR(20) DEFAULT NULL COMMENT '份额基准年度',  -- 已修复
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fund_dividend (ts_code, ex_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_ex_date (ex_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 7.3 Tushare API 参考
- **接口**: `fund_div`
- **参数**: `ts_code` (基金代码)
- **返回字段**: ts_code, ann_date, ex_date, div_cash, base_year, ...
- **频率限制**: 按账户等级标准限制

---

**完成时间**: 2025-11-08
**开发人**: Claude Code
**状态**: ✓ 已投入使用
