"""
标准回测模式

职责：
- 标准（非轮动）回测流程
- 标的筛选和处理
- 批量回测执行
- 结果处理和保存
"""

import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from backtest_runner.config import STRATEGIES
from backtest_runner.core import run_single_backtest, save_best_params
from backtest_runner.processing import (
    enrich_instruments_with_names,
    build_filter_params,
)
from backtest_runner.utils import (
    parse_multi_values,
    parse_blacklist,
    resolve_display_name,
    print_low_volatility_report,
    print_backtest_summary,
)
from backtest_runner.io import save_summary_csv
from utils.data_loader import (
    InstrumentInfo,
    LowVolatilityConfig,
    is_low_volatility,
    list_available_instruments,
    load_instrument_data,
)
from utils.trading_cost import TradingCostConfig

from .main import print_system_info


def run_standard_mode(args) -> int:
    """
    运行标准回测模式

    Args:
        args: 命令行参数

    Returns:
        退出码（0=成功，1=失败）
    """
    verbose = args.verbose

    # 打印系统信息
    print_system_info(args)

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

            # 将股票列表转换为逗号分隔的字符串，覆盖 args.stock
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
    # 获取模块级别的 OPTIMIZE_PARAMS 配置
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

    # 自动生成汇总 CSV
    save_summary_csv(
        all_results=all_results,
        output_dir=args.output_dir,
        aggregate_output=args.aggregate_output,
    )

    # 保存最优参数到配置文件（如果指定了 save_params 且在优化模式）
    if args.save_params and args.optimize:
        strategy_name = args.strategy if args.strategy != 'all' else 'sma_cross'
        strategy_class = STRATEGIES[strategy_name]
        filter_params = build_filter_params(strategy_name, args)

        save_best_params(
            all_results=all_results,
            save_params_file=args.save_params,
            strategy_name=strategy_name,
            strategy_class=strategy_class,
            filter_params=filter_params,
            start_date=args.start_date,
            end_date=args.end_date,
            verbose=verbose
        )
