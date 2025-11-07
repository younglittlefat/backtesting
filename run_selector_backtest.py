#!/usr/bin/env python3
"""
ETF筛选与回测一体化脚本

结合ETF趋势筛选系统和回测系统，提供从筛选到回测的完整自动化流程。

主要功能：
1. 运行ETF趋势筛选，生成优质标的池
2. 自动使用筛选结果进行策略回测
3. 生成筛选分析和回测结果的综合报告
4. 支持多种运行模式和参数配置

使用示例：
    # 基本使用：筛选20只ETF并回测
    python run_selector_backtest.py

    # 自定义筛选参数和回测配置
    python run_selector_backtest.py \\
        --target-size 30 \\
        --strategy sma_cross \\
        --optimize \\
        --start-date 2023-01-01

    # 仅使用现有筛选结果进行回测
    python run_selector_backtest.py \\
        --use-existing results/trend_etf_pool_20251107.csv \\
        --strategy sma_cross

    # 详细模式，生成完整分析报告
    python run_selector_backtest.py \\
        --target-size 15 \\
        --with-analysis \\
        --verbose
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_command(cmd, description="", verbose=True):
    """执行命令并处理结果

    Args:
        cmd: 要执行的命令（列表或字符串）
        description: 命令描述
        verbose: 是否显示详细输出

    Returns:
        (returncode, stdout, stderr) 元组
    """
    if isinstance(cmd, str):
        cmd = cmd.split()

    if verbose and description:
        print(f"\n🚀 {description}")
        print(f"执行命令: {' '.join(cmd)}")
        print("-" * 60)

    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,  # 如果详细模式，直接输出到终端
            text=True,
            cwd=project_root
        )

        if verbose:
            print("-" * 60)
            if result.returncode == 0:
                print(f"✅ {description} 完成")
            else:
                print(f"❌ {description} 失败 (退出码: {result.returncode})")

        return result.returncode, result.stdout, result.stderr

    except Exception as e:
        print(f"❌ 执行命令失败: {e}")
        return -1, "", str(e)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='ETF筛选与回测一体化脚本 - 从筛选到回测的完整自动化流程',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                                    # 筛选20只ETF并回测
  %(prog)s --target-size 30 --optimize        # 筛选30只ETF并优化回测
  %(prog)s --use-existing pool.csv             # 使用现有筛选结果回测
  %(prog)s --strategy sma_cross --verbose      # 详细模式运行

流程说明:
  1. ETF趋势筛选：使用三级漏斗模型筛选优质ETF标的池
  2. 策略回测：对筛选出的ETF进行策略回测和性能评估
  3. 结果分析：生成筛选分析报告和回测汇总报告
        """
    )

    # 基本控制参数
    parser.add_argument(
        '--use-existing', type=str,
        help='使用现有筛选结果文件（CSV格式），跳过筛选步骤'
    )
    parser.add_argument(
        '--selector-only', action='store_true',
        help='仅运行筛选器，不执行回测'
    )
    parser.add_argument(
        '--backtest-only', action='store_true',
        help='仅运行回测，需要配合--use-existing使用'
    )

    # 筛选器参数
    parser.add_argument(
        '--target-size', type=int, default=20,
        help='筛选目标数量 (默认: 20)'
    )
    parser.add_argument(
        '--start-date', type=str,
        help='数据开始日期 (YYYY-MM-DD)，同时用于筛选和回测'
    )
    parser.add_argument(
        '--end-date', type=str,
        help='数据结束日期 (YYYY-MM-DD)，同时用于筛选和回测'
    )
    parser.add_argument(
        '--min-turnover', type=float, default=50_000_000,
        help='最小日均成交额，单位元 (默认: 5000万)'
    )
    parser.add_argument(
        '--max-correlation', type=float, default=0.7,
        help='组合优化最大相关性阈值 (默认: 0.7)'
    )
    parser.add_argument(
        '--with-analysis', action='store_true',
        help='生成详细的组合风险分析报告'
    )

    # 回测参数
    parser.add_argument(
        '--strategy', type=str, default='sma_cross',
        choices=['sma_cross'],  # 可以扩展更多策略
        help='回测策略 (默认: sma_cross)'
    )
    parser.add_argument(
        '--optimize', action='store_true',
        help='启用策略参数优化'
    )
    parser.add_argument(
        '--cost-model', type=str, default='cn_etf',
        choices=['default', 'cn_etf', 'cn_stock', 'us_stock', 'custom'],
        help='交易成本模型 (默认: cn_etf)'
    )
    parser.add_argument(
        '--cash', type=float, default=10000,
        help='初始回测资金 (默认: 10000)'
    )

    # 输出和配置
    parser.add_argument(
        '--output-dir', type=str, default='results/integrated',
        help='输出目录 (默认: results/integrated)'
    )
    parser.add_argument(
        '--data-dir', type=str, default='/mnt/d/git/backtesting/data/csv',
        help='数据目录 (默认: /mnt/d/git/backtesting/data/csv)'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='显示详细输出'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='仅显示将要执行的命令，不实际运行'
    )

    return parser.parse_args()


