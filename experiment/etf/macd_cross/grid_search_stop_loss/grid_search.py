#!/usr/bin/env python3
"""
MACD策略止损超参网格搜索实验

使用Python API直接调用方式，在20只ETF上测试不同止损参数组合的效果。

实验方案：
1. Baseline: 无止损对照组
2. Loss Protection: 连续止损保护 (16种参数组合)
3. Trailing Stop: 跟踪止损 (4种参数组合)
4. Combined: 组合止损 (27种参数组合)

作者: Claude Code
日期: 2025-11-09
"""

import os
import sys
import pandas as pd
import numpy as np
import argparse
import warnings
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from backtesting import Backtest
import itertools
from tqdm import tqdm

warnings.filterwarnings('ignore')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from strategies.macd_cross import MacdCross


def load_etf_data(data_dir: str, ts_code: str) -> pd.DataFrame:
    """
    加载 ETF 数据

    Args:
        data_dir: 数据目录
        ts_code: 标的代码（如 159001.SZ）

    Returns:
        OHLCV DataFrame
    """
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


def load_stock_list(csv_file: str) -> List[str]:
    """从CSV文件加载股票列表"""
    df = pd.read_csv(csv_file)
    if 'ts_code' not in df.columns:
        raise ValueError(f"CSV文件缺少 'ts_code' 列: {csv_file}")
    return df['ts_code'].tolist()


def run_backtest_with_optimize(
    data: pd.DataFrame,
    stop_loss_config: Dict,
    verbose: bool = False
) -> Optional[Dict]:
    """
    使用指定止损参数运行回测（启用MACD参数优化）

    Args:
        data: OHLCV数据
        stop_loss_config: 止损配置字典
            {
                'enable_loss_protection': bool,
                'max_consecutive_losses': int,
                'pause_bars': int,
                'enable_trailing_stop': bool,
                'trailing_stop_pct': float,
            }
        verbose: 是否输出详细日志

    Returns:
        dict: 回测统计结果，失败返回None
    """
    try:
        bt = Backtest(data, MacdCross, cash=10000, commission=0.002)

        # 构建优化参数
        optimize_params = {
            'fast_period': range(8, 21, 2),      # 快速EMA: 8, 10, 12, ..., 20
            'slow_period': range(20, 41, 2),     # 慢速EMA: 20, 22, 24, ..., 40
            'signal_period': range(6, 15, 2),    # 信号线: 6, 8, 10, ..., 14
        }

        # 添加止损参数（作为固定值，不参与优化）
        if stop_loss_config.get('enable_loss_protection', False):
            optimize_params['enable_loss_protection'] = [True]
            optimize_params['max_consecutive_losses'] = [stop_loss_config['max_consecutive_losses']]
            optimize_params['pause_bars'] = [stop_loss_config['pause_bars']]
        else:
            optimize_params['enable_loss_protection'] = [False]

        if stop_loss_config.get('enable_trailing_stop', False):
            optimize_params['enable_trailing_stop'] = [True]
            optimize_params['trailing_stop_pct'] = [stop_loss_config['trailing_stop_pct']]
        else:
            optimize_params['enable_trailing_stop'] = [False]

        # 运行优化
        stats = bt.optimize(
            **optimize_params,
            maximize='Sharpe Ratio',
            constraint=lambda p: p.fast_period < p.slow_period
        )

        return stats

    except Exception as e:
        if verbose:
            print(f"  ⚠️  回测失败: {e}")
        return None


def extract_stats(stats, ts_code: str, strategy: str, stop_loss_config: Dict) -> Dict:
    """
    从回测结果中提取关键指标

    Args:
        stats: 回测统计结果
        ts_code: 标的代码
        strategy: 策略类型（baseline, loss_protection, trailing_stop, combined）
        stop_loss_config: 止损配置

    Returns:
        dict: 提取的指标字典
    """
    result = {
        'ts_code': ts_code,
        'strategy': strategy,
        'return_pct': stats['Return [%]'],
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'win_rate_pct': stats['Win Rate [%]'],
        'num_trades': stats['# Trades'],
        'avg_trade_duration': str(stats['Avg. Trade Duration']),
        'exposure_time_pct': stats['Exposure Time [%]'],
        # 优化后的MACD参数
        'optimized_fast_period': stats._strategy.fast_period,
        'optimized_slow_period': stats._strategy.slow_period,
        'optimized_signal_period': stats._strategy.signal_period,
    }

    # 添加止损参数
    if strategy == 'loss_protection' or strategy == 'combined':
        result['max_consecutive_losses'] = stop_loss_config.get('max_consecutive_losses')
        result['pause_bars'] = stop_loss_config.get('pause_bars')
    else:
        result['max_consecutive_losses'] = None
        result['pause_bars'] = None

    if strategy == 'trailing_stop' or strategy == 'combined':
        result['trailing_stop_pct'] = stop_loss_config.get('trailing_stop_pct')
    else:
        result['trailing_stop_pct'] = None

    return result


