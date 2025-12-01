#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
命令行接口模块

提供 generate_signals 命令行参数解析和模式处理。
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtest_runner.utils.argparse_utils import UnderscoreHyphenArgumentParser

from .config import COST_MODELS
from .core import SignalGenerator
from .reports import (
    print_signal_report,
    print_portfolio_status,
    print_trade_plan,
    print_execution_summary,
    print_snapshot_info,
    print_snapshot_list,
    print_restore_preview,
    print_data_info,
)


def create_argument_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = UnderscoreHyphenArgumentParser(
        description='生成实盘交易信号',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 工作模式
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--init', type=float, metavar='CASH',
                           help='初始化持仓文件（指定初始资金）')
    mode_group.add_argument('--status', action='store_true',
                           help='查看持仓状态')
    mode_group.add_argument('--analyze', action='store_true',
                           help='分析模式（生成交易建议但不执行）')
    mode_group.add_argument('--execute', action='store_true',
                           help='执行模式（执行交易并更新持仓）')
    mode_group.add_argument('--restore', type=str, metavar='YYYYMMDD',
                           help='恢复持仓到指定日期的快照')
    mode_group.add_argument('--list-snapshots', action='store_true',
                           help='列出所有可用的持仓快照')

    # 基本参数
    parser.add_argument('--stock-list',
                       help='股票列表CSV文件路径')
    parser.add_argument('--portfolio-file',
                       help='持仓文件路径（JSON格式）')
    parser.add_argument('--strategy', default='sma_cross',
                       help='策略名称（默认: sma_cross）')
    parser.add_argument('--cash', type=float, default=100000,
                       help='可用资金（默认: 100000，仅无状态模式）')
    parser.add_argument('--positions', type=int, default=10,
                       help='目标持仓数量（默认: 10）')
    parser.add_argument('--cost-model', default='cn_etf',
                       help='费用模型（默认: cn_etf）')
    parser.add_argument('--data-dir', default='data/csv/daily',
                       help='数据目录（默认: data/csv/daily）')
    parser.add_argument('--lookback-days', type=int, default=250,
                       help='回看天数（默认: 250）')
    parser.add_argument('--output', help='输出报告文件路径（可选）')
    parser.add_argument('--csv', help='输出CSV文件路径（可选）')

    # 策略参数
    parser.add_argument('--n1', type=int, help='短期均线周期')
    parser.add_argument('--n2', type=int, help='长期均线周期')
    parser.add_argument('--load-params', type=str, help='从配置文件加载策略参数')

    # 仓位管理参数
    parser.add_argument('--max-position-pct', type=float, default=0.05,
                       help='单仓位上限，占总资金的百分比（默认: 0.05，即5%%）')
    parser.add_argument('--min-buy-signals', type=int, default=1,
                       help='最小买入信号数，少于此数不执行买入（默认: 1）')

    # 日期范围参数
    parser.add_argument('--start-date', type=str,
                       help='起始日期（格式: YYYYMMDD）')
    parser.add_argument('--end-date', type=str,
                       help='截止日期（格式: YYYYMMDD）')

    # 价格模式
    parser.add_argument('--disable-dual-price', action='store_true',
                       help='禁用双价格模式')

    # Anti-Whipsaw 参数
    parser.add_argument('--enable-hysteresis', action='store_true',
                        help='启用自适应滞回阈值')
    parser.add_argument('--hysteresis-mode', choices=['std', 'abs'],
                        help='滞回阈值模式')
    parser.add_argument('--hysteresis-k', type=float,
                        help='std模式下的系数k')
    parser.add_argument('--hysteresis-window', type=int,
                        help='std模式 rolling std 的窗口大小')
    parser.add_argument('--hysteresis-abs', type=float,
                        help='abs模式下的绝对阈值')
    parser.add_argument('--confirm-bars-sell', type=int,
                        help='卖出确认所需K线数')
    parser.add_argument('--min-hold-bars', type=int,
                        help='最短持有期')
    parser.add_argument('--enable-zero-axis', action='store_true',
                        help='启用零轴约束')
    parser.add_argument('--zero-axis-mode', type=str,
                        help='零轴约束模式')

    # 执行参数
    parser.add_argument('--yes', '-y', action='store_true',
                       help='（已弃用）自动执行')
    parser.add_argument('--force', action='store_true',
                       help='强制执行，即使当天已有执行记录')

    return parser


