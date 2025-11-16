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

    # === 策略过滤器参数（通用，适用于所有策略）===
    _add_strategy_filter_arguments(parser)

    # === KAMA 策略特有参数（仅在 --strategy kama_cross 时使用）===
    _add_kama_arguments(parser)

    # === Anti-Whipsaw 参数（适用于MACD系列策略）===
    _add_anti_whipsaw_arguments(parser)

    # === 轮动策略参数 ===
    _add_rotation_arguments(parser)

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
    parser.add_argument(
        '--load-params',
        type=str,
        default=None,
        help='从配置文件加载策略参数与运行时配置（与实盘一致）。',
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


def _add_strategy_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """添加策略过滤器参数（通用，适用于所有策略）"""
    filter_group = parser.add_argument_group('策略过滤器参数（通用，适用于所有策略）')

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
        help='启用连续止损保护（⭐⭐⭐强烈推荐，夏普比率+75%%，最大回撤-34%%）',
    )
    filter_group.add_argument(
        '--enable-trailing-stop',
        action='store_true',
        help='启用跟踪止损',
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
    filter_group.add_argument(
        '--trailing-stop-pct',
        type=float,
        default=0.05,
        help='跟踪止损百分比，默认0.05（5%%）',
    )
    filter_group.add_argument(
        '--debug-loss-protection',
        action='store_true',
        help='启用止损保护调试日志',
    )

def _add_kama_arguments(parser: argparse.ArgumentParser) -> None:
    """添加 KAMA 策略特有参数（仅对 kama_cross 策略有效）"""
    g = parser.add_argument_group('KAMA 策略参数（仅对 kama_cross 策略有效）')
    # 核心KAMA参数（可选覆盖）
    g.add_argument('--kama-period', type=int, help='KAMA计算周期（默认20）')
    g.add_argument('--kama-fast', type=int, help='KAMA快速平滑周期（默认2）')
    g.add_argument('--kama-slow', type=int, help='KAMA慢速平滑周期（默认30）')
    # 策略特有过滤器
    g.add_argument('--enable-efficiency-filter', action='store_true', help='启用效率比率过滤（默认关闭）')
    g.add_argument('--min-efficiency-ratio', type=float, help='最小效率比率阈值（默认0.3）')
    g.add_argument('--enable-slope-confirmation', action='store_true', help='启用KAMA斜率确认（默认关闭）')
    g.add_argument('--min-slope-periods', type=int, help='KAMA斜率确认周期（默认3）')

def _add_anti_whipsaw_arguments(parser: argparse.ArgumentParser) -> None:
    """添加 Anti-Whipsaw 参数（MACD 贴线反复抑制）"""
    g = parser.add_argument_group('Anti-Whipsaw（贴线反复抑制，仅对相关策略有效）')
    g.add_argument('--enable-hysteresis', action='store_true', help='启用自适应滞回阈值')
    g.add_argument('--hysteresis-mode', choices=['std', 'abs'], help='滞回模式 std/abs')
    g.add_argument('--hysteresis-k', type=float, help='std模式系数k（阈值=k×std）')
    g.add_argument('--hysteresis-window', type=int, help='std模式rolling窗口')
    g.add_argument('--hysteresis-abs', type=float, help='abs模式绝对阈值')
    g.add_argument('--confirm-bars-sell', type=int, help='卖出确认所需K线数')
    g.add_argument('--min-hold-bars', type=int, help='最短持有期（建仓后N根内忽略相反信号）')
    g.add_argument('--enable-zero-axis', action='store_true', help='启用零轴约束（买在零上/卖在零下）')
    g.add_argument('--zero-axis-mode', type=str, help='零轴约束模式（默认symmetric）')


def _add_rotation_arguments(parser: argparse.ArgumentParser) -> None:
    """添加ETF轮动策略参数"""
    rotation_group = parser.add_argument_group('ETF轮动策略参数 (Phase 3新增功能)')

    # 轮动模式启用开关
    rotation_group.add_argument(
        '--enable-rotation',
        action='store_true',
        help='启用ETF轮动策略模式（需配合--rotation-schedule参数）',
    )
    rotation_group.add_argument(
        '--rotation-schedule',
        type=str,
        default=None,
        help='轮动表JSON文件路径（启用轮动模式时必填）',
    )

    # 轮动配置参数
    rotation_group.add_argument(
        '--rebalance-mode',
        type=str,
        default='incremental',
        choices=['full_liquidation', 'incremental'],
        help='再平衡模式：full_liquidation（全平仓）或 incremental（增量调整），默认incremental',
    )
    rotation_group.add_argument(
        '--rotation-trading-cost',
        type=float,
        default=0.003,
        help='轮动交易成本比例（单边），默认0.003（0.3%%）',
    )

    # 轮动模式对比
    rotation_group.add_argument(
        '--compare-rotation-modes',
        action='store_true',
        help='同时测试两种再平衡模式（full_liquidation vs incremental）并对比结果',
    )

    # 轮动调试和输出
    rotation_group.add_argument(
        '--save-virtual-etf',
        type=str,
        default=None,
        help='保存虚拟ETF数据到CSV文件（用于调试轮动策略）',
    )


# Note: MACD特定参数已移除，所有策略现在使用统一的过滤器参数
# 参见 _add_strategy_filter_arguments() 函数
