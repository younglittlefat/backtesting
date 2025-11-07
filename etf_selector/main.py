#!/usr/bin/env python3
"""
ETF趋势筛选系统 - 命令行入口

提供完整的命令行接口，支持：
1. 配置参数自定义
2. 筛选流程执行
3. 结果导出和分析
4. 与回测系统集成

使用示例：
    # 基本筛选
    python -m etf_selector.main --target-size 20

    # 自定义参数筛选
    python -m etf_selector.main \\
        --start-date 2023-01-01 \\
        --end-date 2024-10-31 \\
        --target-size 30 \\
        --max-correlation 0.6 \\
        --min-turnover 50000000

    # 导出结果到指定路径
    python -m etf_selector.main \\
        --output results/my_etf_pool.csv \\
        --with-analysis
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from etf_selector.config import FilterConfig
from etf_selector.selector import TrendETFSelector
from etf_selector.data_loader import ETFDataLoader


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='ETF趋势筛选系统 - 从大量ETF中筛选出适合趋势跟踪策略的优质标的池',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                                    # 使用默认参数运行
  %(prog)s --target-size 30                   # 筛选30只ETF
  %(prog)s --start-date 2023-01-01 --end-date 2024-12-31
  %(prog)s --output results/trend_pool.csv --with-analysis
  %(prog)s --config custom_config.json       # 使用自定义配置文件

更多信息请访问: https://github.com/your-repo/backtesting
        """
    )

    # 基本参数
    parser.add_argument(
        '--start-date', type=str,
        help='回测开始日期 (YYYY-MM-DD)，默认使用全部历史数据'
    )
    parser.add_argument(
        '--end-date', type=str,
        help='回测结束日期 (YYYY-MM-DD)，默认使用全部历史数据'
    )
    parser.add_argument(
        '--target-size', type=int, default=20,
        help='目标ETF组合大小 (默认: 20)'
    )

    # 数据和输出
    parser.add_argument(
        '--data-dir', type=str, default='data/csv',
        help='ETF数据目录路径 (默认: data/csv)'
    )
    parser.add_argument(
        '--output', type=str,
        help='结果输出文件路径，默认为 results/trend_etf_pool_YYYYMMDD.csv'
    )
    parser.add_argument(
        '--with-analysis', action='store_true',
        help='同时生成组合风险分析报告'
    )

    # 筛选参数
    parser.add_argument(
        '--min-turnover', type=float, default=100_000_000,
        help='最小日均成交额阈值，单位元 (默认: 1亿)'
    )
    parser.add_argument(
        '--min-listing-days', type=int, default=180,
        help='最小上市天数 (默认: 180天)'
    )
    parser.add_argument(
        '--adx-percentile', type=float, default=80,
        help='ADX筛选百分位数，保留前N%% (默认: 80%%)'
    )
    parser.add_argument(
        '--ret-dd-percentile', type=float, default=70,
        help='收益回撤比筛选百分位数 (默认: 70%%)'
    )
    parser.add_argument(
        '--max-correlation', type=float, default=0.7,
        help='组合优化最大相关系数阈值 (默认: 0.7)'
    )

    # 技术参数
    parser.add_argument(
        '--ma-short', type=int, default=20,
        help='双均线策略短期均线周期 (默认: 20)'
    )
    parser.add_argument(
        '--ma-long', type=int, default=50,
        help='双均线策略长期均线周期 (默认: 50)'
    )
    parser.add_argument(
        '--adx-period', type=int, default=14,
        help='ADX指标计算周期 (默认: 14)'
    )

    # 其他选项
    parser.add_argument(
        '--config', type=str,
        help='自定义配置文件路径 (JSON格式)'
    )
    parser.add_argument(
        '--no-portfolio-optimization', action='store_true',
        help='跳过第三级组合优化，直接使用第二级结果'
    )
    parser.add_argument(
        '--verbose', action='store_true', default=True,
        help='显示详细进度信息 (默认开启)'
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='静默模式，仅显示关键信息'
    )

    return parser.parse_args()


def load_config(config_path: str = None, args: argparse.Namespace = None) -> FilterConfig:
    """加载配置

    Args:
        config_path: 配置文件路径
        args: 命令行参数

    Returns:
        配置对象
    """
    # 如果指定了配置文件，尝试加载
    if config_path:
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            config = FilterConfig(**config_dict)
            print(f"✅ 已加载配置文件: {config_path}")
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            print("🔄 使用默认配置")
            config = FilterConfig()
    else:
        config = FilterConfig()

    # 使用命令行参数覆盖配置
    if args:
        if args.min_turnover:
            config.min_turnover = args.min_turnover
        if args.min_listing_days:
            config.min_listing_days = args.min_listing_days
        if args.adx_percentile:
            config.adx_percentile = args.adx_percentile
        if args.ret_dd_percentile:
            config.ret_dd_percentile = args.ret_dd_percentile
        if args.ma_short:
            config.ma_short = args.ma_short
        if args.ma_long:
            config.ma_long = args.ma_long
        if args.adx_period:
            config.adx_period = args.adx_period
        if args.target_size:
            config.target_portfolio_size = args.target_size

    return config


