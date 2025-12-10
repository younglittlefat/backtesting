#!/usr/bin/env python3
"""
批量回测ETF池

对生成的所有ETF池执行KAMA策略回测
- 2019-2021筛选的池子 → 2022-2023熊市回测
- 2022-2023筛选的池子 → 2024-2025牛市回测
"""
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import json
from datetime import datetime

# 实验目录
EXPERIMENT_DIR = Path(__file__).parent.parent
POOLS_DIR = EXPERIMENT_DIR / "pools"
BACKTESTS_DIR = EXPERIMENT_DIR / "backtests"
ANALYSIS_DIR = EXPERIMENT_DIR / "analysis"

# 项目根目录
PROJECT_ROOT = EXPERIMENT_DIR.parent.parent.parent

# 回测周期映射
BACKTEST_PERIODS = {
    "2019_2021": {
        "start_date": "2022-01-02",
        "end_date": "2023-12-31",
        "market": "bear_market",
        "description": "熊市回测"
    },
    "2022_2023": {
        "start_date": "2024-01-02",
        "end_date": "2025-11-30",
        "market": "bull_market",
        "description": "牛市回测"
    },
}

# KAMA策略配置
KAMA_STRATEGY_ARGS = [
    "--strategy", "kama_cross",
    "--kama-period", "20",
    "--kama-fast", "2",
    "--kama-slow", "30",
    "--enable-adx-filter",
    "--adx-period", "14",
    "--adx-threshold", "25.0",
    "--enable-atr-stop",
    "--atr-period", "14",
    "--atr-multiplier", "2.5",
    "--enable-slope-confirmation",
    "--min-slope-periods", "3",
]


def run_single_backtest(
    pool_path: Path,
    output_dir: Path,
    start_date: str,
    end_date: str,
    verbose: bool = True
) -> Optional[Dict]:
    """执行单个池的回测"""
    pool_name = pool_path.stem

    if verbose:
        print(f"\n  回测: {pool_name}")
        print(f"    周期: {start_date} ~ {end_date}")

    # 构建命令
    backtest_runner_script = PROJECT_ROOT / "backtest_runner.py"
    cmd = [
        sys.executable, str(backtest_runner_script),
        "--stock-list", str(pool_path),
        "--data-dir", "data/chinese_etf/daily",
        "--output-dir", str(output_dir / pool_name),
        "--start-date", start_date,
        "--end-date", end_date,
    ] + KAMA_STRATEGY_ARGS

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        if result.returncode != 0:
            print(f"    错误: 回测失败")
            if verbose:
                print(f"    stderr: {result.stderr[:500]}")
            return None

        # 查找生成的summary文件
        summary_dir = output_dir / pool_name / "summary"
        if summary_dir.exists():
            # 优先使用 backtest_summary（详细数据），如果不存在则使用 global_summary
            backtest_summary_files = list(summary_dir.glob("backtest_summary_*.csv"))
            global_summary_files = list(summary_dir.glob("global_summary_*.csv"))

            if backtest_summary_files:
                summary_path = backtest_summary_files[0]
                summary_df = pd.read_csv(summary_path, encoding='utf-8-sig')

                # 中文列名映射
                col_map = {
                    '收益率(%)': 'return',
                    '夏普比率': 'sharpe',
                    '最大回撤(%)': 'max_dd',
                    '胜率(%)': 'win_rate',
                    '交易次数': 'trades'
                }

                # 提取关键指标
                metrics = {
                    'pool_name': pool_name,
                    'num_stocks': len(summary_df),
                    'return_mean': summary_df['收益率(%)'].mean() if '收益率(%)' in summary_df.columns else None,
                    'return_median': summary_df['收益率(%)'].median() if '收益率(%)' in summary_df.columns else None,
                    'sharpe_mean': summary_df['夏普比率'].mean() if '夏普比率' in summary_df.columns else None,
                    'sharpe_median': summary_df['夏普比率'].median() if '夏普比率' in summary_df.columns else None,
                    'max_dd_mean': summary_df['最大回撤(%)'].mean() if '最大回撤(%)' in summary_df.columns else None,
                    'max_dd_median': summary_df['最大回撤(%)'].median() if '最大回撤(%)' in summary_df.columns else None,
                    'win_rate_mean': summary_df['胜率(%)'].mean() if '胜率(%)' in summary_df.columns else None,
                    'trades_mean': summary_df['交易次数'].mean() if '交易次数' in summary_df.columns else None,
                    'summary_path': str(summary_path),
                }

                if verbose:
                    print(f"    夏普均值: {metrics['sharpe_mean']:.3f}" if metrics['sharpe_mean'] else "    夏普均值: N/A")
                    print(f"    收益均值: {metrics['return_mean']:.2f}%" if metrics['return_mean'] else "    收益均值: N/A")

                return metrics
            elif global_summary_files:
                # 如果只有 global_summary，从中提取数据
                summary_path = global_summary_files[0]
                summary_df = pd.read_csv(summary_path, encoding='utf-8-sig')

                if len(summary_df) > 0:
                    row = summary_df.iloc[0]
                    metrics = {
                        'pool_name': pool_name,
                        'num_stocks': int(row['标的数量']) if '标的数量' in row else None,
                        'return_mean': row['年化收益率-均值(%)'] if '年化收益率-均值(%)' in row else None,
                        'return_median': row['年化收益率-中位数(%)'] if '年化收益率-中位数(%)' in row else None,
                        'sharpe_mean': row['夏普-均值'] if '夏普-均值' in row else None,
                        'sharpe_median': row['夏普-中位数'] if '夏普-中位数' in row else None,
                        'max_dd_mean': row['最大回撤-均值(%)'] if '最大回撤-均值(%)' in row else None,
                        'max_dd_median': row['最大回撤-中位数(%)'] if '最大回撤-中位数(%)' in row else None,
                        'win_rate_mean': row['胜率-均值(%)'] if '胜率-均值(%)' in row else None,
                        'trades_mean': row['交易次数-均值'] if '交易次数-均值' in row else None,
                        'summary_path': str(summary_path),
                    }

                    if verbose:
                        print(f"    夏普均值: {metrics['sharpe_mean']:.3f}" if metrics['sharpe_mean'] else "    夏普均值: N/A")
                        print(f"    收益均值: {metrics['return_mean']:.2f}%" if metrics['return_mean'] else "    收益均值: N/A")

                    return metrics

        print(f"    警告: 未找到回测结果")
        return None

    except subprocess.TimeoutExpired:
        print(f"    错误: 回测超时")
        return None
    except Exception as e:
        print(f"    错误: {e}")
        return None


