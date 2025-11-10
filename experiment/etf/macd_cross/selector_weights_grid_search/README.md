# ETF筛选器权重网格搜索实验

**项目**: Backtesting.py MACD策略优化
**方案**: 方案B - 无偏评分验证
**日期**: 2025-11-10
**状态**: 框架已完成，待执行

---

## 快速开始

### 最简单的方式

```bash
cd /mnt/d/git/backtesting
./experiment/etf/macd_cross/selector_weights_grid_search/run_experiment.sh
```

选择选项2（简化实验）可以快速验证框架是否正常工作。

### 手动执行

```bash
# 1. 激活环境
conda activate backtesting

# 2. 运行实验
cd /mnt/d/git/backtesting
python experiment/etf/macd_cross/selector_weights_grid_search/unbiased_optimizer.py

# 3. 查看结果
cat experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/best_weights.json
```

---

## 项目结构

```
experiment/etf/macd_cross/selector_weights_grid_search/
├── README.md                           # 本文件
├── run_experiment.sh                   # 快速启动脚本
├── REQUIREMENTS.md                     # 实验设计文档
├── parameter_generator.py              # 参数生成器（22个组合）
├── backtest_manager.py                 # 回测管理器
├── unbiased_optimizer.py               # 主实验脚本
├── simplified_optimizer.py             # 简化版本
├── test_selector.py                    # 测试脚本
├── config/                             # 配置文件
├── results/                            # 结果目录
│   └── unbiased/
│       ├── EXPERIMENT_REPORT.md        # 实验框架说明
│       ├── AGENT_SUMMARY.md            # Agent执行总结
│       ├── checkpoint.json             # 检查点（运行时生成）
│       ├── experiment_results.csv      # 结果（运行时生成）
│       └── best_weights.json           # 最优配置（运行时生成）
├── temp/                               # 临时文件
└── logs/                               # 日志
```

---

## 核心文档

### 必读文档

1. **AGENT_SUMMARY.md** - Agent执行总结
   - 完成的工作
   - 遇到的问题
   - 使用建议
   - 下一步行动

2. **EXPERIMENT_REPORT.md** - 实验框架说明
   - 实验设计
   - 技术实现
   - 执行指南
   - 预期结果

3. **REQUIREMENTS.md** - 实验需求文档
   - 方法学
   - 理论基础
   - 双方案对比

### 核心代码

- `unbiased_optimizer.py` - 完整实验（22个权重组合）
- `simplified_optimizer.py` - 简化实验（使用固定ETF池）
- `backtest_manager.py` - 回测管理器
- `parameter_generator.py` - 参数生成器

---

## 实验概述

### 核心理念

**完全去除选择性偏差**：
- 0% 动量指标（历史收益）
- 100% 无偏技术指标（ADX、趋势一致性、价格效率、流动性）
- 配合 MACD参数优化 + 连续止损保护

### 搜索空间

- **ADX权重**: 35%-50%
- **趋势一致性**: 25%-35%
- **价格效率**: 15%-25%
- **流动性**: 5%-15%

约束：四个权重之和 = 1.0

**有效组合数**: 22个

### 预期结果

- 夏普比率: 1.2 - 1.5 (+25% ~ +40% vs 基线)
- 年化收益: 25% - 40%
- 最大回撤: -15% ~ -20% (改善20-25%)
- 胜率: 65% - 75%

---

## 执行选项

### 选项1: 完整实验（推荐）

```bash
# 运行所有22个权重组合
python experiment/etf/macd_cross/selector_weights_grid_search/unbiased_optimizer.py
```

**特点**:
- 完整的参数扫描
- 每个组合独立运行ETF筛选
- 需要2-4小时
- 支持检查点恢复

**输出**:
- `experiment_results.csv` - 所有实验结果
- `best_weights.json` - 最优权重配置
- `checkpoint.json` - 检查点文件

### 选项2: 简化实验（快速验证）

```bash
# 使用已有的ETF池，专注于测试MACD策略
python experiment/etf/macd_cross/selector_weights_grid_search/simplified_optimizer.py
```

**特点**:
- 使用固定ETF池 (results/trend_etf_pool.csv)
- 测试不同的止损保护参数
- 需要10-20分钟
- 快速验证框架

### 选项3: 测试筛选器

```bash
# 测试ETF筛选器配置
python experiment/etf/macd_cross/selector_weights_grid_search/test_selector.py
```

**用途**:
- 调试ETF筛选器
- 验证权重配置
- 检查数据路径

---

## 常见问题

### Q1: ETF筛选器返回0个ETF

**原因**: 流动性阈值太高或数据路径不正确

**解决**:
```python
# 在 unbiased_optimizer.py 中调整:
config = FilterConfig(
    min_turnover=30_000_000,  # 降低到3000万
    min_volatility=0.10,      # 降低到0.10
    max_volatility=1.00,      # 提高到1.00
)
```

### Q2: 实验中断后如何恢复

实验支持检查点机制，重新运行即可从上次中断处继续：

```bash
# 检查点文件会记录已完成的实验
cat results/unbiased/checkpoint.json

# 重新运行，自动跳过已完成的实验
python experiment/etf/macd_cross/selector_weights_grid_search/unbiased_optimizer.py
```

### Q3: 如何查看实验进度

```bash
# 查看日志
tail -f experiment/etf/macd_cross/selector_weights_grid_search/logs/unbiased_experiment_*.log

# 或者如果后台运行
tail -f /tmp/unbiased_exp.log
```

### Q4: 如何应用最优配置

```python
import json

# 加载最优配置
with open('results/unbiased/best_weights.json') as f:
    best_config = json.load(f)

# 使用最优权重运行筛选
from etf_selector.config import FilterConfig
from etf_selector.selector import TrendETFSelector

config = FilterConfig(
    enable_unbiased_scoring=True,
    primary_weight=1.0,
    adx_score_weight=best_config['weights']['adx_weight'],
    trend_consistency_weight=best_config['weights']['trend_consistency_weight'],
    price_efficiency_weight=best_config['weights']['price_efficiency_weight'],
    liquidity_score_weight=best_config['weights']['liquidity_weight'],
    secondary_weight=0.0
)

selector = TrendETFSelector(config=config)
selected_etfs = selector.run_pipeline()
```

---

## 技术支持

### 日志文件位置

- 主实验: `logs/unbiased_experiment_*.log`
- 简化实验: `logs/simplified_experiment_*.log`
- 后台运行: `/tmp/unbiased_exp.log`

### 检查环境

```bash
# 验证conda环境
conda activate backtesting
python --version  # 应该是 3.10.19

# 验证数据路径
ls -l data/chinese_etf/
ls -l data/chinese_etf/daily/

# 验证依赖
python -c "import pandas; import backtesting; print('OK')"
```

### 调试模式

修改日志级别为DEBUG：

```python
# 在脚本开头
logging.basicConfig(level=logging.DEBUG)
```

---

## 参考资料

- [实验设计文档](REQUIREMENTS.md)
- [实验框架说明](results/unbiased/EXPERIMENT_REPORT.md)
- [Agent执行总结](results/unbiased/AGENT_SUMMARY.md)
- [项目主文档](../../../../CLAUDE.md)

---

## 更新日志

**2025-11-10**:
- 创建实验框架
- 生成22个无偏权重组合
- 完成核心代码和文档
- 创建快速启动脚本

---

## 许可和贡献

本项目是 Backtesting.py 项目的一部分。

如有问题或建议，请查看日志文件或联系项目维护者。

---

**开始您的实验吧！Good luck!**