def print_banner():
    """打印程序横幅"""
    print("=" * 80)
    print(" ETF趋势筛选系统 v1.0")
    print(" 基于三级漏斗模型的量化标的筛选")
    print("=" * 80)
    print()


def print_config_summary(config: FilterConfig, args: argparse.Namespace):
    """打印配置摘要"""
    print("📋 筛选配置摘要:")
    print(f"  🎯 目标组合大小: {config.target_portfolio_size} 只")
    print(f"  💰 流动性阈值: {config.min_turnover/1e8:.1f} 亿元")
    print(f"  📅 最小上市天数: {config.min_listing_days} 天")
    print(f"  📊 ADX筛选: 保留前 {config.adx_percentile}%")
    print(f"  📈 收益回撤比筛选: 保留前 {config.ret_dd_percentile}%")
    print(f"  🔗 最大相关性: {args.max_correlation}")
    print(f"  📈 双均线参数: MA({config.ma_short}, {config.ma_long})")
    print()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 设置输出详细程度
    verbose = args.verbose and not args.quiet

    if verbose:
        print_banner()

    # 加载配置
    config = load_config(args.config, args)

    if verbose:
        print_config_summary(config, args)

    # 初始化筛选器
    try:
        if verbose:
            print("🚀 初始化ETF筛选器...")

        data_loader = ETFDataLoader(args.data_dir)
        selector = TrendETFSelector(config=config, data_loader=data_loader)

        if verbose:
            print("✅ 筛选器初始化完成")

    except Exception as e:
        print(f"❌ 筛选器初始化失败: {e}")
        return 1

    # 执行筛选流程
    try:
        if verbose:
            print("\n🎯 开始执行筛选流程...")
            print(f"📅 数据期间: {args.start_date or '全部'} 至 {args.end_date or '全部'}")

        # 调整目标大小，如果启用了组合优化
        target_size = args.target_size
        if args.no_portfolio_optimization:
            if verbose:
                print("⚠️ 已跳过第三级组合优化")

        selected_etfs = selector.run_pipeline(
            start_date=args.start_date,
            end_date=args.end_date,
            target_size=target_size,
            verbose=verbose
        )

        if len(selected_etfs) == 0:
            print("❌ 筛选失败，无符合条件的ETF")
            return 1

    except Exception as e:
        print(f"❌ 筛选流程执行失败: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return 1

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = Path('results') / f'trend_etf_pool_{timestamp}.csv'

    # 导出结果
    try:
        if verbose:
            print(f"\n📁 导出筛选结果...")

        selector.export_results(selected_etfs, output_path)

        if verbose:
            print("✅ 筛选结果已导出")

    except Exception as e:
        print(f"❌ 结果导出失败: {e}")
        return 1

    # 生成风险分析（如果需要）
    if args.with_analysis:
        try:
            if verbose:
                print(f"\n📊 生成组合风险分析...")

            from etf_selector.portfolio import PortfolioOptimizer
            optimizer = PortfolioOptimizer(data_loader=data_loader)

            analysis_path = output_path.with_suffix('.analysis.txt')
            optimizer.export_portfolio_analysis(
                selected_etfs,
                analysis_path,
                start_date=args.start_date,
                end_date=args.end_date
            )

            if verbose:
                print("✅ 风险分析报告已生成")

        except Exception as e:
            print(f"⚠️ 风险分析生成失败: {e}")
            # 这不是致命错误，继续执行

    # 打印最终结果摘要
    if verbose:
        print("\n" + "=" * 80)
        print("🎉 ETF筛选完成！")
        print(f"📊 最终选出 {len(selected_etfs)} 只优质ETF")
        print(f"📄 结果文件: {output_path}")

        if len(selected_etfs) > 0:
            print("\n🏆 前5名ETF:")
            for i, etf in enumerate(selected_etfs[:5]):
                print(f"  {i+1}. {etf['ts_code']} - {etf['name']}")
                if 'industry' in etf:
                    print(f"     行业: {etf['industry']}, 收益回撤比: {etf.get('return_dd_ratio', 'N/A')}")

        # 获取统计摘要
        stats = selector.get_summary_stats()
        if 'stage1' in stats:
            print(f"\n📈 筛选统计:")
            print(f"  第一级筛选: {stats['stage1']['count']} 只")
            if 'stage2' in stats:
                print(f"  第二级筛选: {stats['stage2']['count']} 只")
            print(f"  最终筛选: {len(selected_etfs)} 只")

        print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())