def run_baseline(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    运行Baseline实验（无止损对照组）

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 1: Baseline（无止损对照组）")
    print(f"{'='*70}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"预计耗时: ~5-10分钟")
    print()

    results = []
    stop_loss_config = {
        'enable_loss_protection': False,
        'enable_trailing_stop': False,
    }

    for ts_code in tqdm(stock_list, desc="Baseline回测"):
        try:
            data = load_etf_data(data_dir, ts_code)
            stats = run_backtest_with_optimize(data, stop_loss_config, verbose=False)

            if stats is not None:
                result = extract_stats(stats, ts_code, 'baseline', stop_loss_config)
                results.append(result)

        except Exception as e:
            print(f"  ⚠️  {ts_code}: {e}")
            continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'results_baseline.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Baseline完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{len(stock_list)}")

    if len(results) > 0:
        print(f"\n   平均夏普比率: {df['sharpe_ratio'].mean():.2f}")
        print(f"   平均收益率: {df['return_pct'].mean():.2f}%")
        print(f"   平均最大回撤: {df['max_drawdown_pct'].mean():.2f}%")

    return df


def run_loss_protection_grid(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    运行连续止损保护网格搜索

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 2: Loss Protection（连续止损保护网格搜索）")
    print(f"{'='*70}")

    # 定义网格
    max_losses_range = [2, 3, 4, 5]
    pause_bars_range = [5, 10, 15, 20]

    total_combinations = len(max_losses_range) * len(pause_bars_range)
    total_tests = total_combinations * len(stock_list)

    print(f"参数组合: {total_combinations} (max_losses × pause_bars)")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~2-3小时")
    print()

    results = []

    # 生成所有参数组合
    param_combinations = list(itertools.product(max_losses_range, pause_bars_range))

    # 使用嵌套进度条
    pbar_combinations = tqdm(param_combinations, desc="参数组合", position=0)

    for max_losses, pause_bars in pbar_combinations:
        pbar_combinations.set_description(f"Loss Protection (losses={max_losses}, pause={pause_bars})")

        stop_loss_config = {
            'enable_loss_protection': True,
            'max_consecutive_losses': max_losses,
            'pause_bars': pause_bars,
            'enable_trailing_stop': False,
        }

        pbar_stocks = tqdm(stock_list, desc="  标的", position=1, leave=False)
        for ts_code in pbar_stocks:
            try:
                data = load_etf_data(data_dir, ts_code)
                stats = run_backtest_with_optimize(data, stop_loss_config, verbose=False)

                if stats is not None:
                    result = extract_stats(stats, ts_code, 'loss_protection', stop_loss_config)
                    results.append(result)

            except Exception as e:
                continue

        pbar_stocks.close()

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'results_loss_protection.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Loss Protection完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    if len(results) > 0:
        # 找出最佳参数组合
        avg_by_params = df.groupby(['max_consecutive_losses', 'pause_bars'])['sharpe_ratio'].mean()
        best_params = avg_by_params.idxmax()
        best_sharpe = avg_by_params.max()

        print(f"\n   最佳参数组合: max_losses={best_params[0]}, pause_bars={best_params[1]}")
        print(f"   平均夏普比率: {best_sharpe:.2f}")

    return df


def run_trailing_stop_grid(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    运行跟踪止损网格搜索

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 3: Trailing Stop（跟踪止损网格搜索）")
    print(f"{'='*70}")

    # 定义网格
    trailing_stop_pcts = [0.03, 0.05, 0.07, 0.10]

    total_combinations = len(trailing_stop_pcts)
    total_tests = total_combinations * len(stock_list)

    print(f"参数组合: {total_combinations}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~30-45分钟")
    print()

    results = []

    pbar_combinations = tqdm(trailing_stop_pcts, desc="参数组合", position=0)

    for pct in pbar_combinations:
        pbar_combinations.set_description(f"Trailing Stop (pct={pct*100:.0f}%)")

        stop_loss_config = {
            'enable_loss_protection': False,
            'enable_trailing_stop': True,
            'trailing_stop_pct': pct,
        }

        pbar_stocks = tqdm(stock_list, desc="  标的", position=1, leave=False)
        for ts_code in pbar_stocks:
            try:
                data = load_etf_data(data_dir, ts_code)
                stats = run_backtest_with_optimize(data, stop_loss_config, verbose=False)

                if stats is not None:
                    result = extract_stats(stats, ts_code, 'trailing_stop', stop_loss_config)
                    results.append(result)

            except Exception as e:
                continue

        pbar_stocks.close()

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'results_trailing_stop.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Trailing Stop完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    if len(results) > 0:
        avg_by_params = df.groupby('trailing_stop_pct')['sharpe_ratio'].mean()
        best_pct = avg_by_params.idxmax()
        best_sharpe = avg_by_params.max()

        print(f"\n   最佳参数: trailing_stop_pct={best_pct*100:.0f}%")
        print(f"   平均夏普比率: {best_sharpe:.2f}")

    return df


def run_combined_grid(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    运行组合止损网格搜索

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 4: Combined（组合止损网格搜索）")
    print(f"{'='*70}")

    # 定义网格（相比Loss Protection和Trailing Stop，组合方案的网格更小）
    max_losses_range = [2, 3, 4]
    pause_bars_range = [5, 10, 15]
    trailing_stop_pcts = [0.03, 0.05, 0.07]

    total_combinations = len(max_losses_range) * len(pause_bars_range) * len(trailing_stop_pcts)
    total_tests = total_combinations * len(stock_list)

    print(f"参数组合: {total_combinations} (max_losses × pause_bars × trailing_stop_pct)")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~3-4小时")
    print()

    results = []

    # 生成所有参数组合
    param_combinations = list(itertools.product(max_losses_range, pause_bars_range, trailing_stop_pcts))

    pbar_combinations = tqdm(param_combinations, desc="参数组合", position=0)

    for max_losses, pause_bars, pct in pbar_combinations:
        pbar_combinations.set_description(f"Combined (losses={max_losses}, pause={pause_bars}, pct={pct*100:.0f}%)")

        stop_loss_config = {
            'enable_loss_protection': True,
            'max_consecutive_losses': max_losses,
            'pause_bars': pause_bars,
            'enable_trailing_stop': True,
            'trailing_stop_pct': pct,
        }

        pbar_stocks = tqdm(stock_list, desc="  标的", position=1, leave=False)
        for ts_code in pbar_stocks:
            try:
                data = load_etf_data(data_dir, ts_code)
                stats = run_backtest_with_optimize(data, stop_loss_config, verbose=False)

                if stats is not None:
                    result = extract_stats(stats, ts_code, 'combined', stop_loss_config)
                    results.append(result)

            except Exception as e:
                continue

        pbar_stocks.close()

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'results_combined.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Combined完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    if len(results) > 0:
        avg_by_params = df.groupby(['max_consecutive_losses', 'pause_bars', 'trailing_stop_pct'])['sharpe_ratio'].mean()
        best_params = avg_by_params.idxmax()
        best_sharpe = avg_by_params.max()

        print(f"\n   最佳参数组合: max_losses={best_params[0]}, pause_bars={best_params[1]}, trailing_stop_pct={best_params[2]*100:.0f}%")
        print(f"   平均夏普比率: {best_sharpe:.2f}")

    return df


def generate_summary_report(
    df_baseline: pd.DataFrame,
    df_loss_protection: pd.DataFrame,
    df_trailing_stop: pd.DataFrame,
    df_combined: pd.DataFrame,
    output_dir: Path
) -> None:
    """
    生成汇总报告

    Args:
        df_baseline: Baseline结果
        df_loss_protection: Loss Protection结果
        df_trailing_stop: Trailing Stop结果
        df_combined: Combined结果
        output_dir: 输出目录
    """
    print(f"\n{'='*70}")
    print("生成汇总报告")
    print(f"{'='*70}")

    # 合并所有结果
    all_results = pd.concat([df_baseline, df_loss_protection, df_trailing_stop, df_combined], ignore_index=True)

    # 保存完整结果
    all_results_csv = output_dir / 'all_results.csv'
    all_results.to_csv(all_results_csv, index=False, encoding='utf-8-sig')
    print(f"✅ 完整结果已保存: {all_results_csv}")

    # 按策略汇总统计
    summary_stats = all_results.groupby('strategy').agg({
        'return_pct': ['mean', 'std', 'min', 'max'],
        'sharpe_ratio': ['mean', 'std', 'min', 'max'],
        'max_drawdown_pct': ['mean', 'std', 'min', 'max'],
        'win_rate_pct': ['mean', 'std', 'min', 'max'],
        'num_trades': ['mean', 'std'],
    }).round(2)

    # 保存汇总统计
    summary_csv = output_dir / 'summary_statistics.csv'
    summary_stats.to_csv(summary_csv, encoding='utf-8-sig')
    print(f"✅ 汇总统计已保存: {summary_csv}")

    # 打印汇总统计
    print("\n策略表现汇总:")
    print(summary_stats)

    # 找出各策略的最佳表现
    print(f"\n{'='*70}")
    print("各策略最佳表现（按平均夏普比率）")
    print(f"{'='*70}")

    for strategy in ['baseline', 'loss_protection', 'trailing_stop', 'combined']:
        df_strategy = all_results[all_results['strategy'] == strategy]

        if len(df_strategy) == 0:
            continue

        avg_sharpe = df_strategy['sharpe_ratio'].mean()
        avg_return = df_strategy['return_pct'].mean()
        avg_drawdown = df_strategy['max_drawdown_pct'].mean()
        avg_winrate = df_strategy['win_rate_pct'].mean()

        print(f"\n{strategy.upper()}:")
        print(f"  平均夏普比率: {avg_sharpe:.2f}")
        print(f"  平均收益率: {avg_return:.2f}%")
        print(f"  平均最大回撤: {avg_drawdown:.2f}%")
        print(f"  平均胜率: {avg_winrate:.2f}%")

        # 对于有参数的策略，显示最佳参数组合
        if strategy == 'loss_protection':
            best_params = df_strategy.groupby(['max_consecutive_losses', 'pause_bars'])['sharpe_ratio'].mean().idxmax()
            print(f"  推荐参数: max_consecutive_losses={best_params[0]}, pause_bars={best_params[1]}")
        elif strategy == 'trailing_stop':
            best_pct = df_strategy.groupby('trailing_stop_pct')['sharpe_ratio'].mean().idxmax()
            print(f"  推荐参数: trailing_stop_pct={best_pct*100:.0f}%")
        elif strategy == 'combined':
            best_params = df_strategy.groupby(['max_consecutive_losses', 'pause_bars', 'trailing_stop_pct'])['sharpe_ratio'].mean().idxmax()
            print(f"  推荐参数: max_consecutive_losses={best_params[0]}, pause_bars={best_params[1]}, trailing_stop_pct={best_params[2]*100:.0f}%")


def main():
    parser = argparse.ArgumentParser(
        description='MACD策略止损超参网格搜索实验',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--stock-list', type=str, required=True,
                        help='股票列表CSV文件路径（需包含ts_code列）')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='数据目录路径')
    parser.add_argument('--output-dir', type=str,
                        default='experiment/etf/macd_cross/grid_search_stop_loss',
                        help='输出目录（默认：experiment/etf/macd_cross/grid_search_stop_loss）')
    parser.add_argument('--phases', type=str, default='all',
                        choices=['all', 'baseline', 'loss', 'trailing', 'combined'],
                        help='要运行的实验阶段（默认：all）')

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载股票列表
    print(f"\n{'='*70}")
    print("MACD策略止损超参网格搜索实验")
    print(f"{'='*70}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"股票列表: {args.stock_list}")
    print(f"数据目录: {args.data_dir}")
    print(f"输出目录: {output_dir}")
    print()

    stock_list = load_stock_list(args.stock_list)
    print(f"共加载 {len(stock_list)} 只标的")

    # 根据参数决定运行哪些阶段
    phases = args.phases

    df_baseline = pd.DataFrame()
    df_loss_protection = pd.DataFrame()
    df_trailing_stop = pd.DataFrame()
    df_combined = pd.DataFrame()

    # Phase 1: Baseline
    if phases in ['all', 'baseline']:
        df_baseline = run_baseline(stock_list, args.data_dir, output_dir)

    # Phase 2: Loss Protection
    if phases in ['all', 'loss']:
        df_loss_protection = run_loss_protection_grid(stock_list, args.data_dir, output_dir)

    # Phase 3: Trailing Stop
    if phases in ['all', 'trailing']:
        df_trailing_stop = run_trailing_stop_grid(stock_list, args.data_dir, output_dir)

    # Phase 4: Combined
    if phases in ['all', 'combined']:
        df_combined = run_combined_grid(stock_list, args.data_dir, output_dir)

    # 生成汇总报告
    if phases == 'all':
        generate_summary_report(
            df_baseline,
            df_loss_protection,
            df_trailing_stop,
            df_combined,
            output_dir
        )

    print(f"\n{'='*70}")
    print("实验完成！")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    print(f"\n所有结果已保存到: {output_dir}")
    print("\n下一步:")
    print("1. 查看汇总统计: summary_statistics.csv")
    print("2. 分析各方案结果: results_*.csv")
    print("3. 生成可视化图表: python generate_visualizations.py")


if __name__ == '__main__':
    main()