def load_strategy_class(strategy_name: str):
    """
    加载策略类

    Args:
        strategy_name: 策略名称

    Returns:
        策略类
    """
    try:
        if strategy_name == 'sma_cross':
            from strategies.sma_cross import SmaCross
            return SmaCross
        elif strategy_name == 'sma_cross_enhanced':
            from strategies.sma_cross_enhanced import SmaCrossEnhanced
            return SmaCrossEnhanced
        elif strategy_name == 'macd_cross':
            from strategies.macd_cross import MacdCross
            return MacdCross
        elif strategy_name == 'kama_cross':
            from strategies.kama_cross import KamaCrossStrategy
            return KamaCrossStrategy
        else:
            print(f"错误: 未知策略 '{strategy_name}'")
            sys.exit(1)
    except ImportError as e:
        print(f"错误: 无法加载策略 '{strategy_name}': {e}")
        sys.exit(1)


def load_strategy_params(args) -> dict:
    """
    加载策略参数

    Args:
        args: 命令行参数

    Returns:
        策略参数字典
    """
    from utils.strategy_params_manager import StrategyParamsManager

    strategy_params = {}

    # 从配置文件加载
    if args.load_params:
        try:
            params_manager = StrategyParamsManager(args.load_params)
            loaded_params = params_manager.get_strategy_params(args.strategy)
            strategy_params.update(loaded_params)
            print(f"✓ 从配置文件加载参数: {loaded_params}")

            # 加载运行时配置
            runtime_config = params_manager.get_runtime_config(args.strategy)
            if runtime_config:
                print(f"✓ 从配置文件加载运行时配置")
                _apply_runtime_config(strategy_params, runtime_config)
            else:
                print("  ⚠️ 配置文件中没有运行时配置，使用默认值")

        except Exception as e:
            print(f"⚠️ 加载配置文件失败: {e}")
            print("使用命令行参数或默认参数")

    # 命令行参数覆盖
    _apply_cli_overrides(strategy_params, args)

    if not strategy_params:
        print("使用策略默认参数")

    return strategy_params


def _apply_runtime_config(strategy_params: dict, runtime_config: dict):
    """应用运行时配置"""
    # 过滤器配置
    if 'filters' in runtime_config:
        strategy_params.update(runtime_config['filters'])
        filters_info = ', '.join([
            f"{k.replace('enable_', '')}={'ON' if v else 'OFF'}"
            for k, v in runtime_config['filters'].items()
            if k.startswith('enable_')
        ])
        print(f"  过滤器: {filters_info}")

    # 止损保护配置
    if 'loss_protection' in runtime_config:
        strategy_params.update(runtime_config['loss_protection'])
        if runtime_config['loss_protection'].get('enable_loss_protection'):
            print(f"  止损保护: ON (连续亏损={runtime_config['loss_protection'].get('max_consecutive_losses')}, "
                  f"暂停={runtime_config['loss_protection'].get('pause_bars')})")
        else:
            print(f"  止损保护: OFF")

    # Anti-Whipsaw 配置
    if 'anti_whipsaw' in runtime_config:
        strategy_params.update(runtime_config['anti_whipsaw'])
        aw = runtime_config['anti_whipsaw']
        flags = []
        if aw.get('enable_hysteresis'):
            flags.append("hysteresis=ON")
        if aw.get('enable_zero_axis'):
            flags.append("zero_axis=ON")
        if flags:
            print("  防贴线: " + ", ".join(flags))

    # 跟踪止损配置
    if 'trailing_stop' in runtime_config:
        strategy_params.update(runtime_config['trailing_stop'])
        ts = runtime_config['trailing_stop']
        if ts.get('enable_trailing_stop'):
            print(f"  跟踪止损: ON (止损比例={ts.get('trailing_stop_pct', 0.05):.1%})")

    # ATR止损配置
    if 'atr_stop' in runtime_config:
        strategy_params.update(runtime_config['atr_stop'])
        atr = runtime_config['atr_stop']
        if atr.get('enable_atr_stop'):
            print(f"  ATR止损: ON (周期={atr.get('atr_period', 14)}, 倍数={atr.get('atr_multiplier', 2.5)})")


