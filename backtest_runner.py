#!/usr/bin/env python3
"""
中国市场回测执行器

使用 backtesting.py 框架对中国 ETF/基金等标的进行批量回测
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Dict, List, Optional

import math
import numpy as np
import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backtesting import Backtest
from utils.data_loader import (
    InstrumentInfo,
    LowVolatilityConfig,
    is_low_volatility,
    list_available_instruments,
    load_instrument_data,
)
from strategies.sma_cross import SmaCross, OPTIMIZE_PARAMS, CONSTRAINTS


# 可用的策略映射
STRATEGIES = {
    'sma_cross': SmaCross,
}


CATEGORY_DEFAULT_COMMISSION = {
    'etf': 0.0005,
    'fund': 0.0000,
}
DEFAULT_COMMISSION = 0.001


def resolve_display_name(instrument: InstrumentInfo) -> str:
    """返回用于显示的标的名称."""
    return instrument.display_name or instrument.code


def _duration_to_days(value) -> int:
    """安全地将持续时长转换为天数，兼容 float/Timedelta/timedelta64."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0

    if isinstance(value, pd.Timedelta):
        return int(value.days)

    if isinstance(value, np.timedelta64):
        return int(pd.to_timedelta(value).days)

    if hasattr(value, "days"):
        try:
            return int(value.days)
        except (TypeError, ValueError):
            pass

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_stat(stats: pd.Series, key: str, default: float = 0.0) -> float:
    """从 stats 中安全获取数值，遇到 NaN/缺失时返回默认值。"""
    value = stats.get(key, default)
    if value is None:
        return default
    if isinstance(value, (float, int, np.floating, np.integer)):
        if math.isnan(float(value)):
            return default
        return float(value)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return 0.0 if math.isnan(numeric) else numeric


def parse_multi_values(raw: Optional[str]) -> List[str]:
    """解析逗号分隔的参数，返回去重且保持顺序的列表。"""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw or raw.lower() == 'all':
        return []

    seen = set()
    values: List[str] = []
    for part in raw.split(','):
        token = part.strip()
        if not token:
            continue
        if token not in seen:
            seen.add(token)
            values.append(token)
    return values


def parse_blacklist(raw: Optional[str]) -> List[str]:
    """解析低波动黑名单配置。"""
    if raw is None:
        return []

    normalized = raw.strip()
    if not normalized:
        return []

    if normalized.lower() in {'none', 'null', 'off', 'disable', 'disabled'}:
        return []

    seen = set()
    values: List[str] = []
    for part in normalized.split(','):
        token = part.strip()
        if not token:
            continue
        if token not in seen:
            seen.add(token)
            values.append(token)
    return values


