#!/usr/bin/env python3
"""
ETF轮动策略 vs 固定池策略对比实验
=====================================

Phase 4实验：对比定期重新筛选ETF池（轮动）与固定池的表现

实验设计:
- Baseline（对照组）: 2023-11-01时点筛选的固定top-20 ETF池
- Rotation-30d（实验组1）: 每30天重新筛选ETF池
- Rotation-60d（实验组2）: 每60天重新筛选ETF池

使用策略: KAMA Baseline（无过滤器、无止损保护）
时间跨度: 2023-11-01 至 2025-11-12（2年）

使用方法:
    python experiment/etf/rotation_comparison/run_comparison.py \\
        --execute all  # 执行所有场景

    python experiment/etf/rotation_comparison/run_comparison.py \\
        --execute baseline  # 仅执行对照组

    python experiment/etf/rotation_comparison/run_comparison.py \\
        --analyze  # 仅分析已有结果
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


# 实验配置
EXPERIMENT_CONFIG = {
    'baseline': {
        'name': '固定池（对照组）',
        'type': 'fixed',
        'pool_file': 'results/rotation_fixed_pool/baseline_pool.csv',
        'strategy': 'kama_cross',
        'data_dir': 'data/chinese_etf',
        'output_dir': 'experiment/etf/rotation_comparison/results/baseline/',
        'description': '2023-11-01时点筛选的固定20只ETF'
    },
    'rotation_30d': {
        'name': '30天轮动（实验组1）',
        'type': 'rotation',
        'schedule_file': 'results/rotation_schedules/rotation_30d_full.json',
        'strategy': 'kama_cross',
        'rebalance_mode': 'incremental',
        'trading_cost': 0.003,
        'data_dir': 'data/chinese_etf',
        'output_dir': 'experiment/etf/rotation_comparison/results/rotation_30d/',
        'description': '每30天重新筛选ETF池'
    },
    'rotation_60d': {
        'name': '60天轮动（实验组2）',
        'type': 'rotation',
        'schedule_file': 'results/rotation_schedules/rotation_60d_full.json',
        'strategy': 'kama_cross',
        'rebalance_mode': 'incremental',
        'trading_cost': 0.003,
        'data_dir': 'data/chinese_etf',
        'output_dir': 'experiment/etf/rotation_comparison/results/rotation_60d/',
        'description': '每60天重新筛选ETF池'
    }
}


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='ETF轮动策略对比实验自动化脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--execute', type=str,
        choices=['all', 'baseline', 'rotation_30d', 'rotation_60d', 'none'],
        default='all',
        help='执行哪些场景的回测 (default: all)'
    )
    parser.add_argument(
        '--analyze', action='store_true',
        help='执行结果分析（无需重新回测）'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='显示详细执行日志'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='试运行模式，仅显示命令不执行'
    )

    return parser.parse_args()


def run_fixed_pool_backtest(config: Dict, verbose: bool = False, dry_run: bool = False) -> bool:
    """
    运行固定池回测

    Args:
        config: 实验配置字典
        verbose: 是否显示详细日志
        dry_run: 是否为试运行

    Returns:
        是否执行成功
    """
    print(f"\n{'='*80}")
    print(f"场景: {config['name']}")
    print(f"说明: {config['description']}")
    print(f"{'='*80}")

    # 检查输入文件
    pool_file = project_root / config['pool_file']
    if not pool_file.exists():
        print(f"❌ 错误: 固定池文件不存在: {pool_file}")
        print(f"   请先运行: python scripts/generate_fixed_baseline_pool.py")
        return False

    # 构建命令
    cmd = [
        'bash', str(project_root / 'run_backtest.sh'),
        '--stock-list', str(pool_file),
        '--strategy', config['strategy'],
        '--data-dir', config['data_dir'],
        '--aggregate-output', str(project_root / config['output_dir'] / 'aggregate_results.csv'),
        '--output-dir', str(project_root / config['output_dir']),
        '--verbose' if verbose else '--quiet'
    ]

    print(f"\n📝 执行命令:")
    print(f"   {' '.join(cmd)}")

    if dry_run:
        print(f"   [DRY RUN] 跳过实际执行")
        return True

    # 创建输出目录
    output_dir = project_root / config['output_dir']
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行回测
    try:
        print(f"\n⏳ 开始回测...")
        result = subprocess.run(
            cmd,
            cwd=project_root,
            check=True,
            capture_output=not verbose,
            text=True
        )
        print(f"✅ 回测完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 回测失败: {e}")
        if not verbose and e.stdout:
            print(f"\n标准输出:\n{e.stdout}")
        if not verbose and e.stderr:
            print(f"\n标准错误:\n{e.stderr}")
        return False


def run_rotation_backtest(config: Dict, verbose: bool = False, dry_run: bool = False) -> bool:
    """
    运行轮动策略回测

    Args:
        config: 实验配置字典
        verbose: 是否显示详细日志
        dry_run: 是否为试运行

    Returns:
        是否执行成功
    """
    print(f"\n{'='*80}")
    print(f"场景: {config['name']}")
    print(f"说明: {config['description']}")
    print(f"{'='*80}")

    # 检查输入文件
    schedule_file = project_root / config['schedule_file']
    if not schedule_file.exists():
        print(f"❌ 错误: 轮动表文件不存在: {schedule_file}")
        print(f"   请先运行: python scripts/prepare_rotation_schedule.py ...")
        return False

    # 构建命令
    cmd = [
        'python', str(project_root / 'scripts' / 'run_rotation_strategy.py'),
        '--rotation-schedule', str(schedule_file),
        '--strategy', config['strategy'],
        '--rebalance-mode', config['rebalance_mode'],
        '--trading-cost', str(config['trading_cost']),
        '--data-dir', config['data_dir'],
        '--output', str(project_root / config['output_dir'])
    ]

    if verbose:
        cmd.append('--verbose')

    print(f"\n📝 执行命令:")
    print(f"   {' '.join(cmd)}")

    if dry_run:
        print(f"   [DRY RUN] 跳过实际执行")
        return True

    # 创建输出目录
    output_dir = project_root / config['output_dir']
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行回测
    try:
        print(f"\n⏳ 开始回测...")
        # 使用conda环境
        conda_cmd = [
            '/home/zijunliu/miniforge3/condabin/conda', 'run',
            '-n', 'backtesting'
        ] + cmd

        result = subprocess.run(
            conda_cmd,
            cwd=project_root,
            check=True,
            capture_output=not verbose,
            text=True
        )
        print(f"✅ 回测完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 回测失败: {e}")
        if not verbose and e.stdout:
            print(f"\n标准输出:\n{e.stdout[-2000:]}")  # 只显示最后2000字符
        if not verbose and e.stderr:
            print(f"\n标准错误:\n{e.stderr[-2000:]}")
        return False


def load_baseline_results() -> pd.DataFrame:
    """加载固定池回测结果"""
    results_file = project_root / 'experiment/etf/rotation_comparison/results/baseline/aggregate_results.csv'
    if not results_file.exists():
        raise FileNotFoundError(f"未找到对照组结果: {results_file}")
    return pd.read_csv(results_file)


def load_rotation_results(rotation_period: str) -> Tuple[pd.DataFrame, Dict]:
    """
    加载轮动策略回测结果

    Args:
        rotation_period: '30d' or '60d'

    Returns:
        (backtest_results_df, rotation_metadata)
    """
    results_dir = project_root / f'experiment/etf/rotation_comparison/results/rotation_{rotation_period}'

    # 加载回测结果
    backtest_file = results_dir / 'backtest_results.csv'
    if not backtest_file.exists():
        raise FileNotFoundError(f"未找到轮动策略结果: {backtest_file}")
    backtest_df = pd.read_csv(backtest_file)

    # 加载虚拟ETF元数据（包含轮动统计）
    metadata_file = results_dir / 'virtual_etf_metadata.json'
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

    return backtest_df, metadata


def calculate_statistics(baseline_df: pd.DataFrame, rotation_30d_df: pd.DataFrame,
                         rotation_60d_df: pd.DataFrame) -> Dict:
    """
    计算对比统计指标

    Returns:
        统计结果字典
    """
    # 对照组：20个ETF的平均表现
    baseline_stats = {
        'sharpe_mean': baseline_df['Sharpe Ratio'].mean(),
        'sharpe_median': baseline_df['Sharpe Ratio'].median(),
        'sharpe_std': baseline_df['Sharpe Ratio'].std(),
        'return_mean': baseline_df['Return [%]'].mean(),
        'return_median': baseline_df['Return [%]'].median(),
        'return_total': baseline_df['Return [%]'].sum(),  # 等权组合近似
        'max_dd_mean': baseline_df['Max. Drawdown [%]'].mean(),
        'max_dd_worst': baseline_df['Max. Drawdown [%]'].min(),
        'win_rate': (baseline_df['Return [%]'] > 0).sum() / len(baseline_df) * 100,
        'n_etfs': len(baseline_df)
    }

    # 实验组1：30天轮动（单一虚拟ETF）
    rotation_30d_stats = {
        'sharpe': rotation_30d_df['Sharpe Ratio'].iloc[0],
        'return': rotation_30d_df['Return [%]'].iloc[0],
        'max_dd': rotation_30d_df['Max. Drawdown [%]'].iloc[0],
        'win_rate': rotation_30d_df['Win Rate [%]'].iloc[0] if 'Win Rate [%]' in rotation_30d_df else None,
        'n_trades': rotation_30d_df['# Trades'].iloc[0]
    }

    # 实验组2：60天轮动（单一虚拟ETF）
    rotation_60d_stats = {
        'sharpe': rotation_60d_df['Sharpe Ratio'].iloc[0],
        'return': rotation_60d_df['Return [%]'].iloc[0],
        'max_dd': rotation_60d_df['Max. Drawdown [%]'].iloc[0],
        'win_rate': rotation_60d_df['Win Rate [%]'].iloc[0] if 'Win Rate [%]' in rotation_60d_df else None,
        'n_trades': rotation_60d_df['# Trades'].iloc[0]
    }

    return {
        'baseline': baseline_stats,
        'rotation_30d': rotation_30d_stats,
        'rotation_60d': rotation_60d_stats
    }


def generate_comparison_report(stats: Dict, metadata_30d: Dict, metadata_60d: Dict):
    """
    生成对比分析报告

    Args:
        stats: 统计结果字典
        metadata_30d: 30天轮动元数据
        metadata_60d: 60天轮动元数据
    """
    report_path = project_root / 'experiment/etf/rotation_comparison/RESULTS.md'

    baseline = stats['baseline']
    rot_30d = stats['rotation_30d']
    rot_60d = stats['rotation_60d']

    # 计算相对提升
    sharpe_30d_improvement = (rot_30d['sharpe'] - baseline['sharpe_mean']) / baseline['sharpe_mean'] * 100 if baseline['sharpe_mean'] != 0 else 0
    sharpe_60d_improvement = (rot_60d['sharpe'] - baseline['sharpe_mean']) / baseline['sharpe_mean'] * 100 if baseline['sharpe_mean'] != 0 else 0

    return_30d_improvement = (rot_30d['return'] - baseline['return_mean']) / baseline['return_mean'] * 100 if baseline['return_mean'] != 0 else 0
    return_60d_improvement = (rot_60d['return'] - baseline['return_mean']) / baseline['return_mean'] * 100 if baseline['return_mean'] != 0 else 0

    # 生成报告内容
    report = f"""# ETF轮动策略 vs 固定池策略对比实验报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 执行摘要

