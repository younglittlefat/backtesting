#!/usr/bin/env python3
"""
中国市场回测执行器 - CLI入口

模块化重构版本，保持向后兼容
"""

import os
import sys
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# 禁用进度条输出（在导入backtesting之前设置）
os.environ['BACKTESTING_DISABLE_PROGRESS'] = 'true'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 过滤掉关于未平仓交易的UserWarning
warnings.filterwarnings('ignore', message='.*Some trades remain open.*')
warnings.filterwarnings('ignore', category=UserWarning, module='backtesting')

# 导入模块化组件
from backtest_runner.config import (
    create_argument_parser,
    STRATEGIES,
)
from backtest_runner.core import (
    run_single_backtest,
    save_best_params,
)
from backtest_runner.processing import (
    enrich_instruments_with_names,
    build_filter_params,
    build_aggregate_payload,
)
from backtest_runner.utils import (
    parse_multi_values,
    parse_blacklist,
    resolve_display_name,
    print_low_volatility_report,
    print_backtest_summary,
    _safe_stat,
)
from utils.data_loader import (
    InstrumentInfo,
    LowVolatilityConfig,
    is_low_volatility,
    list_available_instruments,
    load_instrument_data,
)
from utils.trading_cost import TradingCostConfig
from backtest_runner.data.virtual_etf_builder import VirtualETFBuilder, RebalanceMode
from backtesting import Backtest