def _apply_cli_overrides(strategy_params: dict, args):
    """应用命令行参数覆盖"""
    if args.n1:
        strategy_params['n1'] = args.n1
        print(f"使用命令行指定的 n1: {args.n1}")
    if args.n2:
        strategy_params['n2'] = args.n2
        print(f"使用命令行指定的 n2: {args.n2}")

    # Anti-Whipsaw CLI 覆盖
    if args.enable_hysteresis:
        strategy_params['enable_hysteresis'] = True
    if args.hysteresis_mode:
        strategy_params['hysteresis_mode'] = args.hysteresis_mode
    if args.hysteresis_k is not None:
        strategy_params['hysteresis_k'] = args.hysteresis_k
    if args.hysteresis_window is not None:
        strategy_params['hysteresis_window'] = args.hysteresis_window
    if args.hysteresis_abs is not None:
        strategy_params['hysteresis_abs'] = args.hysteresis_abs
    if args.confirm_bars_sell is not None:
        strategy_params['confirm_bars_sell'] = args.confirm_bars_sell
    if args.min_hold_bars is not None:
        strategy_params['min_hold_bars'] = args.min_hold_bars
    if args.enable_zero_axis:
        strategy_params['enable_zero_axis'] = True
    if args.zero_axis_mode:
        strategy_params['zero_axis_mode'] = args.zero_axis_mode


# ========== 模式处理函数 ==========

def handle_init_mode(args):
    """处理初始化模式"""
    from portfolio_manager import Portfolio

    if not args.portfolio_file:
        print("错误: 初始化模式必须指定 --portfolio-file")
        sys.exit(1)

    if args.init <= 0:
        print("错误: 初始资金必须大于0")
        sys.exit(1)

    Portfolio.initialize(args.init, args.portfolio_file)
    print("=" * 80)
    print("✓ 持仓状态已初始化")
    print("=" * 80)
    print(f"  初始资金: ¥{args.init:,.2f}")
    print(f"  持仓文件: {args.portfolio_file}")
    print("=" * 80)


def handle_status_mode(args):
    """处理状态查看模式"""
    from portfolio_manager import Portfolio

    if not args.portfolio_file:
        print("错误: 状态查看模式必须指定 --portfolio-file")
        sys.exit(1)

    try:
        portfolio = Portfolio.load(args.portfolio_file)
    except FileNotFoundError:
        print(f"错误: 持仓文件不存在: {args.portfolio_file}")
        print("请先使用 --init 初始化持仓文件")
        sys.exit(1)

    # 获取当前价格
    generator = SignalGenerator(
        strategy_class=None,
        cash=0,
        cost_model=args.cost_model,
        data_dir=args.data_dir,
        lookback_days=args.lookback_days,
        start_date=getattr(args, 'start_date', None),
        end_date=getattr(args, 'end_date', None)
    )

    current_prices = {}
    for pos in portfolio.positions:
        df = generator.load_instrument_data(pos.ts_code)
        if df is not None:
            current_prices[pos.ts_code] = df['Close'].iloc[-1]
        else:
            current_prices[pos.ts_code] = pos.entry_price

    print_portfolio_status(portfolio, current_prices, args.positions)


def handle_list_snapshots_mode(args):
    """处理列出快照模式"""
    from portfolio_manager import SnapshotManager

    if not args.portfolio_file:
        print("错误: 列出快照模式必须指定 --portfolio-file")
        sys.exit(1)

    history_dir = Path(args.portfolio_file).parent / 'history'
    snapshot_manager = SnapshotManager(str(history_dir))
    portfolio_name = Path(args.portfolio_file).stem

    snapshots = snapshot_manager.list_snapshots(portfolio_name)
    print_snapshot_list(snapshots, portfolio_name)


