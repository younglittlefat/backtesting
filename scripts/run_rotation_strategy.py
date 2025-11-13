#!/usr/bin/env python3
"""
ETF轮动策略回测脚本

Phase 3实现：将现有策略应用到动态轮动的ETF池上

使用方法:
    python scripts/run_rotation_strategy.py \
        --rotation-schedule results/rotation_schedules/rotation_30d.json \
        --strategy kama_cross \
        --rebalance-mode incremental \
        --trading-cost 0.003 \
        --data-dir data/chinese_etf/daily

核心思路:
1. 使用VirtualETFBuilder将轮动的ETF池合成为虚拟ETF
2. 将现有策略（KAMA、SMA、MACD等）应用到虚拟ETF上
3. 比较轮动策略与固定池策略的表现

技术实现:
- 复用现有的策略类（继承BaseEnhancedStrategy）
- 复用现有的过滤器和止损保护功能
- 新增轮动相关的参数解析和数据处理
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest_runner.data.virtual_etf_builder import VirtualETFBuilder, RebalanceMode
from backtest_runner.config.strategy_registry import STRATEGIES
from backtest_runner.processing.filter_builder import build_filter_params
from utils.trading_cost import TradingCostConfig
from strategies.base_strategy import get_strategy_runtime_config
from backtesting import Backtest
import json


def create_rotation_argument_parser():
    """创建轮动策略专用的参数解析器"""
    parser = argparse.ArgumentParser(
        description='ETF轮动策略回测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 基础KAMA轮动策略
    python scripts/run_rotation_strategy.py \\
        --rotation-schedule results/rotation_schedules/rotation_30d.json \\
        --strategy kama_cross \\
        --rebalance-mode incremental \\
        --trading-cost 0.003

    # 带过滤器和止损保护的轮动策略
    python scripts/run_rotation_strategy.py \\
        --rotation-schedule results/rotation_schedules/rotation_30d.json \\
        --strategy kama_cross \\
        --enable-adx-filter \\
        --enable-loss-protection \\
        --rebalance-mode incremental

    # 对比实验：全平仓 vs 增量调整
    python scripts/run_rotation_strategy.py \\
        --rotation-schedule results/rotation_schedules/rotation_30d.json \\
        --strategy kama_cross \\
        --rebalance-mode full_liquidation \\
        --compare-modes
        """
    )

    # 必需参数
    parser.add_argument(
        '--rotation-schedule', type=str, required=True,
        help='轮动表JSON文件路径'
    )
    parser.add_argument(
        '--strategy', type=str, required=True,
        choices=list(STRATEGIES.keys()),
        help='策略名称'
    )

    # 轮动相关参数
    parser.add_argument(
        '--rebalance-mode', type=str, default='incremental',
        choices=['full_liquidation', 'incremental'],
        help='再平衡模式 (default: incremental)'
    )
    parser.add_argument(
        '--trading-cost', type=float, default=0.003,
        help='交易成本比例（单边），默认0.3%'
    )
    parser.add_argument(
        '--data-dir', type=str, default='data/chinese_etf',
        help='ETF数据根目录'
    )
    parser.add_argument(
        '--cash', type=float, default=100000,
        help='初始资金 (default: 100000)'
    )

    # 策略过滤器开关（继承自BaseEnhancedStrategy）
    parser.add_argument(
        '--enable-slope-filter', action='store_true',
        help='启用价格斜率过滤器'
    )
    parser.add_argument(
        '--enable-adx-filter', action='store_true',
        help='启用ADX趋势强度过滤器'
    )
    parser.add_argument(
        '--enable-volume-filter', action='store_true',
        help='启用成交量确认过滤器'
    )
    parser.add_argument(
        '--enable-confirm-filter', action='store_true',
        help='启用持续确认过滤器'
    )

    # 止损保护参数
    parser.add_argument(
        '--enable-loss-protection', action='store_true',
        help='启用连续止损保护'
    )
    parser.add_argument(
        '--max-consecutive-losses', type=int, default=3,
        help='连续亏损次数阈值 (default: 3)'
    )
    parser.add_argument(
        '--pause-bars', type=int, default=10,
        help='触发保护后暂停的K线数 (default: 10)'
    )

    # 过滤器参数
    parser.add_argument(
        '--slope-lookback', type=int, default=5,
        help='斜率计算回溯期 (default: 5)'
    )
    parser.add_argument(
        '--adx-period', type=int, default=14,
        help='ADX计算周期 (default: 14)'
    )
    parser.add_argument(
        '--adx-threshold', type=int, default=25,
        help='ADX阈值 (default: 25)'
    )
    parser.add_argument(
        '--volume-period', type=int, default=20,
        help='成交量均值周期 (default: 20)'
    )
    parser.add_argument(
        '--volume-ratio', type=float, default=1.2,
        help='成交量放大倍数 (default: 1.2)'
    )
    parser.add_argument(
        '--confirm-bars', type=int, default=3,
        help='确认所需K线数 (default: 3)'
    )

    # 输出和调试
    parser.add_argument(
        '--output', type=str,
        help='输出结果CSV文件路径（可选）'
    )
    parser.add_argument(
        '--save-virtual-etf', type=str,
        help='保存虚拟ETF数据到CSV文件（用于调试）'
    )
    parser.add_argument(
        '--compare-modes', action='store_true',
        help='同时测试两种再平衡模式并对比'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='显示详细日志'
    )

    return parser