本实验对比了**定期重新筛选ETF池（轮动策略）**与**固定池策略**的表现，回答核心问题：

**动态轮动能否提升风险调整后收益？**

### 结论

"""

    # 根据实验结果写结论
    if sharpe_30d_improvement > 5 or sharpe_60d_improvement > 5:
        best_period = '30天' if sharpe_30d_improvement > sharpe_60d_improvement else '60天'
        best_improvement = max(sharpe_30d_improvement, sharpe_60d_improvement)
        report += f"""✅ **轮动策略优于固定池**

- **最优轮动周期**: {best_period}
- **夏普比率提升**: {best_improvement:+.1f}%
- **推荐**: 采用{best_period}轮动周期

"""
    elif sharpe_30d_improvement < -5 or sharpe_60d_improvement < -5:
        report += f"""❌ **轮动策略劣于固定池**

- **夏普比率下降**: 30天({sharpe_30d_improvement:+.1f}%), 60天({sharpe_60d_improvement:+.1f}%)
- **可能原因**: 轮动成本过高、市场不适合频繁调整、或筛选指标不稳定
- **推荐**: 使用固定池策略

"""
    else:
        report += f"""⚖️ **轮动策略与固定池表现相当**

- **夏普比率变化**: 30天({sharpe_30d_improvement:+.1f}%), 60天({sharpe_60d_improvement:+.1f}%)
- **差异不显著**: 轮动带来的收益提升被交易成本抵消
- **推荐**: 优先使用固定池（简单且成本更低）