def handle_restore_mode(args):
    """处理恢复快照模式"""
    import shutil
    from portfolio_manager import SnapshotManager

    if not args.portfolio_file:
        print("错误: 恢复模式必须指定 --portfolio-file")
        sys.exit(1)

    history_dir = Path(args.portfolio_file).parent / 'history'
    invalid_history_dir = Path(args.portfolio_file).parent / 'invalid_history'
    snapshot_manager = SnapshotManager(str(history_dir))
    portfolio_name = Path(args.portfolio_file).stem

    snapshot_data = snapshot_manager.load_snapshot(args.restore, portfolio_name)
    if not snapshot_data:
        print(f"错误: 未找到日期 {args.restore} 的快照")
        print("使用 --list-snapshots 查看可用快照")
        sys.exit(1)

    print_restore_preview(args.restore, snapshot_data)
    print("")

    # 查找并移动回滚日期之后的历史记录
    restore_date = int(args.restore)
    files_to_move = []

    if history_dir.exists():
        for filepath in history_dir.glob(f"*_{portfolio_name}_*.json"):
            # 从文件名提取日期，格式: trades_xxx_YYYYMMDD.json 或 snapshot_xxx_YYYYMMDD.json
            filename = filepath.name
            # 提取最后的日期部分（去掉.json后取最后8位数字）
            date_part = filename.replace('.json', '').split('_')[-1]
            if date_part.isdigit() and len(date_part) == 8:
                file_date = int(date_part)
                if file_date > restore_date:
                    files_to_move.append(filepath)

    print("⚠️  警告: 恢复操作将覆盖当前持仓文件！")
    print(f"  目标文件: {args.portfolio_file}")
    if files_to_move:
        print(f"  将移动 {len(files_to_move)} 个历史记录到 invalid_history/")
        for f in sorted(files_to_move):
            print(f"    - {f.name}")
    print("")
    print("正在执行恢复...")

    # 移动历史记录到 invalid_history
    if files_to_move:
        invalid_history_dir.mkdir(parents=True, exist_ok=True)
        for filepath in files_to_move:
            dest = invalid_history_dir / filepath.name
            # 如果目标已存在，添加时间戳避免覆盖
            if dest.exists():
                from datetime import datetime
                timestamp = datetime.now().strftime('%H%M%S')
                dest = invalid_history_dir / f"{filepath.stem}_{timestamp}.json"
            shutil.move(str(filepath), str(dest))
        print(f"✓ 已移动 {len(files_to_move)} 个历史记录到 {invalid_history_dir}/")

    portfolio = snapshot_manager.restore_snapshot(
        args.restore,
        args.portfolio_file,
        portfolio_name
    )

    print("")
    print("=" * 80)
    print("✓ 持仓已恢复")
    print("=" * 80)
    print(f"  恢复日期: {args.restore}")
    print(f"  可用现金: ¥{portfolio.cash:,.2f}")
    print(f"  持仓数量: {len(portfolio.positions)}")
    print(f"  持仓文件: {args.portfolio_file}")
    if files_to_move:
        print(f"  已移动历史: {len(files_to_move)} 个文件 → invalid_history/")
    print("=" * 80)


