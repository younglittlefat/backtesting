# 三策略对比实验开发计划

**实验代号**: `strategy_comparison`
**创建日期**: 2025-11-11
**开发状态**: 📋 规划中

---

## 开发任务分解

### Phase 1: 配置文件准备 ⏱️ 30分钟

#### Task 1.1: 创建SMA配置文件

**文件**: `configs/sma_baseline.json`, `configs/sma_best_stop_loss.json`

**SMA Baseline配置**:
```json
{
  "strategy_name": "SMA",
  "config_type": "baseline",
  "strategy_class": "sma_cross_enhanced",
  "params": {
    "n1": 10,
    "n2": 20
  },
  "filters": {
    "enable_adx_filter": false,
    "enable_volume_filter": false,
    "enable_slope_filter": false,
    "enable_confirm_filter": false
  },
  "stop_loss": null
}
```

**SMA BestStopLoss配置**:
```json
{
  "strategy_name": "SMA",
  "config_type": "best_stop_loss",
  "strategy_class": "sma_cross_enhanced",
  "params": {
    "n1": 10,
    "n2": 20
  },
  "filters": {
    "enable_adx_filter": false,
    "enable_volume_filter": false,
    "enable_slope_filter": false,
    "enable_confirm_filter": false
  },
  "stop_loss": {
    "enable_loss_protection": true,
    "max_consecutive_losses": 3,
    "pause_bars": 10
  }
}
```

**数据来源**:
- 基础参数：`experiment/etf/sma_cross/stop_loss_comparison/compare_stop_loss.py:101`
- 止损参数：`requirement_docs/20251109_native_stop_loss_implementation.md:36-40`

---

#### Task 1.2: 创建MACD配置文件

**文件**: `configs/macd_baseline.json`, `configs/macd_best_stop_loss.json`

**MACD Baseline配置**:
```json
{
  "strategy_name": "MACD",
  "config_type": "baseline",
  "strategy_class": "macd_cross",
  "params": null,
  "optimize": true,
  "optimize_config": {
    "target": "Sharpe Ratio",
    "params": {
      "fast_period": [8, 10, 12, 14, 16, 18, 20],
      "slow_period": [20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40],
      "signal_period": [5, 7, 9, 11, 13, 15]
    },
    "constraint": "fast_period < slow_period"
  },
  "filters": {
    "enable_adx_filter": false,
    "enable_volume_filter": false,
    "enable_slope_filter": false,
    "enable_confirm_filter": false
  },
  "stop_loss": null
}
```

**MACD BestStopLoss配置**:
```json
{
  "strategy_name": "MACD",
  "config_type": "best_stop_loss",
  "strategy_class": "macd_cross",
  "params": "inherit_from_baseline",
  "filters": {
    "enable_adx_filter": false,
    "enable_volume_filter": false,
    "enable_slope_filter": false,
    "enable_confirm_filter": false
  },
  "stop_loss": {
    "enable_loss_protection": true,
    "max_consecutive_losses": 2,
    "pause_bars": 5,
    "enable_trailing_stop": true,
    "trailing_stop_pct": 0.03
  }
}
```

**数据来源**:
- 优化范围：`experiment/etf/macd_cross/grid_search_stop_loss/grid_search.py:125-127`
- 止损参数：`experiment/etf/macd_cross/grid_search_stop_loss/RESULTS.md:141-144`

**关键实现点**:
- Baseline需要先优化参数，保存优化结果
- BestStopLoss复用Baseline的优化参数（避免重复优化）

---

#### Task 1.3: 创建KAMA配置文件

**文件**: `configs/kama_baseline.json`, `configs/kama_best_stop_loss.json`

