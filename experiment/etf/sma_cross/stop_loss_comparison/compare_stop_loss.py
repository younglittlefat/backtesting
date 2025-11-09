#!/usr/bin/env python3
"""
止损策略对比实验

比较4种策略的回测表现：
1. base: SmaCross 基准策略（无止损）
2. trailing_stop: 跟踪止损策略（参数：3%, 5%, 7%）
3. loss_protection: 连续止损保护策略（参数网格：max_losses x pause_bars）
4. combined: 组合策略（trailing_stop_pct=5%, max_losses=3, pause_bars=10）

作者: Claude Code
日期: 2025-11-09
"""

import os
import sys
import pandas as pd
import argparse
from pathlib import Path
from typing import List, Dict
from backtesting import Backtest
import warnings
warnings.filterwarnings('ignore')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from strategies.sma_cross import SmaCross
from strategies.stop_loss_strategies import (
    SmaCrossWithTrailingStop,
    SmaCrossWithLossProtection,
    SmaCrossWithFullRiskControl
)


def load_etf_data(data_dir: str, ts_code: str) -> pd.DataFrame:
    """
    加载 ETF 数据

    Args:
        data_dir: 数据目录
        ts_code: 标的代码（如 159001.SZ）

    Returns:
        OHLCV DataFrame
    """
    # 尝试两种路径：直接路径和带etf子目录的路径
    csv_path = Path(data_dir) / f"{ts_code}.csv"
    if not csv_path.exists():
        csv_path = Path(data_dir) / "etf" / f"{ts_code}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {csv_path}")

    # 读取CSV数据
    df = pd.read_csv(csv_path)

    # 检查必要的列
    required_cols = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"缺少必要列: {missing_cols}")

    # 转换日期列为 datetime
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('trade_date')

    # 重命名列为 backtesting.py 格式
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })

    # 选择需要的列
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

    # 按日期升序排列
    df = df.sort_index()

    return df


