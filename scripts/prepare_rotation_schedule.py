#!/usr/bin/env python3
"""
轮动表生成脚本

为动态池子轮动策略生成时间序列轮动表。在每个轮动日期，使用历史数据重新筛选ETF池，
生成JSON格式的轮动时间表供后续回测使用。

关键特性：
1. 避免未来数据泄露：评分窗口严格限制在[T-lookback, T-1]
2. 支持多种轮动周期（7/15/30/60天）
3. 输出完整统计信息（换手率、池子稳定性等）

使用示例：
    python scripts/prepare_rotation_schedule.py \\
        --start-date 2023-11-01 \\
        --end-date 2025-11-12 \\
        --rotation-period 30 \\
        --pool-size 20 \\
        --output results/rotation_schedules/rotation_30d.json
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from etf_selector.config import FilterConfig
from etf_selector.data_loader import ETFDataLoader
from etf_selector.selector import TrendETFSelector


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='生成动态池子轮动时间表',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 必需参数
    parser.add_argument(
        '--start-date', type=str, required=True,
        help='轮动开始日期 (YYYY-MM-DD)，如 2023-11-01'
    )
    parser.add_argument(
        '--end-date', type=str, required=True,
        help='轮动结束日期 (YYYY-MM-DD)，如 2025-11-12'
    )
    parser.add_argument(
        '--rotation-period', type=int, required=True,
        help='轮动周期（天），如 7/15/30/60'
    )

    # 可选参数
    parser.add_argument(
        '--pool-size', type=int, default=20,
        help='每次筛选的ETF数量 (默认: 20)'
    )
    parser.add_argument(
        '--lookback-days', type=int, default=120,
        help='评分窗口天数 (默认: 120天)'
    )
    parser.add_argument(
        '--data-dir', type=str, default='data/chinese_etf',
        help='ETF数据根目录路径 (默认: data/chinese_etf)'
    )
    parser.add_argument(
        '--output', type=str,
        help='输出JSON文件路径，默认为 results/rotation_schedules/rotation_{period}d.json'
    )
    parser.add_argument(
        '--verbose', action='store_true', default=True,
        help='显示详细进度信息'
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='静默模式，仅显示关键信息'
    )
    parser.add_argument(
        '--no-score-threshold', action='store_true', default=True,
        help='跳过二阶段百分位过滤，改为纯评分排序取top-N (默认: True)'
    )
    parser.add_argument(
        '--use-score-threshold', dest='no_score_threshold', action='store_false',
        help='启用二阶段百分位过滤（与默认行为相反）'
    )

    return parser.parse_args()


def calculate_rotation_dates(
    start_date: str,
    end_date: str,
    rotation_period: int
) -> List[str]:
    """计算轮动日期序列

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        rotation_period: 轮动周期（天）

    Returns:
        日期字符串列表 (YYYY-MM-DD格式)
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    rotation_dates = []
    current = start

    while current <= end:
        rotation_dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=rotation_period)

    return rotation_dates


def select_etfs_for_date(
    selector: TrendETFSelector,
    rotation_date: str,
    lookback_days: int,
    pool_size: int,
    verbose: bool = False
) -> Tuple[List[str], Dict]:
    """为指定日期筛选ETF池

    关键点：使用截止到rotation_date-1的全部历史数据进行评分
    （不限制120天窗口，因为短窗口会导致流动性等指标计算失败）

    Args:
        selector: ETF筛选器实例
        rotation_date: 轮动日期 (YYYY-MM-DD)
        lookback_days: 评分窗口天数（已弃用，保留参数兼容性）
        pool_size: 目标池子大小
        verbose: 是否显示详细信息

    Returns:
        (etf_codes, metadata): ETF代码列表和元数据字典
    """
    rot_date = datetime.strptime(rotation_date, '%Y-%m-%d')

    # 使用截止到轮动日期前一天的全部历史数据（不限制窗口）
    end_date_str = (rot_date - timedelta(days=1)).strftime('%Y-%m-%d')

    if verbose:
        print(f"  📊 评分窗口: 全部历史数据 至 {end_date_str}")

    # 执行筛选（静默模式）
    try:
        selected_etfs = selector.run_pipeline(
            start_date=None,  # None表示使用全部历史数据
            end_date=end_date_str,
            target_size=pool_size,
            verbose=True  # 临时启用详细日志，用于调试
        )

        # 提取代码列表
        etf_codes = [etf['ts_code'] for etf in selected_etfs]

        # 收集元数据
        metadata = {
            'count': len(etf_codes),
            'score_window_start': 'all_history',
            'score_window_end': end_date_str,
            'top_3_etfs': etf_codes[:3] if len(etf_codes) >= 3 else etf_codes
        }

        return etf_codes, metadata

    except Exception as e:
        if verbose:
            print(f"  ❌ 筛选失败: {e}")
        return [], {'count': 0, 'error': str(e)}


