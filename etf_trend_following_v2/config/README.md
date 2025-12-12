# 配置文件快速参考

本目录包含多个预配置的示例配置文件，适用于不同的投资风格和策略选择。

## 配置文件清单

### 1. `config.json` - 默认配置（推荐）
- **策略**: KAMA自适应均线
- **风险等级**: 中性
- **持仓数量**: 10只（缓冲带至15）
- **特点**: 平衡收益与风险，适合大多数投资者
- **预期表现**: 夏普1.69，年化收益34.63%

### 2. `config_macd.json` - MACD策略
- **策略**: MACD交叉
- **风险等级**: 中性
- **持仓数量**: 10只（缓冲带至15）
- **特点**: 经典趋势策略，直观易理解
- **预期表现**: 夏普0.94（需配合止损）

### 3. `config_combo.json` - 组合策略
- **策略**: KAMA + MACD共识
- **风险等级**: 保守
- **持仓数量**: 8只（缓冲带至12）
- **特点**: 双重确认，信号少但质量高
- **适用场景**: 保守型投资者，追求高胜率

### 4. `config_conservative.json` - 保守配置
- **策略**: KAMA
- **风险等级**: 低
- **持仓数量**: 5只（缓冲带至8）
- **关键参数**:
  - ATR止损倍数: 2.0（较紧）
  - 单标的上限: 15%
  - 总仓位上限: 85%
  - 相关性阈值: 0.4（更严格的分散）
- **适用场景**: 风险厌恶型投资者

### 5. `config_aggressive.json` - 激进配置
- **策略**: KAMA
- **风险等级**: 高
- **持仓数量**: 15只（缓冲带至20）
- **关键参数**:
  - ATR止损倍数: 4.0（较宽）
  - 单标的上限: 25%
  - 总仓位上限: 100%
  - 相关性阈值: 0.6（允许较高相关性）
- **适用场景**: 追求高收益，可承受较大回撤

## 参数对比表

| 参数 | 保守 | 中性（默认） | 激进 |
|------|------|-------------|------|
| **持仓数量** | 5 | 10 | 15 |
| **缓冲带** | 5→8 | 10→15 | 15→20 |
| **ATR止损** | 2.0x | 3.0x | 4.0x |
| **单标的上限** | 15% | 20% | 25% |
| **总仓位** | 85% | 100% | 100% |
| **相关性阈值** | 0.4 | 0.5 | 0.6 |
| **每簇最多** | 2 | 2 | 3 |

## 使用建议

### 初次使用
```bash
# 使用默认配置（KAMA策略）
python backtest_runner.py --config config/config.json
```

### 保守投资者
```bash
# 使用保守配置
python backtest_runner.py --config config/config_conservative.json
```

### 激进投资者
```bash
# 使用激进配置
python backtest_runner.py --config config/config_aggressive.json
```

### 策略对比测试
```bash
# KAMA vs MACD vs Combo
for config in config.json config_macd.json config_combo.json; do
  python backtest_runner.py \
    --config config/$config \
    --output results/$(basename $config .json)_result.json
done
```

## 自定义配置

基于现有配置文件进行修改：

```bash
# 复制默认配置
cp config/config.json config/my_config.json

# 编辑配置文件
# 修改需要调整的参数

# 使用自定义配置运行
python backtest_runner.py --config config/my_config.json
```

## 关键参数调优指南

### 1. 策略选择 (`strategy.type`)
- `kama`: 推荐，自适应，夏普1.69
- `macd`: 经典，直观，夏普0.94
- `combo`: 保守，高质量信号

### 2. 持仓数量 (`buffer.buy_top_n`)
- **5只**: 集中持仓，高收益高风险
- **10只**: 平衡分散（推荐）
- **15只**: 高度分散，更平稳

### 3. 缓冲带宽度 (`buffer.hold_until_rank - buffer.buy_top_n`)
- **窄缓冲带**（3-5）: 更频繁调整，捕捉最强标的
- **中等缓冲带**（5-7）: 平衡换仓频率（推荐）
- **宽缓冲带**（8-10）: 减少交易成本，更稳定

### 4. ATR止损倍数 (`risk.atr_multiplier`)
- **2.0x**: 严格止损，减少亏损但可能频繁触发
- **3.0x**: 平衡设置（推荐）
- **4.0x**: 宽松止损，给予标的更多波动空间

### 5. 相关性阈值 (`clustering.correlation_threshold`)
- **0.4**: 严格去相关，强制分散
- **0.5**: 适度去相关（推荐）
- **0.6**: 宽松聚类，允许一定相关性

### 6. 仓位限制 (`position_sizing.max_position_size`)
- **15%**: 保守，强制分散
- **20%**: 平衡（推荐）
- **25%**: 激进，允许集中

## 性能基准（基于历史回测）

| 配置 | 年化收益 | 夏普比率 | 最大回撤 | 胜率 | 交易次数 |
|------|---------|---------|---------|------|---------|
| KAMA默认 | 34.63% | 1.69 | -5.27% | ~75% | 中等 |
| MACD默认 | ~25% | 0.94 | -15% | ~60% | 较高 |
| Combo | ~20% | ~1.2 | ~-8% | ~80% | 较低 |
| 保守 | ~20% | ~1.5 | ~-7% | ~70% | 低 |
| 激进 | ~40% | ~1.4 | ~-12% | ~65% | 高 |

*注: 实际表现取决于市场环境和ETF池质量*

## 常见配置错误

### 错误1: 缓冲带设置不合理
```json
❌ 错误:
"buffer": {
  "buy_top_n": 10,
  "hold_until_rank": 8  // 小于buy_top_n！
}

✅ 正确:
"buffer": {
  "buy_top_n": 10,
  "hold_until_rank": 15  // 必须大于buy_top_n
}
```

### 错误2: 止损倍数过小
```json
❌ 风险:
"risk": {
  "atr_multiplier": 1.0  // 可能频繁触发止损
}

✅ 推荐:
"risk": {
  "atr_multiplier": 3.0  // 给予合理波动空间
}
```

### 错误3: 聚类参数过于严格
```json
❌ 可能导致持仓不足:
"clustering": {
  "correlation_threshold": 0.3,  // 太严格
  "max_per_cluster": 1           // 太少
}

✅ 平衡设置:
"clustering": {
  "correlation_threshold": 0.5,
  "max_per_cluster": 2
}
```

## 配置验证

运行前验证配置文件正确性：

```bash
python -c "
from src.config_loader import load_config
config = load_config('config/my_config.json')
print('✓ 配置文件验证通过')
print(f'策略类型: {config[\"strategy\"][\"type\"]}')
print(f'买入前N名: {config[\"buffer\"][\"buy_top_n\"]}')
print(f'持有至排名: {config[\"buffer\"][\"hold_until_rank\"]}')
"
```

## 进一步阅读

- **完整文档**: `/mnt/d/git/backtesting/etf_trend_following_v2/README.md`
- **需求文档**: `/mnt/d/git/backtesting/requirement_docs/20251211_etf_trend_following_v2_requirement.md`
- **策略实验**: `/mnt/d/git/backtesting/experiment/etf/kama_cross/`
