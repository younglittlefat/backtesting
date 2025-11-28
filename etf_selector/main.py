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
import math
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from etf_selector.config import FilterConfig
from etf_selector.config_loader import ConfigLoader
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
    # 注意：使用argparse.SUPPRESS作为default，确保未显式传参时args不含该属性
    # 这样CLI参数只有在用户显式传递时才会覆盖配置文件值
    parser.add_argument(
        '--start-date', type=str, default=argparse.SUPPRESS,
        help='回测开始日期 (YYYY-MM-DD)，默认使用全部历史数据'
    )
    parser.add_argument(
        '--end-date', type=str, default=argparse.SUPPRESS,
        help='回测结束日期 (YYYY-MM-DD)，默认使用全部历史数据'
    )
    parser.add_argument(
        '--target-size', type=int, default=argparse.SUPPRESS,
        help='目标ETF组合大小 (默认: 20)'
    )

    # 数据和输出
    parser.add_argument(
        '--data-dir', type=str, default=argparse.SUPPRESS,
        help='ETF数据目录路径 (默认: data/csv)'
    )
    parser.add_argument(
        '--output', type=str, default=argparse.SUPPRESS,
        help='结果输出文件路径，默认为 results/trend_etf_pool_YYYYMMDD.csv'
    )
    parser.add_argument(
        '--with-analysis', action='store_true',
        help='同时生成组合风险分析报告'
    )

    # 筛选参数 - 全部使用SUPPRESS
    parser.add_argument(
        '--min-turnover', type=float, default=argparse.SUPPRESS,
        help='最小日均成交额阈值，单位元 (默认: 1亿)'
    )
    parser.add_argument(
        '--min-listing-days', type=int, default=argparse.SUPPRESS,
        help='最小上市天数 (默认: 180天)'
    )
    parser.add_argument(
        '--adx-percentile', type=float, default=argparse.SUPPRESS,
        help='ADX筛选百分位数，保留前N%% (默认: 80，即保留前20%%)'
    )
    parser.add_argument(
        '--ret-dd-percentile', type=float, default=argparse.SUPPRESS,
        help='收益回撤比筛选百分位数 (默认: 70，即保留前30%%)'
    )
    parser.add_argument(
        '--disable-ma-filter', action='store_true',
        help='禁用双均线回测过滤，仅依赖ADX/波动率/动量条件'
    )
    parser.add_argument(
        '--enable-ma-filter', action='store_true',
        help='启用双均线回测过滤（默认禁用，可通过该选项开启）'
    )
    parser.add_argument(
        '--min-volatility', type=float, default=argparse.SUPPRESS,
        help='最小年化波动率 (默认: 0.20 = 20%%)'
    )
    parser.add_argument(
        '--max-volatility', type=float, default=argparse.SUPPRESS,
        help='最大年化波动率 (默认: 0.60 = 60%%)'
    )
    parser.add_argument(
        '--momentum-min-positive', action='store_true',
        help='仅要求动量为正（不进行排名筛选）'
    )
    parser.add_argument(
        '--max-correlation', type=float, default=argparse.SUPPRESS,
        help='组合优化最大相关系数阈值 (默认: 0.7)'
    )

    # 无偏评分参数
    parser.add_argument(
        '--enable-unbiased-scoring', action='store_true',
        help='启用无偏评分系统 (默认: 启用)'
    )
    parser.add_argument(
        '--disable-unbiased-scoring', action='store_true',
        help='禁用无偏评分系统，回退到传统排序方式'
    )
    parser.add_argument(
        '--score-mode', type=str, choices=['optimized', 'legacy'], default=argparse.SUPPRESS,
        help='综合评分模式：optimized（新公式）或 legacy（默认，旧版权重与动量配比）'
    )

    # 去重参数
    parser.add_argument(
        '--enable-deduplication', action='store_true',
        help='启用智能去重功能 (默认: 启用)'
    )
    parser.add_argument(
        '--disable-deduplication', action='store_true',
        help='禁用智能去重功能'
    )
    parser.add_argument(
        '--dedup-min-ratio', type=float, default=argparse.SUPPRESS,
        help='去重后最小保留比例 (默认: 0.8, 即保留80%%目标数量)'
    )

    # 二级筛选模式控制
    parser.add_argument(
        '--skip-stage2-filtering', action='store_true',
        help='跳过第二级的百分位筛选（ADX、收益回撤比），直接按综合评分排序返回topN'
    )

    # V2分散逻辑控制
    parser.add_argument(
        '--diversify-v2', action='store_true',
        help='启用V2分散逻辑：P0-贪心选择使用max pairwise相关性（而非平均相关性），'
             'P1-去重时Score差异显著则无条件保留高分者（趋势跟踪优先）'
    )
    parser.add_argument(
        '--score-diff-threshold', type=float, default=argparse.SUPPRESS,
        help='V2去重时Score差异阈值，超过则无条件保留高分（默认: 0.05，即5%%）'
    )

    # 技术参数
    parser.add_argument(
        '--ma-short', type=int, default=argparse.SUPPRESS,
        help='双均线策略短期均线周期 (默认: 20)'
    )
    parser.add_argument(
        '--ma-long', type=int, default=argparse.SUPPRESS,
        help='双均线策略长期均线周期 (默认: 50)'
    )
    parser.add_argument(
        '--adx-period', type=int, default=argparse.SUPPRESS,
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
    # 如果指定了配置文件，使用ConfigLoader加载
    if config_path:
        try:
            config = ConfigLoader.load_from_json(config_path)
            print(f"✅ 已加载配置文件: {config_path}")
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            print("🔄 使用默认配置")
            config = FilterConfig()
    else:
        config = FilterConfig()

    # 使用命令行参数覆盖配置（CLI优先级最高）
    if args:
        config = ConfigLoader.merge_with_cli_args(config, args)

    return config


def print_banner():
    """打印程序横幅"""
    print("=" * 80)
    print(" ETF趋势筛选系统 v1.0")
    print(" 基于三级漏斗模型的量化标的筛选")
    print("=" * 80)
    print()


def print_config_summary(config: FilterConfig):
    """打印配置摘要（仅使用config对象，不依赖args）"""
    print("📋 筛选配置摘要:")
    print(f"  🎯 目标组合大小: {config.target_portfolio_size} 只")
    print(f"  💰 流动性阈值: {config.min_turnover/1e8:.2f} 亿元")
    print(f"  📅 最小上市天数: {config.min_listing_days} 天")
    print(f"  📊 ADX筛选: 保留前 {100 - config.adx_percentile:.0f}%")
    ret_dd_summary = f"保留前 {100 - config.ret_dd_percentile:.0f}%"
    if not config.enable_ma_backtest_filter:
        ret_dd_summary += "（已禁用）"
    print(f"  📈 收益回撤比筛选: {ret_dd_summary}")
    print(f"  🌊 波动率范围: {config.min_volatility*100:.0f}% - {config.max_volatility*100:.0f}%")
    print(f"  🚀 动量要求: {'仅要求>0' if config.momentum_min_positive else '排名筛选'}")
    print(f"  📏 双均线过滤: {'启用' if config.enable_ma_backtest_filter else '禁用'}")
    score_mode = "优化版（超额/质量/ADX/量能）" if config.use_optimized_score else "旧版（ADX+趋势一致性+效率+流动性+3M/12M动量）"
    print(f"  🎯 无偏评分系统: {'启用 - ' + score_mode if config.enable_unbiased_scoring else '禁用 (传统排序)'}")
    print(f"  🔗 最大相关性: {config.max_correlation}")
    print(f"  📈 双均线参数: MA({config.ma_short}, {config.ma_long})")
    # V2分散模式
    if getattr(config, 'diversify_v2', False):
        print(f"  🆕 分散V2模式: 启用 (max pairwise相关性 + Score优先去重)")
        print(f"     Score差异阈值: {getattr(config, 'score_diff_threshold', 0.05):.0%}")
    print()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 设置输出详细程度（这两个使用action='store_true'所以默认为False）
    verbose = getattr(args, 'verbose', True) and not getattr(args, 'quiet', False)

    if verbose:
        print_banner()

    # 加载配置 - config属性使用SUPPRESS，未传时为None
    config = load_config(getattr(args, 'config', None), args)

    if verbose:
        # 打印完整配置参数
        ConfigLoader.print_all_params(config, title="完整配置参数（用于验收和调试）")
        print()
        print_config_summary(config)

    # 初始化筛选器
    try:
        if verbose:
            print("🚀 初始化ETF筛选器...")

        # data_dir使用配置值或默认值
        data_dir = getattr(args, 'data_dir', None) or config.data_dir
        data_loader = ETFDataLoader(data_dir)
        selector = TrendETFSelector(config=config, data_loader=data_loader)

        if verbose:
            print("✅ 筛选器初始化完成")

    except Exception as e:
        print(f"❌ 筛选器初始化失败: {e}")
        return 1

    # 执行筛选流程
    try:
        # 从args获取日期参数，未传时从config获取
        start_date = getattr(args, 'start_date', None) or config.start_date
        end_date = getattr(args, 'end_date', None) or config.end_date

        if verbose:
            print("\n🎯 开始执行筛选流程...")
            print(f"📅 数据期间: {start_date or '全部'} 至 {end_date or '全部'}")

        # 目标大小使用配置值
        target_size = config.target_portfolio_size

        if getattr(args, 'no_portfolio_optimization', False):
            if verbose:
                print("⚠️ 已跳过第三级组合优化")

        selected_etfs = selector.run_pipeline(
            start_date=start_date,
            end_date=end_date,
            target_size=target_size,
            verbose=verbose,
            diversify_v2=config.diversify_v2,
            score_diff_threshold=config.score_diff_threshold
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
    output_arg = getattr(args, 'output', None)
    if output_arg:
        output_path = Path(output_arg)
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
    if getattr(args, 'with_analysis', False):
        try:
            if verbose:
                print(f"\n📊 生成组合风险分析...")

            from etf_selector.portfolio import PortfolioOptimizer
            optimizer = PortfolioOptimizer(data_loader=data_loader)

            analysis_path = output_path.with_suffix('.analysis.txt')
            optimizer.export_portfolio_analysis(
                selected_etfs,
                analysis_path,
                start_date=start_date,
                end_date=end_date
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
                    ret_dd = etf.get('return_dd_ratio', 'N/A')
                    if isinstance(ret_dd, float) and math.isnan(ret_dd):
                        ret_dd = 'N/A'
                    print(f"     行业: {etf['industry']}, 收益回撤比: {ret_dd}")

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