def run_base_strategy(data: pd.DataFrame, ts_code: str, output_dir: str) -> Dict:
    """运行基准策略（无止损）"""
    print(f"\n{'='*70}")
    print(f"策略: Base (无止损)")
    print(f"标的: {ts_code}")
    print(f"{'='*70}")

    bt = Backtest(data, SmaCross, cash=10000, commission=0.002)
    stats = bt.run()

    # 提取关键指标
    result = {
        'strategy': 'base',
        'ts_code': ts_code,
        'params': 'n1=10, n2=20',
        'return_pct': stats['Return [%]'],
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'win_rate_pct': stats['Win Rate [%]'],
        'num_trades': stats['# Trades'],
        'avg_trade_duration': stats['Avg. Trade Duration']
    }

    print(f"收益率: {result['return_pct']:.2f}%")
    print(f"夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"胜率: {result['win_rate_pct']:.2f}%")
    print(f"交易次数: {result['num_trades']}")

    return result


def run_trailing_stop(data: pd.DataFrame, ts_code: str, output_dir: str) -> List[Dict]:
    """运行跟踪止损策略（3个参数组合）"""
    print(f"\n{'='*70}")
    print(f"策略: Trailing Stop (跟踪止损)")
    print(f"标的: {ts_code}")
    print(f"{'='*70}")

    trailing_stop_pcts = [0.03, 0.05, 0.07]
    results = []

    for pct in trailing_stop_pcts:
        print(f"\n--- 参数: trailing_stop_pct={pct*100:.0f}% ---")

        bt = Backtest(data, SmaCrossWithTrailingStop, cash=10000, commission=0.002)
        stats = bt.run(trailing_stop_pct=pct)

        result = {
            'strategy': 'trailing_stop',
            'ts_code': ts_code,
            'params': f'trailing_stop_pct={pct}',
            'return_pct': stats['Return [%]'],
            'sharpe_ratio': stats['Sharpe Ratio'],
            'max_drawdown_pct': stats['Max. Drawdown [%]'],
            'win_rate_pct': stats['Win Rate [%]'],
            'num_trades': stats['# Trades'],
            'avg_trade_duration': stats['Avg. Trade Duration']
        }

        print(f"收益率: {result['return_pct']:.2f}%")
        print(f"夏普比率: {result['sharpe_ratio']:.2f}")
        print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
        print(f"胜率: {result['win_rate_pct']:.2f}%")
        print(f"交易次数: {result['num_trades']}")

        results.append(result)

    return results


def run_loss_protection(data: pd.DataFrame, ts_code: str, output_dir: str) -> List[Dict]:
    """运行连续止损保护策略（9个参数组合）"""
    print(f"\n{'='*70}")
    print(f"策略: Loss Protection (连续止损保护)")
    print(f"标的: {ts_code}")
    print(f"{'='*70}")

    max_losses_range = [2, 3, 4]
    pause_bars_range = [5, 10, 15]
    results = []

    for max_losses in max_losses_range:
        for pause_bars in pause_bars_range:
            print(f"\n--- 参数: max_losses={max_losses}, pause_bars={pause_bars} ---")

            bt = Backtest(data, SmaCrossWithLossProtection, cash=10000, commission=0.002)
            stats = bt.run(max_consecutive_losses=max_losses, pause_bars=pause_bars)

            result = {
                'strategy': 'loss_protection',
                'ts_code': ts_code,
                'params': f'max_losses={max_losses}, pause_bars={pause_bars}',
                'return_pct': stats['Return [%]'],
                'sharpe_ratio': stats['Sharpe Ratio'],
                'max_drawdown_pct': stats['Max. Drawdown [%]'],
                'win_rate_pct': stats['Win Rate [%]'],
                'num_trades': stats['# Trades'],
                'avg_trade_duration': stats['Avg. Trade Duration']
            }

            print(f"收益率: {result['return_pct']:.2f}%")
            print(f"夏普比率: {result['sharpe_ratio']:.2f}")
            print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
            print(f"胜率: {result['win_rate_pct']:.2f}%")
            print(f"交易次数: {result['num_trades']}")

            results.append(result)

    return results


def run_combined(data: pd.DataFrame, ts_code: str, output_dir: str) -> Dict:
    """运行组合策略（最优参数组合）"""
    print(f"\n{'='*70}")
    print(f"策略: Combined (组合策略)")
    print(f"标的: {ts_code}")
    print(f"{'='*70}")

    # 使用推荐的最优参数
    trailing_stop_pct = 0.05
    max_consecutive_losses = 3
    pause_bars = 10

    print(f"\n参数: trailing_stop_pct={trailing_stop_pct*100:.0f}%, "
          f"max_losses={max_consecutive_losses}, pause_bars={pause_bars}")

    bt = Backtest(data, SmaCrossWithFullRiskControl, cash=10000, commission=0.002)
    stats = bt.run(
        trailing_stop_pct=trailing_stop_pct,
        max_consecutive_losses=max_consecutive_losses,
        pause_bars=pause_bars
    )

    result = {
        'strategy': 'combined',
        'ts_code': ts_code,
        'params': f'trailing_stop_pct={trailing_stop_pct}, max_losses={max_consecutive_losses}, pause_bars={pause_bars}',
        'return_pct': stats['Return [%]'],
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'win_rate_pct': stats['Win Rate [%]'],
        'num_trades': stats['# Trades'],
        'avg_trade_duration': stats['Avg. Trade Duration']
    }

    print(f"收益率: {result['return_pct']:.2f}%")
    print(f"夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"胜率: {result['win_rate_pct']:.2f}%")
    print(f"交易次数: {result['num_trades']}")

    return result


def load_stock_list(csv_file: str) -> List[str]:
    """从CSV文件加载股票列表"""
    df = pd.read_csv(csv_file)
    if 'ts_code' not in df.columns:
        raise ValueError(f"CSV文件缺少 'ts_code' 列: {csv_file}")
    return df['ts_code'].tolist()


def main():
    parser = argparse.ArgumentParser(
        description='止损策略对比实验',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--stock-list', type=str, required=True,
                        help='股票列表CSV文件路径（需包含ts_code列）')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='数据目录路径')
    parser.add_argument('--output-dir', type=str,
                        default='experiment/etf/sma_cross/stop_loss_comparison',
                        help='输出目录（默认：当前目录）')

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载股票列表
    print(f"\n加载股票列表: {args.stock_list}")
    stock_list = load_stock_list(args.stock_list)
    print(f"共 {len(stock_list)} 只标的")

    # 存储所有结果
    all_results = []

    # 对每个标的运行测试
    for ts_code in stock_list:
        print(f"\n\n{'#'*70}")
        print(f"# 标的: {ts_code}")
        print(f"{'#'*70}")

        try:
            # 加载数据
            data = load_etf_data(args.data_dir, ts_code)
            print(f"数据范围: {data.index[0]} 至 {data.index[-1]}")
            print(f"数据量: {len(data)} 条")

            # 1. 基准策略
            result_base = run_base_strategy(data, ts_code, args.output_dir)
            all_results.append(result_base)

            # 2. 跟踪止损策略
            results_trailing = run_trailing_stop(data, ts_code, args.output_dir)
            all_results.extend(results_trailing)

            # 3. 连续止损保护策略
            results_loss = run_loss_protection(data, ts_code, args.output_dir)
            all_results.extend(results_loss)

            # 4. 组合策略
            result_combined = run_combined(data, ts_code, args.output_dir)
            all_results.append(result_combined)

        except Exception as e:
            print(f"错误: {ts_code} - {e}")
            continue

    # 保存结果到CSV
    results_df = pd.DataFrame(all_results)
    output_csv = output_dir / 'comparison_results.csv'
    results_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n\n{'='*70}")
    print(f"结果已保存到: {output_csv}")
    print(f"{'='*70}")

    # 检查是否有有效结果
    if results_df.empty:
        print(f"\n\n{'='*70}")
        print("⚠️  没有成功的回测结果，请检查数据文件和标的代码")
        print(f"{'='*70}")
        return

    # 打印统计汇总
    print(f"\n\n{'='*70}")
    print("策略表现汇总")
    print(f"{'='*70}")

    summary = results_df.groupby('strategy').agg({
        'return_pct': ['mean', 'std', 'min', 'max'],
        'sharpe_ratio': ['mean', 'std'],
        'max_drawdown_pct': ['mean', 'std'],
        'win_rate_pct': ['mean', 'std'],
        'num_trades': ['mean', 'std']
    }).round(2)

    print(summary)

    # 保存汇总统计
    summary_csv = output_dir / 'summary_statistics.csv'
    summary.to_csv(summary_csv, encoding='utf-8-sig')
    print(f"\n汇总统计已保存到: {summary_csv}")


if __name__ == '__main__':
    main()