def build_strategy_instance(strategy_name: str, strategy_class, args):
    """构建策略实例，应用用户指定的参数"""

    # 创建策略实例的参数字典
    strategy_params = {}

    # 应用过滤器开关
    if hasattr(strategy_class, 'enable_slope_filter'):
        strategy_params['enable_slope_filter'] = args.enable_slope_filter
    if hasattr(strategy_class, 'enable_adx_filter'):
        strategy_params['enable_adx_filter'] = args.enable_adx_filter
    if hasattr(strategy_class, 'enable_volume_filter'):
        strategy_params['enable_volume_filter'] = args.enable_volume_filter
    if hasattr(strategy_class, 'enable_confirm_filter'):
        strategy_params['enable_confirm_filter'] = args.enable_confirm_filter

    # 应用止损保护参数
    if hasattr(strategy_class, 'enable_loss_protection'):
        strategy_params['enable_loss_protection'] = args.enable_loss_protection
        strategy_params['max_consecutive_losses'] = args.max_consecutive_losses
        strategy_params['pause_bars'] = args.pause_bars

    # 应用过滤器参数
    if hasattr(strategy_class, 'slope_lookback'):
        strategy_params['slope_lookback'] = args.slope_lookback
    if hasattr(strategy_class, 'adx_period'):
        strategy_params['adx_period'] = args.adx_period
    if hasattr(strategy_class, 'adx_threshold'):
        strategy_params['adx_threshold'] = args.adx_threshold
    if hasattr(strategy_class, 'volume_period'):
        strategy_params['volume_period'] = args.volume_period
    if hasattr(strategy_class, 'volume_ratio'):
        strategy_params['volume_ratio'] = args.volume_ratio
    if hasattr(strategy_class, 'confirm_bars'):
        strategy_params['confirm_bars'] = args.confirm_bars

    # 动态创建策略类（带参数）
    class ParameterizedStrategy(strategy_class):
        pass

    # 设置参数为类属性
    for param_name, param_value in strategy_params.items():
        setattr(ParameterizedStrategy, param_name, param_value)

    return ParameterizedStrategy


