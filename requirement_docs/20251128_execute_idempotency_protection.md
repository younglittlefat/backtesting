# 执行幂等性保护 - Execute Idempotency Protection

**日期**: 2025-11-28
**状态**: ✅ 已完成
**优先级**: 高
**影响范围**: generate_signals.py, portfolio_manager.py

## 1. 问题背景

### 1.1 现状问题

在 `generate_daily_signals.sh` 脚本执行 `--execute` 模式时，如果同一天重复执行会导致：

1. **快照文件覆盖**: `snapshot_{portfolio}_{YYYYMMDD}.json` 被覆盖，丢失原始执行前状态
2. **交易日志覆盖**: `trades_{portfolio}_{YYYYMMDD}.json` 被覆盖，丢失交易记录
3. **持仓状态不一致**: Portfolio 文件可能因重复操作产生错误状态

### 1.2 业务需求

- 同一天重复执行 `--execute` 时，应阻止执行并提示用户
- 显示当日已执行的交易记录，方便用户查看
- 提供强制覆盖机制，用于特殊情况下的重新执行
- 对所有策略（SMA/MACD/KAMA 及未来新增策略）统一适用

## 2. 解决方案

### 2.1 核心设计

在系统层面（`generate_signals.py`）统一实现"执行幂等性"检查，而非在各策略中分别处理。

```
execute 模式入口
      ↓
┌─────────────────────────────────────┐
│  幂等性检查                          │
│  1. 检查 trades_{portfolio}_{date}   │
│  2. 已存在 → 显示记录并退出          │
│  3. 不存在/--force → 正常执行        │
└─────────────────────────────────────┘
```

### 2.2 实现细节

#### 2.2.1 portfolio_manager.py 增强

**TradeLogger.log_trades() 方法增强**:
```python
def log_trades(self, trades: List[Trade], date: Optional[str] = None,
               portfolio_name: Optional[str] = None,
               allow_empty: bool = False,           # 新增：允许记录空交易
               execution_context: Optional[Dict] = None):  # 新增：执行上下文
```

**新增 TradeLogger.get_execution_record() 方法**:
```python
def get_execution_record(self, date: str, portfolio_name: Optional[str] = None) -> Optional[Dict]:
    """获取指定日期的完整执行记录（用于幂等性检查）"""
```

**增强的日志结构**:
```json
{
  "date": "20251128",
  "trades": [...],
  "trade_count": 3,
  "timestamp": "2025-11-28 10:30:00",
  "execution_time": "2025-11-28T10:30:00.123456",
  "execution_context": {
    "status": "executed",
    "strategy": "kama_cross",
    "sell_count": 1,
    "buy_count": 2,
    "forced": false
  }
}
```

#### 2.2.2 generate_signals.py 修改

**新增 --force 参数**:
```bash
--force    强制执行，即使当天已有执行记录（会覆盖历史记录）
```

**幂等性检查逻辑** (第 1668-1720 行):
1. 检查是否存在当日执行记录
2. 已存在且无 --force → 显示历史记录并退出
3. 已存在且有 --force → 显示警告并继续执行
4. 不存在 → 正常执行

**空交易日处理**:
- 无交易信号时，也记录空日志标记"已检查"
- 防止同一天多次检查

## 3. 用户交互示例

### 3.1 已执行过时的输出

```
======================================================================
⚠️  今日（2025-11-26）已执行过交易
======================================================================

📋 执行时间: 2025-11-26 22:28:49
📋 交易记录数: 3 笔

📋 今日已执行交易明细：
   🟢 买入 159994.SZ × 30100股 @ ¥1.658 = ¥49,915.78
   🟢 买入 159941.SZ × 34600股 @ ¥1.443 = ¥49,937.79
   🟢 买入 159819.SZ × 34700股 @ ¥1.440 = ¥49,977.99

📊 当日快照持仓状态：
   现金: ¥850,168.44
   持仓数: 3 只
   估算总值: ¥1,000,000.00

======================================================================
💡 如需重新执行（会覆盖历史记录），请使用 --force 参数
======================================================================
```

### 3.2 使用 --force 强制覆盖

```bash
./generate_daily_signals.sh --execute --yes --force
```

输出:
```
⚠️  检测到今日已有执行记录，使用 --force 强制覆盖...

📸 已保存执行前快照: positions/history/snapshot_xxx_20251128.json
...（正常执行流程）
```

### 3.3 空交易日（无信号）

```
无需执行任何交易。
✓ 已记录今日检查状态（无需交易）
```

## 4. 技术实现

### 4.1 修改的文件

| 文件 | 修改类型 | 修改内容 |
|------|----------|----------|
| `portfolio_manager.py` | 增强 | `log_trades()` 增加 `allow_empty`, `execution_context` 参数 |
| `portfolio_manager.py` | 新增 | `get_execution_record()` 方法 |
| `generate_signals.py` | 新增 | `--force` 参数 |
| `generate_signals.py` | 新增 | 幂等性检查逻辑（约50行） |

### 4.2 向后兼容性

- ✅ 新功能完全兼容现有历史文件
- ✅ `get_execution_record()` 支持新旧文件命名格式
- ✅ 旧格式日志文件可正常读取
- ✅ 现有脚本无需修改

### 4.3 关键代码位置

- 幂等性检查入口: `generate_signals.py:1668-1720`
- `get_execution_record()`: `portfolio_manager.py:526-573`
- `log_trades()` 增强: `portfolio_manager.py:444-488`

## 5. 测试验收

### 5.1 测试用例

| 测试项 | 预期结果 | 状态 |
|--------|----------|------|
| 语法检查 | 编译通过 | ✅ |
| --help 显示 --force | 参数文档正确 | ✅ |
| 重复执行阻止 | 显示历史记录并退出 | ✅ |
| --force 强制执行 | 显示警告并继续 | ✅ |
| 空交易日记录 | 记录"已检查"状态 | ✅ |

### 5.2 验收结论

✅ **完全通过** - 功能实现完整、正确，推荐立即投入生产使用。

## 6. 使用指南

### 6.1 日常使用

```bash
# 正常执行（自动检查幂等性）
./generate_daily_signals.sh --execute --yes

# 如果当日已执行，会显示历史记录并退出
```

### 6.2 特殊情况

```bash
# 强制重新执行（覆盖当日记录）
./generate_daily_signals.sh --execute --yes --force
```

### 6.3 查看历史记录

历史记录保存在 `positions/history/` 目录：
- `trades_{portfolio}_{YYYYMMDD}.json` - 交易记录
- `snapshot_{portfolio}_{YYYYMMDD}.json` - 执行前快照

## 7. 未来扩展

### 7.1 可选增强（未实现）

- [ ] 支持部分重新执行（仅买入/卖出）
- [ ] 历史记录清理工具
- [ ] Web 界面查看历史记录

### 7.2 与其他功能的集成

本功能与以下系统自动集成，无需额外配置：
- 所有策略类型（SMA/MACD/KAMA）
- 所有持仓配置文件
- cron 定时任务