def calculate_turnover_rate(old_pool: List[str], new_pool: List[str]) -> float:
    """计算换手率

    定义：(卖出数量 + 买入数量) / (2 * 池子大小)

    Args:
        old_pool: 旧池子代码列表
        new_pool: 新池子代码列表

    Returns:
        换手率（0-1之间）
    """
    if not old_pool or not new_pool:
        return 0.0

    old_set = set(old_pool)
    new_set = set(new_pool)

    n_sell = len(old_set - new_set)  # 被淘汰的
    n_buy = len(new_set - old_set)   # 新增的

    pool_size = len(old_pool)
    turnover = (n_sell + n_buy) / (2 * pool_size)

    return turnover


def calculate_statistics(
    schedule: Dict[str, List[str]]
) -> Dict:
    """计算轮动统计信息

    Args:
        schedule: 轮动时间表 {date: [codes]}

    Returns:
        统计信息字典
    """
    dates = sorted(schedule.keys())

    if len(dates) < 2:
        return {
            'total_rotations': len(dates),
            'avg_turnover_rate': 0.0,
            'median_overlap': 0,
            'most_stable_etfs': [],
            'most_volatile_etfs': []
        }

    # 计算换手率序列
    turnover_rates = []
    overlap_counts = []

    for i in range(1, len(dates)):
        old_pool = schedule[dates[i-1]]
        new_pool = schedule[dates[i]]

        turnover = calculate_turnover_rate(old_pool, new_pool)
        turnover_rates.append(turnover)

        overlap = len(set(old_pool) & set(new_pool))
        overlap_counts.append(overlap)

    # 统计每个ETF出现次数
    all_etfs = []
    for codes in schedule.values():
        all_etfs.extend(codes)

    etf_counter = Counter(all_etfs)
    total_rotations = len(dates)

    # 最稳定的ETF（出现次数最多）
    most_stable = [
        {'code': code, 'appearances': count, 'stability': count / total_rotations}
        for code, count in etf_counter.most_common(5)
    ]

    # 最不稳定的ETF（只出现1次）
    least_stable = [
        {'code': code, 'appearances': count}
        for code, count in etf_counter.items()
        if count == 1
    ]

    return {
        'total_rotations': total_rotations,
        'avg_turnover_rate': float(sum(turnover_rates) / len(turnover_rates)),
        'min_turnover_rate': float(min(turnover_rates)),
        'max_turnover_rate': float(max(turnover_rates)),
        'median_overlap': int(sorted(overlap_counts)[len(overlap_counts) // 2]),
        'avg_overlap': float(sum(overlap_counts) / len(overlap_counts)),
        'unique_etfs_count': len(etf_counter),
        'most_stable_etfs': most_stable,
        'least_stable_count': len(least_stable),
        'turnover_trend': {
            'first_3_avg': float(sum(turnover_rates[:3]) / min(3, len(turnover_rates))),
            'last_3_avg': float(sum(turnover_rates[-3:]) / min(3, len(turnover_rates)))
        }
    }


def print_summary(
    schedule: Dict[str, List[str]],
    statistics: Dict,
    output_path: Path
):
    """打印轮动表摘要

    Args:
        schedule: 轮动时间表
        statistics: 统计信息
        output_path: 输出文件路径
    """
    print("\n" + "=" * 80)
    print("🎉 轮动表生成完成！")
    print("=" * 80)

    print(f"\n📊 基本信息:")
    print(f"  轮动周期数: {statistics['total_rotations']} 次")
    print(f"  每次池子大小: {len(next(iter(schedule.values())))} 只")
    print(f"  涉及ETF总数: {statistics['unique_etfs_count']} 只")
    print(f"  输出文件: {output_path}")

    print(f"\n🔄 换手率统计:")
    print(f"  平均换手率: {statistics['avg_turnover_rate']:.2%}")
    print(f"  换手率范围: {statistics['min_turnover_rate']:.2%} - {statistics['max_turnover_rate']:.2%}")
    print(f"  平均保留数量: {statistics['avg_overlap']:.1f} 只 ({statistics['avg_overlap']/20*100:.0f}%)")
    print(f"  中位保留数量: {statistics['median_overlap']} 只")

    print(f"\n⭐ 最稳定的5只ETF (出现频率最高):")
    for i, etf in enumerate(statistics['most_stable_etfs'][:5]):
        print(f"  {i+1}. {etf['code']}: {etf['appearances']}/{statistics['total_rotations']} 次 ({etf['stability']:.0%})")

    print(f"\n📈 换手率趋势:")
    print(f"  前3次平均: {statistics['turnover_trend']['first_3_avg']:.2%}")
    print(f"  后3次平均: {statistics['turnover_trend']['last_3_avg']:.2%}")

    trend_direction = "上升" if statistics['turnover_trend']['last_3_avg'] > statistics['turnover_trend']['first_3_avg'] else "下降"
    print(f"  趋势: {trend_direction}")

    print(f"\n📅 首尾轮动日期:")
    dates = sorted(schedule.keys())
    print(f"  首次轮动: {dates[0]}")
    print(f"  末次轮动: {dates[-1]}")

    # 显示首次和末次的Top 3
    print(f"\n🏆 首次轮动Top 3: {', '.join(schedule[dates[0]][:3])}")
    print(f"🏆 末次轮动Top 3: {', '.join(schedule[dates[-1]][:3])}")

    print("\n" + "=" * 80)


def main():
    """主函数"""
    args = parse_arguments()
    verbose = args.verbose and not args.quiet

    if verbose:
        print("=" * 80)
        print(" 轮动表生成器 - 动态池子轮动策略")
        print("=" * 80)
        print(f"\n⚙️  配置参数:")
        print(f"  轮动周期: {args.rotation_period} 天")
        print(f"  池子大小: {args.pool_size} 只")
        print(f"  评分窗口: {args.lookback_days} 天")
        print(f"  回测区间: {args.start_date} 至 {args.end_date}")
        print(f"  数据根目录: {args.data_dir}")

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path('results/rotation_schedules') / f'rotation_{args.rotation_period}d.json'

    # 创建输出目录
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 初始化ETF筛选器
    try:
        if verbose:
            print("\n🚀 初始化ETF筛选器...")

        config = FilterConfig()
        config.target_portfolio_size = args.pool_size
        # 放宽流动性阈值，适应A股ETF市场特点和短期历史窗口
        config.min_turnover = 50_000  # 5万元，原默认1亿
        # 放宽其他限制，确保短窗口下能筛选出足够ETF
        config.min_listing_days = 60  # 原默认180天，降低到60天
        # ⭐ 跳过第二级的百分位筛选和范围过滤，直接按综合评分排序（可通过命令行控制）
        config.skip_stage2_percentile_filtering = args.no_score_threshold
        config.skip_stage2_range_filtering = args.no_score_threshold
        # 启用无偏评分（避免动量偏差）
        config.enable_unbiased_scoring = True

        data_loader = ETFDataLoader(args.data_dir)
        selector = TrendETFSelector(config=config, data_loader=data_loader)

        if verbose:
            print("✅ 筛选器初始化完成")

    except Exception as e:
        print(f"❌ 筛选器初始化失败: {e}")
        return 1

    # 计算轮动日期序列
    rotation_dates = calculate_rotation_dates(
        args.start_date,
        args.end_date,
        args.rotation_period
    )

    if verbose:
        print(f"\n📅 生成轮动日期序列:")
        print(f"  共 {len(rotation_dates)} 个轮动点")
        print(f"  首次: {rotation_dates[0]}")
        print(f"  末次: {rotation_dates[-1]}")

    # 逐日筛选ETF池
    schedule = {}
    metadata_log = {}

    if verbose:
        print(f"\n🔍 开始逐日筛选ETF池...")
        print("-" * 80)

    for i, rot_date in enumerate(rotation_dates):
        if verbose:
            print(f"\n[{i+1}/{len(rotation_dates)}] 处理 {rot_date}:")

        etf_codes, metadata = select_etfs_for_date(
            selector=selector,
            rotation_date=rot_date,
            lookback_days=args.lookback_days,
            pool_size=args.pool_size,
            verbose=verbose
        )

        if len(etf_codes) == 0:
            print(f"  ⚠️  警告: {rot_date} 筛选结果为空，跳过")
            continue

        schedule[rot_date] = etf_codes
        metadata_log[rot_date] = metadata

        if verbose:
            print(f"  ✅ 筛选完成: {len(etf_codes)} 只")
            print(f"  Top 3: {', '.join(etf_codes[:3])}")

            # 计算与上一期的变化（如果存在）
            if i > 0 and len(schedule) >= 2:
                prev_date = rotation_dates[i-1]
                if prev_date in schedule:
                    turnover = calculate_turnover_rate(schedule[prev_date], etf_codes)
                    overlap = len(set(schedule[prev_date]) & set(etf_codes))
                    print(f"  🔄 换手率: {turnover:.2%} (保留 {overlap} 只)")

    if len(schedule) == 0:
        print("❌ 轮动表生成失败：所有日期筛选结果均为空")
        return 1

    if verbose:
        print("\n" + "-" * 80)
        print("✅ 所有日期筛选完成")

    # 计算统计信息
    statistics = calculate_statistics(schedule)

    # 构建输出JSON
    output_data = {
        'metadata': {
            'rotation_period': args.rotation_period,
            'pool_size': args.pool_size,
            'lookback_days': args.lookback_days,
            'start_date': args.start_date,
            'end_date': args.end_date,
            'total_rotations': len(schedule),
            'data_dir': args.data_dir,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'schedule': schedule,
        'statistics': statistics,
        'metadata_log': metadata_log
    }

    # 保存JSON文件
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        if verbose:
            print(f"\n💾 轮动表已保存: {output_path}")

    except Exception as e:
        print(f"❌ 保存文件失败: {e}")
        return 1

    # 打印摘要
    if verbose:
        print_summary(schedule, statistics, output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