def run_all_backtests(verbose: bool = True) -> pd.DataFrame:
    """执行所有回测"""
    # 获取所有池文件
    pool_files = sorted(POOLS_DIR.glob("*.csv"))
    # 过滤掉 _all_scores 文件
    pool_files = [p for p in pool_files if "_all_scores" not in p.name]

    if not pool_files:
        print("错误: 未找到ETF池文件，请先运行 generate_pools.py")
        return pd.DataFrame()

    print(f"找到 {len(pool_files)} 个ETF池")

    all_results = []

    for period_key, period_config in BACKTEST_PERIODS.items():
        market = period_config["market"]
        output_dir = BACKTESTS_DIR / market
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"回测周期: {period_config['description']} ({period_config['start_date']} ~ {period_config['end_date']})")
        print(f"{'='*60}")

        # 筛选对应周期的池
        period_pools = [p for p in pool_files if period_key in p.name]
        print(f"匹配池数量: {len(period_pools)}")

        for i, pool_path in enumerate(period_pools, 1):
            print(f"\n[{i}/{len(period_pools)}]", end="")
            result = run_single_backtest(
                pool_path,
                output_dir,
                period_config["start_date"],
                period_config["end_date"],
                verbose=verbose
            )

            if result:
                # 解析池名称
                parts = pool_path.stem.split('_')
                algorithm = parts[-1]
                period = f"{parts[-3]}_{parts[-2]}"
                dimension = '_'.join(parts[:-3])

                result['dimension'] = dimension
                result['period'] = period
                result['algorithm'] = algorithm
                result['market'] = market
                result['backtest_start'] = period_config["start_date"]
                result['backtest_end'] = period_config["end_date"]

                all_results.append(result)

    # 汇总结果
    if all_results:
        results_df = pd.DataFrame(all_results)

        # 保存汇总
        summary_path = ANALYSIS_DIR / "backtest_results_summary.csv"
        results_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
        print(f"\n\n回测汇总已保存: {summary_path}")

        return results_df

    return pd.DataFrame()


def main():
    print("=" * 60)
    print("批量回测ETF池 (聚类 vs 贪心对比实验)")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查池文件是否存在
    if not POOLS_DIR.exists() or not list(POOLS_DIR.glob("*.csv")):
        print("\nETF池文件不存在，请先运行 generate_pools.py")
        return

    # 执行回测
    results_df = run_all_backtests(verbose=True)

    if not results_df.empty:
        print("\n" + "=" * 60)
        print("回测完成!")
        print("=" * 60)
        print(f"成功回测 {len(results_df)} 个池")
        print(f"结果目录: {BACKTESTS_DIR}")
        print(f"汇总文件: {ANALYSIS_DIR / 'backtest_results_summary.csv'}")


if __name__ == "__main__":
    main()
