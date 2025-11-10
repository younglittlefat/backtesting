# MACD策略止损超参网格搜索实验报告

**实验日期**: 2025-11-10

**报告生成时间**: 2025-11-10 00:36:35

---

## 1. 实验概述

### 1.1 实验目标

通过网格搜索优化MACD策略的止损保护参数，提升风险调整后收益（夏普比率）。

### 1.2 实验配置

- **测试标的**: 20 只中国ETF
- **测试周期**: 2023-11至2025-11（约2年）
- **总测试次数**: 960
- **优化方法**: 每个止损参数组合下，优化MACD基础参数（fast_period, slow_period, signal_period）
- **优化目标**: 夏普比率最大化

### 1.3 测试方案

| 方案 | 描述 | 参数组合数 | 测试次数 |
|------|------|-----------|----------|
| Baseline | 无止损对照组 | 1 | 20 |
| Loss Protection | 连续止损保护 | 16 | 320 |
| Trailing Stop | 跟踪止损 | 4 | 80 |
| Combined | 组合止损 | 27 | 540 |

## 2. Baseline结果（无止损对照组）

### 2.1 汇总统计

| 指标 | 值 |
|------|----|
| 平均收益率 (%) | 75.84 |
| 收益率标准差 (%) | 122.14 |
| 平均夏普比率 | 0.73 |
| 夏普标准差 | 0.38 |
| 平均最大回撤 (%) | -20.12 |
| 平均胜率 (%) | 48.88 |
| 平均交易次数 | 14.00 |

### 2.2 最佳/最差标的

**最佳标的**: 588870.SH
- 夏普比率: 1.31
- 收益率: 37.14%
- 最大回撤: -13.24%

**最差标的**: 588170.SH
- 夏普比率: -0.45
- 收益率: -7.39%
- 最大回撤: -21.77%

## 3. Loss Protection结果（连续止损保护）

### 3.1 参数网格搜索结果

**平均夏普比率 by 参数组合**:

|         |   sharpe_ratio |
|:--------|---------------:|
| (2, 5)  |           0.75 |
| (2, 10) |           0.76 |
| (2, 15) |           0.79 |
| (2, 20) |           0.82 |
| (3, 5)  |           0.75 |
| (3, 10) |           0.74 |
| (3, 15) |           0.79 |
| (3, 20) |           0.85 |
| (4, 5)  |           0.73 |
| (4, 10) |           0.73 |
| (4, 15) |           0.74 |
| (4, 20) |           0.72 |
| (5, 5)  |           0.73 |
| (5, 10) |           0.73 |
| (5, 15) |           0.76 |
| (5, 20) |           0.76 |

### 3.2 最佳参数推荐

- **max_consecutive_losses**: 3
- **pause_bars**: 20
- **平均夏普比率**: 0.85

### 3.3 相比Baseline的改进

- Baseline平均夏普: 0.73
- Loss Protection最佳夏普: 0.85
- **提升幅度**: +16.3%

### 3.4 参数敏感性

**按 max_consecutive_losses 分组**:

|   max_consecutive_losses |   mean |   std |
|-------------------------:|-------:|------:|
|                        2 |   0.78 |  0.34 |
|                        3 |   0.78 |  0.32 |
|                        4 |   0.73 |  0.38 |
|                        5 |   0.75 |  0.34 |

**按 pause_bars 分组**:

|   pause_bars |   mean |   std |
|-------------:|-------:|------:|
|            5 |   0.74 |  0.38 |
|           10 |   0.74 |  0.37 |
|           15 |   0.77 |  0.32 |
|           20 |   0.79 |  0.32 |

## 4. Trailing Stop结果（跟踪止损）

### 4.1 参数对比