"""

    report += f"""
---

## 实验设计

### 实验矩阵

| 场景ID | 类型 | ETF池 | 轮动周期 | 再平衡模式 | 交易成本 |
|--------|------|-------|----------|-----------|---------|
| Baseline | 对照组 | 固定池（2023-11-01时点top-20） | - | - | 0.3%单边 |
| Rotation-30d | 实验组1 | 动态轮动 | 30天 | 增量调整 | 0.3%单边 |
| Rotation-60d | 实验组2 | 动态轮动 | 60天 | 增量调整 | 0.3%单边 |

### 共同配置

- **时间跨度**: 2023-11-01 至 2025-11-12（2年）
- **策略**: KAMA Baseline（无过滤器、无止损保护）
- **初始资金**: 100,000元
- **ETF筛选规则**: 一阶段过滤（流动性≥5万元，上市≥60天）+ 纯评分排序取top-20

---

## 详细结果

### 1. 核心指标对比

| 指标 | Baseline<br/>(固定池) | Rotation-30d<br/>(30天轮动) | Rotation-60d<br/>(60天轮动) |
|------|------------|--------------|--------------|
| **夏普比率** | {baseline['sharpe_mean']:.2f} | {rot_30d['sharpe']:.2f} ({sharpe_30d_improvement:+.1f}%) | {rot_60d['sharpe']:.2f} ({sharpe_60d_improvement:+.1f}%) |
| **总收益率** | {baseline['return_mean']:.2f}% | {rot_30d['return']:.2f}% ({return_30d_improvement:+.1f}%) | {rot_60d['return']:.2f}% ({return_60d_improvement:+.1f}%) |
| **最大回撤** | {baseline['max_dd_mean']:.2f}% | {rot_30d['max_dd']:.2f}% | {rot_60d['max_dd']:.2f}% |
| **胜率** | {baseline['win_rate']:.1f}% | {rot_30d['win_rate'] if rot_30d['win_rate'] else 'N/A'} | {rot_60d['win_rate'] if rot_60d['win_rate'] else 'N/A'} |
| **交易次数** | - | {rot_30d['n_trades']} | {rot_60d['n_trades']} |

