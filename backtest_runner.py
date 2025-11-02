#!/usr/bin/env python3
"""
美股回测执行器

使用backtesting.py框架对特斯拉和英伟达股票进行回测
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backtesting import Backtest
from utils.data_loader import load_lixinger_data, list_available_stocks, get_stock_name
from strategies.sma_cross import SmaCross, OPTIMIZE_PARAMS, CONSTRAINTS


# 可用的策略映射
STRATEGIES = {
    'sma_cross': SmaCross,
}

# 可用的股票名称映射
STOCK_NAMES = {
    'tesla': '特斯拉',
    'nvidia': '英伟达',
}


def run_single_backtest(data, strategy_class, stock_name, strategy_name,
                       cash=10000, commission=0.002, optimize=False,
                       output_dir='results', start_date=None, end_date=None):
    """
    运行单次回测

    Args:
        data: OHLCV格式的DataFrame
        strategy_class: 策略类
        stock_name: 股票名称
        strategy_name: 策略名称
        cash: 初始资金
        commission: 手续费率
        optimize: 是否进行参数优化
        output_dir: 输出目录
        start_date: 开始日期（用于显示）
        end_date: 结束日期（用于显示）

    Returns:
        回测统计结果
    """
    print("\n" + "=" * 70)
    print(f"回测: {STOCK_NAMES.get(stock_name, stock_name)} - {strategy_name}")
    if start_date or end_date:
        date_range = f"{start_date or '开始'} 至 {end_date or '结束'}"
        print(f"日期范围: {date_range}")
    print("=" * 70)

    # 创建回测实例
    bt = Backtest(
        data,
        strategy_class,
        cash=cash,
        commission=commission,
        exclusive_orders=True,
        finalize_trades=True
    )

    # 运行回测或优化
    if optimize:
        print("\n开始参数优化...")
        print(f"参数空间: {OPTIMIZE_PARAMS}")

        stats = bt.optimize(
            **OPTIMIZE_PARAMS,
            constraint=CONSTRAINTS,
            maximize='Sharpe Ratio',
            max_tries=200,
            random_state=42
        )

        print(f"\n最优参数:")
        print(f"  短期均线 (n1): {stats._strategy.n1}")
        print(f"  长期均线 (n2): {stats._strategy.n2}")
    else:
        print("\n运行回测...")
        stats = bt.run()

    # 显示关键指标
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

    # 保存结果
    save_results(stats, stock_name, strategy_name, output_dir, optimize)

    # 生成图表
    plot_path = f"{output_dir}/plots/{stock_name}_{strategy_name}.html"
    print(f"\n生成图表: {plot_path}")
    bt.plot(filename=plot_path, open_browser=False)

    return stats


def save_results(stats, stock_name, strategy_name, output_dir, optimized=False):
    """
    保存回测结果

    Args:
        stats: 回测统计结果
        stock_name: 股票名称
        strategy_name: 策略名称
        output_dir: 输出目录
        optimized: 是否为优化结果
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 确保输出目录存在
    os.makedirs(f"{output_dir}/stats", exist_ok=True)

    # 保存统计数据
    stats_file = f"{output_dir}/stats/{stock_name}_{strategy_name}_{timestamp}.csv"

    # 提取主要统计指标
    summary_data = {
        '股票': STOCK_NAMES.get(stock_name, stock_name),
        '策略': strategy_name,
        '是否优化': '是' if optimized else '否',
        '开始日期': str(stats['Start']),
        '结束日期': str(stats['End']),
        '持续天数': stats['Duration'].days,
        '初始资金': 10000,  # 从参数获取
        '最终资金': stats['Equity Final [$]'],
        '收益率(%)': stats['Return [%]'],
        '年化收益率(%)': stats['Return (Ann.) [%]'],
        '买入持有收益率(%)': stats['Buy & Hold Return [%]'],
        '夏普比率': stats['Sharpe Ratio'],
        '索提诺比率': stats['Sortino Ratio'],
        '卡玛比率': stats['Calmar Ratio'],
        '最大回撤(%)': stats['Max. Drawdown [%]'],
        '平均回撤(%)': stats['Avg. Drawdown [%]'],
        '最大回撤持续天数': stats['Max. Drawdown Duration'].days,
        '交易次数': stats['# Trades'],
        '胜率(%)': stats['Win Rate [%]'],
        '最佳交易(%)': stats['Best Trade [%]'],
        '最差交易(%)': stats['Worst Trade [%]'],
        '平均交易(%)': stats['Avg. Trade [%]'],
        '盈亏比': stats['Profit Factor'],
        '期望值(%)': stats['Expectancy [%]'],
        'SQN': stats['SQN'],
        '手续费': stats['Commissions [$]'],
    }

    # 如果是优化结果，添加参数信息
    if optimized and hasattr(stats._strategy, 'n1'):
        summary_data['短期均线(n1)'] = stats._strategy.n1
        summary_data['长期均线(n2)'] = stats._strategy.n2

    # 保存为CSV
    summary_df = pd.DataFrame([summary_data])
    summary_df.to_csv(stats_file, index=False, encoding='utf-8-sig')
    print(f"保存统计数据: {stats_file}")

    # 保存交易记录
    if len(stats._trades) > 0:
        trades_file = f"{output_dir}/stats/{stock_name}_{strategy_name}_{timestamp}_trades.csv"
        stats._trades.to_csv(trades_file, encoding='utf-8-sig')
        print(f"保存交易记录: {trades_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='美股回测系统 - 使用backtesting.py对特斯拉和英伟达进行策略回测',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 对特斯拉运行双均线策略
  python backtest_runner.py -s tesla -t sma_cross

  # 对所有股票运行策略并优化参数
  python backtest_runner.py -s all -t sma_cross -o

  # 自定义初始资金和手续费
  python backtest_runner.py -s nvidia -t sma_cross -m 50000 -c 0.001

  # 限定日期范围（只分析最近5年）
  python backtest_runner.py -s tesla --start-date 2020-01-01

  # 分析特定时间段
  python backtest_runner.py -s nvidia --start-date 2015-01-01 --end-date 2020-12-31
        """
    )

    parser.add_argument('-s', '--stock',
                       choices=['tesla', 'nvidia', 'all'],
                       default='all',
                       help='股票选择 (默认: all)')

    parser.add_argument('-t', '--strategy',
                       choices=list(STRATEGIES.keys()) + ['all'],
                       default='sma_cross',
                       help='策略选择 (默认: sma_cross)')

    parser.add_argument('-o', '--optimize',
                       action='store_true',
                       help='启用参数优化')

    parser.add_argument('-c', '--commission',
                       type=float,
                       default=0.002,
                       help='手续费率 (默认: 0.002, 即0.2%%)')

    parser.add_argument('-m', '--cash',
                       type=float,
                       default=10000,
                       help='初始资金 (默认: 10000美元)')

    parser.add_argument('-d', '--output-dir',
                       default='results',
                       help='输出目录 (默认: results)')

    parser.add_argument('--data-dir',
                       default='data/american_stocks',
                       help='数据目录 (默认: data/american_stocks)')

    parser.add_argument('--start-date',
                       type=str,
                       help='开始日期，格式：YYYY-MM-DD (例如: 2020-01-01)')

    parser.add_argument('--end-date',
                       type=str,
                       help='结束日期，格式：YYYY-MM-DD (例如: 2025-12-31)')

    args = parser.parse_args()

    # 显示配置
    print("=" * 70)
    print("美股回测系统")
    print("=" * 70)
    print(f"数据目录:     {args.data_dir}")
    print(f"输出目录:     {args.output_dir}")
    print(f"初始资金:     ${args.cash:,.2f}")
    print(f"手续费率:     {args.commission * 100:.2f}%")
    print(f"参数优化:     {'是' if args.optimize else '否'}")
    if args.start_date:
        print(f"开始日期:     {args.start_date}")
    if args.end_date:
        print(f"结束日期:     {args.end_date}")
    print("=" * 70)

    # 获取可用股票
    available_stocks = list_available_stocks(args.data_dir)
    if not available_stocks:
        print(f"\n错误: 在 {args.data_dir} 中未找到数据文件")
        return 1

    print(f"\n发现 {len(available_stocks)} 个股票数据文件:")
    for name, path in available_stocks.items():
        print(f"  - {STOCK_NAMES.get(name, name)}: {os.path.basename(path)}")

    # 确定要处理的股票
    if args.stock == 'all':
        stocks_to_process = list(available_stocks.keys())
    else:
        if args.stock not in available_stocks:
            print(f"\n错误: 未找到股票 '{args.stock}' 的数据文件")
            return 1
        stocks_to_process = [args.stock]

    # 确定要使用的策略
    if args.strategy == 'all':
        strategies_to_process = list(STRATEGIES.keys())
    else:
        strategies_to_process = [args.strategy]

    # 运行回测
    all_results = []
    for stock_name in stocks_to_process:
        csv_path = available_stocks[stock_name]

        # 加载数据
        try:
            data = load_lixinger_data(csv_path, stock_name,
                                     start_date=args.start_date,
                                     end_date=args.end_date)
        except Exception as e:
            print(f"\n错误: 加载 {stock_name} 数据失败: {e}")
            continue

        # 对每个策略运行回测
        for strategy_name in strategies_to_process:
            strategy_class = STRATEGIES[strategy_name]

            try:
                stats = run_single_backtest(
                    data=data,
                    strategy_class=strategy_class,
                    stock_name=stock_name,
                    strategy_name=strategy_name,
                    cash=args.cash,
                    commission=args.commission,
                    optimize=args.optimize,
                    output_dir=args.output_dir,
                    start_date=args.start_date,
                    end_date=args.end_date
                )
                all_results.append({
                    'stock': stock_name,
                    'strategy': strategy_name,
                    'stats': stats
                })
            except Exception as e:
                print(f"\n错误: 运行回测失败: {e}")
                import traceback
                traceback.print_exc()
                continue

    # 显示汇总
    if len(all_results) > 0:
        print("\n" + "=" * 70)
        print("回测汇总")
        print("=" * 70)
        print(f"{'股票':<15} {'策略':<15} {'收益率':<12} {'夏普比率':<12} {'最大回撤':<12}")
        print("-" * 70)
        for result in all_results:
            stock_name = STOCK_NAMES.get(result['stock'], result['stock'])
            stats = result['stats']
            print(f"{stock_name:<15} {result['strategy']:<15} "
                  f"{stats['Return [%]']:>10.2f}% "
                  f"{stats['Sharpe Ratio']:>10.2f} "
                  f"{stats['Max. Drawdown [%]']:>10.2f}%")
        print("=" * 70)

        print(f"\n结果已保存到 {args.output_dir}/ 目录")
        print(f"  - 统计数据: {args.output_dir}/stats/")
        print(f"  - 图表: {args.output_dir}/plots/")

    return 0


if __name__ == '__main__':
    sys.exit(main())
