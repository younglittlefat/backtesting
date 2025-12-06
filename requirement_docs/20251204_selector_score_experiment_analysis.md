# ETF Selector Score 实验分析报告

## 概述

本文档总结了基于不同单一 Score（ADX、Trend Consistency、Price Efficiency、Liquidity Score）筛选出的 ETF 池子，在 KAMA 策略下的贪心超参搜索实验结果，为后续策略优化提供参考。

---

## 实验数据来源

| Score 类型 | 实验目录 | 回测数量 |
|-----------|---------|---------|
| ADX Score | `mega_test_kama_single_adx_score_20251129_171022` | 58 组配置 |
| Trend Consistency | `mega_test_kama_single_trend_consistency_parallel_20251129_173223` | 54 组配置 |
| Price Efficiency | `mega_test_kama_single_price_efficiency_parallel_20251129_221914` | 44 组配置 |
| Liquidity Score | `mega_test_kama_single_liquidity_score_parallel_20251130_083727` | 55 组配置 |

---

## 一、各 Score 池子的最优策略对比

### 1.1 汇总表

| Score 池 | Baseline 夏普 | 最优配置 | 最优夏普 | 最优回撤 | 收益中位数 |
|----------|--------------|---------|---------|---------|-----------|
| **ADX Score** | 0.07 | k4_adx+atr-stop+slope-confirm+volume | **0.76** | -11.26% | 12.82% |
| **Price Efficiency** | 0.19 | k3_adx+atr-stop+slope-confirm | **0.71** | -12.86% | 10.96% |
| **Liquidity Score** | -0.07 | k3_atr-stop+slope-confirm+volume | **0.66** | -10.56% | 7.48% |
| **Trend Consistency** | -0.01 | k3_atr-stop+slope-confirm+volume | **0.61** | -13.34% | 11.16% |

### 1.2 关键发现

1. **ADX Score 池子表现最佳**：最优夏普达到 0.76，说明 ADX 趋势强度是筛选趋势跟踪标的的有效指标

2. **所有池子都从策略优化中受益**：夏普提升幅度从 Baseline 到最优：
   - ADX Score: 0.07 → 0.76 (+986%)
   - Price Efficiency: 0.19 → 0.71 (+274%)
   - Liquidity Score: -0.07 → 0.66 (+1043%)
   - Trend Consistency: -0.01 → 0.61 (+6200%)

3. **回撤控制一致**：所有最优策略的回撤都控制在 -10% 到 -14% 之间

---

## 二、高夏普策略的共同特征

### 2.1 必选组件（出现频率最高）

分析所有夏普 > 0.6 的策略配置，发现以下核心组件：

#### ATR Stop（动态止损）
```
enable-atr-stop = TRUE
atr-period = 14
atr-multiplier = 2.5
```
- **作用**: 基于真实波幅设置动态止损线
- **效果**: 几乎所有最优策略都启用，是控制回撤的关键

#### Slope Confirmation（斜率确认）
```
enable-slope-confirmation = TRUE
min-slope-periods = 3
```
- **作用**: 要求价格方向持续 3 个周期才确认信号
- **效果**: 有效过滤假突破，提升信号质量

#### Volume Filter（成交量过滤）
```
enable-volume-filter = TRUE
volume-period = 20
volume-ratio = 1.2
```
- **作用**: 要求成交量放大 1.2 倍以上确认趋势有效性
- **效果**: 避免量能不足时的假信号

### 2.2 可选增强组件

#### ADX Filter（趋势强度过滤）
```
enable-adx-filter = TRUE
adx-period = 14
adx-threshold = 25
```
- **作用**: ADX > 25 时才允许开仓，过滤震荡市
- **适用场景**: 对 ADX Score 池效果最好（池子本身已筛选高 ADX 标的）

#### Slope Filter（均线斜率过滤）
```
enable-slope-filter = TRUE
slope-lookback = 5
```
- **作用**: 额外的斜率方向过滤
- **效果**: 与 slope-confirmation 配合使用效果更佳

