# 美股回测系统设计文档

## 1. 项目概述

### 1.1 目标
为特斯拉和英伟达两支美股的历史数据创建一个自动化回测系统，使用 backtesting.py 框架测试多种交易策略，并通过命令行脚本方便地执行回测。

### 1.2 数据源
- 数据目录: `data/american_stocks/`
- 特斯拉数据: `特斯拉_PE-TTM_20251030_223158.csv` (约3860行)
- 英伟达数据: `英伟达_PE-TTM_20251030_223250.csv` (约6737行)
- 数据时间范围:
  - 特斯拉: 2010-06-29 至 2025-10-29
  - 英伟达: 时间范围需确认
- 数据来源: 理杏仁网站(lixinger.com)

### 1.3 数据格式分析

#### 原始CSV格式
```
﻿日期,理杏仁前复权(美元),前复权(美元),后复权(美元),股价(美元),市值(美元),PE-TTM,PE-TTM 分位点,PE-TTM 80%分位点值,PE-TTM 50%分位点值,PE-TTM 20%分位点值
2025-10-29,=461.5100,=461.5100,=6922.6500,=461.5100,=1534898803762.1699,=291.1969,=0.2478,=-27.9154,=-83.2873,=157.3445
```

**问题点:**
1. 字段值包含 `=` 前缀（Excel公式格式）
2. 列名为中文
3. 缺少 backtesting.py 需要的 OHLCV 格式（Open, High, Low, Close, Volume）
4. BOM 标记（﻿）在文件开头

#### 目标格式 (backtesting.py要求)
```
Date,Open,High,Low,Close,Volume
2025-10-29,461.51,461.51,461.51,461.51,0
```

**转换策略:**
- Date: 从"日期"列转换，并设为 DataFrame 索引
- Open/High/Low/Close: 均使用"股价(美元)"列（因原始数据只有收盘价）
- Volume: 设为 0 或从其他字段推算（原始数据无成交量）

## 2. 策略选择

### 2.1 推荐策略

基于 doc/examples 中的示例策略分析，推荐以下三种策略：

#### 策略 1: 双均线交叉策略 (SmaCross) - **最推荐**
**来源**: Quick Start User Guide

**原因:**
- 简单经典，适合长期股价数据
- 参数少，易于理解和调优
- 适合趋势明显的科技股（特斯拉、英伟达）

**实现:**
```python
class SmaCross(Strategy):
    n1 = 10  # 短期均线
    n2 = 20  # 长期均线

    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()
```

**优化参数:**
- n1: 5-50 天
- n2: 20-200 天

#### 策略 2: 带止损的双均线策略 (SmaCrossWithTrailing)
**来源**: Strategies Library

**原因:**
- 在策略1基础上增加风险管理
- 使用 ATR 追踪止损，自动保护利润
- 适合波动较大的股票

**特性:**
- 继承 SignalStrategy 和 TrailingStrategy
- 自动设置追踪止损
- 可调整止损倍数

#### 策略 3: 四均线交叉优化策略 (Sma4Cross)
**来源**: Parameter Heatmap & Optimization

**原因:**
- 更复杂的趋势判断
- 适合参数优化和热力图分析
- 可以找到最优参数组合

**特性:**
- 4个可优化参数
- 趋势过滤 + 入场出场信号
- 适合深度优化

### 2.2 不推荐策略
- **Trading with Machine Learning**: 需要额外的机器学习库和训练数据
- **Multiple Time Frames**: 需要多时间框架数据，当前只有日线数据

## 3. 系统架构设计

### 3.1 目录结构
```
backtesting/
├── data/
│   └── american_stocks/
│       ├── 特斯拉_PE-TTM_20251030_223158.csv
│       └── 英伟达_PE-TTM_20251030_223250.csv
├── strategies/
│   ├── __init__.py
│   ├── sma_cross.py           # 策略1
│   ├── sma_trailing.py        # 策略2
│   └── sma4_cross.py          # 策略3
├── utils/
│   ├── __init__.py
│   └── data_loader.py         # 数据加载和转换模块
├── results/
│   ├── reports/               # HTML报告输出
│   ├── plots/                 # 图表输出
│   └── stats/                 # 统计数据CSV输出
├── run_backtest.sh            # 主执行脚本
└── backtest_runner.py         # Python回测执行器
```

### 3.2 模块设计

#### 3.2.1 数据加载模块 (utils/data_loader.py)

**功能:**
- 读取理杏仁格式的CSV文件
- 清理数据（去除BOM、去除"="前缀）
- 转换为backtesting.py需要的OHLCV格式
- 数据验证和清洗