def run_selector(args):
    """运行ETF筛选器

    Args:
        args: 命令行参数

    Returns:
        (success, output_file_path) 元组
    """
    # 构建筛选器命令
    cmd = [
        sys.executable, '-m', 'etf_selector.main',
        '--target-size', str(args.target_size),
        '--min-turnover', str(args.min_turnover),
        '--max-correlation', str(args.max_correlation),
    ]

    # 添加可选参数
    if args.start_date:
        cmd.extend(['--start-date', args.start_date])
    if args.end_date:
        cmd.extend(['--end-date', args.end_date])

    # 设置输出文件
    timestamp = datetime.now().strftime('%Y%m%d')
    output_file = Path(args.output_dir) / f'trend_etf_pool_{timestamp}.csv'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    cmd.extend(['--output', str(output_file)])

    if args.with_analysis:
        cmd.append('--with-analysis')

    if not args.verbose:
        cmd.append('--quiet')

    # 执行命令
    if args.dry_run:
        print(f"🔍 [DRY RUN] 筛选器命令: {' '.join(cmd)}")
        print(f"🔍 [DRY RUN] 输出文件: {output_file}")
        return True, output_file

    returncode, stdout, stderr = run_command(
        cmd, "运行ETF趋势筛选器", args.verbose
    )

    if returncode == 0:
        # 查找实际生成的文件（可能包含额外的时间戳）
        pattern = f"trend_etf_pool_{timestamp}*.csv"
        possible_files = list(output_file.parent.glob(pattern))
        if possible_files:
            actual_file = max(possible_files, key=lambda x: x.stat().st_mtime)
            return True, actual_file
        else:
            return True, output_file
    else:
        print(f"❌ 筛选器执行失败")
        if not args.verbose and stderr:
            print(f"错误信息: {stderr}")
        return False, None


def run_backtest(selector_output_file, args):
    """运行回测

    Args:
        selector_output_file: 筛选结果文件路径
        args: 命令行参数

    Returns:
        成功标志 (bool)
    """
    # 构建回测命令
    cmd = [
        './run_backtest.sh',
        '--stock-list', str(selector_output_file),
        '--strategy', args.strategy,
        '--cost-model', args.cost_model,
        '--cash', str(args.cash),
        '--data-dir', args.data_dir,
        '--output-dir', args.output_dir,
    ]

    # 添加可选参数
    if args.start_date:
        cmd.extend(['--start-date', args.start_date])
    if args.end_date:
        cmd.extend(['--end-date', args.end_date])

    if args.optimize:
        cmd.append('--optimize')

    if args.verbose:
        cmd.append('--verbose')

    # 执行命令
    if args.dry_run:
        print(f"🔍 [DRY RUN] 回测命令: {' '.join(cmd)}")
        return True

    returncode, stdout, stderr = run_command(
        cmd, "运行策略回测", args.verbose
    )

    if returncode == 0:
        return True
    else:
        print(f"❌ 回测执行失败")
        if not args.verbose and stderr:
            print(f"错误信息: {stderr}")
        return False