|   trailing_stop_pct |   sharpe_ratio |   return_pct |   max_drawdown_pct |   win_rate_pct |
|--------------------:|---------------:|-------------:|-------------------:|---------------:|
|                0.03 |           0.76 |        29.02 |             -14.66 |          47.39 |
|                0.05 |           0.83 |        59.55 |             -15.82 |          44.5  |
|                0.07 |           0.78 |        67.6  |             -16.43 |          49.66 |
|                0.1  |           0.76 |        63.69 |             -17.89 |          48.82 |

### 4.2 最佳参数推荐

- **trailing_stop_pct**: 5%
- **平均夏普比率**: 0.83

### 4.3 相比Baseline的改进

- Baseline平均夏普: 0.73
- Trailing Stop最佳夏普: 0.83
- **提升幅度**: +13.6%

## 5. Combined结果（组合止损）

### 5.1 最佳参数组合

- **max_consecutive_losses**: 2
- **pause_bars**: 15
- **trailing_stop_pct**: 5%
- **平均夏普比率**: 0.94

### 5.2 相比Baseline的改进

- Baseline平均夏普: 0.73
- Combined最佳夏普: 0.94
- **提升幅度**: +28.8%

### 5.3 Top 5 参数组合

|   max_losses |   pause_bars | trailing_stop_pct   |   avg_sharpe |
|-------------:|-------------:|:--------------------|-------------:|
|            2 |           15 | 5%                  |     0.941307 |
|            2 |           10 | 5%                  |     0.85947  |
|            2 |            5 | 5%                  |     0.850913 |
|            4 |            5 | 5%                  |     0.838212 |
|            2 |           15 | 3%                  |     0.837414 |

## 6. 策略对比

### 6.1 整体表现

| 策略              |   平均夏普 |   平均收益(%) |   平均回撤(%) |   平均胜率(%) |
|:----------------|-------:|----------:|----------:|----------:|
| combined        |   0.81 |     52.88 |    -15.38 |     47.54 |
| trailing_stop   |   0.78 |     54.96 |    -16.2  |     47.59 |
| loss_protection |   0.76 |     77.19 |    -19.65 |     48.6  |
| baseline        |   0.73 |     75.84 |    -20.12 |     48.88 |

**最佳策略**: combined

## 7. 结论和建议

### 7.1 主要发现

1. **最有效的止损方式**: loss_protection，相比Baseline提升 **+nan%**
2. **参数敏感性**: 根据实验结果，参数变化对结果的影响程度
3. **稳定性**: 各策略在不同标的上的表现稳定性

### 7.2 推荐配置

**Loss Protection推荐**:
```bash
--enable-macd-loss-protection \
--macd-max-consecutive-losses 3 \
--macd-pause-bars 20
```

**Trailing Stop推荐**:
```bash
--enable-macd-trailing-stop \
--macd-trailing-stop-pct 0.05
```

**Combined推荐**:
```bash
--enable-macd-loss-protection \
--macd-max-consecutive-losses 2 \
--macd-pause-bars 15 \
--enable-macd-trailing-stop \
--macd-trailing-stop-pct 0.05
```

### 7.3 后续工作

1. **跨市场验证**: 在美股ETF上验证参数的通用性
2. **组合过滤器**: 测试止损 + ADX/成交量过滤器的组合效果
3. **滚动窗口回测**: Walk-forward分析，评估参数的时间稳定性
4. **实盘验证**: 使用推荐参数进行模拟盘测试

## 8. 可视化图表

实验生成了以下可视化图表：

1. `heatmap_loss_protection_sharpe_ratio.png` - Loss Protection参数热力图（夏普比率）
2. `heatmap_loss_protection_max_drawdown_pct.png` - Loss Protection参数热力图（最大回撤）
3. `comparison_trailing_stop.png` - Trailing Stop参数对比图
4. `comparison_all_strategies.png` - 各策略表现对比图
5. `heatmap_combined_by_trailing_stop.png` - Combined策略热力图
6. `sensitivity_loss_protection.png` - Loss Protection参数敏感性分析
7. `sensitivity_trailing_stop.png` - Trailing Stop参数敏感性分析