def handle_analyze_execute_mode(args):
    """处理分析/执行模式"""
    from portfolio_manager import Portfolio, PortfolioTrader, TradeLogger, SnapshotManager

    if not args.portfolio_file:
        print("错误: 分析/执行模式必须指定 --portfolio-file")
        sys.exit(1)

    if not args.stock_list:
        print("错误: 分析/执行模式必须指定 --stock-list")
        sys.exit(1)

    # 加载持仓
    try:
        portfolio = Portfolio.load(args.portfolio_file)
    except FileNotFoundError:
        print(f"错误: 持仓文件不存在: {args.portfolio_file}")
        print("请先使用 --init 初始化持仓文件")
        sys.exit(1)

    # 加载策略
    strategy_class = load_strategy_class(args.strategy)
    strategy_params = load_strategy_params(args)

    # 获取费用配置
    cost_config = COST_MODELS.get(args.cost_model, COST_MODELS['cn_etf'])

    # 创建信号生成器
    generator = SignalGenerator(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        cash=portfolio.cash,
        cost_model=args.cost_model,
        data_dir=args.data_dir,
        lookback_days=args.lookback_days,
        use_dual_price=not args.disable_dual_price,
        max_position_pct=args.max_position_pct,
        min_buy_signals=args.min_buy_signals,
        start_date=getattr(args, 'start_date', None),
        end_date=getattr(args, 'end_date', None)
    )

    # 读取股票列表
    stock_df = pd.read_csv(args.stock_list)
    if 'ts_code' not in stock_df.columns:
        print(f"错误: 股票列表文件缺少 'ts_code' 列: {args.stock_list}")
        sys.exit(1)

    ts_codes = stock_df['ts_code'].tolist()

    # 生成信号
    print(f"开始分析 {len(ts_codes)} 只标的...")
    print("=" * 80)

    signals = {}
    current_prices = {}

    for i, ts_code in enumerate(ts_codes, 1):
        print(f"[{i}/{len(ts_codes)}] 分析 {ts_code}...", end=' ')
        signal = generator.get_signal(ts_code)
        signals[ts_code] = signal
        current_prices[ts_code] = signal['price']
        print(f"{signal['signal']}")
        msg = str(signal.get('message', ''))
        if msg.startswith('触发金叉但被过滤') or msg.startswith('触发死叉但被过滤'):
            print(f"    {msg}")

    print("")
    print_data_info(generator)
    print_portfolio_status(portfolio, current_prices, args.positions)

    # 创建交易引擎
    trader = PortfolioTrader(
        portfolio=portfolio,
        commission=cost_config['commission'],
        spread=cost_config.get('spread', 0.0),
        max_positions=args.positions,
        max_position_pct=args.max_position_pct,
        min_buy_signals=args.min_buy_signals,
        trade_date=generator.end_date,
        min_hold_bars=int(strategy_params.get('min_hold_bars', 0)),
        data_dir=args.data_dir
    )

    # 生成交易计划
    sell_trades, buy_trades = trader.generate_trade_plan(signals)
    print_trade_plan(sell_trades, buy_trades, portfolio)

    # 执行模式
    if args.execute:
        _execute_trades(args, generator, portfolio, trader, sell_trades, buy_trades, strategy_params)


def _execute_trades(args, generator, portfolio, trader, sell_trades, buy_trades, strategy_params):
    """执行交易"""
    from portfolio_manager import TradeLogger, SnapshotManager

    # 幂等性检查
    history_dir = Path(args.portfolio_file).parent / 'history'
    portfolio_name = Path(args.portfolio_file).stem
    trade_date_compact = generator.end_date.replace('-', '')
    trade_date_display = generator.end_date

    # 计算前一天日期
    trade_date_obj = datetime.strptime(generator.end_date, '%Y-%m-%d')
    prev_date_obj = trade_date_obj - timedelta(days=1)
    prev_date_compact = prev_date_obj.strftime('%Y%m%d')

    logger = TradeLogger(str(history_dir))
    existing_record = logger.get_execution_record(trade_date_compact, portfolio_name)

    if existing_record and not args.force:
        print_execution_summary(existing_record, trade_date_display)

        snapshot_manager = SnapshotManager(str(history_dir))
        snapshot_data = snapshot_manager.load_snapshot(trade_date_compact, portfolio_name)
        if snapshot_data:
            print_snapshot_info(snapshot_data)

        print("")
        print("=" * 70)
        print("💡 如需重新执行（会覆盖历史记录），请使用 --force 参数")
        print("=" * 70)
        return

    if existing_record and args.force:
        print("")
        print("⚠️  检测到今日已有执行记录，使用 --force 强制覆盖...")
        print("")

    if not sell_trades and not buy_trades:
        print("无需执行任何交易。")
        logger.log_trades(
            [],
            date=trade_date_compact,
            portfolio_name=portfolio_name,
            allow_empty=True,
            execution_context={
                'status': 'no_trade_needed',
                'reason': '今日无交易信号',
                'strategy': args.strategy,
            }
        )
        print(f"✓ 已记录今日检查状态（无需交易）")
        return

    print("")
    print("⚠️  即将执行交易操作：")
    print(f"  - 卖出 {len(sell_trades)} 只标的")
    print(f"  - 买入 {len(buy_trades)} 只标的")
    print("")

    # 保存执行前快照
    snapshot_manager = SnapshotManager(str(history_dir))
    snapshot_path = snapshot_manager.save_snapshot(
        portfolio,
        date=prev_date_compact,
        portfolio_name=portfolio_name,
        snapshot_type='pre_execute'
    )
    print(f"📸 已保存执行前快照: {snapshot_path}")
    print("")

    # 执行交易
    print("")
    print("开始执行交易...")
    trader.execute_trades(sell_trades, buy_trades, dry_run=False)

    for trade in sell_trades:
        print(f"✓ 卖出: {trade.ts_code} {trade.shares}股 @¥{trade.price:.3f} 收入¥{trade.amount:,.2f}")

    for trade in buy_trades:
        print(f"✓ 买入: {trade.ts_code} {trade.shares}股 @¥{trade.price:.3f} 成本¥{abs(trade.amount):,.2f}")

    # 保存持仓
    portfolio.save()
    print(f"\n✓ 持仓已更新: {args.portfolio_file}")

    # 记录交易历史
    all_trades = sell_trades + buy_trades
    logger.log_trades(
        all_trades,
        date=trade_date_compact,
        portfolio_name=portfolio_name,
        execution_context={
            'status': 'executed',
            'strategy': args.strategy,
            'sell_count': len(sell_trades),
            'buy_count': len(buy_trades),
            'forced': getattr(args, 'force', False),
        }
    )
    print(f"✓ 交易记录已保存: {history_dir}/trades_{portfolio_name}_{trade_date_compact}.json")


