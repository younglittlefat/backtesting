"""
轮动策略模式

职责：
- ETF 轮动策略回测流程
- 虚拟 ETF 数据构建
- 轮动统计计算
- 轮动模式结果输出
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd

from backtest_runner.config import STRATEGIES, build_strategy_instance
from backtest_runner.data.virtual_etf_builder import VirtualETFBuilder, RebalanceMode
from backtest_runner.io import save_rotation_summary_csv
from backtesting import Backtest


def run_rotation_mode(args) -> int:
    """
    运行 ETF 轮动策略模式

    Args:
        args: 命令行参数

    Returns:
        退出码（0=成功，1=失败）
    """
    _print_rotation_header(args)

    try:
        # 检查是否为对比模式
        if hasattr(args, 'compare_rotation_modes') and args.compare_rotation_modes:
            return _run_rotation_comparison(args)
        else:
            return _run_single_rotation_strategy(args)
    except Exception as e:
        print(f"\n错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def _print_rotation_header(args) -> None:
    """打印轮动模式头部信息"""
    print("=" * 70)
    print("ETF轮动策略回测模式")
    print("=" * 70)
    print(f"轮动表文件: {args.rotation_schedule}")
    print(f"策略选择:   {args.strategy}")
    print(f"再平衡模式: {args.rebalance_mode}")
    print(f"轮动成本:   {args.rotation_trading_cost:.3%}")
    print(f"初始资金:   {args.cash:,.2f}")

    # 显示启用的功能
    enabled_features = _get_enabled_features(args)
    if enabled_features:
        print(f"启用功能:   {', '.join(enabled_features)}")
    else:
        print("启用功能:   Baseline（无过滤器和保护）")
    print("=" * 70)


def _get_enabled_features(args) -> List[str]:
    """获取启用的功能列表"""
    enabled_features = []
    if hasattr(args, 'enable_slope_filter') and args.enable_slope_filter:
        enabled_features.append("斜率过滤")
    if hasattr(args, 'enable_adx_filter') and args.enable_adx_filter:
        enabled_features.append("ADX过滤")
    if hasattr(args, 'enable_volume_filter') and args.enable_volume_filter:
        enabled_features.append("成交量过滤")
    if hasattr(args, 'enable_confirm_filter') and args.enable_confirm_filter:
        enabled_features.append("确认过滤")
    if hasattr(args, 'enable_loss_protection') and args.enable_loss_protection:
        enabled_features.append(f"止损保护({args.max_consecutive_losses}次/{args.pause_bars}bars)")
    return enabled_features


def _run_single_rotation_strategy(args) -> int:
    """运行单个轮动策略"""

    # Step 1: 构建虚拟 ETF 数据
    print("\n[1/3] 构建虚拟ETF数据...")

    builder = VirtualETFBuilder(
        rotation_schedule_path=args.rotation_schedule,
        data_dir=args.data_dir
    )

    rebalance_mode = RebalanceMode(args.rebalance_mode)
    virtual_etf_data = builder.build(
        rebalance_mode=rebalance_mode,
        trading_cost_pct=args.rotation_trading_cost,
        verbose=args.verbose
    )

    # 保存虚拟 ETF 数据（如果指定）
    if hasattr(args, 'save_virtual_etf') and args.save_virtual_etf:
        save_path = Path(args.save_virtual_etf)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        virtual_etf_data.to_csv(save_path)
        if args.verbose:
            print(f"虚拟ETF数据已保存到: {save_path}")

    # Step 2: 应用策略回测
    print(f"\n[2/3] 应用{args.strategy}策略...")

    strategy_class = STRATEGIES[args.strategy]
    ParameterizedStrategy = build_strategy_instance(strategy_class, args)

    bt = Backtest(
        virtual_etf_data,
        ParameterizedStrategy,
        cash=args.cash,
        commission=0.0,  # 成本已在虚拟 ETF 中计入
    )

    stats = bt.run()

    # Step 3: 输出结果
    print(f"\n[3/3] 结果分析...")

    rotation_stats = _calculate_rotation_stats(virtual_etf_data, stats)
    _print_rotation_results(stats, rotation_stats, args)

    # 保存结果（如果指定汇总输出）
    if args.aggregate_output:
        save_rotation_summary_csv(stats, rotation_stats, args)
        print(f"\n汇总结果已保存: {args.aggregate_output}")

    return 0


def _run_rotation_comparison(args) -> int:
    """对比两种再平衡模式"""

    print("\n" + "=" * 70)
    print("再平衡模式对比实验")
    print("=" * 70)

    modes = [RebalanceMode.FULL_LIQUIDATION, RebalanceMode.INCREMENTAL]
    results = {}

    for mode in modes:
        print(f"\n运行{mode.value}模式...")

        # 临时修改参数
        original_mode = args.rebalance_mode
        args.rebalance_mode = mode.value

        try:
            # 构建虚拟 ETF
            builder = VirtualETFBuilder(
                rotation_schedule_path=args.rotation_schedule,
                data_dir=args.data_dir
            )

            virtual_etf_data = builder.build(
                rebalance_mode=mode,
                trading_cost_pct=args.rotation_trading_cost,
                verbose=False  # 减少噪音
            )

            # 运行回测
            strategy_class = STRATEGIES[args.strategy]
            ParameterizedStrategy = build_strategy_instance(strategy_class, args)

            bt = Backtest(
                virtual_etf_data,
                ParameterizedStrategy,
                cash=args.cash,
                commission=0.0,
            )

            stats = bt.run()
            rotation_stats = _calculate_rotation_stats(virtual_etf_data, stats)

            results[mode.value] = {
                'backtest_stats': stats,
                'rotation_stats': rotation_stats,
            }

        finally:
            # 恢复原始参数
            args.rebalance_mode = original_mode

    # 对比结果
    _print_rotation_comparison_results(results)

    return 0


def _calculate_rotation_stats(virtual_etf_data: pd.DataFrame, backtest_stats) -> Dict:
    """计算轮动相关的统计信息"""

    # 轮动次数和成本
    rebalance_dates = virtual_etf_data[virtual_etf_data['rebalance_cost'] > 0]
    total_rotations = len(rebalance_dates)
    total_rebalance_cost = virtual_etf_data['rebalance_cost'].sum()

    # 平均轮动间隔
    if total_rotations > 1:
        rotation_dates = rebalance_dates.index
        intervals = [
            (rotation_dates[i] - rotation_dates[i - 1]).days
            for i in range(1, len(rotation_dates))
        ]
        avg_rotation_interval = sum(intervals) / len(intervals)
    else:
        avg_rotation_interval = None

    # 活跃 ETF 统计
    avg_active_etfs = virtual_etf_data['active_etf_count'].mean()

    return {
        'total_rotations': total_rotations,
        'total_rebalance_cost_pct': total_rebalance_cost,
        'avg_rotation_interval_days': avg_rotation_interval,
        'avg_active_etfs': avg_active_etfs,
        'rebalance_dates': rebalance_dates.index.tolist(),
    }


def _print_rotation_results(stats, rotation_stats: Dict, args) -> None:
    """打印轮动策略结果"""

    print("\n" + "=" * 70)
    print("ETF轮动策略回测结果")
    print("=" * 70)

    # 基本信息
    print(f"策略: {args.strategy}")
    print(f"再平衡模式: {args.rebalance_mode}")
    print(f"交易成本: {args.rotation_trading_cost:.3%}")

    # 轮动统计
    print(f"\n轮动统计:")
    print(f"  总轮动次数: {rotation_stats['total_rotations']}")
    print(f"  累计轮动成本: {rotation_stats['total_rebalance_cost_pct']:.3%}")
    if rotation_stats['avg_rotation_interval_days']:
        print(f"  平均轮动间隔: {rotation_stats['avg_rotation_interval_days']:.1f}天")
    print(f"  平均活跃ETF数: {rotation_stats['avg_active_etfs']:.1f}")

    # 策略表现
    print(f"\n策略表现:")
    print(f"  回测期间: {stats['Start']} 至 {stats['End']}")
    print(f"  总收益率: {stats['Return [%]']:.2f}%")
    if 'Return (Ann.) [%]' in stats:
        print(f"  年化收益率: {stats['Return (Ann.) [%]']:.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.3f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")

    if args.verbose and len(rotation_stats['rebalance_dates']) > 0:
        print(f"\n轮动时点:")
        for i, date in enumerate(rotation_stats['rebalance_dates'][:10]):
            print(f"  {i + 1}. {str(date)[:10]}")
        if len(rotation_stats['rebalance_dates']) > 10:
            print(f"  ... 等共{len(rotation_stats['rebalance_dates'])}次轮动")


def _print_rotation_comparison_results(results: Dict) -> None:
    """打印轮动模式对比结果"""

    print("\n" + "=" * 70)
    print("对比结果")
    print("=" * 70)

    headers = ["指标", "全平仓", "增量调整", "差异"]
    print(f"{headers[0]:<20} {headers[1]:<15} {headers[2]:<15} {headers[3]:<15}")
    print("-" * 70)

    # 提取对比数据
    full_stats = results['full_liquidation']['backtest_stats']
    incr_stats = results['incremental']['backtest_stats']
    full_rotation = results['full_liquidation']['rotation_stats']
    incr_rotation = results['incremental']['rotation_stats']

    # 对比项目
    comparisons = [
        ("总收益率(%)", full_stats['Return [%]'], incr_stats['Return [%]']),
        ("夏普比率", full_stats['Sharpe Ratio'], incr_stats['Sharpe Ratio']),
        ("最大回撤(%)", full_stats['Max. Drawdown [%]'], incr_stats['Max. Drawdown [%]']),
        (
            "轮动成本(%)",
            full_rotation['total_rebalance_cost_pct'] * 100,
            incr_rotation['total_rebalance_cost_pct'] * 100
        ),
        ("交易次数", full_stats['# Trades'], incr_stats['# Trades']),
    ]

    for metric, full_val, incr_val in comparisons:
        diff = incr_val - full_val
        diff_str = f"+{diff:.3f}" if diff > 0 else f"{diff:.3f}"
        print(f"{metric:<20} {full_val:<15.3f} {incr_val:<15.3f} {diff_str:<15}")

    # 推荐
    incr_return = incr_stats['Return [%]']
    full_return = full_stats['Return [%]']
    incr_cost = incr_rotation['total_rebalance_cost_pct']
    full_cost = full_rotation['total_rebalance_cost_pct']

    print(f"\n推荐模式:")
    if incr_return > full_return and incr_cost < full_cost:
        print("✅ 增量调整: 收益更高且成本更低")
    elif incr_return > full_return:
        print("✅ 增量调整: 收益更高")
    elif incr_cost < full_cost:
        print("✅ 增量调整: 成本更低")
    else:
        print("⚠️ 全平仓: 需要根据具体情况选择")