**KAMA Baseline配置**:
```json
{
  "strategy_name": "KAMA",
  "config_type": "baseline",
  "strategy_class": "kama_cross",
  "params": {
    "kama_period": 20,
    "kama_fast": 2,
    "kama_slow": 30,
    "enable_efficiency_filter": true,
    "min_efficiency_ratio": 0.3,
    "enable_slope_confirmation": true,
    "min_slope_periods": 3
  },
  "filters": {
    "enable_adx_filter": false,
    "enable_volume_filter": false,
    "enable_slope_filter": false,
    "enable_confirm_filter": false
  },
  "stop_loss": null
}
```

**KAMA BestStopLoss配置**:
```json
{
  "strategy_name": "KAMA",
  "config_type": "best_stop_loss",
  "strategy_class": "kama_cross",
  "params": {
    "kama_period": 20,
    "kama_fast": 2,
    "kama_slow": 30,
    "enable_efficiency_filter": true,
    "min_efficiency_ratio": 0.3,
    "enable_slope_confirmation": true,
    "min_slope_periods": 3
  },
  "filters": {
    "enable_adx_filter": false,
    "enable_volume_filter": false,
    "enable_slope_filter": false,
    "enable_confirm_filter": false
  },
  "stop_loss": {
    "enable_loss_protection": true,
    "max_consecutive_losses": 3,
    "pause_bars": 10
  }
}
```

**数据来源**:
- 基础参数：`strategies/kama_cross.py:258-266`
- 止损参数：参考SMA最佳实践（Loss Protection）

**注意事项**:
- KAMA首次大规模回测，建议先在1-2只ETF上验证
- 如Loss Protection效果不佳，可后续尝试Combined方案

---

### Phase 2: 主脚本开发 ⏱️ 2小时

#### Task 2.1: 核心类设计

**文件**: `compare_strategies.py`

**核心类结构**:

```python
class StrategyComparison:
    """
    三策略对比实验主控类

    职责:
    1. 加载配置文件
    2. 管理回测执行
    3. 收集和汇总结果
    4. 生成对比报告
    """

    def __init__(self, stock_list_path, data_dir, output_dir):
        """初始化实验环境"""
        self.stock_list = self.load_stock_list(stock_list_path)
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.configs = self.load_all_configs()
        self.results = {}  # 存储所有回测结果

    def load_stock_list(self, path):
        """加载股票池"""
        # 读取CSV，返回股票代码列表

    def load_all_configs(self):
        """加载6个策略配置文件"""
        # 从configs/目录加载JSON配置

    def run_experiment(self):
        """执行完整实验流程"""
        for strategy_name in ['SMA', 'MACD', 'KAMA']:
            print(f"\n{'='*60}")
            print(f"Testing Strategy: {strategy_name}")
            print(f"{'='*60}")

            # 1. 测试Baseline配置
            self.run_strategy_config(strategy_name, 'baseline')

            # 2. 测试BestStopLoss配置
            self.run_strategy_config(strategy_name, 'best_stop_loss')

        # 3. 汇总分析
        self.generate_summary()

        # 4. 生成报告
        self.generate_report()

    def run_strategy_config(self, strategy_name, config_type):
        """运行单个策略配置的所有回测"""
        config = self.configs[strategy_name][config_type]
        results = []

        # 处理MACD参数优化
        if config.get('optimize'):
            optimized_params = self.optimize_params(config)
            config['params'] = optimized_params

        # 对每只股票运行回测
        for stock_code in self.stock_list:
            result = self.run_single_backtest(stock_code, config)
            results.append(result)

        # 保存原始结果
        self.save_raw_results(strategy_name, config_type, results)

        # 保存到内存
        key = f"{strategy_name}_{config_type}"
        self.results[key] = results

    def run_single_backtest(self, stock_code, config):
        """运行单只股票的回测"""
        # 调用backtest_runner执行回测
        # 返回统计结果字典

    def optimize_params(self, config):
        """优化MACD参数（仅用于MACD Baseline）"""
        # 使用Backtest.optimize()进行网格搜索
        # 返回最优参数字典

    def save_raw_results(self, strategy_name, config_type, results):
        """保存原始结果到CSV"""
        output_path = f"{self.output_dir}/raw/{strategy_name}_{config_type}.csv"
        # 保存DataFrame

    def generate_summary(self):
        """生成汇总对比表"""
        # 计算各策略的统计指标
        # 生成comparison_summary.csv

    def generate_report(self):
        """生成RESULTS.md报告"""
        # 使用模板生成Markdown报告
        # 包含表格、结论、可视化链接
```