**说明**:
- Baseline采用20只ETF等权持仓，指标为平均值
- Rotation采用虚拟ETF合成法，指标为单一策略表现

### 2. 稳定性分析

| 指标 | Baseline | 说明 |
|------|----------|------|
| 夏普比率中位数 | {baseline['sharpe_median']:.2f} | 中位数反映典型表现 |
| 夏普比率标准差 | {baseline['sharpe_std']:.2f} | 标准差反映稳定性 |
| 最差ETF回撤 | {baseline['max_dd_worst']:.2f}% | 风险分散效果 |

**轮动策略稳定性**: 无标的分散（单一虚拟ETF），风险集中度更高

### 3. 轮动成本分析

#### 30天轮动周期
"""

    if metadata_30d:
        report += f"""
- **轮动次数**: {metadata_30d.get('n_rotations', 'N/A')}
- **平均换手率**: {metadata_30d.get('avg_turnover_rate', 0)*100:.1f}%
- **平均保留数量**: {metadata_30d.get('avg_overlap', 'N/A')} 只
- **累计轮动成本**: {metadata_30d.get('total_rotation_cost', 'N/A')}
"""
    else:
        report += "\n*元数据未找到*\n"

    report += "\n#### 60天轮动周期\n"

    if metadata_60d:
        report += f"""
