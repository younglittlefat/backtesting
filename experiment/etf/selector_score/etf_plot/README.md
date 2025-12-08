# ETF 趋势可视化工具

## 概述

本工具为不同评分指标筛选出的 ETF 生成专业 K 线图，用于直观验证高分 ETF 在**基准期**（评分期）和**未来期**（样本外）是否呈现可见的趋势特征。

## 目的

核心问题：

> **基准期趋势分数高的 ETF，在未来期是否仍然呈现良好的趋势特征？**

这对于验证各类评分指标在 ETF 筛选中的预测能力至关重要。

## 生成的图表

### 单个 ETF 图表

每张图表包含：

1. **K 线蜡烛图（基准期）** - 评分期内的 OHLC 价格走势
2. **ADX 指标（基准期）** - 趋势强度，>25 区域高亮显示
3. **K 线蜡烛图（未来期）** - 样本外价格走势
4. **ADX 指标（未来期）** - 未来期趋势强度
5. **均线叠加** - MA20（蓝色）和 MA60（紫色）
6. **统计面板** - 两个周期的关键指标：
   - 收益率 (%)
   - 年化收益 (%)
   - 最大回撤 (%)
   - 夏普比率
   - 波动率 (%)
   - 趋势天数（ADX > 25 的天数）

### 汇总散点图

每个池子目录生成一张汇总散点图，展示：
- X 轴：筛选分数
- Y 轴：未来收益 (%)
- 颜色：排名（绿色=高排名，红色=低排名）
- 趋势线及相关系数

用于揭示高分是否能预测更好的未来表现。

## 目录结构

```
etf_plot/
├── README.md                          # 本文件
├── generate_etf_charts.py             # 主脚本
├── pool/                              # 2019-2021/2022 基准期结果
│   ├── single_adx_score/              # ADX 分数池
│   │   ├── rank01_159752_SZ.png       # 排名第 1 的 ETF 图表
│   │   ├── rank02_159865_SZ.png       # 排名第 2 的 ETF 图表
│   │   └── ...                        # 排名 3-20
│   ├── single_liquidity_score/        # 流动性分数池
│   ├── single_momentum_3m/            # 3 个月动量池
│   ├── single_momentum_12m/           # 12 个月动量池
│   ├── single_price_efficiency/       # 价格效率池
│   ├── single_trend_consistency/      # 趋势一致性池
│   ├── single_trend_quality/          # 趋势质量池
│   ├── single_volume/                 # 成交量分数池
│   ├── single_idr/                    # IDR 分数池
│   ├── single_core_trend_excess_return_20d/  # 20 日超额收益池
│   ├── single_core_trend_excess_return_60d/  # 60 日超额收益池
│   └── summary_score_vs_future_return.png    # 相关性分析图
│
└── pool_2022_2023/                    # 2022-2023 基准期结果
    ├── single_adx_score/
    ├── ...                            # 与上述结构相同
    └── summary_score_vs_future_return.png
```

## 时间周期

| 池子目录 | 基准期 | 未来期 |
|---------|--------|--------|
| `pool/` | 2019-2021 或 2019-2022 | 2022-2023 或 2023-2024 |
| `pool_2022_2023/` | 2022-2023 | 2024-2025 |

注：具体周期取决于 CSV 文件名（如 `single_adx_score_pool_2019_2021.csv` → 基准期: 2019-2021，未来期: 2022-2023）

## 运行方法

```bash
# 激活 conda 环境
conda activate backtesting

# 运行脚本
python experiment/etf/selector_score/etf_plot/generate_etf_charts.py
```

## 脚本详情

### 输入数据

- **池子 CSV 文件**: `experiment/etf/selector_score/pool/*.csv` 和 `pool_2022_2023/*.csv`
- **价格数据**: `data/chinese_etf/daily/etf/*.csv`

### 核心函数

| 函数 | 功能 |
|------|------|
| `calculate_adx()` | 使用 Wilder 平滑法计算 ADX 指标 |
| `calculate_stats()` | 计算收益率、夏普、回撤、波动率 |
| `plot_candlestick()` | 绘制 OHLC K 线图 |
| `plot_moving_averages()` | 叠加 MA20 和 MA60 均线 |
| `plot_adx()` | 绘制 ADX 并高亮阈值区域 |
| `add_stats_panel()` | 创建统计指标文本面板 |
| `generate_etf_chart()` | 生成单个 ETF 完整图表 |
| `generate_summary_scatter()` | 生成分数 vs 未来收益散点图 |

### 输出格式

- **分辨率**: 1920 x 1080 像素（PNG）
- **DPI**: 100
- **命名规则**: `rank{NN}_{ts_code}.png`（如 `rank01_159752_SZ.png`）

## 关键发现（来自汇总图）

### Pool（2019-2021 → 2022-2023）

| 评分类型 | 相关系数 | 解读 |
|---------|---------|------|
| single_volume | +0.357 | ⭐ 最佳正向预测因子 |
| single_idr | +0.314 | ⭐ 较好正向预测因子 |
| single_momentum_12m | +0.225 | 弱正相关 |
| single_trend_consistency | +0.224 | 弱正相关 |
| single_adx_score | +0.013 | 几乎无相关 |
| single_price_efficiency | -0.003 | 无相关 |
| single_trend_quality | -0.075 | 弱负相关 |
| single_momentum_3m | -0.210 | 负相关 |
| single_liquidity_score | -0.359 | ⚠️ 较强负相关 |
| single_core_trend_excess_return_20d | -0.476 | ⚠️ 最强负相关 |

### 洞察

1. **成交量和 IDR 分数**对未来收益具有最佳预测能力
2. **短期动量（3 个月）**和**超额收益指标**呈现均值回归特性
3. **ADX 分数**单独使用时对未来表现无预测能力
4. **流动性分数**呈负相关——高流动性 ETF 反而表现较差

## 依赖库

- pandas
- numpy
- matplotlib

## 注意事项

- 图表使用英文标签以避免 WSL 环境下的字体问题
- CSV 文件中的 ETF 名称为中文，但不在图表中显示
- ADX > 25 的区域用橙色填充高亮，表示处于趋势状态的时期