---

#### Task 2.2: 回测执行逻辑

**关键函数**: `run_single_backtest()`

**实现要点**:
1. 复用 `backtest_runner` 模块的标准接口
2. 动态加载策略类（`sma_cross_enhanced`, `macd_cross`, `kama_cross`）
3. 应用配置中的参数和止损设置
4. 捕获异常并记录（避免单个标的失败影响全局）

**伪代码**:
```python
def run_single_backtest(self, stock_code, config):
    try:
        # 1. 加载数据
        data = self.load_stock_data(stock_code)

        # 2. 构建策略类
        strategy_class = self.get_strategy_class(config['strategy_class'])

        # 3. 设置参数
        strategy_params = config['params'].copy()
        if config.get('stop_loss'):
            strategy_params.update(config['stop_loss'])

        # 4. 运行回测
        bt = Backtest(data, strategy_class, **backtest_settings)
        stats = bt.run(**strategy_params)

        # 5. 提取关键指标
        return {
            'stock_code': stock_code,
            'sharpe_ratio': stats['Sharpe Ratio'],
            'return_pct': stats['Return [%]'],
            'max_drawdown_pct': stats['Max. Drawdown [%]'],
            'win_rate_pct': stats['Win Rate [%]'],
            'num_trades': stats['# Trades'],
            # ... 其他指标
        }

    except Exception as e:
        logging.error(f"Failed on {stock_code}: {e}")
        return None  # 标记为失败
```

---

#### Task 2.3: MACD参数优化处理

**关键函数**: `optimize_params()`

**实现要点**:
1. 仅在MACD Baseline阶段调用
2. 对每只股票独立优化
3. 保存优化参数，供BestStopLoss阶段复用

**伪代码**:
```python
def optimize_params(self, stock_code, config):
    """为单只股票优化MACD参数"""
    data = self.load_stock_data(stock_code)
    strategy_class = self.get_strategy_class(config['strategy_class'])

    optimize_config = config['optimize_config']

    bt = Backtest(data, strategy_class, **backtest_settings)
    stats = bt.optimize(
        fast_period=optimize_config['params']['fast_period'],
        slow_period=optimize_config['params']['slow_period'],
        signal_period=optimize_config['params']['signal_period'],
        constraint=lambda p: p.fast_period < p.slow_period,
        maximize='Sharpe Ratio'
    )

    optimized = {
        'fast_period': stats._strategy.fast_period,
        'slow_period': stats._strategy.slow_period,
        'signal_period': stats._strategy.signal_period
    }

    # 保存优化参数
    self.macd_optimized_params[stock_code] = optimized

    return optimized
```

**MACD BestStopLoss阶段参数复用**:
```python
if config['params'] == 'inherit_from_baseline':
    config['params'] = self.macd_optimized_params[stock_code]
```

---

#### Task 2.4: 汇总统计分析

**关键函数**: `generate_summary()`

**生成文件**: `results/comparison_summary.csv`

**汇总表结构**:

