"""命令行参数解析"""

import argparse
from typing import List

from .strategy_registry import get_global_registry


def create_argument_parser() -> argparse.ArgumentParser:
    """
    创建命令行参数解析器

    Returns:
        配置好的ArgumentParser对象
    """
    parser = argparse.ArgumentParser(
        description='中国市场回测系统 - 使用 backtesting.py 对 ETF / 基金进行策略回测',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 对单只 ETF 运行双均线策略
  python backtest_runner.py -s 159001.SZ -t sma_cross

  # 批量回测所有 ETF
  python backtest_runner.py --category etf -t all

  # 指定多个标的并优化参数
  python backtest_runner.py -s 159001.SZ,510300.SH -t sma_cross -o

  # 限定日期范围
  python backtest_runner.py -s all --start-date 2020-01-01 --end-date 2023-12-31
        """,
    )

    # === 基础参数 ===
    _add_basic_arguments(parser)

    # === 成本参数 ===
    _add_cost_arguments(parser)

    # === 数据参数 ===
    _add_data_arguments(parser)

    # === 低波动过滤参数 ===
    _add_volatility_filter_arguments(parser)

    # === 过滤器参数（sma_cross_enhanced 策略专用）===
    _add_sma_filter_arguments(parser)

    # === MACD策略过滤器参数 ===
    _add_macd_filter_arguments(parser)

    return parser


def _add_basic_arguments(parser: argparse.ArgumentParser) -> None:
    """添加基础参数"""
    registry = get_global_registry()
    strategy_choices = registry.list_strategies() + ['all']

    parser.add_argument(
        '-s',
        '--stock',
        default='all',
        help='标的代码（逗号分隔），默认为 all 处理所有标的。支持 category:etf 语法。',
    )
    parser.add_argument(
        '--stock-list',
        type=str,
        default=None,
        help='从CSV文件读取标的列表（需包含ts_code列），优先级高于-s参数。',
    )
    parser.add_argument(
        '--category',
        default=None,
        help='按类别过滤标的（逗号分隔），例如 etf,fund。',
    )
    parser.add_argument(
        '-t',
        '--strategy',
        choices=strategy_choices,
        default='sma_cross',
        help='策略选择，默认 sma_cross。',
    )
    parser.add_argument(
        '-o',
        '--optimize',
        action='store_true',
        help='启用参数优化。',
    )
    parser.add_argument(
        '-m',
        '--cash',
        type=float,
        default=10000,
        help='初始资金，默认 10000。',
    )
    parser.add_argument(
        '-d',
        '--output-dir',
        default='results',
        help='输出目录，默认 results。',
    )
    parser.add_argument(
        '--instrument-limit',
        type=int,
        default=None,
        help='限制本次回测的标的数量，按筛选顺序截取前 N 个。',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='输出详细日志（默认仅显示回测汇总）。',
    )
    parser.add_argument(
        '--save-params',
        type=str,
        default=None,
        help='保存优化参数到指定配置文件（仅在optimize模式下有效）。',
    )


def _add_cost_arguments(parser: argparse.ArgumentParser) -> None:
    """添加成本参数"""
    parser.add_argument(
        '--cost-model',
        choices=['default', 'cn_etf', 'cn_stock', 'us_stock', 'custom'],
        default='cn_etf',
        help='交易成本模型，默认 cn_etf（中国A股ETF）。',
    )
    parser.add_argument(
        '-c',
        '--commission',
        type=float,
        default=None,
        help='自定义佣金率（覆盖cost-model配置），使用custom模型时必填。',
    )
    parser.add_argument(
        '--spread',
        type=float,
        default=None,
        help='自定义滑点率（覆盖cost-model配置）。',
    )


def _add_data_arguments(parser: argparse.ArgumentParser) -> None:
    """添加数据参数"""
    parser.add_argument(
        '--data-dir',
        default='data/chinese_stocks',
        help='数据目录，默认 data/chinese_stocks。',
    )
    parser.add_argument(
        '--aggregate-output',
        default=None,
        help='可选：将聚合结果写入指定 CSV 文件（预留统一汇总接口）。',
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='开始日期，格式 YYYY-MM-DD。',
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='结束日期，格式 YYYY-MM-DD。',
    )


def _add_volatility_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """添加低波动过滤参数"""
    parser.add_argument(
        '--min-annual-vol',
        type=float,
        default=0.02,
        help='低波动过滤的年化波动率阈值 (默认 0.02，即 2%%)。',
    )
    parser.add_argument(
        '--vol-lookback',
        type=int,
        default=60,
        help='计算年化波动率的收益样本数量 (默认 60)。',
    )
    parser.add_argument(
        '--low-vol-blacklist',
        default='159001.SZ',
        help='逗号分隔的低波动黑名单，默认包含 159001.SZ。传入 none 表示不启用黑名单。',
    )
    parser.add_argument(
        '--disable-low-vol-filter',
        action='store_true',
        help='关闭低波动标的过滤逻辑。',
    )


def _add_sma_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """添加双均线增强策略过滤器参数"""
    filter_group = parser.add_argument_group('过滤器参数（仅sma_cross_enhanced策略可用）')

    # 过滤器开关
    filter_group.add_argument(
        '--enable-slope-filter',
        action='store_true',
        help='启用均线斜率过滤器',
    )
    filter_group.add_argument(
        '--enable-adx-filter',
        action='store_true',
        help='启用ADX趋势强度过滤器',
    )
    filter_group.add_argument(
        '--enable-volume-filter',
        action='store_true',
        help='启用成交量确认过滤器',
    )
    filter_group.add_argument(
        '--enable-confirm-filter',
        action='store_true',
        help='启用持续确认过滤器',
    )
    filter_group.add_argument(
        '--enable-loss-protection',
        action='store_true',
        help='启用连续止损保护（推荐，夏普比率+75%%，最大回撤-34%%）',
    )

    # 过滤器参数配置
    filter_group.add_argument(
        '--slope-lookback',
        type=int,
        default=5,
        help='斜率过滤器回溯周期，默认5',
    )
    filter_group.add_argument(
        '--adx-period',
        type=int,
        default=14,
        help='ADX计算周期，默认14',
    )
    filter_group.add_argument(
        '--adx-threshold',
        type=float,
        default=25.0,
        help='ADX阈值，默认25',
    )
    filter_group.add_argument(
        '--volume-period',
        type=int,
        default=20,
        help='成交量均值周期，默认20',
    )
    filter_group.add_argument(
        '--volume-ratio',
        type=float,
        default=1.2,
        help='成交量放大倍数，默认1.2',
    )
    filter_group.add_argument(
        '--confirm-bars',
        type=int,
        default=2,
        help='持续确认所需K线数，默认2',
    )
    filter_group.add_argument(
        '--max-consecutive-losses',
        type=int,
        default=3,
        help='触发保护的最大连续亏损次数，默认3（推荐值，来自实验结果）',
    )
    filter_group.add_argument(
        '--pause-bars',
        type=int,
        default=10,
        help='触发保护后暂停的K线数，默认10（推荐值，来自实验结果）',
    )


def _add_macd_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """添加MACD策略过滤器参数"""
    macd_filter_group = parser.add_argument_group('MACD策略过滤器参数（仅macd_cross策略可用）')

    # MACD过滤器开关
    macd_filter_group.add_argument(
        '--enable-macd-adx-filter',
        action='store_true',
        help='启用MACD策略的ADX过滤器',
    )
    macd_filter_group.add_argument(
        '--enable-macd-volume-filter',
        action='store_true',
        help='启用MACD策略的成交量过滤器',
    )
    macd_filter_group.add_argument(
        '--enable-macd-slope-filter',
        action='store_true',
        help='启用MACD策略的MACD斜率过滤器',
    )
    macd_filter_group.add_argument(
        '--enable-macd-confirm-filter',
        action='store_true',
        help='启用MACD策略的持续确认过滤器',
    )

    # MACD过滤器参数配置
    macd_filter_group.add_argument(
        '--macd-adx-period',
        type=int,
        default=14,
        help='MACD策略ADX计算周期，默认14',
    )
    macd_filter_group.add_argument(
        '--macd-adx-threshold',
        type=float,
        default=25.0,
        help='MACD策略ADX阈值，默认25',
    )
    macd_filter_group.add_argument(
        '--macd-volume-period',
        type=int,
        default=20,
        help='MACD策略成交量均值周期，默认20',
    )
    macd_filter_group.add_argument(
        '--macd-volume-ratio',
        type=float,
        default=1.2,
        help='MACD策略成交量放大倍数，默认1.2',
    )
    macd_filter_group.add_argument(
        '--macd-slope-lookback',
        type=int,
        default=5,
        help='MACD斜率回溯周期，默认5',
    )
    macd_filter_group.add_argument(
        '--macd-confirm-bars',
        type=int,
        default=2,
        help='MACD确认所需K线数，默认2',
    )

    # MACD止损保护参数（Phase 3）
    macd_filter_group.add_argument(
        '--enable-macd-loss-protection',
        action='store_true',
        help='启用MACD策略的连续止损保护（⭐⭐⭐强烈推荐）',
    )
    macd_filter_group.add_argument(
        '--macd-max-consecutive-losses',
        type=int,
        default=3,
        help='MACD策略连续亏损次数阈值，默认3',
    )
    macd_filter_group.add_argument(
        '--macd-pause-bars',
        type=int,
        default=10,
        help='MACD策略触发保护后暂停交易的K线数，默认10',
    )
    macd_filter_group.add_argument(
        '--macd-debug-loss-protection',
        action='store_true',
        help='启用MACD策略止损保护调试日志',
    )

    # MACD跟踪止损参数（Phase 3b）
    macd_filter_group.add_argument(
        '--enable-macd-trailing-stop',
        action='store_true',
        help='启用MACD策略的跟踪止损',
    )
    macd_filter_group.add_argument(
        '--macd-trailing-stop-pct',
        type=float,
        default=0.05,
        help='MACD策略跟踪止损百分比，默认0.05（5%%）',
    )