**主要函数:**
```python
def load_lixinger_data(csv_path: str) -> pd.DataFrame:
    """加载理杏仁CSV数据并转换为OHLCV格式"""

def clean_excel_format(value: str) -> float:
    """清理Excel公式格式（去除=前缀）"""

def validate_ohlc_data(df: pd.DataFrame) -> bool:
    """验证OHLCV数据格式"""

def get_stock_name(csv_path: str) -> str:
    """从文件名提取股票名称"""
```

#### 3.2.2 策略模块 (strategies/)

每个策略文件包含:
- 策略类定义
- 默认参数
- 参数优化范围（如果支持）

**示例结构:**
```python
# strategies/sma_cross.py
from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

def SMA(values, n):
    return pd.Series(values).rolling(n).mean()

class SmaCross(Strategy):
    n1 = 10
    n2 = 20

    def init(self):
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()

# 优化参数范围
OPTIMIZE_PARAMS = {
    'n1': range(5, 51, 5),
    'n2': range(20, 201, 20),
}

CONSTRAINTS = lambda p: p.n1 < p.n2
```

#### 3.2.3 回测执行器 (backtest_runner.py)

**功能:**
- 解析命令行参数
- 加载指定股票数据
- 执行指定策略回测
- 可选参数优化
- 保存结果（统计、图表、HTML报告）

**主要参数:**
```python
--stock: 股票选择 (tesla/nvidia/all)
--strategy: 策略选择 (sma_cross/sma_trailing/sma4_cross/all)
--optimize: 是否执行参数优化 (flag)
--commission: 手续费率 (默认0.002, 即0.2%)
--cash: 初始资金 (默认10000美元)
--output-dir: 结果输出目录 (默认results/)
--plot: 是否生成图表 (flag)
--save-html: 是否保存HTML报告 (flag)
```

**核心流程:**
```python
def run_backtest(stock_name, strategy_name, optimize=False, **kwargs):
    # 1. 加载数据
    data = load_lixinger_data(csv_path)

    # 2. 加载策略
    strategy_class = load_strategy(strategy_name)

    # 3. 创建Backtest实例
    bt = Backtest(data, strategy_class,
                  cash=kwargs['cash'],
                  commission=kwargs['commission'])

    # 4. 执行回测或优化
    if optimize:
        stats = bt.optimize(**OPTIMIZE_PARAMS)
    else:
        stats = bt.run()

    # 5. 保存结果
    save_results(stats, output_dir, stock_name, strategy_name)

    # 6. 生成图表
    if kwargs['plot']:
        bt.plot(filename=f"{output_dir}/plots/{stock_name}_{strategy_name}.html")

    return stats
```

#### 3.2.4 Shell脚本 (run_backtest.sh)

**功能:**
- 激活conda环境
- 参数验证
- 调用Python回测执行器
- 显示友好的使用帮助

**参数设计:**
```bash
#!/bin/bash
# 美股回测执行脚本

# 使用方法:
# ./run_backtest.sh [options]
#
# Options:
#   -s, --stock <name>       股票名称: tesla, nvidia, all (默认: all)
#   -t, --strategy <name>    策略名称: sma_cross, sma_trailing, sma4_cross, all (默认: sma_cross)
#   -o, --optimize           启用参数优化
#   -c, --commission <rate>  手续费率 (默认: 0.002)
#   -m, --cash <amount>      初始资金 (默认: 10000)
#   -p, --plot               生成交互式图表
#   -h, --html               保存HTML报告
#   -d, --output-dir <path>  输出目录 (默认: results)
#   --help                   显示帮助信息

# 示例:
# ./run_backtest.sh -s tesla -t sma_cross -p -h
# ./run_backtest.sh -s all -t all -o
# ./run_backtest.sh -s nvidia -t sma_trailing -c 0.001 -m 50000
```

## 4. 实现细节

### 4.1 数据转换细节

**关键处理:**
1. **BOM处理**: 使用 `encoding='utf-8-sig'` 读取
2. **Excel公式清理**:
   ```python
   df = df.applymap(lambda x: float(str(x).replace('=', '')) if isinstance(x, str) else x)
   ```
3. **日期处理**:
   ```python
   df['日期'] = pd.to_datetime(df['日期'])
   df.set_index('日期', inplace=True)
   ```
4. **OHLC构造**: 由于只有收盘价，设置 Open=High=Low=Close
5. **缺失值处理**: 使用前向填充或删除

### 4.2 结果输出格式

#### 4.2.1 统计报告 (CSV)
```
股票,策略,开始日期,结束日期,初始资金,最终资金,收益率,年化收益率,夏普比率,最大回撤,交易次数,胜率,...
特斯拉,SmaCross,2010-06-29,2025-10-29,10000,25000,150%,12.5%,1.2,-25%,150,55%,...
```

