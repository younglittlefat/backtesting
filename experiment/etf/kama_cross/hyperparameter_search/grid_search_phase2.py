#!/usr/bin/env python3
"""
KAMA策略Phase 2止损保护参数网格搜索实验

测试连续止损保护参数对KAMA策略的影响。

实验方案：
- Phase 2A: 最佳过滤器Baseline（无止损对照组）- 60次
  - baseline: 无过滤器
  - adx_only: ADX过滤器（Phase 1最佳单一过滤器）
  - adx_slope: ADX+Slope组合（Phase 1最佳双过滤器）
- Phase 2B: 止损保护参数网格搜索 - 960次
  - max_consecutive_losses: [2, 3, 4, 5]
  - pause_bars: [5, 10, 15, 20]
  - 16组合 × 3种过滤器 × 20标的 = 960次

总计: 1020次回测，预计耗时约2-3小时

作者: Claude Code
日期: 2025-11-11
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

from strategies.kama_cross import KamaCrossStrategy


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


def run_backtest_with_config(
    data: pd.DataFrame,
    filter_config: Dict,
    loss_protection_config: Dict,
    verbose: bool = False
) -> Optional[Dict]:
    """
    使用指定配置运行KAMA策略回测

    Args:
        data: OHLCV数据
        filter_config: 过滤器配置字典
        loss_protection_config: 止损保护配置字典
        verbose: 是否输出详细日志

    Returns:
        dict: 回测统计结果，失败返回None
    """
    try:
        bt = Backtest(data, KamaCrossStrategy, cash=10000, commission=0.002)

        # KAMA策略使用固定参数（不优化）
        params = {
            # KAMA核心参数（使用默认值）
            'kama_period': 20,
            'kama_fast': 2,
            'kama_slow': 30,
            # KAMA内置过滤器（始终启用）
            'enable_efficiency_filter': True,
            'min_efficiency_ratio': 0.3,
            'enable_slope_confirmation': True,
            'min_slope_periods': 3,
            # 通用过滤器（根据配置启用）
            'enable_adx_filter': filter_config.get('enable_adx_filter', False),
            'enable_volume_filter': filter_config.get('enable_volume_filter', False),
            'enable_slope_filter': filter_config.get('enable_slope_filter', False),
            'enable_confirm_filter': filter_config.get('enable_confirm_filter', False),
            # 止损保护配置
            'enable_loss_protection': loss_protection_config.get('enable_loss_protection', False),
            'max_consecutive_losses': loss_protection_config.get('max_consecutive_losses', 3),
            'pause_bars': loss_protection_config.get('pause_bars', 10),
        }

        # 运行回测（不优化）
        stats = bt.run(**params)

        return stats

    except Exception as e:
        if verbose:
            print(f"回测失败: {e}")
        return None


def extract_stats(
    stats: Dict,
    ts_code: str,
    config_name: str,
    filter_config: Dict,
    loss_protection_config: Dict
) -> Dict:
    """
    提取关键统计指标

    Args:
        stats: backtesting.py返回的stats对象
        ts_code: 标的代码
        config_name: 配置名称
        filter_config: 过滤器配置
        loss_protection_config: 止损保护配置

    Returns:
        dict: 扁平化的统计数据
    """
    # 提取性能指标
    result = {
        'ts_code': ts_code,
        'config_name': config_name,
        'return_pct': stats['Return [%]'],
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'win_rate_pct': stats['Win Rate [%]'],
        'num_trades': stats['# Trades'],
        'avg_trade_duration': stats['Avg. Trade Duration'],
        'exposure_time_pct': stats['Exposure Time [%]'],
    }

    # 添加过滤器配置
    result['enable_adx_filter'] = filter_config.get('enable_adx_filter', False)
    result['enable_volume_filter'] = filter_config.get('enable_volume_filter', False)
    result['enable_slope_filter'] = filter_config.get('enable_slope_filter', False)
    result['enable_confirm_filter'] = filter_config.get('enable_confirm_filter', False)

    # 添加止损保护配置
    result['enable_loss_protection'] = loss_protection_config.get('enable_loss_protection', False)
    result['max_consecutive_losses'] = loss_protection_config.get('max_consecutive_losses', 0)
    result['pause_bars'] = loss_protection_config.get('pause_bars', 0)

    return result


def run_phase_2a_baseline(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    Phase 2A: 最佳过滤器Baseline（无止损对照组）

    测试3种过滤器配置的基础表现（无止损保护）：
    - baseline: 无过滤器
    - adx_only: ADX过滤器（Phase 1最佳单一过滤器，夏普1.68）
    - adx_slope: ADX+Slope组合（Phase 1最佳双过滤器，回撤最优-4.38%）

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 2A: 最佳过滤器Baseline（无止损对照组）")
    print(f"{'='*70}")

    # 定义3种过滤器配置
    filter_configs = [
        ('baseline', {
            'enable_adx_filter': False,
            'enable_volume_filter': False,
            'enable_slope_filter': False,
        }),
        ('adx_only', {
            'enable_adx_filter': True,
            'enable_volume_filter': False,
            'enable_slope_filter': False,
        }),
        ('adx_slope', {
            'enable_adx_filter': True,
            'enable_volume_filter': False,
            'enable_slope_filter': True,
        }),
    ]

    loss_protection_config = {'enable_loss_protection': False}

    total_tests = len(filter_configs) * len(stock_list)
    print(f"过滤器配置: {len(filter_configs)}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~10-15分钟")
    print()

    results = []

    # 使用嵌套进度条
    pbar_filters = tqdm(filter_configs, desc="过滤器配置", position=0)

    for config_name, filter_config in pbar_filters:
        pbar_filters.set_description(f"Phase 2A ({config_name})")

        pbar_stocks = tqdm(stock_list, desc=f"  {config_name}", position=1, leave=False)
        for ts_code in pbar_stocks:
            try:
                data = load_etf_data(data_dir, ts_code)
                stats = run_backtest_with_config(data, filter_config, loss_protection_config, verbose=False)

                if stats is not None:
                    result = extract_stats(stats, ts_code, config_name, filter_config, loss_protection_config)
                    results.append(result)

            except Exception as e:
                print(f"  ⚠️  {ts_code} ({config_name}): {e}")
                continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'phase2a_baseline.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Phase 2A完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    if len(results) > 0:
        # 按配置分组统计
        for config_name, _ in filter_configs:
            config_df = df[df['config_name'] == config_name]
            if len(config_df) > 0:
                print(f"\n   {config_name}:")
                print(f"     夏普比率: {config_df['sharpe_ratio'].mean():.2f}")
                print(f"     收益率: {config_df['return_pct'].mean():.2f}%")
                print(f"     最大回撤: {config_df['max_drawdown_pct'].mean():.2f}%")

    return df


def run_phase_2b_loss_protection_grid(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    Phase 2B: 止损保护参数网格搜索

    测试连续止损保护参数的网格搜索：
    - max_consecutive_losses: [2, 3, 4, 5] - 连续亏损次数阈值
    - pause_bars: [5, 10, 15, 20] - 暂停交易K线数
    - 3种过滤器配置（baseline, adx_only, adx_slope）

    总测试: 4×4×3×20 = 960次

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 2B: 止损保护参数网格搜索")
    print(f"{'='*70}")

    # 定义网格参数
    max_losses_values = [2, 3, 4, 5]
    pause_bars_values = [5, 10, 15, 20]

    # 定义3种过滤器配置
    filter_configs = [
        ('baseline', {
            'enable_adx_filter': False,
            'enable_volume_filter': False,
            'enable_slope_filter': False,
        }),
        ('adx_only', {
            'enable_adx_filter': True,
            'enable_volume_filter': False,
            'enable_slope_filter': False,
        }),
        ('adx_slope', {
            'enable_adx_filter': True,
            'enable_volume_filter': False,
            'enable_slope_filter': True,
        }),
    ]

    # 生成所有参数组合
    param_combinations = list(itertools.product(max_losses_values, pause_bars_values))

    total_tests = len(param_combinations) * len(filter_configs) * len(stock_list)
    print(f"max_consecutive_losses: {max_losses_values}")
    print(f"pause_bars: {pause_bars_values}")
    print(f"参数组合: {len(param_combinations)}")
    print(f"过滤器配置: {len(filter_configs)}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~2-3小时")
    print()

    results = []

    # 三层嵌套进度条
    pbar_filters = tqdm(filter_configs, desc="过滤器配置", position=0)

    for filter_name, filter_config in pbar_filters:
        pbar_filters.set_description(f"过滤器: {filter_name}")

        pbar_params = tqdm(param_combinations, desc="  参数组合", position=1, leave=False)

        for max_losses, pause_bars in pbar_params:
            config_name = f"{filter_name}_loss{max_losses}_pause{pause_bars}"
            pbar_params.set_description(f"  {config_name}")

            loss_protection_config = {
                'enable_loss_protection': True,
                'max_consecutive_losses': max_losses,
                'pause_bars': pause_bars,
            }

            pbar_stocks = tqdm(stock_list, desc=f"    标的", position=2, leave=False)
            for ts_code in pbar_stocks:
                try:
                    data = load_etf_data(data_dir, ts_code)
                    stats = run_backtest_with_config(data, filter_config, loss_protection_config, verbose=False)

                    if stats is not None:
                        result = extract_stats(stats, ts_code, config_name, filter_config, loss_protection_config)
                        results.append(result)

                except Exception as e:
                    print(f"  ⚠️  {ts_code} ({config_name}): {e}")
                    continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'phase2b_loss_protection_grid.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Phase 2B完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    return df


def generate_summary_statistics(output_dir: Path):
    """
    生成Phase 2实验的汇总统计

    Args:
        output_dir: 输出目录
    """
    print(f"\n{'='*70}")
    print("生成Phase 2汇总统计")
    print(f"{'='*70}")

    # 读取Phase 2A和2B结果
    phase2a = pd.read_csv(output_dir / 'phase2a_baseline.csv')
    phase2b = pd.read_csv(output_dir / 'phase2b_loss_protection_grid.csv')

    # 合并所有结果
    all_results = pd.concat([phase2a, phase2b], ignore_index=True)

    # 计算汇总统计：按配置分组
    summary = all_results.groupby('config_name').agg({
        'return_pct': ['mean', 'median', 'std', 'min', 'max'],
        'sharpe_ratio': ['mean', 'median', 'std', 'min', 'max'],
        'max_drawdown_pct': ['mean', 'median', 'std', 'min', 'max'],
        'win_rate_pct': ['mean', 'median', 'std'],
        'num_trades': ['mean', 'median', 'std'],
    }).round(4)

    # 保存汇总统计
    summary_csv = output_dir / 'phase2_summary_statistics.csv'
    summary.to_csv(summary_csv, encoding='utf-8-sig')

    print(f"✅ 汇总统计已保存: {summary_csv}")
    print(f"\n前10个配置（按平均夏普比率排序）:")
    print(all_results.groupby('config_name')['sharpe_ratio'].mean().sort_values(ascending=False).head(10))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='KAMA策略Phase 2止损保护参数网格搜索')
    parser.add_argument('--stock-list', type=str, required=True,
                        help='股票列表CSV文件路径（必须包含ts_code列）')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='ETF数据目录路径')
    parser.add_argument('--output-dir', type=str,
                        default='experiment/etf/kama_cross/hyperparameter_search/results',
                        help='结果输出目录（默认: experiment/etf/kama_cross/hyperparameter_search/results）')
    parser.add_argument('--phases', type=str, default='all',
                        choices=['all', '2a', '2b'],
                        help='运行哪些阶段（默认: all）')

    args = parser.parse_args()

    # 加载股票列表
    print(f"{'='*70}")
    print("KAMA策略Phase 2止损保护参数网格搜索实验")
    print(f"{'='*70}")
    print(f"标的池: {args.stock_list}")
    stock_list = load_stock_list(args.stock_list)
    print(f"标的数量: {len(stock_list)}")
    print(f"数据目录: {args.data_dir}")

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {output_dir}")
    print(f"实验阶段: {args.phases}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 运行实验阶段
    if args.phases in ['all', '2a']:
        run_phase_2a_baseline(stock_list, args.data_dir, output_dir)

    if args.phases in ['all', '2b']:
        run_phase_2b_loss_protection_grid(stock_list, args.data_dir, output_dir)

    # 生成汇总统计（仅当运行所有阶段时）
    if args.phases == 'all':
        generate_summary_statistics(output_dir)

    print(f"\n{'='*70}")
    print(f"实验完成！结果已保存到: {output_dir}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