def run_rotation_strategy(
    rotation_schedule_path: str,
    strategy_name: str,
    rebalance_mode: RebalanceMode,
    trading_cost_pct: float,
    data_dir: str,
    cash: float,
    args,
    verbose: bool = True
) -> dict:
    """
    运行轮动策略回测

    Returns:
        dict: 包含回测结果和元数据的字典
    """

    if verbose:
        print("=" * 80)
        print("ETF轮动策略回测")
        print("=" * 80)
        print(f"轮动表文件: {rotation_schedule_path}")
        print(f"策略: {strategy_name}")
        print(f"再平衡模式: {rebalance_mode.value}")
        print(f"交易成本: {trading_cost_pct:.3%}")
        print(f"初始资金: {cash:,.2f}")

        # 显示启用的功能
        enabled_features = []
        if args.enable_slope_filter:
            enabled_features.append("斜率过滤")
        if args.enable_adx_filter:
            enabled_features.append("ADX过滤")
        if args.enable_volume_filter:
            enabled_features.append("成交量过滤")
        if args.enable_confirm_filter:
            enabled_features.append("确认过滤")
        if args.enable_loss_protection:
            enabled_features.append(f"止损保护({args.max_consecutive_losses}次/{args.pause_bars}bars)")

        if enabled_features:
            print(f"启用功能: {', '.join(enabled_features)}")
        else:
            print("启用功能: Baseline（无过滤器和保护）")
        print("-" * 80)

    # Step 1: 构建虚拟ETF数据
    if verbose:
        print("\n[1/3] 构建虚拟ETF数据...")

    builder = VirtualETFBuilder(
        rotation_schedule_path=rotation_schedule_path,
        data_dir=data_dir
    )

    virtual_etf_data = builder.build(
        rebalance_mode=rebalance_mode,
        trading_cost_pct=trading_cost_pct,
        verbose=verbose
    )

    # 保存虚拟ETF数据（如果指定）
    if args.save_virtual_etf:
        save_path = Path(args.save_virtual_etf)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        virtual_etf_data.to_csv(save_path)
        if verbose:
            print(f"虚拟ETF数据已保存到: {save_path}")

    # Step 2: 应用策略回测
    if verbose:
        print(f"\n[2/3] 应用{strategy_name}策略...")

    strategy_class = STRATEGIES[strategy_name]

    # 构建带参数的策略实例
    ParameterizedStrategy = build_strategy_instance(strategy_name, strategy_class, args)

    # 运行回测
    bt = Backtest(
        virtual_etf_data,
        ParameterizedStrategy,
        cash=cash,
        commission=0.0,  # 成本已在虚拟ETF中计入
    )

    stats = bt.run()

    # Step 3: 提取结果
    if verbose:
        print(f"\n[3/3] 结果分析...")

    # 计算轮动相关统计
    rotation_stats = _calculate_rotation_stats(virtual_etf_data, stats)

    result = {
        'backtest_stats': stats,
        'rotation_stats': rotation_stats,
        'virtual_etf_data': virtual_etf_data,
        'metadata': {
            'rotation_schedule_path': rotation_schedule_path,
            'strategy_name': strategy_name,
            'rebalance_mode': rebalance_mode.value,
            'trading_cost_pct': trading_cost_pct,
            'cash': cash,
            'enabled_features': {
                'slope_filter': args.enable_slope_filter,
                'adx_filter': args.enable_adx_filter,
                'volume_filter': args.enable_volume_filter,
                'confirm_filter': args.enable_confirm_filter,
                'loss_protection': args.enable_loss_protection,
            }
        }
    }

    # 获取策略运行时配置
    if hasattr(ParameterizedStrategy, '__call__'):
        # 创建一个临时实例获取运行时配置
        temp_instance = ParameterizedStrategy()
        if hasattr(temp_instance, 'get_runtime_config'):
            result['runtime_config'] = temp_instance.get_runtime_config()

    return result


def _calculate_rotation_stats(virtual_etf_data: pd.DataFrame, backtest_stats) -> dict:
    """计算轮动相关的统计信息"""

    # 轮动次数和成本
    rebalance_dates = virtual_etf_data[virtual_etf_data['rebalance_cost'] > 0]
    total_rotations = len(rebalance_dates)
    total_rebalance_cost = virtual_etf_data['rebalance_cost'].sum()

    # 平均轮动间隔
    if total_rotations > 1:
        rotation_dates = rebalance_dates.index
        intervals = [(rotation_dates[i] - rotation_dates[i-1]).days for i in range(1, len(rotation_dates))]
        avg_rotation_interval = sum(intervals) / len(intervals)
    else:
        avg_rotation_interval = None

    # 活跃ETF统计
    avg_active_etfs = virtual_etf_data['active_etf_count'].mean()

    return {
        'total_rotations': total_rotations,
        'total_rebalance_cost_pct': total_rebalance_cost,
        'avg_rotation_interval_days': avg_rotation_interval,
        'avg_active_etfs': avg_active_etfs,
        'rebalance_dates': rebalance_dates.index.tolist(),
    }