def main() -> int:
    """命令行入口"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # 参数验证
    if args.instrument_limit is not None and args.instrument_limit <= 0:
        print("\n错误: 标的数量限制必须为正整数。")
        return 1

    # 轮动模式参数验证
    if hasattr(args, 'enable_rotation') and args.enable_rotation:
        if not args.rotation_schedule:
            print("\n错误: 启用轮动模式时必须指定 --rotation-schedule 参数。")
            return 1
        if not Path(args.rotation_schedule).exists():
            print(f"\n错误: 轮动表文件不存在: {args.rotation_schedule}")
            return 1

    verbose = args.verbose

    # 检查是否为轮动模式
    if hasattr(args, 'enable_rotation') and args.enable_rotation:
        return _run_rotation_mode(args)

    # 打印系统信息
    _print_system_info(args)

    # 配置低波动过滤
    low_vol_config = _configure_low_volatility_filter(args)

    # 获取可用标的
    available_instruments = _get_available_instruments(args)
    if not available_instruments:
        print(f"\n错误: 在 {args.data_dir} 中未找到符合条件的数据文件")
        return 1

    # 打印标的统计
    _print_instruments_statistics(available_instruments)

    # 处理标的列表
    instruments_to_process = _process_instrument_list(args, available_instruments)
    if not instruments_to_process:
        print("\n错误: 无标的可供回测，请检查参数。")
        return 1

    # 应用标的数量限制
    if args.instrument_limit is not None and len(instruments_to_process) > args.instrument_limit:
        print(f"\n标的数量限制: 仅回测前 {args.instrument_limit} 只标的。")
        instruments_to_process = instruments_to_process[:args.instrument_limit]

    # 获取中文名称
    print("\n获取标的中文名称...")
    instruments_to_process = enrich_instruments_with_names(instruments_to_process)

    # 确定要处理的策略
    if args.strategy == 'all':
        strategies_to_process = list(STRATEGIES.keys())
    else:
        strategies_to_process = [args.strategy]

    # 批量回测
    all_results, low_vol_skipped = _run_batch_backtests(
        instruments=instruments_to_process,
        strategies=strategies_to_process,
        args=args,
        low_vol_config=low_vol_config,
        verbose=verbose,
    )

    # 显示过滤报告
    print_low_volatility_report(low_vol_skipped, verbose=verbose)

    # 处理结果
    if all_results:
        _process_results(all_results, args, verbose)
        return 0
    else:
        if low_vol_skipped:
            print("\n未生成任何回测结果（所有标的均被低波动过滤）。")
        else:
            print("\n未生成任何回测结果。")
        return 1


def _print_system_info(args) -> None:
    """打印系统信息"""
    print("=" * 70)
    print("中国市场回测系统")
    print("=" * 70)
    print(f"数据目录:     {args.data_dir}")
    print(f"输出目录:     {args.output_dir}")
    print(f"策略选择:     {args.strategy}")
    print(f"参数优化:     {'是' if args.optimize else '否'}")
    print(f"初始资金:     {args.cash:,.2f}")
    print(f"费用模型:     {args.cost_model}")
    if args.commission is not None:
        print(f"佣金覆盖:     {args.commission:.4%}")
    if args.spread is not None:
        print(f"滑点覆盖:     {args.spread:.4%}")
    if args.category:
        print(f"类别筛选:     {args.category}")
    if args.start_date:
        print(f"开始日期:     {args.start_date}")
    if args.end_date:
        print(f"结束日期:     {args.end_date}")
    if args.instrument_limit is not None:
        print(f"标的数量限制: {args.instrument_limit}")
    if args.verbose:
        print("详细日志:     已启用")
    else:
        print("详细日志:     关闭 (使用 --verbose 查看明细)")
    print("=" * 70)


def _configure_low_volatility_filter(args) -> Optional[LowVolatilityConfig]:
    """配置低波动过滤器"""
    low_vol_blacklist = parse_blacklist(args.low_vol_blacklist)

    if args.disable_low_vol_filter:
        print("低波动过滤:   已关闭")
        return None

    try:
        low_vol_config = LowVolatilityConfig(
            threshold=args.min_annual_vol,
            lookback=args.vol_lookback,
            blacklist=tuple(low_vol_blacklist),
        )
    except ValueError as exc:
        print(f"\n错误: {exc}")
        sys.exit(1)

    blacklist_label = ",".join(low_vol_blacklist) or "无"
    print(
        f"低波动过滤:   阈值={low_vol_config.threshold:.2%} "
        f"回看={low_vol_config.lookback}日 黑名单={blacklist_label}"
    )
    return low_vol_config


def _get_available_instruments(args) -> Dict[str, InstrumentInfo]:
    """获取可用标的"""
    category_filter = parse_multi_values(args.category) if args.category else []
    category_filter = category_filter or None

    return list_available_instruments(
        args.data_dir,
        categories=category_filter,
    )


def _print_instruments_statistics(available_instruments: Dict[str, InstrumentInfo]) -> None:
    """打印标的统计信息"""
    category_counts = Counter(info.category for info in available_instruments.values())
    print(f"\n可用标的总数: {len(available_instruments)}")
    category_summary = ", ".join(f"{cat}={count}" for cat, count in category_counts.items())
    print(f"按类别统计: {category_summary}")


def _process_instrument_list(args, available_instruments: Dict[str, InstrumentInfo]) -> List[InstrumentInfo]:
    """处理标的列表"""
    # 处理股票列表文件（如果提供）
    if args.stock_list:
        try:
            print(f"\n从股票列表文件读取标的: {args.stock_list}")
            stock_list_df = pd.read_csv(args.stock_list)

            if 'ts_code' not in stock_list_df.columns:
                print(f"错误: 股票列表文件缺少 'ts_code' 列")
                sys.exit(1)

            stock_list_codes = stock_list_df['ts_code'].dropna().unique().tolist()
            print(f"✅ 从文件读取了 {len(stock_list_codes)} 只标的")

            # 将股票列表转换为逗号分隔的字符串，覆盖args.stock
            args.stock = ','.join(stock_list_codes)

        except Exception as e:
            print(f"错误: 读取股票列表文件失败: {e}")
            sys.exit(1)

    requested_tokens = parse_multi_values(args.stock)
    pending_codes: List[str] = []

    if not requested_tokens:
        pending_codes = sorted(available_instruments.keys())
    else:
        missing_codes: List[str] = []
        for token in requested_tokens:
            if token.lower().startswith('category:'):
                cat = token.split(':', 1)[1].lower()
                matched = [
                    code
                    for code, info in available_instruments.items()
                    if info.category == cat
                ]
                if not matched:
                    print(f"警告: 未找到类别 '{cat}' 的标的")
                pending_codes.extend(matched)
            else:
                if token not in available_instruments:
                    missing_codes.append(token)
                else:
                    pending_codes.append(token)
        if missing_codes:
            print(f"\n错误: 未找到以下标的数据文件: {', '.join(missing_codes)}")
            sys.exit(1)

    # 去重并保持顺序
    seen_codes = set()
    instruments_to_process: List[InstrumentInfo] = []
    for code in pending_codes:
        if code not in seen_codes and code in available_instruments:
            instruments_to_process.append(available_instruments[code])
            seen_codes.add(code)

    return instruments_to_process


def _run_batch_backtests(
    instruments: List[InstrumentInfo],
    strategies: List[str],
    args,
    low_vol_config: Optional[LowVolatilityConfig],
    verbose: bool,
) -> tuple:
    """批量运行回测"""
    all_results: List[Dict] = []
    low_vol_skipped: List[Dict] = []

    for instrument in instruments:
        if verbose:
            print("\n" + "#" * 70)
            print(f"准备加载标的: {instrument.code} ({instrument.category})")

        try:
            data = load_instrument_data(
                instrument=instrument,
                start_date=args.start_date,
                end_date=args.end_date,
                verbose=verbose,
            )
        except Exception as exc:
            print(f"错误: 加载 {instrument.code} 数据失败: {exc}")
            continue

        # 低波动过滤
        if low_vol_config is not None:
            is_low, volatility, reason = is_low_volatility(
                instrument=instrument,
                data=data,
                config=low_vol_config,
            )
            if is_low:
                display_name = resolve_display_name(instrument)
                vol_msg = f"{volatility:.4%}" if volatility is not None else "样本不足"
                if verbose:
                    print(f"跳过低波动标的: {display_name} ({instrument.code})")
                    print(f"  原因: {reason}")
                    print(f"  年化波动率: {vol_msg}")
                low_vol_skipped.append({
                    'instrument': instrument,
                    'volatility': volatility,
                    'reason': reason,
                })
                continue

        # 配置交易成本
        cost_config = _configure_trading_cost(args, instrument)

        # 对每个策略进行回测
        for strategy_name in strategies:
            strategy_class = STRATEGIES[strategy_name]

            # 构建过滤器参数
            filter_params = build_filter_params(strategy_name, args)

            try:
                if not verbose:
                    # 在非详细模式下提供进度反馈
                    current_idx = instruments.index(instrument) + 1
                    total_instruments = len(instruments)
                    display_name = resolve_display_name(instrument)
                    print(f"[{current_idx}/{total_instruments}] 回测 {display_name} ({instrument.code}) - {strategy_name}")

                stats, bt_result = run_single_backtest(
                    data=data,
                    strategy_class=strategy_class,
                    instrument=instrument,
                    strategy_name=strategy_name,
                    cash=args.cash,
                    cost_config=cost_config,
                    optimize=args.optimize,
                    output_dir=args.output_dir,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    verbose=verbose,
                    save_params_file=args.save_params,
                    filter_params=filter_params,
                )

                # 保存结果
                result_entry = {
                    'instrument': instrument,
                    'strategy': strategy_name,
                    'stats': stats,
                    'cost_model': cost_config.name,
                }

                # 如果是优化模式，保存优化参数信息
                if args.optimize and hasattr(bt_result, '_strategy'):
                    result_entry['optimized_params'] = _extract_optimized_params(
                        bt_result._strategy,
                        strategy_class
                    )

                all_results.append(result_entry)
            except Exception as exc:
                print(f"\n错误: 运行回测失败: {exc}")
                import traceback
                traceback.print_exc()
                continue

    return all_results, low_vol_skipped


def _configure_trading_cost(args, instrument: InstrumentInfo) -> TradingCostConfig:
    """配置交易成本"""
    if args.cost_model == 'custom':
        if args.commission is None:
            print(f"\n错误: 使用 custom 模型时必须指定 --commission 参数")
            sys.exit(1)
        cost_config = TradingCostConfig(
            name='custom',
            commission_rate=args.commission,
            spread=args.spread or 0.0,
        )
    else:
        cost_config = TradingCostConfig.get_preset(args.cost_model)
        # 允许参数覆盖
        if args.commission is not None:
            cost_config.commission_rate = args.commission
        if args.spread is not None:
            cost_config.spread = args.spread

    return cost_config


def _extract_optimized_params(strategy_obj, strategy_class) -> Dict:
    """提取优化参数"""
    # 获取模块级别的OPTIMIZE_PARAMS配置，判断需要保存哪些参数
    strategy_module = sys.modules[strategy_class.__module__]
    optimize_params_config = getattr(strategy_module, 'OPTIMIZE_PARAMS', {})

    # 根据配置提取对应的优化参数
    optimized_params = {}
    for param_name in optimize_params_config.keys():
        if hasattr(strategy_obj, param_name):
            optimized_params[param_name] = getattr(strategy_obj, param_name)

    return optimized_params


def _process_results(all_results: List[Dict], args, verbose: bool) -> None:
    """处理和保存回测结果"""
    # 打印汇总表格
    print_backtest_summary(all_results, args.output_dir, verbose)

    # 自动生成汇总CSV
    _save_summary_csv(all_results, args)

    # 保存最优参数到配置文件（如果指定了save_params且在优化模式）
    if args.save_params and args.optimize:
        # 获取策略名称
        strategy_name = args.strategy if args.strategy != 'all' else 'sma_cross'
        # 获取策略类
        strategy_class = STRATEGIES[strategy_name]
        # 构建过滤器参数
        from backtest_runner.processing import build_filter_params
        filter_params = build_filter_params(strategy_name, args)

        save_best_params(
            all_results=all_results,
            save_params_file=args.save_params,
            strategy_name=strategy_name,
            strategy_class=strategy_class,  # 新增：策略类
            filter_params=filter_params,  # 新增：过滤器参数
            start_date=args.start_date,
            end_date=args.end_date,
            verbose=verbose
        )


def _save_summary_csv(all_results: List[Dict], args) -> None:
    """保存汇总CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 如果用户指定了aggregate_output，使用用户指定的路径
    if args.aggregate_output:
        aggregate_path = Path(args.aggregate_output)
    else:
        # 否则自动生成到 results/summary 目录
        summary_dir = Path(args.output_dir) / 'summary'
        summary_dir.mkdir(parents=True, exist_ok=True)
        aggregate_path = summary_dir / f"backtest_summary_{timestamp}.csv"

    # 构建汇总DataFrame，格式与终端输出一致
    summary_rows = []
    for result in all_results:
        instrument = result['instrument']
        stats = result['stats']
        return_pct = _safe_stat(stats, 'Return [%]')
        sharpe_value = stats['Sharpe Ratio']
        max_dd = _safe_stat(stats, 'Max. Drawdown [%]', default=0.0)

        # 获取实际回测起止日期
        start_date = str(stats['Start'])[:10] if 'Start' in stats else '未知'
        end_date = str(stats['End'])[:10] if 'End' in stats else '未知'

        summary_rows.append({
            '代码': instrument.code,
            '标的名称': resolve_display_name(instrument),
            '类型': instrument.category,
            '策略': result['strategy'],
            '回测开始日期': start_date,
            '回测结束日期': end_date,
            '收益率(%)': round(return_pct, 3) if return_pct is not None else None,
            '夏普比率': round(sharpe_value, 3) if not pd.isna(sharpe_value) else None,
            '最大回撤(%)': round(max_dd, 3) if max_dd is not None else None,
        })

    summary_df = pd.DataFrame(summary_rows)
    # 按代码排序
    summary_df = summary_df.sort_values(by='代码')
    aggregate_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(aggregate_path, index=False, encoding='utf-8-sig')
    print(f"汇总结果已保存: {aggregate_path}")


