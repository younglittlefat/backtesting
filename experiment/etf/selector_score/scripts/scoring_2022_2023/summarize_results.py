#!/usr/bin/env python
"""汇总所有池子的回测结果"""
import pandas as pd
from pathlib import Path
from backtest_config import RESULTS_DIR

def collect_summary_results():
    """收集所有池子的global_summary结果"""
    all_results = []

    for pool_dir in sorted(RESULTS_DIR.glob("*")):
        if not pool_dir.is_dir():
            continue

        pool_name = pool_dir.name

        # 查找 global_summary CSV文件
        summary_files = list((pool_dir / "summary").glob("global_summary_*.csv"))

        if not summary_files:
            print(f"警告: {pool_name} 没有找到summary文件")
            continue

        # 读取最新的summary文件
        summary_file = sorted(summary_files)[-1]
        print(f"读取: {pool_name} - {summary_file.name}")

        try:
            df = pd.read_csv(summary_file, encoding='utf-8-sig')  # 处理BOM

            # 提取关键指标（中文列名）
            if len(df) > 0:
                result = {
                    "pool_name": pool_name,
                    "num_stocks": df["标的数量"].iloc[0],
                    "annual_return_mean": df["年化收益率-均值(%)"].iloc[0],
                    "annual_return_median": df["年化收益率-中位数(%)"].iloc[0],
                    "sharpe_mean": df["夏普-均值"].iloc[0],
                    "sharpe_median": df["夏普-中位数"].iloc[0],
                    "max_drawdown_mean": df["最大回撤-均值(%)"].iloc[0],
                    "max_drawdown_median": df["最大回撤-中位数(%)"].iloc[0],
                    "win_rate_mean": df["胜率-均值(%)"].iloc[0],
                    "win_rate_median": df["胜率-中位数(%)"].iloc[0],
                    "profit_loss_ratio_mean": df["盈亏比-均值"].iloc[0],
                    "total_trades_mean": df["交易次数-均值"].iloc[0],
                }
                all_results.append(result)
        except Exception as e:
            print(f"错误: 读取 {pool_name} 失败 - {e}")

    return pd.DataFrame(all_results)

def main():
    print("开始汇总回测结果...")
    print(f"结果目录: {RESULTS_DIR}")

    # 收集所有结果
    df = collect_summary_results()

    if len(df) == 0:
        print("\n错误: 没有找到任何回测结果！")
        return

    # 按夏普比率排序
    df = df.sort_values("sharpe_mean", ascending=False)

    # 保存汇总结果
    output_file = RESULTS_DIR.parent / "pool_comparison_summary.csv"
    df.to_csv(output_file, index=False, float_format="%.4f")
    print(f"\n✓ 汇总结果已保存到: {output_file}")

    # 打印汇总表
    print("\n" + "="*100)
    print("回测结果汇总（按平均夏普比率排序）")
    print("="*100)

    # 格式化输出
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 180)
    pd.set_option('display.float_format', '{:.2f}'.format)

    print(df.to_string(index=False))

    print("\n" + "="*100)
    print("表现最好的3个维度:")
    print("="*100)
    for i, row in df.head(3).iterrows():
        print(f"\n{i+1}. {row['pool_name']}")
        print(f"   平均夏普比率: {row['sharpe_mean']:.3f} (中位数: {row['sharpe_median']:.3f})")
        print(f"   平均年化收益率: {row['annual_return_mean']:.2f}% (中位数: {row['annual_return_median']:.2f}%)")
        print(f"   平均最大回撤: {row['max_drawdown_mean']:.2f}% (中位数: {row['max_drawdown_median']:.2f}%)")
        print(f"   平均胜率: {row['win_rate_mean']:.2f}% (中位数: {row['win_rate_median']:.2f}%)")

    print("\n" + "="*100)
    print("表现最差的3个维度:")
    print("="*100)
    for i, row in df.tail(3).iloc[::-1].iterrows():
        idx = len(df) - list(df.tail(3).iloc[::-1].index).index(i)
        print(f"\n{idx}. {row['pool_name']}")
        print(f"   平均夏普比率: {row['sharpe_mean']:.3f} (中位数: {row['sharpe_median']:.3f})")
        print(f"   平均年化收益率: {row['annual_return_mean']:.2f}% (中位数: {row['annual_return_median']:.2f}%)")
        print(f"   平均最大回撤: {row['max_drawdown_mean']:.2f}% (中位数: {row['max_drawdown_median']:.2f}%)")
        print(f"   平均胜率: {row['win_rate_mean']:.2f}% (中位数: {row['win_rate_median']:.2f}%)")

if __name__ == "__main__":
    main()