def print_results(results, verbose=True):
    """打印回测结果"""

    stats = results['backtest_stats']
    rotation_stats = results['rotation_stats']
    metadata = results['metadata']

    print("\n" + "=" * 80)
    print("ETF轮动策略回测结果")
    print("=" * 80)

    # 基本信息
    print(f"策略: {metadata['strategy_name']}")
    print(f"再平衡模式: {metadata['rebalance_mode']}")
    print(f"交易成本: {metadata['trading_cost_pct']:.3%}")

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
    print(f"  年化收益率: {stats.get('Return (Ann.) [%]', 'N/A'):.2f}%")
    print(f"  夏普比率: {stats['Sharpe Ratio']:.3f}")
    print(f"  最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  交易次数: {stats['# Trades']}")
    print(f"  胜率: {stats['Win Rate [%]']:.2f}%")

    if verbose and rotation_stats['rebalance_dates']:
        print(f"\n轮动时点:")
        for i, date in enumerate(rotation_stats['rebalance_dates'][:10]):  # 只显示前10个
            print(f"  {i+1}. {str(date)[:10]}")
        if len(rotation_stats['rebalance_dates']) > 10:
            print(f"  ... 等共{len(rotation_stats['rebalance_dates'])}次轮动")


def compare_rebalance_modes(args):
    """对比两种再平衡模式"""

    print("\n" + "=" * 80)
    print("再平衡模式对比实验")
    print("=" * 80)

    modes = [RebalanceMode.FULL_LIQUIDATION, RebalanceMode.INCREMENTAL]
    results = {}

    for mode in modes:
        print(f"\n运行{mode.value}模式...")
        result = run_rotation_strategy(
            rotation_schedule_path=args.rotation_schedule,
            strategy_name=args.strategy,
            rebalance_mode=mode,
            trading_cost_pct=args.trading_cost,
            data_dir=args.data_dir,
            cash=args.cash,
            args=args,
            verbose=False  # 减少噪音
        )
        results[mode.value] = result

    # 对比结果
    print("\n" + "=" * 80)
    print("对比结果")
    print("=" * 80)

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
        ("轮动成本(%)", full_rotation['total_rebalance_cost_pct']*100, incr_rotation['total_rebalance_cost_pct']*100),
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


def main():
    """主入口"""
    parser = create_rotation_argument_parser()
    args = parser.parse_args()

    # 验证参数
    if not Path(args.rotation_schedule).exists():
        print(f"错误: 轮动表文件不存在: {args.rotation_schedule}")
        return 1

    if args.strategy not in STRATEGIES:
        print(f"错误: 不支持的策略: {args.strategy}")
        print(f"支持的策略: {', '.join(STRATEGIES.keys())}")
        return 1

    try:
        if args.compare_modes:
            # 对比模式
            compare_rebalance_modes(args)
        else:
            # 单模式运行
            rebalance_mode = RebalanceMode(args.rebalance_mode)

            results = run_rotation_strategy(
                rotation_schedule_path=args.rotation_schedule,
                strategy_name=args.strategy,
                rebalance_mode=rebalance_mode,
                trading_cost_pct=args.trading_cost,
                data_dir=args.data_dir,
                cash=args.cash,
                args=args,
                verbose=args.verbose
            )

            # 打印结果
            print_results(results, verbose=args.verbose)

            # 保存结果（如果指定）
            if args.output:
                save_results_to_csv(results, args.output)
                print(f"\n结果已保存到: {args.output}")

        return 0

    except Exception as e:
        print(f"错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def save_results_to_csv(results, output_path):
    """保存结果到CSV文件"""
    stats = results['backtest_stats']
    rotation_stats = results['rotation_stats']
    metadata = results['metadata']

    # 构建结果字典
    result_dict = {
        # 基本信息
        'strategy': metadata['strategy_name'],
        'rebalance_mode': metadata['rebalance_mode'],
        'trading_cost_pct': metadata['trading_cost_pct'],
        'initial_cash': metadata['cash'],

        # 轮动统计
        'total_rotations': rotation_stats['total_rotations'],
        'total_rebalance_cost_pct': rotation_stats['total_rebalance_cost_pct'],
        'avg_rotation_interval_days': rotation_stats.get('avg_rotation_interval_days'),
        'avg_active_etfs': rotation_stats['avg_active_etfs'],

        # 回测结果
        'start_date': str(stats['Start']),
        'end_date': str(stats['End']),
        'return_pct': stats['Return [%]'],
        'return_ann_pct': stats.get('Return (Ann.) [%]'),
        'sharpe_ratio': stats['Sharpe Ratio'],
        'max_drawdown_pct': stats['Max. Drawdown [%]'],
        'num_trades': stats['# Trades'],
        'win_rate_pct': stats['Win Rate [%]'],

        # 启用的功能
        **{f'enable_{k}': v for k, v in metadata['enabled_features'].items()}
    }

    # 保存到CSV
    df = pd.DataFrame([result_dict])
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    sys.exit(main())