def _run_rotation_mode(args) -> int:
    """运行ETF轮动策略模式"""

    print("=" * 70)
    print("ETF轮动策略回测模式")
    print("=" * 70)
    print(f"轮动表文件: {args.rotation_schedule}")
    print(f"策略选择:   {args.strategy}")
    print(f"再平衡模式: {args.rebalance_mode}")
    print(f"轮动成本:   {args.rotation_trading_cost:.3%}")
    print(f"初始资金:   {args.cash:,.2f}")

    # 显示启用的功能
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

    if enabled_features:
        print(f"启用功能:   {', '.join(enabled_features)}")
    else:
        print("启用功能:   Baseline（无过滤器和保护）")
    print("=" * 70)

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


def _run_single_rotation_strategy(args) -> int:
    """运行单个轮动策略"""

    # Step 1: 构建虚拟ETF数据
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

    # 保存虚拟ETF数据（如果指定）
    if hasattr(args, 'save_virtual_etf') and args.save_virtual_etf:
        save_path = Path(args.save_virtual_etf)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        virtual_etf_data.to_csv(save_path)
        if args.verbose:
            print(f"虚拟ETF数据已保存到: {save_path}")

    # Step 2: 应用策略回测
    print(f"\n[2/3] 应用{args.strategy}策略...")

    strategy_class = STRATEGIES[args.strategy]

    # 构建带参数的策略实例
    ParameterizedStrategy = _build_strategy_instance(strategy_class, args)

    # 运行回测
    bt = Backtest(
        virtual_etf_data,
        ParameterizedStrategy,
        cash=args.cash,
        commission=0.0,  # 成本已在虚拟ETF中计入
    )

    stats = bt.run()

    # Step 3: 输出结果
    print(f"\n[3/3] 结果分析...")

    rotation_stats = _calculate_rotation_stats(virtual_etf_data, stats)
    _print_rotation_results(stats, rotation_stats, args)

    # 保存结果（如果指定汇总输出）
    if args.aggregate_output:
        _save_rotation_summary_csv(stats, rotation_stats, args)
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
            # 构建虚拟ETF
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
            ParameterizedStrategy = _build_strategy_instance(strategy_class, args)

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


