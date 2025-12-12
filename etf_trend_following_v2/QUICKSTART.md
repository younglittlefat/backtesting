# ETF趋势跟踪系统 v2 - 快速开始指南

## 5分钟快速开始

### 第1步: 环境准备（30秒）

```bash
# 激活conda环境
conda activate backtesting

# 进入项目目录
cd /mnt/d/git/backtesting/etf_trend_following_v2
```

### 第2步: 检查数据（30秒）

```bash
# 确保ETF池文件存在
ls -l ../results/trend_etf_pool.csv

# 确保数据目录存在
ls -l ../data/chinese_etf/daily/ | head -5
```

### 第3步: 运行回测（2分钟）

```bash
# 使用默认配置（KAMA策略）运行回测
python src/backtest_runner.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2023-11-01 \
  --end-date 2025-11-30 \
  --output output/quickstart_result.json
```

### 第4步: 查看结果（1分钟）

```bash
# 查看回测报告
cat output/quickstart_result.json

# 提取关键指标
python -c "
import json
with open('output/quickstart_result.json') as f:
    result = json.load(f)
print(f'总收益: {result[\"total_return\"]*100:.2f}%')
print(f'年化收益: {result[\"annual_return\"]*100:.2f}%')
print(f'夏普比率: {result[\"sharpe_ratio\"]:.2f}')
print(f'最大回撤: {result[\"max_drawdown\"]*100:.2f}%')
"
```

### 第5步: 生成今日信号（1分钟）

```bash
# 初始化空投资组合（首次运行）
echo '{"positions": {}, "cash": 1000000.0, "last_update": null}' > output/portfolio.json

# 生成今日信号
python src/signal_pipeline.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --portfolio-file output/portfolio.json \
  --output output/signal_today.json

# 查看买入信号
cat output/signal_today.json | python -m json.tool | grep -A 20 '"buy"'
```

## 常见使用场景

### 场景1: 对比不同策略

```bash
# 创建输出目录
mkdir -p output/strategy_comparison

# KAMA策略
python src/backtest_runner.py \
  --config config/config.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output output/strategy_comparison/kama_result.json

# MACD策略
python src/backtest_runner.py \
  --config config/config_macd.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output output/strategy_comparison/macd_result.json

# Combo策略
python src/backtest_runner.py \
  --config config/config_combo.json \
  --etf-pool ../results/trend_etf_pool.csv \
  --data-dir ../data/chinese_etf/daily \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output output/strategy_comparison/combo_result.json

# 对比结果
for file in output/strategy_comparison/*.json; do
  echo "=== $(basename $file) ==="
  python -c "
import json
with open('$file') as f:
    r = json.load(f)
print(f'年化收益: {r[\"annual_return\"]*100:.2f}%')
print(f'夏普比率: {r[\"sharpe_ratio\"]:.2f}')
print(f'最大回撤: {r[\"max_drawdown\"]*100:.2f}%')
"
  echo ""
done
```

### 场景2: 测试不同风险等级

```bash
# 保守配置
python src/backtest_runner.py \
  --config config/config_conservative.json \
  --output output/conservative_result.json

# 中性配置（默认）
python src/backtest_runner.py \
  --config config/config.json \
  --output output/neutral_result.json

# 激进配置
python src/backtest_runner.py \
  --config config/config_aggressive.json \
  --output output/aggressive_result.json
```

### 场景3: 参数敏感性测试

```bash
# 测试不同的持仓数量
for n in 5 10 15; do
  # 复制配置并修改buy_top_n
  cat config/config.json | \
    python -c "
import json, sys
config = json.load(sys.stdin)
config['buffer']['buy_top_n'] = $n
config['buffer']['hold_until_rank'] = $n + 5
print(json.dumps(config, indent=2))
" > config/temp_n${n}.json

  # 运行回测
  python src/backtest_runner.py \
    --config config/temp_n${n}.json \
    --output output/test_n${n}_result.json

  # 清理临时配置
  rm config/temp_n${n}.json
done

# 对比结果
for n in 5 10 15; do
  echo "=== 持仓数量: $n ==="
  python -c "
import json
with open('output/test_n${n}_result.json') as f:
    r = json.load(f)
print(f'夏普比率: {r[\"sharpe_ratio\"]:.2f}')
"
done
```

### 场景4: 实盘每日信号生成（定时任务）

创建脚本 `scripts/daily_signal.sh`:

```bash
#!/bin/bash
# 每日信号生成脚本

# 配置
CONFIG_FILE="config/config.json"
ETF_POOL="../results/trend_etf_pool.csv"
DATA_DIR="../data/chinese_etf/daily"
PORTFOLIO_FILE="output/live_portfolio.json"
DATE=$(date +%Y%m%d)
OUTPUT_FILE="output/signals/signal_${DATE}.json"

# 创建输出目录
mkdir -p output/signals

# 更新数据（假设有数据更新脚本）
# python ../scripts/update_etf_data.py

# 生成信号
python src/signal_pipeline.py \
  --config $CONFIG_FILE \
  --etf-pool $ETF_POOL \
  --data-dir $DATA_DIR \
  --portfolio-file $PORTFOLIO_FILE \
  --output $OUTPUT_FILE

# 打印信号摘要
echo "=== 信号生成完成: $DATE ==="
python -c "
import json
with open('$OUTPUT_FILE') as f:
    signal = json.load(f)
print(f'买入: {len(signal.get(\"buy\", []))} 只')
print(f'卖出: {len(signal.get(\"sell\", []))} 只')
print(f'持有: {len(signal.get(\"hold\", []))} 只')
if signal.get('buy'):
    print(f'买入标的: {signal[\"buy\"]}')
if signal.get('sell'):
    print(f'卖出标的: {signal[\"sell\"]}')
"
```