def build_aggregate_payload(results: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    构建聚合统计数据的占位结构，便于未来汇总分析。
    当前仅包含基础收益指标，可按需扩展。
    """
    payload: List[Dict[str, object]] = []
    for item in results:
        instrument: InstrumentInfo = item['instrument']  # type: ignore[index]
        stats: pd.Series = item['stats']  # type: ignore[index]
        payload.append(
            {
                'code': instrument.code,
                'category': instrument.category,
                'strategy': item['strategy'],  # type: ignore[index]
                'return_pct': _safe_stat(stats, 'Return [%]'),
                'annual_return_pct': _safe_stat(stats, 'Return (Ann.) [%]'),
                'sharpe': stats['Sharpe Ratio'],
                'max_drawdown_pct': _safe_stat(stats, 'Max. Drawdown [%]', default=0.0),
            }
        )
    return payload


def run_single_backtest(
    data,
    strategy_class,
    instrument: InstrumentInfo,
    strategy_name,
    cash: float = 10000,
    commission: float = 0.002,
    optimize: bool = False,
    output_dir: str = 'results',
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    verbose: bool = False,
) -> pd.Series:
    """
    运行单次回测。
    """
    display_name = resolve_display_name(instrument)
    if verbose:
        print("\n" + "=" * 70)
        print(f"回测: {display_name} ({instrument.code}) - {strategy_name}")
        print(f"标的类型: {instrument.category} | 货币: {instrument.currency}")
        print(f"初始资金: {cash:,.2f} | 手续费率: {commission:.4f}")
        if start_date or end_date:
            date_range = f"{start_date or '开始'} 至 {end_date or '结束'}"
            print(f"日期范围: {date_range}")
        print("=" * 70)

    bt = Backtest(
        data,
        strategy_class,
        cash=cash,
        commission=commission,
        exclusive_orders=True,
        finalize_trades=True,
    )

    if optimize:
        if verbose:
            print("\n开始参数优化...")
            print(f"参数空间: {OPTIMIZE_PARAMS}")
        stats = bt.optimize(
            **OPTIMIZE_PARAMS,
            constraint=CONSTRAINTS,
            maximize='Sharpe Ratio',
            max_tries=200,
            random_state=42,
        )
        if verbose:
            print("\n最优参数:")
            if hasattr(stats._strategy, 'n1'):
                print(f"  短期均线 (n1): {stats._strategy.n1}")
            if hasattr(stats._strategy, 'n2'):
                print(f"  长期均线 (n2): {stats._strategy.n2}")
    else:
        if verbose:
            print("\n运行回测...")
        stats = bt.run()

    if verbose:
        print("\n" + "-" * 70)
        print("回测结果")
        print("-" * 70)
        print(f"初始资金:     ${cash:,.2f}")
        print(f"最终资金:     ${stats['Equity Final [$]']:,.2f}")
        print(f"收益率:       {stats['Return [%]']:.2f}%")
        print(f"年化收益率:   {stats['Return (Ann.) [%]']:.2f}%")
        print(f"夏普比率:     {stats['Sharpe Ratio']:.2f}")
        print(f"最大回撤:     {stats['Max. Drawdown [%]']:.2f}%")
        print(f"交易次数:     {stats['# Trades']}")
        print(f"胜率:         {stats['Win Rate [%]']:.2f}%")
        print(f"盈亏比:       {stats['Profit Factor']:.2f}")
        print("-" * 70)

    save_results(
        stats=stats,
        instrument=instrument,
        strategy_name=strategy_name,
        output_dir=output_dir,
        optimized=optimize,
        cash=cash,
        verbose=verbose,
    )

    plot_dir = Path(output_dir) / instrument.category / 'plots'
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_file = plot_dir / f"{instrument.code}_{strategy_name}.html"
    if verbose:
        print(f"\n生成图表: {plot_file}")
    bt.plot(filename=str(plot_file), open_browser=False)

    return stats


def save_results(
    stats: pd.Series,
    instrument: InstrumentInfo,
    strategy_name: str,
    output_dir: str,
    optimized: bool = False,
    cash: float = 10000,
    verbose: bool = False,
) -> None:
    """保存回测结果和交易记录。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_root = Path(output_dir) / instrument.category
    stats_dir = output_root / 'stats'
    stats_dir.mkdir(parents=True, exist_ok=True)

    stats_file = stats_dir / f"{instrument.code}_{strategy_name}_{timestamp}.csv"

    summary_data = {
        '标的代码': instrument.code,
        '标的名称': resolve_display_name(instrument),
        '标的类型': instrument.category,
        '货币': instrument.currency,
        '策略': strategy_name,
        '是否优化': '是' if optimized else '否',
        '开始日期': str(stats['Start']),
        '结束日期': str(stats['End']),
        '持续天数': _duration_to_days(stats.get('Duration')),
        '初始资金': cash,
        '最终资金': stats['Equity Final [$]'],
        '收益率(%)': _safe_stat(stats, 'Return [%]'),
        '年化收益率(%)': _safe_stat(stats, 'Return (Ann.) [%]'),
        '买入持有收益率(%)': _safe_stat(stats, 'Buy & Hold Return [%]', default=0.0),
        '夏普比率': stats['Sharpe Ratio'],
        '索提诺比率': stats['Sortino Ratio'],
        '卡玛比率': stats['Calmar Ratio'],
        '最大回撤(%)': _safe_stat(stats, 'Max. Drawdown [%]', default=0.0),
        '平均回撤(%)': _safe_stat(stats, 'Avg. Drawdown [%]', default=0.0),
        '最大回撤持续天数': _duration_to_days(stats.get('Max. Drawdown Duration')),
        '交易次数': stats['# Trades'],
        '胜率(%)': _safe_stat(stats, 'Win Rate [%]', default=0.0),
        '最佳交易(%)': _safe_stat(stats, 'Best Trade [%]', default=0.0),
        '最差交易(%)': _safe_stat(stats, 'Worst Trade [%]', default=0.0),
        '平均交易(%)': _safe_stat(stats, 'Avg. Trade [%]', default=0.0),
        '盈亏比': _safe_stat(stats, 'Profit Factor', default=0.0),
        '期望值(%)': _safe_stat(stats, 'Expectancy [%]', default=0.0),
        'SQN': _safe_stat(stats, 'SQN', default=0.0),
        '手续费': stats.get('Commissions [$]', 0),
    }

    if optimized and hasattr(stats._strategy, 'n1'):
        summary_data['短期均线(n1)'] = stats._strategy.n1
        if hasattr(stats._strategy, 'n2'):
            summary_data['长期均线(n2)'] = stats._strategy.n2

    summary_df = pd.DataFrame([summary_data])
    summary_df.to_csv(stats_file, index=False, encoding='utf-8-sig')
    if verbose:
        print(f"保存统计数据: {stats_file}")

    if len(stats._trades) > 0:
        trades_file = stats_dir / f"{instrument.code}_{strategy_name}_{timestamp}_trades.csv"
        stats._trades.to_csv(trades_file, encoding='utf-8-sig')
        if verbose:
            print(f"保存交易记录: {trades_file}")


def main() -> int:
    """命令行入口。"""
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

    parser.add_argument(
        '-s',
        '--stock',
        default='all',
        help='标的代码（逗号分隔），默认为 all 处理所有标的。支持 category:etf 语法。',
    )
    parser.add_argument(
        '--category',
        default=None,
        help='按类别过滤标的（逗号分隔），例如 etf,fund。',
    )
    parser.add_argument(
        '-t',
        '--strategy',
        choices=list(STRATEGIES.keys()) + ['all'],
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
        '-c',
        '--commission',
        type=float,
        default=None,
        help='统一手续费率，未指定时按标的类别使用默认值。',
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
    parser.add_argument(
        '--min-annual-vol',
        type=float,
        default=0.02,
        help='低波动过滤的年化波动率阈值 (默认 0.02，即 2%)。',
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

    args = parser.parse_args()

    if args.instrument_limit is not None and args.instrument_limit <= 0:
        print("\n错误: 标的数量限制必须为正整数。")
        return 1

    verbose = args.verbose

    print("=" * 70)
    print("中国市场回测系统")
    print("=" * 70)
    print(f"数据目录:     {args.data_dir}")
    print(f"输出目录:     {args.output_dir}")
    print(f"策略选择:     {args.strategy}")
    print(f"参数优化:     {'是' if args.optimize else '否'}")
    print(f"初始资金:     {args.cash:,.2f}")
    if args.commission is not None:
        print(f"统一手续费:   {args.commission:.4f}")
    else:
        print("统一手续费:   按类别默认值")
    if args.category:
        print(f"类别筛选:     {args.category}")
    if args.start_date:
        print(f"开始日期:     {args.start_date}")
    if args.end_date:
        print(f"结束日期:     {args.end_date}")
    if args.instrument_limit is not None:
        print(f"标的数量限制: {args.instrument_limit}")
    if verbose:
        print("详细日志:     已启用")
    else:
        print("详细日志:     关闭 (使用 --verbose 查看明细)")
    print("=" * 70)

    low_vol_blacklist = parse_blacklist(args.low_vol_blacklist)
    low_vol_config: Optional[LowVolatilityConfig]
    if args.disable_low_vol_filter:
        low_vol_config = None
        print("低波动过滤:   已关闭")
    else:
        try:
            low_vol_config = LowVolatilityConfig(
                threshold=args.min_annual_vol,
                lookback=args.vol_lookback,
                blacklist=tuple(low_vol_blacklist),
            )
        except ValueError as exc:
            print(f"\n错误: {exc}")
            return 1
        blacklist_label = ",".join(low_vol_blacklist) or "无"
        print(
            f"低波动过滤:   阈值={low_vol_config.threshold:.2%} "
            f"回看={low_vol_config.lookback}日 黑名单={blacklist_label}"
        )

    category_filter = parse_multi_values(args.category) if args.category else []
    category_filter = category_filter or None

    available_instruments = list_available_instruments(
        args.data_dir,
        categories=category_filter,
    )
    if not available_instruments:
        print(f"\n错误: 在 {args.data_dir} 中未找到符合条件的数据文件")
        return 1

    category_counts = Counter(info.category for info in available_instruments.values())
    print(f"\n可用标的总数: {len(available_instruments)}")
    category_summary = ", ".join(f"{cat}={count}" for cat, count in category_counts.items())
    print(f"按类别统计: {category_summary}")

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
            return 1

    seen_codes = set()
    instruments_to_process: List[InstrumentInfo] = []
    for code in pending_codes:
        if code not in seen_codes and code in available_instruments:
            instruments_to_process.append(available_instruments[code])
            seen_codes.add(code)

    if not instruments_to_process:
        print("\n错误: 无标的可供回测，请检查参数。")
        return 1

    instrument_limit = args.instrument_limit
    if instrument_limit is not None and len(instruments_to_process) > instrument_limit:
        print(f"\n标的数量限制: 仅回测前 {instrument_limit} 只标的。")
        instruments_to_process = instruments_to_process[:instrument_limit]

    if args.strategy == 'all':
        strategies_to_process = list(STRATEGIES.keys())
    else:
        strategies_to_process = [args.strategy]

    all_results: List[Dict[str, object]] = []
    low_vol_skipped: List[Dict[str, object]] = []
    for instrument in instruments_to_process:
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
                low_vol_skipped.append(
                    {
                        'instrument': instrument,
                        'volatility': volatility,
                        'reason': reason,
                    }
                )
                continue

        commission_rate = (
            args.commission
            if args.commission is not None
            else CATEGORY_DEFAULT_COMMISSION.get(instrument.category, DEFAULT_COMMISSION)
        )

        for strategy_name in strategies_to_process:
            strategy_class = STRATEGIES[strategy_name]
            try:
                stats = run_single_backtest(
                    data=data,
                    strategy_class=strategy_class,
                    instrument=instrument,
                    strategy_name=strategy_name,
                    cash=args.cash,
                    commission=commission_rate,
                    optimize=args.optimize,
                    output_dir=args.output_dir,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    verbose=verbose,
                )
                all_results.append(
                    {
                        'instrument': instrument,
                        'strategy': strategy_name,
                        'stats': stats,
                        'commission': commission_rate,
                    }
                )
            except Exception as exc:
                print(f"\n错误: 运行回测失败: {exc}")
                import traceback

                traceback.print_exc()
                continue

    if low_vol_skipped:
        if verbose:
            print("\n低波动过滤统计")
            print("-" * 70)
            for entry in low_vol_skipped:
                instrument = entry['instrument']  # type: ignore[assignment]
                volatility = entry['volatility']  # type: ignore[assignment]
                reason = entry['reason']  # type: ignore[assignment]
                vol_display = f"{volatility:.4%}" if volatility is not None else "样本不足"
                print(
                    f"{instrument.code:<12} {instrument.category:<8} 波动率={vol_display:<12} 原因: {reason}"
                )
            print(f"共跳过 {len(low_vol_skipped)} 只标的。")
        else:
            print(f"\n低波动过滤: 共跳过 {len(low_vol_skipped)} 只标的（使用 --verbose 查看明细）。")

    if all_results:
        print("\n" + "=" * 70)
        print("回测汇总")
        print("=" * 70)
        header = f"{'代码':<12} {'类型':<8} {'策略':<15} {'收益率':>10} {'夏普':>8} {'最大回撤':>10}"
        print(header)
        print("-" * len(header))
        for result in all_results:
            instrument = result['instrument']  # type: ignore[assignment]
            stats = result['stats']  # type: ignore[assignment]
            return_pct = _safe_stat(stats, 'Return [%]')
            sharpe_value = stats['Sharpe Ratio']
            sharpe_display = f"{sharpe_value:>7.2f}" if not pd.isna(sharpe_value) else "   -- "
            max_dd = _safe_stat(stats, 'Max. Drawdown [%]', default=0.0)
            print(
                f"{instrument.code:<12} "
                f"{instrument.category:<8} "
                f"{result['strategy']:<15} "
                f"{return_pct:>9.2f}% "
                f"{sharpe_display} "
                f"{max_dd:>9.2f}%"
            )
        print("=" * 70)

        print(f"\n结果已保存到 {args.output_dir}/<category>/stats|plots/ 目录")

        aggregate_payload = build_aggregate_payload(all_results)
        if args.aggregate_output:
            aggregate_df = pd.DataFrame(aggregate_payload)
            aggregate_path = Path(args.aggregate_output)
            aggregate_path.parent.mkdir(parents=True, exist_ok=True)
            aggregate_df.to_csv(aggregate_path, index=False, encoding='utf-8-sig')
            print(f"聚合结果已写入: {aggregate_path}")
        else:
            print(f"聚合数据条目: {len(aggregate_payload)} (预留统一汇总接口)")

        return 0

    if low_vol_skipped:
        print("\n未生成任何回测结果（所有标的均被低波动过滤）。")
    else:
        print("\n未生成任何回测结果。")
    return 1


if __name__ == '__main__':
    sys.exit(main())