def _build_strategy_instance(strategy_class, args):
    """构建带参数的策略实例"""

    # 创建策略实例的参数字典
    strategy_params = {}

    # 应用过滤器开关
    if hasattr(strategy_class, 'enable_slope_filter') and hasattr(args, 'enable_slope_filter'):
        strategy_params['enable_slope_filter'] = args.enable_slope_filter
    if hasattr(strategy_class, 'enable_adx_filter') and hasattr(args, 'enable_adx_filter'):
        strategy_params['enable_adx_filter'] = args.enable_adx_filter
    if hasattr(strategy_class, 'enable_volume_filter') and hasattr(args, 'enable_volume_filter'):
        strategy_params['enable_volume_filter'] = args.enable_volume_filter
    if hasattr(strategy_class, 'enable_confirm_filter') and hasattr(args, 'enable_confirm_filter'):
        strategy_params['enable_confirm_filter'] = args.enable_confirm_filter

    # 应用止损保护参数
    if hasattr(strategy_class, 'enable_loss_protection') and hasattr(args, 'enable_loss_protection'):
        strategy_params['enable_loss_protection'] = args.enable_loss_protection
        strategy_params['max_consecutive_losses'] = args.max_consecutive_losses
        strategy_params['pause_bars'] = args.pause_bars

    # 应用过滤器参数
    if hasattr(strategy_class, 'slope_lookback') and hasattr(args, 'slope_lookback'):
        strategy_params['slope_lookback'] = args.slope_lookback
    if hasattr(strategy_class, 'adx_period') and hasattr(args, 'adx_period'):
        strategy_params['adx_period'] = args.adx_period
    if hasattr(strategy_class, 'adx_threshold') and hasattr(args, 'adx_threshold'):
        strategy_params['adx_threshold'] = args.adx_threshold
    if hasattr(strategy_class, 'volume_period') and hasattr(args, 'volume_period'):
        strategy_params['volume_period'] = args.volume_period
    if hasattr(strategy_class, 'volume_ratio') and hasattr(args, 'volume_ratio'):
        strategy_params['volume_ratio'] = args.volume_ratio
    if hasattr(strategy_class, 'confirm_bars') and hasattr(args, 'confirm_bars'):
        strategy_params['confirm_bars'] = args.confirm_bars

    # 动态创建策略类（带参数）
    class ParameterizedStrategy(strategy_class):
        pass

    # 设置参数为类属性
    for param_name, param_value in strategy_params.items():
        setattr(ParameterizedStrategy, param_name, param_value)

    return ParameterizedStrategy


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