| 策略 | 配置 | 平均夏普 | 夏普中位数 | 夏普标准差 | 平均收益(%) | 收益中位数(%) | 总收益(%) | 平均回撤(%) | 平均胜率(%) | 平均交易数 |
|------|------|----------|-----------|-----------|------------|--------------|-----------|-----------|-----------|-----------|
| SMA | Baseline | 0.61 | 0.58 | 0.38 | 51.09 | 42.5 | 1021.8 | -21.17 | 48.41 | 12.5 |
| SMA | BestStopLoss | 1.07 | 1.05 | 0.32 | 53.91 | 48.2 | 1078.2 | -13.88 | 61.42 | 11.2 |
| MACD | Baseline | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| MACD | BestStopLoss | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| KAMA | Baseline | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| KAMA | BestStopLoss | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**计算逻辑**:
```python
def calculate_summary_stats(self, results):
    """计算单个配置的汇总统计"""
    df = pd.DataFrame(results)

    return {
        'mean_sharpe': df['sharpe_ratio'].mean(),
        'median_sharpe': df['sharpe_ratio'].median(),
        'std_sharpe': df['sharpe_ratio'].std(),
        'mean_return': df['return_pct'].mean(),
        'median_return': df['return_pct'].median(),
        'total_return': df['return_pct'].sum(),
        'mean_drawdown': df['max_drawdown_pct'].mean(),
        'mean_win_rate': df['win_rate_pct'].mean(),
        'mean_trades': df['num_trades'].mean()
    }
```

---

### Phase 3: 实验执行 ⏱️ 1-2小时

#### Task 3.1: 环境准备

**检查清单**:
- [x] 股票池文件存在：`results/trend_etf_pool.csv`
- [ ] ETF数据完整性检查
- [ ] Conda环境激活：`backtesting`
- [ ] 日志目录创建：`logs/`
- [ ] 输出目录创建：`results/raw/`

**验证脚本**:
```bash
# 检查股票池
wc -l results/trend_etf_pool.csv

# 检查ETF数据
ls data/chinese_etf/daily/*.csv | wc -l

# 检查策略文件
ls -lh strategies/{sma_cross_enhanced,macd_cross,kama_cross}.py
```

---

#### Task 3.2: 试运行（单标的验证）

**目的**: 验证脚本正确性，避免全量运行时失败

**命令**:
```bash
conda activate backtesting

python experiment/etf/strategy_comparison/compare_strategies.py \
    --stock-list results/trend_etf_pool.csv \
    --data-dir data/chinese_etf/daily \
    --output-dir experiment/etf/strategy_comparison/results \
    --test-mode \
    --test-stocks 510300.SH  # 仅测试1只ETF
```

**验证点**:
- [ ] 6个配置都能正常运行
- [ ] MACD参数优化成功
- [ ] 结果文件正确生成
- [ ] 日志无ERROR

---

#### Task 3.3: 全量执行

**预估时间**: 1-2小时（取决于MACD优化速度）

**命令**:
```bash
python experiment/etf/strategy_comparison/compare_strategies.py \
    --stock-list results/trend_etf_pool.csv \
    --data-dir data/chinese_etf/daily \
    --output-dir experiment/etf/strategy_comparison/results \
    --log-file logs/experiment_$(date +%Y%m%d_%H%M%S).log
```

**监控**:
```bash
# 实时查看日志
tail -f logs/experiment_*.log

# 检查进度
ls -lh results/raw/*.csv
```

---

### Phase 4: 结果分析和报告 ⏱️ 1小时

#### Task 4.1: 汇总统计分析

**自动生成**:
- `results/comparison_summary.csv`: 汇总对比表
- 关键指标计算和排名

**手动分析**:
1. 验证假设H1-H3（见EXPERIMENT_DESIGN.md 4.1节）
2. 识别异常值（夏普<0的标的）
3. 分析止损增益率（BestStopLoss vs Baseline）

---

#### Task 4.2: 生成RESULTS.md报告

**报告结构**:

