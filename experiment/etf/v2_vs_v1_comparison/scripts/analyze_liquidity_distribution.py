#!/usr/bin/env python3
"""
分析 ETF 流动性指标分布，确定合理的筛选阈值

指标说明:
- volume: 成交量（股）
- amount: 成交额（元，需要乘以1000，因为数据单位是千元）
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# 数据目录
DATA_DIR = Path("/mnt/d/git/backtesting/data/chinese_etf/daily/etf")

def load_etf_data(lookback_days=252):
    """加载所有ETF数据，计算流动性指标"""

    etf_files = list(DATA_DIR.glob("*.csv"))
    print(f"找到 {len(etf_files)} 个ETF数据文件")

    end_date = datetime(2025, 11, 30)
    start_date = end_date - timedelta(days=lookback_days * 1.5)

    results = []

    for f in etf_files:
        try:
            df = pd.read_csv(f, parse_dates=['trade_date'],
                           date_parser=lambda x: pd.to_datetime(x, format='%Y%m%d'))

            if df.empty:
                continue

            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]

            if len(df) < 60:
                continue

            df = df.tail(lookback_days)
            symbol = f.stem

            avg_volume = df['volume'].mean()
            avg_amount = df['amount'].mean() * 1000  # 原数据单位是千元

            recent_df = df.tail(20)
            recent_avg_volume = recent_df['volume'].mean()
            recent_avg_amount = recent_df['amount'].mean() * 1000

            results.append({
                'symbol': symbol,
                'name': df['instrument_name'].iloc[-1] if 'instrument_name' in df.columns else symbol,
                'data_days': len(df),
                'avg_volume': avg_volume,
                'avg_amount': avg_amount,
                'recent_avg_volume': recent_avg_volume,
                'recent_avg_amount': recent_avg_amount,
                'last_close': df['close'].iloc[-1],
            })

        except Exception as e:
            continue

    return pd.DataFrame(results)


def analyze_distribution(df):
    """分析流动性指标分布"""

    print("\n" + "="*80)
    print("ETF 流动性指标分布分析")
    print("="*80)
    print(f"\n有效ETF数量: {len(df)}")

    percentiles = [5, 10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95]

    metrics = {
        'avg_volume': '平均成交量（股）',
        'avg_amount': '平均成交额（元）',
        'recent_avg_volume': '近20日平均成交量（股）',
        'recent_avg_amount': '近20日平均成交额（元）',
    }

    results = {}

    for col, name in metrics.items():
        print(f"\n### {name}")
        print("-" * 60)

        data = df[col]

        print(f"最小值: {data.min():,.0f}")
        print(f"最大值: {data.max():,.0f}")
        print(f"均值: {data.mean():,.0f}")
        print(f"中位数: {data.median():,.0f}")

        print(f"\n分位点分布:")
        pct_values = {}
        for p in percentiles:
            val = data.quantile(p/100)
            pct_values[p] = val
            print(f"  {p:3d}%: {val:>18,.0f}")

        results[col] = pct_values

    return results


def suggest_thresholds(df):
    """根据分布建议筛选阈值"""

    print("\n" + "="*80)
    print("流动性筛选阈值分析")
    print("="*80)

    print("\n### 成交额阈值分析")
    print("-" * 70)

    thresholds_amount = [100_000, 500_000, 1_000_000, 2_000_000, 5_000_000,
                         10_000_000, 20_000_000, 50_000_000, 100_000_000]

    print(f"{'阈值（元）':>15} | {'保留数量':>10} | {'保留比例':>10}")
    print("-" * 50)

    for thresh in thresholds_amount:
        count = (df['avg_amount'] >= thresh).sum()
        pct = count / len(df) * 100
        print(f"{thresh:>15,} | {count:>10} | {pct:>9.1f}%")

    print("\n### 成交量阈值分析")
    print("-" * 70)

    thresholds_volume = [10_000, 50_000, 100_000, 500_000, 1_000_000,
                         5_000_000, 10_000_000, 50_000_000]

    print(f"{'阈值（股）':>15} | {'保留数量':>10} | {'保留比例':>10}")
    print("-" * 50)

    for thresh in thresholds_volume:
        count = (df['avg_volume'] >= thresh).sum()
        pct = count / len(df) * 100
        print(f"{thresh:>15,} | {count:>10} | {pct:>9.1f}%")

    print("\n### 组合阈值分析")
    print("-" * 80)

    combos = [
        (1_000_000, 100_000),
        (5_000_000, 500_000),
        (10_000_000, 1_000_000),
        (20_000_000, 2_000_000),
        (50_000_000, 5_000_000),
        (100_000_000, 10_000_000),
    ]

    print(f"{'成交额阈值':>15} | {'成交量阈值':>12} | {'保留数量':>10} | {'保留比例':>10}")
    print("-" * 60)

    for amount_thresh, volume_thresh in combos:
        mask = (df['avg_amount'] >= amount_thresh) & (df['avg_volume'] >= volume_thresh)
        count = mask.sum()
        pct = count / len(df) * 100
        print(f"{amount_thresh:>15,} | {volume_thresh:>12,} | {count:>10} | {pct:>9.1f}%")


if __name__ == "__main__":
    print("开始分析 ETF 流动性分布...")

    df = load_etf_data(lookback_days=252)

    if df.empty:
        print("错误: 未能加载任何ETF数据")
        exit(1)

    analyze_distribution(df)
    suggest_thresholds(df)

    # 保存结果
    output_path = Path("/mnt/d/git/backtesting/experiment/etf/v2_vs_v1_comparison/results/etf_liquidity_analysis.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values('avg_amount', ascending=False).to_csv(output_path, index=False)
    print(f"\n结果已保存到: {output_path}")