### 2.3 负面组件（降低夏普）

| 组件 | 单独使用效果 | 原因分析 |
|-----|-------------|---------|
| `enable-confirm-filter` | 夏普显著下降 | 与 KAMA 自适应特性冲突 |
| `enable-loss-protection` | 效果有限 | 单独使用不如 ATR Stop |
| `enable-trailing-stop` | 几乎无效 | 与 baseline 表现相同 |

---

## 三、最优策略模板

### 3.1 推荐配置（夏普 0.65-0.76）

```bash
./run_backtest.sh \
  --stock-list results/trend_etf_pool.csv \
  --strategy kama_cross \
  --data-dir data/chinese_etf/daily \
  --enable-atr-stop --atr-period 14 --atr-multiplier 2.5 \
  --enable-slope-confirmation --min-slope-periods 3 \
  --enable-volume-filter --volume-period 20 --volume-ratio 1.2 \
  --enable-adx-filter --adx-period 14 --adx-threshold 25
```

### 3.2 各池子的最优具体配置

#### ADX Score 池（夏普 0.76）
```
k4_enable-adx-filter_enable-atr-stop_enable-slope-confirmation_enable-volume-filter
- enable-adx-filter: TRUE (period=14, threshold=25)
- enable-atr-stop: TRUE (period=14, multiplier=2.5)
- enable-slope-confirmation: TRUE (min-slope-periods=3)
- enable-volume-filter: TRUE (period=20, ratio=1.2)
```

#### Price Efficiency 池（夏普 0.71）
```
k3_enable-adx-filter_enable-atr-stop_enable-slope-confirmation
- enable-adx-filter: TRUE (period=14, threshold=25)
- enable-atr-stop: TRUE (period=14, multiplier=2.5)
- enable-slope-confirmation: TRUE (min-slope-periods=3)
```

#### Liquidity Score 池（夏普 0.66）
```
k3_enable-atr-stop_enable-slope-confirmation_enable-volume-filter
- enable-atr-stop: TRUE (period=14, multiplier=2.5)
- enable-slope-confirmation: TRUE (min-slope-periods=3)
- enable-volume-filter: TRUE (period=20, ratio=1.2)
```

#### Trend Consistency 池（夏普 0.61）
```
k3_enable-atr-stop_enable-slope-confirmation_enable-volume-filter
- enable-atr-stop: TRUE (period=14, multiplier=2.5)
- enable-slope-confirmation: TRUE (min-slope-periods=3)
- enable-volume-filter: TRUE (period=20, ratio=1.2)
```

---

## 四、策略优化建议

### 4.1 自适应 ATR 乘数策略

当前 ATR 乘数固定为 2.5，建议根据市场状态动态调整：

| 市场状态 | ADX 范围 | 建议 ATR 乘数 | 理由 |
|---------|---------|--------------|-----|
| 强趋势 | > 30 | 2.0 | 紧止损锁定利润 |
| 中等趋势 | 20-30 | 2.5 | 标准配置 |
| 弱趋势/震荡 | < 20 | 3.0 或空仓 | 宽止损或观望 |

**实现思路**:
```python
def get_dynamic_atr_multiplier(adx_value):
    if adx_value > 30:
        return 2.0
    elif adx_value > 20:
        return 2.5
    else:
        return 3.0  # 或返回 None 表示不开仓
```

### 4.2 复合 Volume 确认策略

当前仅判断 volume_ratio > 1.2，建议增加量价配合逻辑：

| 情况 | 价格变化 | 成交量比 | 信号 |
|-----|---------|---------|-----|
| 量价齐升 | > 0 | > 1.2 | ✅ 确认做多 |
| 价升量缩 | > 0 | < 0.8 | ⚠️ 背离预警，考虑减仓 |
| 价跌量增 | < 0 | > 1.5 | ❌ 可能反转，暂停开仓 |

