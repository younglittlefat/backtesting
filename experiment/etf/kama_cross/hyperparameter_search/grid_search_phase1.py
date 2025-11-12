#!/usr/bin/env python3
"""
KAMA策略Phase 1信号过滤器网格搜索实验

测试不同信号过滤器组合对KAMA策略的影响。

实验方案：
- Phase 1A: Baseline（无过滤器对照组）- 20次
- Phase 1B: 单一过滤器测试 - 80次
- Phase 1C: 双过滤器组合测试 - 80次
- Phase 1D: 全组合过滤器测试 - 20次

总计: 200次回测，预计耗时约1小时

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


def run_backtest_with_filters(
    data: pd.DataFrame,
    filter_config: Dict,
    verbose: bool = False
) -> Optional[Dict]:
    """
    使用指定过滤器配置运行KAMA策略回测

    Args:
        data: OHLCV数据
        filter_config: 过滤器配置字典
            {
                'enable_adx_filter': bool,
                'enable_volume_filter': bool,
                'enable_slope_filter': bool,
                'enable_confirm_filter': bool,
            }
        verbose: 是否输出详细日志

    Returns:
        dict: 回测统计结果，失败返回None
    """
    try:
        bt = Backtest(data, KamaCrossStrategy, cash=10000, commission=0.002)

        # KAMA策略使用固定参数（不优化）
        params = {
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
            # 止损保护（Phase 1不启用）
            'enable_loss_protection': False,
            # Note: KAMA策略当前未实现trailing_stop，Phase 1不需要
        }

        # 运行回测（不优化）
        stats = bt.run(**params)

        return stats

    except Exception as e:
        if verbose:
            print(f"  ⚠️  回测失败: {e}")
        return None


def extract_stats(stats, ts_code: str, config_name: str, filter_config: Dict) -> Dict:
    """
    从回测结果中提取关键指标

    Args:
        stats: 回测统计结果
        ts_code: 标的代码
        config_name: 配置名称（如 baseline, adx_only, adx_volume, etc.）
        filter_config: 过滤器配置

    Returns:
        dict: 提取的指标字典
    """
    result = {
        'ts_code': ts_code,
        'config_name': config_name,
        'return_pct': stats['Return [%]'],
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'win_rate_pct': stats['Win Rate [%]'],
        'num_trades': stats['# Trades'],
        'avg_trade_duration': str(stats['Avg. Trade Duration']),
        'exposure_time_pct': stats['Exposure Time [%]'],
        # 过滤器配置
        'enable_adx_filter': filter_config.get('enable_adx_filter', False),
        'enable_volume_filter': filter_config.get('enable_volume_filter', False),
        'enable_slope_filter': filter_config.get('enable_slope_filter', False),
        'enable_confirm_filter': filter_config.get('enable_confirm_filter', False),
    }

    return result


def run_phase_1a_baseline(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    Phase 1A: Baseline（无过滤器对照组）

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 1A: Baseline（无过滤器对照组）")
    print(f"{'='*70}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"预计耗时: ~5-10分钟")
    print()

    results = []
    filter_config = {
        'enable_adx_filter': False,
        'enable_volume_filter': False,
        'enable_slope_filter': False,
        'enable_confirm_filter': False,
    }

    for ts_code in tqdm(stock_list, desc="Phase 1A Baseline"):
        try:
            data = load_etf_data(data_dir, ts_code)
            stats = run_backtest_with_filters(data, filter_config, verbose=False)

            if stats is not None:
                result = extract_stats(stats, ts_code, 'baseline', filter_config)
                results.append(result)

        except Exception as e:
            print(f"  ⚠️  {ts_code}: {e}")
            continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'phase1a_baseline.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Phase 1A完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{len(stock_list)}")

    if len(results) > 0:
        print(f"\n   平均夏普比率: {df['sharpe_ratio'].mean():.2f}")
        print(f"   平均收益率: {df['return_pct'].mean():.2f}%")
        print(f"   平均最大回撤: {df['max_drawdown_pct'].mean():.2f}%")

    return df


def run_phase_1b_single_filters(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    Phase 1B: 单一过滤器测试

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 1B: 单一过滤器测试")
    print(f"{'='*70}")

    # 定义单一过滤器配置
    filter_configs = [
        ('adx_only', {'enable_adx_filter': True}),
        ('volume_only', {'enable_volume_filter': True}),
        ('slope_only', {'enable_slope_filter': True}),
        ('confirm_only', {'enable_confirm_filter': True}),
    ]

    total_tests = len(filter_configs) * len(stock_list)
    print(f"过滤器类型: {len(filter_configs)}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~20-30分钟")
    print()

    results = []

    # 使用嵌套进度条
    pbar_filters = tqdm(filter_configs, desc="过滤器", position=0)

    for config_name, filter_params in pbar_filters:
        pbar_filters.set_description(f"Phase 1B ({config_name})")

        # 完整的过滤器配置（未指定的都是False）
        full_config = {
            'enable_adx_filter': filter_params.get('enable_adx_filter', False),
            'enable_volume_filter': filter_params.get('enable_volume_filter', False),
            'enable_slope_filter': filter_params.get('enable_slope_filter', False),
            'enable_confirm_filter': filter_params.get('enable_confirm_filter', False),
        }

        pbar_stocks = tqdm(stock_list, desc=f"  {config_name}", position=1, leave=False)
        for ts_code in pbar_stocks:
            try:
                data = load_etf_data(data_dir, ts_code)
                stats = run_backtest_with_filters(data, full_config, verbose=False)

                if stats is not None:
                    result = extract_stats(stats, ts_code, config_name, full_config)
                    results.append(result)

            except Exception as e:
                continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'phase1b_single_filters.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Phase 1B完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    if len(results) > 0:
        print(f"\n   各过滤器平均夏普比率:")
        for config_name, _ in filter_configs:
            config_df = df[df['config_name'] == config_name]
            if len(config_df) > 0:
                print(f"     {config_name:15s}: {config_df['sharpe_ratio'].mean():.2f}")

    return df


def run_phase_1c_dual_filters(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    Phase 1C: 双过滤器组合测试

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 1C: 双过滤器组合测试")
    print(f"{'='*70}")

    # 定义精选的双过滤器组合
    filter_configs = [
        ('adx_volume', {'enable_adx_filter': True, 'enable_volume_filter': True}),
        ('adx_slope', {'enable_adx_filter': True, 'enable_slope_filter': True}),
        ('volume_confirm', {'enable_volume_filter': True, 'enable_confirm_filter': True}),
        ('slope_confirm', {'enable_slope_filter': True, 'enable_confirm_filter': True}),
    ]

    total_tests = len(filter_configs) * len(stock_list)
    print(f"组合类型: {len(filter_configs)}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"总测试次数: {total_tests}")
    print(f"预计耗时: ~20-30分钟")
    print()

    results = []

    # 使用嵌套进度条
    pbar_combos = tqdm(filter_configs, desc="组合", position=0)

    for config_name, filter_params in pbar_combos:
        pbar_combos.set_description(f"Phase 1C ({config_name})")

        # 完整的过滤器配置
        full_config = {
            'enable_adx_filter': filter_params.get('enable_adx_filter', False),
            'enable_volume_filter': filter_params.get('enable_volume_filter', False),
            'enable_slope_filter': filter_params.get('enable_slope_filter', False),
            'enable_confirm_filter': filter_params.get('enable_confirm_filter', False),
        }

        pbar_stocks = tqdm(stock_list, desc=f"  {config_name}", position=1, leave=False)
        for ts_code in pbar_stocks:
            try:
                data = load_etf_data(data_dir, ts_code)
                stats = run_backtest_with_filters(data, full_config, verbose=False)

                if stats is not None:
                    result = extract_stats(stats, ts_code, config_name, full_config)
                    results.append(result)

            except Exception as e:
                continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'phase1c_dual_filters.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Phase 1C完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{total_tests}")

    if len(results) > 0:
        print(f"\n   各组合平均夏普比率:")
        for config_name, _ in filter_configs:
            config_df = df[df['config_name'] == config_name]
            if len(config_df) > 0:
                print(f"     {config_name:15s}: {config_df['sharpe_ratio'].mean():.2f}")

    return df


def run_phase_1d_full_stack(stock_list: List[str], data_dir: str, output_dir: Path) -> pd.DataFrame:
    """
    Phase 1D: 全组合过滤器测试

    Args:
        stock_list: 标的代码列表
        data_dir: 数据目录
        output_dir: 输出目录

    Returns:
        DataFrame: 实验结果
    """
    print(f"\n{'='*70}")
    print("Phase 1D: 全组合过滤器测试")
    print(f"{'='*70}")
    print(f"测试标的数: {len(stock_list)}")
    print(f"预计耗时: ~5-10分钟")
    print()

    results = []
    filter_config = {
        'enable_adx_filter': True,
        'enable_volume_filter': True,
        'enable_slope_filter': True,
        'enable_confirm_filter': True,
    }

    for ts_code in tqdm(stock_list, desc="Phase 1D Full Stack"):
        try:
            data = load_etf_data(data_dir, ts_code)
            stats = run_backtest_with_filters(data, filter_config, verbose=False)

            if stats is not None:
                result = extract_stats(stats, ts_code, 'full_stack', filter_config)
                results.append(result)

        except Exception as e:
            print(f"  ⚠️  {ts_code}: {e}")
            continue

    # 保存结果
    df = pd.DataFrame(results)
    output_csv = output_dir / 'phase1d_full_stack.csv'
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"\n✅ Phase 1D完成，结果已保存: {output_csv}")
    print(f"   成功: {len(results)}/{len(stock_list)}")

    if len(results) > 0:
        print(f"\n   平均夏普比率: {df['sharpe_ratio'].mean():.2f}")
        print(f"   平均收益率: {df['return_pct'].mean():.2f}%")
        print(f"   平均最大回撤: {df['max_drawdown_pct'].mean():.2f}%")

    return df


def generate_summary_statistics(output_dir: Path):
    """
    生成Phase 1的汇总统计

    Args:
        output_dir: 输出目录
    """
    print(f"\n{'='*70}")
    print("生成汇总统计")
    print(f"{'='*70}")

    # 读取所有Phase 1结果
    phase1a = pd.read_csv(output_dir / 'phase1a_baseline.csv')
    phase1b = pd.read_csv(output_dir / 'phase1b_single_filters.csv')
    phase1c = pd.read_csv(output_dir / 'phase1c_dual_filters.csv')
    phase1d = pd.read_csv(output_dir / 'phase1d_full_stack.csv')

    # 合并所有结果
    all_results = pd.concat([phase1a, phase1b, phase1c, phase1d], ignore_index=True)

    # 按配置名称分组统计
    summary = all_results.groupby('config_name').agg({
        'return_pct': ['mean', 'std', 'min', 'max'],
        'sharpe_ratio': ['mean', 'std', 'min', 'max'],
        'max_drawdown_pct': ['mean', 'std', 'min', 'max'],
        'win_rate_pct': ['mean', 'std'],
        'num_trades': ['mean', 'std'],
    }).round(2)

    # 保存汇总统计
    output_csv = output_dir / 'phase1_summary_statistics.csv'
    summary.to_csv(output_csv, encoding='utf-8-sig')

    print(f"\n✅ 汇总统计已保存: {output_csv}")
    print("\n主要配置夏普比率对比:")
    print(summary['sharpe_ratio']['mean'].sort_values(ascending=False))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='KAMA策略Phase 1信号过滤器网格搜索')
    parser.add_argument('--stock-list', type=str, required=True,
                        help='标的池CSV文件路径（如 results/trend_etf_pool.csv）')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='数据目录路径（如 data/chinese_etf/daily）')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='输出目录（默认：experiment/etf/kama_cross/hyperparameter_search/results）')
    parser.add_argument('--phases', type=str, default='all',
                        help='运行的阶段（all, 1a, 1b, 1c, 1d 或逗号分隔）')

    args = parser.parse_args()

    # 设置输出目录
    if args.output_dir is None:
        output_dir = Path(__file__).parent / 'results'
    else:
        output_dir = Path(args.output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载标的列表
    stock_list = load_stock_list(args.stock_list)

    print(f"\n{'='*70}")
    print("KAMA策略Phase 1信号过滤器网格搜索实验")
    print(f"{'='*70}")
    print(f"标的池: {args.stock_list}")
    print(f"标的数量: {len(stock_list)}")
    print(f"数据目录: {args.data_dir}")
    print(f"输出目录: {output_dir}")
    print(f"实验阶段: {args.phases}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 解析phases参数
    if args.phases == 'all':
        phases = ['1a', '1b', '1c', '1d']
    else:
        phases = args.phases.split(',')

    # 运行实验
    start_time = datetime.now()

    if '1a' in phases:
        run_phase_1a_baseline(stock_list, args.data_dir, output_dir)

    if '1b' in phases:
        run_phase_1b_single_filters(stock_list, args.data_dir, output_dir)

    if '1c' in phases:
        run_phase_1c_dual_filters(stock_list, args.data_dir, output_dir)

    if '1d' in phases:
        run_phase_1d_full_stack(stock_list, args.data_dir, output_dir)

    # 生成汇总统计
    if args.phases == 'all' or len(phases) == 4:
        generate_summary_statistics(output_dir)

    # 完成
    end_time = datetime.now()
    elapsed_time = end_time - start_time

    print(f"\n{'='*70}")
    print("✅ 实验完成！")
    print(f"{'='*70}")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {elapsed_time}")
    print(f"结果文件保存在: {output_dir}")
    print()


if __name__ == '__main__':
    main()