def handle_stateless_mode(args):
    """处理无状态模式（原有逻辑）"""
    if not args.stock_list:
        print("错误: 必须指定 --stock-list")
        sys.exit(1)

    if not os.path.exists(args.stock_list):
        print(f"错误: 股票列表文件不存在: {args.stock_list}")
        sys.exit(1)

    # 加载策略
    strategy_class = load_strategy_class(args.strategy)

    # 准备策略参数
    strategy_params = {}
    if args.n1:
        strategy_params['n1'] = args.n1
    if args.n2:
        strategy_params['n2'] = args.n2

    # 创建信号生成器
    generator = SignalGenerator(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        cash=args.cash,
        cost_model=args.cost_model,
        data_dir=args.data_dir,
        lookback_days=args.lookback_days,
        use_dual_price=not args.disable_dual_price,
        max_position_pct=args.max_position_pct,
        min_buy_signals=args.min_buy_signals,
        start_date=getattr(args, 'start_date', None),
        end_date=getattr(args, 'end_date', None)
    )

    # 生成信号
    signals_df, allocation = generator.generate_signals_for_pool(
        stock_list_file=args.stock_list,
        target_positions=args.positions
    )

    # 打印报告
    print("\n")
    print_signal_report(signals_df, allocation, args.output)

    # 保存CSV
    if args.csv:
        signals_df.to_csv(args.csv, index=False, encoding='utf-8-sig')
        print(f"信号数据已保存到: {args.csv}")


def main():
    """主函数"""
    # 禁用进度条
    os.environ['BACKTESTING_DISABLE_PROGRESS'] = 'true'

    # 过滤警告
    import warnings
    warnings.filterwarnings('ignore', message='.*Some trades remain open.*')
    warnings.filterwarnings('ignore', category=UserWarning, module='backtesting')

    parser = create_argument_parser()
    args = parser.parse_args()

    # 根据模式处理
    if args.init is not None:
        handle_init_mode(args)
    elif args.status:
        handle_status_mode(args)
    elif args.list_snapshots:
        handle_list_snapshots_mode(args)
    elif args.restore:
        handle_restore_mode(args)
    elif args.analyze or args.execute:
        handle_analyze_execute_mode(args)
    else:
        handle_stateless_mode(args)


if __name__ == '__main__':
    main()