**实现思路**:
```python
def enhanced_volume_confirm(price_change, volume_ratio):
    if price_change > 0 and volume_ratio > 1.2:
        return "CONFIRM_LONG"
    elif price_change > 0 and volume_ratio < 0.8:
        return "DIVERGENCE_WARNING"
    elif price_change < 0 and volume_ratio > 1.5:
        return "POTENTIAL_REVERSAL"
    return "NEUTRAL"
```

### 4.3 动态 Slope 周期策略

根据趋势强度调整 slope-confirmation 的确认周期：

| 趋势强度 | ADX 范围 | min-slope-periods | 理由 |
|---------|---------|-------------------|-----|
| 强趋势 | > 30 | 2 | 快速入场捕捉趋势 |
| 中等趋势 | 20-30 | 3 | 标准配置 |
| 弱趋势 | < 20 | 5 | 谨慎入场减少假信号 |

### 4.4 Score 正交组合策略

从实验看，不同 Score 池的最优策略参数相似，但**池子选出的 ETF 差异可能较大**。

**建议实验**:
1. 运行正交性分析脚本验证各 Score 之间的相关性
2. 如果 ADX Score 和 Liquidity Score 正交性高（|r| < 0.3），尝试组合：
   ```
   final_score = 0.6 * adx_score + 0.4 * liquidity_score
   ```
3. 避免组合高度相关的 Score（如 Trend Consistency 和 Price Efficiency 可能都反映趋势质量）

**验证命令**:
```bash
python scripts/analyze_score_correlation.py \
  results/trend_etf_pool_all_scores.csv \
  --output-dir experiment/etf/selector_score/correlation_analysis
```

---

## 五、下一步实验计划

### 5.1 短期（验证性实验）

1. [ ] 运行正交性分析，确定 Score 相关性矩阵
2. [ ] 测试 ADX + Liquidity 组合权重（如 60:40, 70:30）
3. [ ] 验证动态 ATR 乘数策略的效果

### 5.2 中期（策略增强）

1. [ ] 实现量价背离预警逻辑
2. [ ] 实现动态 slope-periods 自适应
3. [ ] 测试不同 ADX threshold（20, 25, 30）的效果差异

### 5.3 长期（系统优化）

1. [ ] 构建多 Score 融合评分系统
2. [ ] 实现市场状态识别模块（趋势/震荡/反转）
3. [ ] 开发参数自适应机制

---

## 六、关键结论

### 6.1 策略层面

1. **核心三要素**: ATR 动态止损 + 斜率确认 + 成交量确认，是提升夏普的关键组合
2. **组合优于单一**: 3-4 个过滤器组合使用，效果远优于单一过滤器
3. **参数稳定性**: 最优参数（ATR=14/2.5, Volume=20/1.2, Slope=3）在不同池子上表现一致

### 6.2 Score 筛选层面

1. **ADX Score 最优**: 作为单一筛选指标，ADX Score 产生的池子策略表现最好
2. **贪心方法有效但有局限**: 单 Score 测试 + 贪心组合可以找到较优解，但可能遗漏正交组合的增益
3. **建议下一步**: 通过正交性分析指导 Score 组合设计

### 6.3 量化提升

| 指标 | Baseline (无优化) | 最优策略 | 提升幅度 |
|-----|------------------|---------|---------|
| 夏普比率 | 0.07 | 0.76 | +986% |
| 最大回撤 | -30.3% | -11.26% | -63% |
| 收益中位数 | 2.36% | 12.82% | +443% |

---

## 相关文件

- 实验数据目录: `experiment/etf/selector_score/single_primary/`
- 正交性分析脚本: `scripts/analyze_score_correlation.py`
- 正交性分析需求文档: `requirement_docs/20251204_score_orthogonality_analysis.md`
- ETF 筛选器代码: `etf_selector/selector.py`