添加到crontab（每天15:30运行）:
```bash
30 15 * * 1-5 cd /mnt/d/git/backtesting/etf_trend_following_v2 && ./scripts/daily_signal.sh >> logs/daily_signal.log 2>&1
```

## 故障排除检查清单

### ✓ 环境检查
```bash
# 1. 检查Python环境
conda activate backtesting
python --version  # 应该是Python 3.9+

# 2. 检查必要的包
python -c "import pandas, numpy, scipy; print('✓ 依赖包正常')"

# 3. 检查工作目录
pwd  # 应该在 /mnt/d/git/backtesting/etf_trend_following_v2
```

### ✓ 数据检查
```bash
# 1. 检查ETF池文件
cat ../results/trend_etf_pool.csv | wc -l  # 应该有20+行

# 2. 检查数据目录
ls ../data/chinese_etf/daily/*.csv | wc -l  # 应该有很多CSV文件

# 3. 检查单个数据文件
head -5 ../data/chinese_etf/daily/510300.SH.csv
```

### ✓ 配置检查
```bash
# 1. 验证JSON格式
python -c "import json; json.load(open('config/config.json')); print('✓ JSON格式正确')"

# 2. 检查关键配置项
python -c "
import json
config = json.load(open('config/config.json'))
assert config['buffer']['buy_top_n'] < config['buffer']['hold_until_rank'], '缓冲带设置错误'
assert config['risk']['atr_multiplier'] >= 1.0, 'ATR倍数过小'
print('✓ 配置参数合理')
"
```

### ✓ 运行检查
```bash
# 1. 测试数据加载
python -c "
from src.data_loader import DataLoader
dl = DataLoader('../data/chinese_etf/daily')
df = dl.load_single('510300.SH')
print(f'✓ 数据加载成功，共 {len(df)} 行')
"

# 2. 测试配置加载
python -c "
from src.config_loader import load_config
config = load_config('config/config.json')
print(f'✓ 配置加载成功，策略类型: {config[\"strategy\"][\"type\"]}')
"

# 3. 测试策略初始化
python -c "
from src.strategies.kama import KAMASignalGenerator
from src.data_loader import DataLoader
import pandas as pd

dl = DataLoader('../data/chinese_etf/daily')
df = dl.load_single('510300.SH')

sg = KAMASignalGenerator(period=20, fast_sc=2, slow_sc=30, lookback=3)
signals = sg.generate(df)
print(f'✓ 策略运行成功，信号数量: {signals.sum()}')
"
```

## 常见错误及解决方案

### 错误1: `ModuleNotFoundError: No module named 'src'`
```bash
# 解决方案：确保在正确的目录
cd /mnt/d/git/backtesting/etf_trend_following_v2

# 或者使用绝对导入
export PYTHONPATH=/mnt/d/git/backtesting/etf_trend_following_v2:$PYTHONPATH
```

### 错误2: `FileNotFoundError: ETF pool file not found`
```bash
# 解决方案：检查ETF池文件路径
ls ../results/trend_etf_pool.csv

# 如果不存在，生成ETF池
cd ../etf_selector
python main_selector.py
```

### 错误3: `KeyError: '510300.SH'`
```bash
# 解决方案：检查数据文件
ls ../data/chinese_etf/daily/510300.SH.csv

# 如果数据缺失，下载数据
python ../scripts/fetch_etf_data.py --code 510300.SH
```

### 错误4: 信号生成为空
```bash
# 排查步骤1：检查是否有趋势信号
python -c "
from src.strategies.kama import KAMASignalGenerator
from src.data_loader import DataLoader

dl = DataLoader('../data/chinese_etf/daily')
df = dl.load_single('510300.SH')

sg = KAMASignalGenerator(period=20, fast_sc=2, slow_sc=30, lookback=3)
signals = sg.generate(df)
print(f'最近10天信号: {signals.tail(10).tolist()}')
"

# 排查步骤2：检查数据是否最新
python -c "
from src.data_loader import DataLoader
dl = DataLoader('../data/chinese_etf/daily')
df = dl.load_single('510300.SH')
print(f'最新数据日期: {df.index[-1]}')
"
```

## 性能优化建议

### 1. 减少数据加载时间
```python
# 只加载必要的时间范围
from src.data_loader import DataLoader
dl = DataLoader('../data/chinese_etf/daily')
df = dl.load_single('510300.SH', start_date='2024-01-01')
```

### 2. 并行回测多个配置
```bash
# 使用GNU parallel
parallel -j 4 python src/backtest_runner.py --config {} --output output/{/.}_result.json ::: config/*.json
```

### 3. 缓存计算结果
```python
# 在src/scoring.py中使用缓存
import functools

@functools.lru_cache(maxsize=128)
def compute_momentum_score(etf_code, date):
    # ... 计算逻辑
    pass
```

## 下一步学习

1. **深入理解核心概念** → 阅读 `/mnt/d/git/backtesting/etf_trend_following_v2/README.md`
2. **配置参数调优** → 阅读 `/mnt/d/git/backtesting/etf_trend_following_v2/config/README.md`
3. **策略原理** → 阅读 `/mnt/d/git/backtesting/requirement_docs/20251211_etf_trend_following_v2_requirement.md`
4. **实验验证** → 查看 `/mnt/d/git/backtesting/experiment/etf/kama_cross/`

## 获取帮助

- 查看完整文档：`README.md`
- 查看配置说明：`config/README.md`
- 查看模块文档：`src/*/README*.md`
- 提交Issue：项目GitHub仓库
