#!/usr/bin/env python3
"""
生成固定基准ETF池
===================================

为对比实验生成固定ETF池（对照组），使用2023-11-01时点的筛选结果。

关键点：
- 使用2023-10-31之前的全部历史数据进行筛选
- 一阶段过滤：流动性（5万元）+ 上市天数（60天）
- 纯评分排序：跳过二阶段百分位过滤，直接按综合评分排序取top-20
- 启用无偏评分：避免动量偏差

使用示例：
    python scripts/generate_fixed_baseline_pool.py \\
        --data-dir data/chinese_etf \\
        --output results/rotation_fixed_pool/baseline_pool.csv
"""

import argparse
import sys
from pathlib import Path

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
        description='生成固定基准ETF池（对照组）',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--baseline-date', type=str, default='2023-11-01',
        help='基准日期 (YYYY-MM-DD)，使用此日期之前的历史数据筛选 (默认: 2023-11-01)'
    )
    parser.add_argument(
        '--pool-size', type=int, default=20,
        help='池子大小 (默认: 20)'
    )
    parser.add_argument(
        '--data-dir', type=str, default='data/chinese_etf',
        help='ETF数据根目录路径 (默认: data/chinese_etf)'
    )
    parser.add_argument(
        '--output', type=str, default='results/rotation_fixed_pool/baseline_pool.csv',
        help='输出CSV文件路径 (默认: results/rotation_fixed_pool/baseline_pool.csv)'
    )
    parser.add_argument(
        '--verbose', action='store_true', default=True,
        help='显示详细信息'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()

    if args.verbose:
        print("=" * 80)
        print(" 固定基准池生成器 - 对照组ETF池")
        print("=" * 80)
        print(f"\n⚙️  配置参数:")
        print(f"  基准日期: {args.baseline_date}")
        print(f"  池子大小: {args.pool_size} 只")
        print(f"  数据根目录: {args.data_dir}")
        print(f"  输出路径: {args.output}")

    # 创建输出目录
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 计算筛选截止日期（baseline_date - 1天）
    from datetime import datetime, timedelta
    baseline_dt = datetime.strptime(args.baseline_date, '%Y-%m-%d')
    end_date_dt = baseline_dt - timedelta(days=1)
    end_date_str = end_date_dt.strftime('%Y-%m-%d')

    if args.verbose:
        print(f"\n📊 筛选设置:")
        print(f"  评分窗口: 全部历史数据 至 {end_date_str}")
        print(f"  一阶段过滤: 流动性≥5万元, 上市天数≥60天")
        print(f"  二阶段过滤: 跳过（纯评分排序）")
        print(f"  无偏评分: 启用（避免动量偏差）")

    # 初始化ETF筛选器
    try:
        if args.verbose:
            print("\n🚀 初始化ETF筛选器...")

        config = FilterConfig()
        config.target_portfolio_size = args.pool_size
        # 一阶段过滤配置
        config.min_turnover = 50_000  # 5万元
        config.min_listing_days = 60  # 60天
        # 跳过二阶段百分位过滤（纯排序）
        config.skip_stage2_percentile_filtering = True
        config.skip_stage2_range_filtering = True
        # 启用无偏评分
        config.enable_unbiased_scoring = True

        data_loader = ETFDataLoader(args.data_dir)
        selector = TrendETFSelector(config=config, data_loader=data_loader)

        if args.verbose:
            print("✅ 筛选器初始化完成")

    except Exception as e:
        print(f"❌ 筛选器初始化失败: {e}")
        return 1

    # 执行筛选
    try:
        if args.verbose:
            print(f"\n🔍 开始筛选ETF池（时点: {args.baseline_date}）...")
            print("-" * 80)

        selected_etfs = selector.run_pipeline(
            start_date=None,  # 使用全部历史数据
            end_date=end_date_str,
            target_size=args.pool_size,
            verbose=True
        )

        if args.verbose:
            print("-" * 80)
            print(f"✅ 筛选完成: {len(selected_etfs)} 只ETF")

    except Exception as e:
        print(f"❌ 筛选失败: {e}")
        return 1

    # 保存结果
    try:
        # 提取关键字段
        output_data = []
        for etf in selected_etfs:
            output_data.append({
                'ts_code': etf['ts_code'],
                'name': etf['name'],
                '综合评分': etf.get('综合评分', 0),
                'ADX': etf.get('ADX', 0),
                'ADX百分位': etf.get('ADX百分位', 0),
                'ADX趋势强度评分': etf.get('ADX趋势强度评分', 0),
                '收益回撤比': etf.get('收益回撤比', 0),
                '收益回撤比百分位': etf.get('收益回撤比百分位', 0),
                '年化收益': etf.get('年化收益', 0),
                '最大回撤': etf.get('最大回撤', 0),
                '日均成交额': etf.get('日均成交额', 0)
            })

        df = pd.DataFrame(output_data)
        df.to_csv(output_path, index=False, encoding='utf-8')

        if args.verbose:
            print(f"\n💾 固定基准池已保存: {output_path}")
            print(f"\n📊 池子概况:")
            print(f"  ETF数量: {len(df)} 只")
            print(f"  平均综合评分: {df['综合评分'].mean():.2f}")
            print(f"  平均ADX: {df['ADX'].mean():.2f}")
            print(f"  平均收益回撤比: {df['收益回撤比'].mean():.2f}")
            print(f"\n🏆 Top 5 ETF:")
            for i, row in df.head(5).iterrows():
                print(f"  {i+1}. {row['ts_code']:<12} {row['name']:<20} 评分: {row['综合评分']:.2f}")

            print("\n" + "=" * 80)
            print("✅ 固定基准池生成完成！")
            print("=" * 80)

    except Exception as e:
        print(f"❌ 保存文件失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