```markdown
# 三策略对比实验结果报告

## 1. 实验概述
- 测试标的：20只中国ETF
- 测试周期：2023-11至2025-11
- 总测试次数：120次

## 2. 汇总对比

### 2.1 稳健性指标（主要）
| 策略 | 配置 | 平均夏普 | 夏普中位数 | 夏普标准差 |
|------|------|----------|-----------|-----------|
| ... | ... | ... | ... | ... |

**排名**:
1. KAMA BestStopLoss: 夏普 X.XX (最稳健)
2. ...

### 2.2 盈利能力指标（次要）
| 策略 | 配置 | 平均收益(%) | 收益中位数(%) | 总收益(%) |
|------|------|------------|--------------|-----------|
| ... | ... | ... | ... | ... |

**排名**:
1. MACD BestStopLoss: 总收益 XXX% (最赚钱)
2. ...

### 2.3 风险控制指标（辅助）
| 策略 | 配置 | 平均回撤(%) | 平均胜率(%) | 平均交易数 |
|------|------|-----------|-----------|-----------|
| ... | ... | ... | ... | ... |

## 3. 止损增益分析

| 策略 | Baseline夏普 | BestStopLoss夏普 | 增益率(%) |
|------|-------------|------------------|----------|
| SMA  | 0.61        | 1.07             | +75.4%   |
| MACD | ...         | ...              | ...      |
| KAMA | ...         | ...              | ...      |

**结论**: ...

## 4. 假设验证

### H1: 止损保护对所有策略都有正向增益
✅ / ❌  验证通过/失败
理由: ...

### H2: KAMA策略因自适应特性，稳健性最优
✅ / ❌  验证通过/失败
理由: ...

### H3: MACD策略经优化后盈利能力最强
✅ / ❌  验证通过/失败
理由: ...

## 5. 策略推荐

### 5.1 最佳综合表现
推荐：XXX + BestStopLoss
理由：平衡稳健性和收益

### 5.2 适用场景
- **追求稳定**: KAMA + BestStopLoss
- **追求高收益**: MACD + BestStopLoss
- **保守操作**: SMA + BestStopLoss

## 6. 异常标的分析
（列出夏普<0的标的及原因）

## 7. 后续优化方向
1. ...
2. ...
```

---

### Phase 5: 可视化和文档完善 ⏱️ 30分钟

#### Task 5.1: 生成对比图表

**图表1**: `sharpe_comparison.png` - 夏普比率对比
- X轴：6个策略配置
- Y轴：夏普比率
- 柱状图：平均值 + 误差线（标准差）
- 参考线：夏普=1.0

**图表2**: `return_comparison.png` - 收益对比
- X轴：6个策略配置
- Y轴：收益率(%)
- 柱状图：平均值 + 中位数标记
- 颜色：Baseline vs BestStopLoss区分

**图表3**: `risk_metrics.png` - 风险指标雷达图
- 轴：夏普、收益、回撤、胜率、交易次数
- 每个策略一条线
- 归一化处理

**实现工具**: matplotlib或plotly

---

#### Task 5.2: 文档完善

**检查清单**:
- [ ] RESULTS.md格式正确，表格对齐
- [ ] 所有数字保留2位小数
- [ ] 结论有数据支撑
- [ ] 可视化图表嵌入报告
- [ ] 添加实验元信息（日期、耗时、数据版本）

---

## 开发检查清单

### 代码质量
- [ ] 所有函数有docstring
- [ ] 异常处理完整（try-except）
- [ ] 日志记录清晰（INFO/WARNING/ERROR）
- [ ] 配置文件验证（JSON schema）
- [ ] 结果文件格式统一（CSV编码UTF-8）

### 测试验证
- [ ] 单标的试运行通过
- [ ] 配置加载无错误
- [ ] MACD优化逻辑正确
- [ ] 汇总统计计算准确
- [ ] 报告生成完整

### 文档完整性
- [x] EXPERIMENT_DESIGN.md
- [x] DEVELOPMENT_PLAN.md
- [ ] RESULTS.md（实验后生成）
- [ ] README.md（实验说明）

---

## 技术难点和解决方案

### 难点1: MACD参数优化耗时

**问题**: 每只ETF优化需5-10分钟，20只需1.5-3小时

**解决方案**:
1. **并行优化**（推荐）:
   ```python
   from concurrent.futures import ProcessPoolExecutor

   with ProcessPoolExecutor(max_workers=4) as executor:
       results = executor.map(optimize_single_stock, stock_list)
   ```