def generate_final_report(selector_output_file, args):
    """生成最终综合报告

    Args:
        selector_output_file: 筛选结果文件路径
        args: 命令行参数
    """
    if args.dry_run:
        print(f"🔍 [DRY RUN] 将生成综合报告")
        return

    try:
        import pandas as pd

        print("\n📊 生成综合报告...")

        # 读取筛选结果
        selector_df = pd.read_csv(selector_output_file)

        # 查找最新的回测汇总文件
        summary_pattern = Path(args.output_dir) / 'summary' / 'backtest_summary_*.csv'
        summary_files = list(Path(args.output_dir).glob('summary/backtest_summary_*.csv'))

        report_content = []
        report_content.append("=" * 80)
        report_content.append("ETF筛选与回测一体化报告")
        report_content.append("=" * 80)
        report_content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_content.append(f"数据期间: {args.start_date or '全部'} 至 {args.end_date or '全部'}")
        report_content.append("")

        # 筛选结果摘要
        report_content.append("🎯 筛选结果摘要:")
        report_content.append(f"  目标数量: {args.target_size} 只")
        report_content.append(f"  实际筛选: {len(selector_df)} 只")
        if 'industry' in selector_df.columns:
            industry_dist = selector_df['industry'].value_counts()
            report_content.append(f"  行业分布: {dict(industry_dist)}")
        report_content.append("")

        # 筛选结果详情
        report_content.append("📋 筛选标的详情:")
        for i, row in selector_df.iterrows():
            report_content.append(f"  {i+1}. {row['ts_code']} - {row['name']}")
            if 'industry' in row:
                report_content.append(f"     行业: {row['industry']}")
            if 'return_dd_ratio' in row:
                report_content.append(f"     收益回撤比: {row['return_dd_ratio']:.3f}")
            if 'adx_mean' in row:
                report_content.append(f"     ADX均值: {row['adx_mean']:.1f}")

        # 回测结果摘要（如果可用）
        if summary_files and not args.selector_only:
            latest_summary = max(summary_files, key=lambda x: x.stat().st_mtime)
            backtest_df = pd.read_csv(latest_summary)

            report_content.append("")
            report_content.append("📈 回测结果摘要:")
            report_content.append(f"  回测标的数量: {len(backtest_df)}")

            if len(backtest_df) > 0:
                # 检查列名并适配不同的格式
                return_col = '收益率' if '收益率' in backtest_df.columns else '收益率(%)'
                sharpe_col = '夏普' if '夏普' in backtest_df.columns else '夏普比率'
                drawdown_col = '最大回撤' if '最大回撤' in backtest_df.columns else '最大回撤(%)'
                code_col = '代码' if '代码' in backtest_df.columns else 'Code'
                name_col = '名称' if '名称' in backtest_df.columns else '标的名称'

                if return_col in backtest_df.columns:
                    # 处理收益率和回撤列（可能已经是数值或带%的字符串）
                    if backtest_df[return_col].dtype == 'object':
                        avg_return = backtest_df[return_col].str.rstrip('%').astype(float).mean()
                    else:
                        avg_return = backtest_df[return_col].mean()

                    avg_sharpe = backtest_df[sharpe_col].mean()

                    if backtest_df[drawdown_col].dtype == 'object':
                        avg_drawdown = backtest_df[drawdown_col].str.rstrip('%').astype(float).mean()
                    else:
                        avg_drawdown = backtest_df[drawdown_col].mean()

                    report_content.append(f"  平均收益率: {avg_return:.2f}%")
                    report_content.append(f"  平均夏普比: {avg_sharpe:.2f}")
                    report_content.append(f"  平均最大回撤: {avg_drawdown:.2f}%")

                    # 显示前5名回测结果
                    report_content.append("")
                    report_content.append("🏆 回测结果排行（按收益率）:")

                    # 转换收益率为数值进行排序
                    if backtest_df[return_col].dtype == 'object':
                        backtest_df['return_numeric'] = backtest_df[return_col].str.rstrip('%').astype(float)
                    else:
                        backtest_df['return_numeric'] = backtest_df[return_col]

                    top_performers = backtest_df.nlargest(5, 'return_numeric')

                    for i, (idx, row) in enumerate(top_performers.iterrows()):
                        report_content.append(f"  {i+1}. {row[code_col]} - {row[name_col]}")
                        report_content.append(f"     收益率: {row[return_col]}, 夏普: {row[sharpe_col]:.2f}, 最大回撤: {row[drawdown_col]}")
                else:
                    report_content.append("  ⚠️ 回测结果格式不匹配，无法生成详细统计")
                    report_content.append(f"  📊 可用列: {list(backtest_df.columns)}")

        report_content.append("")
        report_content.append("=" * 80)

        # 保存报告
        report_path = Path(args.output_dir) / f'integrated_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_content))

        print(f"✅ 综合报告已生成: {report_path}")

        if args.verbose:
            print("\n" + '\n'.join(report_content))

    except Exception as e:
        print(f"⚠️ 生成综合报告失败: {e}")


def main():
    """主函数"""
    args = parse_arguments()

    # 参数验证
    if args.backtest_only and not args.use_existing:
        print("❌ --backtest-only 选项需要配合 --use-existing 使用")
        return 1

    # 输出配置摘要
    print("=" * 80)
    print("🚀 ETF筛选与回测一体化脚本")
    print("=" * 80)
    print(f"运行模式: {'仅筛选' if args.selector_only else '仅回测' if args.backtest_only else '完整流程'}")
    print(f"目标数量: {args.target_size} 只ETF")
    print(f"回测策略: {args.strategy}")
    print(f"数据期间: {args.start_date or '全部'} 至 {args.end_date or '全部'}")
    print(f"输出目录: {args.output_dir}")
    if args.dry_run:
        print("🔍 DRY RUN 模式：仅显示命令，不实际执行")
    print("=" * 80)

    selector_output_file = None

    # 第一步：运行筛选器（除非使用现有结果或仅回测模式）
    if not args.backtest_only:
        if args.use_existing:
            selector_output_file = Path(args.use_existing)
            if not selector_output_file.exists():
                print(f"❌ 指定的筛选结果文件不存在: {selector_output_file}")
                return 1
            print(f"📁 使用现有筛选结果: {selector_output_file}")
        else:
            success, selector_output_file = run_selector(args)
            if not success:
                print("❌ 筛选步骤失败，程序终止")
                return 1

    # 第二步：运行回测（除非仅筛选模式）
    if not args.selector_only and selector_output_file:
        success = run_backtest(selector_output_file, args)
        if not success:
            print("❌ 回测步骤失败")
            return 1

    # 第三步：生成综合报告
    if selector_output_file:
        generate_final_report(selector_output_file, args)

    if not args.dry_run:
        print("\n🎉 一体化流程完成！")
        print(f"📁 所有结果保存在: {args.output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())