#### 4.2.2 交互式图表 (HTML)
- 使用 Bokeh 生成
- 包含蜡烛图、指标线、买卖信号
- 权益曲线
- 回撤曲线

#### 4.2.3 优化结果 (CSV + 热力图)
- 参数组合与对应的收益率
- 热力图可视化（如果是2D参数空间）

### 4.3 环境配置

**Conda环境要求:**
```bash
# 激活环境
conda activate backtesting

# 确保安装依赖
pip install -e '.[test]'
```

**环境变量:**
```bash
CONDA_PATH=/home/zijunliu/miniforge3/condabin/conda
PROJECT_ROOT=/mnt/d/git/backtesting
```

## 5. 使用场景

### 5.1 基础回测
```bash
# 对特斯拉运行双均线策略
./run_backtest.sh -s tesla -t sma_cross -p -h

# 对英伟达运行带止损策略
./run_backtest.sh -s nvidia -t sma_trailing -p
```

### 5.2 参数优化
```bash
# 优化特斯拉的双均线参数
./run_backtest.sh -s tesla -t sma_cross -o -h

# 优化所有股票的四均线策略
./run_backtest.sh -s all -t sma4_cross -o
```

### 5.3 批量测试
```bash
# 对所有股票运行所有策略
./run_backtest.sh -s all -t all -p -h

# 自定义手续费和初始资金
./run_backtest.sh -s nvidia -t sma_cross -c 0.001 -m 50000 -p
```

## 6. 技术考虑

### 6.1 性能优化
- 使用向量化操作处理大量数据
- 优化时使用多进程（backtesting.py 内置支持）
- 缓存加载的数据避免重复读取

### 6.2 错误处理
- 文件不存在时的友好提示
- 数据格式错误的详细报错
- 策略运行异常的捕获和日志

### 6.3 扩展性
- 模块化设计，易于添加新策略
- 数据加载器可支持其他数据源格式
- 策略基类可以提取共同逻辑

### 6.4 用户体验
- 清晰的命令行帮助信息
- 进度条显示（优化时）
- 彩色输出区分不同信息类型
- 结果摘要表格显示

## 7. 测试计划

### 7.1 单元测试
- `test_data_loader.py`: 测试数据加载和转换
- `test_strategies.py`: 测试各策略类
- `test_backtest_runner.py`: 测试回测执行器

### 7.2 集成测试
- 端到端测试完整流程
- 测试所有参数组合
- 验证输出文件正确性

### 7.3 数据验证
- 确认转换后的OHLCV格式正确
- 验证日期索引连续性
- 检查是否有缺失值或异常值

## 8. 交付物

### 8.1 代码模块
- [x] `utils/data_loader.py` - 数据加载器
- [x] `strategies/sma_cross.py` - 双均线策略
- [x] `strategies/sma_trailing.py` - 带止损策略
- [x] `strategies/sma4_cross.py` - 四均线策略
- [x] `backtest_runner.py` - 回测执行器
- [x] `run_backtest.sh` - Shell脚本

### 8.2 文档
- [x] 本设计文档
- [ ] README_BACKTESTING.md - 用户使用指南
- [ ] API文档（docstrings）

### 8.3 示例输出
- [ ] 示例统计报告
- [ ] 示例HTML图表
- [ ] 示例优化结果

## 9. 时间估算

- 数据加载模块: 2-3小时
- 策略实现: 2-3小时
- 回测执行器: 3-4小时
- Shell脚本: 1-2小时
- 测试和调试: 2-3小时
- 文档编写: 1-2小时

**总计: 11-17小时**

## 10. 风险和挑战

### 10.1 数据质量
- 理杏仁数据可能有缺失值
- 只有收盘价，无法构造真实的OHLC
- PE-TTM等基本面数据如何利用

### 10.2 策略适用性
- 只有收盘价数据，某些策略可能不适用
- 需要根据实际数据调整参数范围

### 10.3 回测准确性
- 无成交量数据可能影响某些分析
- 滑点和市场影响未考虑
- 历史数据不代表未来表现

## 11. 后续优化方向

1. **数据增强**:
   - 整合其他数据源获取完整OHLCV
   - 加入成交量数据
   - 利用PE-TTM等基本面数据构建策略

2. **策略扩展**:
   - 基于PE-TTM的价值投资策略
   - 结合多个技术指标的复合策略
   - 机器学习预测策略

3. **功能增强**:
   - Web界面可视化
   - 实时数据回测
   - 多股票组合回测
   - 风险管理模块

4. **性能优化**:
   - 分布式优化
   - GPU加速计算
   - 增量更新机制