def _print_rotation_results(stats, rotation_stats, args):
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
        for i, date in enumerate(rotation_stats['rebalance_dates'][:10]):  # 只显示前10个
            print(f"  {i+1}. {str(date)[:10]}")
        if len(rotation_stats['rebalance_dates']) > 10:
            print(f"  ... 等共{len(rotation_stats['rebalance_dates'])}次轮动")


def _print_rotation_comparison_results(results):
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


def _save_rotation_summary_csv(stats, rotation_stats, args):
    """保存轮动策略汇总结果到CSV"""

    # 构建结果字典
    result_dict = {
        # 基本信息
        'strategy': args.strategy,
        'rebalance_mode': args.rebalance_mode,
        'rotation_trading_cost_pct': args.rotation_trading_cost,
        'initial_cash': args.cash,

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
        'enable_slope_filter': getattr(args, 'enable_slope_filter', False),
        'enable_adx_filter': getattr(args, 'enable_adx_filter', False),
        'enable_volume_filter': getattr(args, 'enable_volume_filter', False),
        'enable_confirm_filter': getattr(args, 'enable_confirm_filter', False),
        'enable_loss_protection': getattr(args, 'enable_loss_protection', False),
    }

    # 保存到CSV
    df = pd.DataFrame([result_dict])
    output_path = Path(args.aggregate_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    sys.exit(main())