- **轮动次数**: {metadata_60d.get('n_rotations', 'N/A')}
- **平均换手率**: {metadata_60d.get('avg_turnover_rate', 0)*100:.1f}%
- **平均保留数量**: {metadata_60d.get('avg_overlap', 'N/A')} 只
- **累计轮动成本**: {metadata_60d.get('total_rotation_cost', 'N/A')}
"""
    else:
        report += "\n*元数据未找到*\n"

    report += f"""
### 4. 市场环境分析

*(需要进一步分析不同市场阶段的表现)*

- 上涨市场：固定池 vs 轮动策略
- 下跌市场：固定池 vs 轮动策略
- 震荡市场：固定池 vs 轮动策略

---

## 结论与建议

### 核心发现

"""

    if sharpe_30d_improvement > 5:
        report += f"""
1. **轮动策略显著优于固定池** (夏普比率+{max(sharpe_30d_improvement, sharpe_60d_improvement):.1f}%)
2. {'30天' if sharpe_30d_improvement > sharpe_60d_improvement else '60天'}轮动周期为最优选择
3. 动态调整ETF池能够捕捉市场轮动机会
"""
    elif sharpe_30d_improvement < -5:
        report += f"""
1. **固定池优于轮动策略** (夏普比率差异: 30天{sharpe_30d_improvement:+.1f}%, 60天{sharpe_60d_improvement:+.1f}%)
2. 轮动成本侵蚀了策略收益
3. 当前筛选指标可能不适合短期轮动
"""
    else:
        report += f"""
1. **两种策略表现相当** (夏普比率差异<5%)
2. 轮动带来的边际收益被交易成本抵消
3. 从简单性和成本角度，优先选择固定池
"""

    report += f"""

### 最优配置推荐

"""

    if sharpe_30d_improvement > 5 or sharpe_60d_improvement > 5:
        best_period = '30天' if sharpe_30d_improvement > sharpe_60d_improvement else '60天'
        report += f"""
**推荐使用轮动策略**:
- 轮动周期: {best_period}
- 再平衡模式: 增量调整（节省成本）
- 预期夏普比率: {rot_30d['sharpe'] if sharpe_30d_improvement > sharpe_60d_improvement else rot_60d['sharpe']:.2f}
"""
    else:
        report += f"""
**推荐使用固定池策略**:
- 池子来源: 定期（如每年）重新筛选即可
- 优势: 简单、成本低、稳定性好
- 预期夏普比率: {baseline['sharpe_mean']:.2f}
"""

    report += f"""

### 适用场景与限制

**轮动策略适用于**:
- 市场风格轮动明显
- 行业/板块周期性强
- 有较强的动量/反转效应

**固定池适用于**:
- 市场相对稳定
- 交易成本敏感
- 追求简单策略

### 后续研究方向

1. **优化轮动周期**: 测试15天、90天等其他周期
2. **改进筛选指标**: 加入市场环境判断（牛熊市分离）
3. **动态轮动频率**: 根据市场波动率调整轮动频率
4. **成本优化**: 研究更低成本的再平衡方法

---

## 附录

### A. 数据文件清单

**固定池数据**:
- `results/rotation_fixed_pool/baseline_pool.csv`

**轮动表数据**:
- `results/rotation_schedules/rotation_30d_full.json`
- `results/rotation_schedules/rotation_60d_full.json`