2. **缓存机制**:
   - 保存优化结果到`results/macd_optimized_params.json`
   - 后续运行直接加载（支持`--use-cache`参数）

3. **缩减搜索空间**:
   - 步长从2改为4：`range(8, 21, 4)`
   - 减少组合数：7×6×3 = 126种 → 4×3×2 = 24种

---

### 难点2: MACD参数在BestStopLoss阶段的复用

**问题**: BestStopLoss需要使用与Baseline相同的优化参数

**解决方案**:
1. Baseline阶段保存每只股票的优化参数到内存：
   ```python
   self.macd_optimized_params = {
       '510300.SH': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
       '510500.SH': {...},
       ...
   }
   ```

2. BestStopLoss阶段读取：
   ```python
   if config['params'] == 'inherit_from_baseline':
       stock_params = self.macd_optimized_params[stock_code]
       config['params'] = stock_params
   ```

3. 保存到文件（可选）:
   ```python
   with open('results/macd_optimized_params.json', 'w') as f:
       json.dump(self.macd_optimized_params, f, indent=2)
   ```

---

### 难点3: 策略类动态加载

**问题**: 需要根据配置文件动态加载不同策略类

**解决方案**:
```python
def get_strategy_class(self, strategy_name):
    """动态加载策略类"""
    strategy_map = {
        'sma_cross_enhanced': SmaCrossEnhanced,
        'macd_cross': MacdCrossStrategy,
        'kama_cross': KamaCrossStrategy
    }

    if strategy_name not in strategy_map:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    return strategy_map[strategy_name]
```

**导入语句**:
```python
from strategies.sma_cross_enhanced import SmaCrossEnhanced
from strategies.macd_cross import MacdCrossStrategy
from strategies.kama_cross import KamaCrossStrategy
```

---

### 难点4: 结果文件管理

**问题**: 120次回测产生大量结果文件，需要合理组织

**解决方案**:
```
results/
├── raw/
│   ├── SMA_baseline/
│   │   ├── 510300.SH_stats.json
│   │   ├── 510500.SH_stats.json
│   │   └── ...
│   ├── SMA_best_stop_loss/
│   ├── MACD_baseline/
│   ├── MACD_best_stop_loss/
│   ├── KAMA_baseline/
│   └── KAMA_best_stop_loss/
├── comparison_summary.csv
└── RESULTS.md
```

**文件命名规范**:
- 原始结果：`{stock_code}_stats.json`
- 汇总CSV：`{strategy}_{config_type}_summary.csv`

---

## 开发注意事项

### 代码风格
- 遵循PEP 8
- 使用类型注解（Type Hints）
- 函数单一职责原则

### 错误处理
- 单只股票失败不影响全局
- 记录详细错误日志
- 生成错误统计报告

### 性能优化
- 数据预加载（避免重复读取）
- 并行计算（MACD优化）
- 内存管理（及时释放大数组）

### 可扩展性
- 配置驱动设计
- 易于添加新策略
- 支持自定义指标

---

## 附录：命令行参数设计

```bash
python compare_strategies.py \
    --stock-list results/trend_etf_pool.csv \  # 必需
    --data-dir data/chinese_etf/daily \         # 必需
    --output-dir experiment/etf/strategy_comparison/results \  # 必需
    --config-dir configs \                      # 可选，默认configs/
    --test-mode \                               # 可选，仅测试模式
    --test-stocks 510300.SH,510500.SH \        # 可选，测试模式下指定标的
    --use-cache \                               # 可选，使用MACD优化缓存
    --parallel \                                # 可选，并行优化（默认True）
    --max-workers 4 \                           # 可选，并行工作进程数
    --log-file logs/experiment.log \            # 可选，日志文件路径
    --log-level INFO                            # 可选，日志级别
```

---

**开发负责人**: Claude
**审批状态**: 待用户确认
**版本**: v1.0