**回测结果**:
- `experiment/etf/rotation_comparison/results/baseline/aggregate_results.csv`
- `experiment/etf/rotation_comparison/results/rotation_30d/backtest_results.csv`
- `experiment/etf/rotation_comparison/results/rotation_60d/backtest_results.csv`

### B. 复现实验

```bash
# Step 1: 生成固定池
python scripts/generate_fixed_baseline_pool.py

# Step 2: 生成轮动表
python scripts/prepare_rotation_schedule.py \\
  --start-date 2023-11-01 --end-date 2025-11-12 \\
  --rotation-period 30 --pool-size 20 \\
  --data-dir data/chinese_etf \\
  --output results/rotation_schedules/rotation_30d_full.json

python scripts/prepare_rotation_schedule.py \\
  --start-date 2023-11-01 --end-date 2025-11-12 \\
  --rotation-period 60 --pool-size 20 \\
  --data-dir data/chinese_etf \\
  --output results/rotation_schedules/rotation_60d_full.json

# Step 3: 执行对比实验
python experiment/etf/rotation_comparison/run_comparison.py --execute all
```

---

**报告结束**
"""

    # 写入报告
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📄 对比报告已生成: {report_path}")
    return report_path


def main():
    """主函数"""
    args = parse_arguments()

    print("=" * 80)
    print(" ETF轮动策略 vs 固定池策略对比实验")
    print("=" * 80)
    print(f"\n⚙️  配置:")
    print(f"  执行场景: {args.execute}")
    print(f"  分析模式: {'是' if args.analyze else '否'}")
    print(f"  试运行: {'是' if args.dry_run else '否'}")
    print(f"  详细日志: {'是' if args.verbose else '否'}")

    # 执行回测
    if args.execute != 'none':
        print(f"\n{'='*80}")
        print(" 步骤 1/2: 执行回测")
        print(f"{'='*80}")

        scenarios_to_run = []
        if args.execute == 'all':
            scenarios_to_run = ['baseline', 'rotation_30d', 'rotation_60d']
        else:
            scenarios_to_run = [args.execute]

        success_count = 0
        for scenario_id in scenarios_to_run:
            config = EXPERIMENT_CONFIG[scenario_id]

            if config['type'] == 'fixed':
                success = run_fixed_pool_backtest(config, args.verbose, args.dry_run)
            else:
                success = run_rotation_backtest(config, args.verbose, args.dry_run)

            if success:
                success_count += 1

        print(f"\n{'='*80}")
        print(f"回测执行完成: {success_count}/{len(scenarios_to_run)} 场景成功")
        print(f"{'='*80}")

        if success_count < len(scenarios_to_run) and not args.dry_run:
            print(f"\n⚠️  警告: 部分场景执行失败，请检查错误信息")
            if not args.analyze:
                return 1

    # 分析结果
    if args.analyze or args.execute != 'none':
        print(f"\n{'='*80}")
        print(" 步骤 2/2: 分析结果")
        print(f"{'='*80}")

        if args.dry_run:
            print("\n[DRY RUN] 跳过结果分析")
            return 0

        try:
            print("\n📊 加载实验结果...")
            baseline_df = load_baseline_results()
            rotation_30d_df, metadata_30d = load_rotation_results('30d')
            rotation_60d_df, metadata_60d = load_rotation_results('60d')

            print(f"  ✅ 对照组: {len(baseline_df)} 只ETF")
            print(f"  ✅ 30天轮动: 1 个虚拟ETF")
            print(f"  ✅ 60天轮动: 1 个虚拟ETF")

            print("\n🔬 计算统计指标...")
            stats = calculate_statistics(baseline_df, rotation_30d_df, rotation_60d_df)

            print("\n📝 生成对比报告...")
            report_path = generate_comparison_report(stats, metadata_30d, metadata_60d)

            print(f"\n{'='*80}")
            print(" 实验完成！")
            print(f"{'='*80}")
            print(f"\n查看完整报告: {report_path}")

        except FileNotFoundError as e:
            print(f"\n❌ 错误: {e}")
            print(f"   请确保所有场景的回测已完成")
            return 1
        except Exception as e:
            print(f"\n❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
