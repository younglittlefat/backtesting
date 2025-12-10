#!/usr/bin/env python3
"""
ETF趋势可视化工具
================

为不同分数池子的Top20 ETF生成专业K线图，包含：
- K线蜡烛图（基准期 + 未来期）
- 20/60日均线叠加
- ADX趋势强度指标
- 关键统计指标面板

用于验证趋势分数在基准期和未来期的预测能力。
"""

import os
import sys
import glob
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import matplotlib.gridspec as gridspec

# 设置中文字体 - 使用英文避免WSL字体问题
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 100

# 全局使用英文标签
LABEL_EN = True

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "chinese_etf" / "daily" / "etf"
SELECTOR_SCORE_DIR = PROJECT_ROOT / "experiment" / "etf" / "selector_score"
OUTPUT_DIR = SELECTOR_SCORE_DIR / "visualizations"


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算ADX指标"""
    high = df['adj_high'].values
    low = df['adj_low'].values
    close = df['adj_close'].values

    n = len(df)
    if n < period * 2:
        return pd.Series([np.nan] * n, index=df.index)

    # True Range
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1]))

    # +DM and -DM
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Smoothed using Wilder's smoothing (EMA with alpha=1/period)
    atr = np.zeros(n)
    smooth_plus_dm = np.zeros(n)
    smooth_minus_dm = np.zeros(n)

    # Initial SMA
    atr[period-1] = np.mean(tr[:period])
    smooth_plus_dm[period-1] = np.mean(plus_dm[:period])
    smooth_minus_dm[period-1] = np.mean(minus_dm[:period])

    # Wilder's smoothing
    for i in range(period, n):
        atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
        smooth_plus_dm[i] = (smooth_plus_dm[i-1] * (period-1) + plus_dm[i]) / period
        smooth_minus_dm[i] = (smooth_minus_dm[i-1] * (period-1) + minus_dm[i]) / period

    # +DI and -DI
    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    for i in range(period-1, n):
        if atr[i] > 0:
            plus_di[i] = 100 * smooth_plus_dm[i] / atr[i]
            minus_di[i] = 100 * smooth_minus_dm[i] / atr[i]

    # DX
    dx = np.zeros(n)
    for i in range(period-1, n):
        denom = plus_di[i] + minus_di[i]
        if denom > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / denom

    # ADX (SMA of DX)
    adx = np.zeros(n)
    for i in range(2*period-2, n):
        adx[i] = np.mean(dx[i-period+1:i+1])

    # Set early values to NaN
    adx[:2*period-2] = np.nan

    return pd.Series(adx, index=df.index)


def calculate_stats(df: pd.DataFrame) -> Dict:
    """计算关键统计指标"""
    if df.empty or len(df) < 2:
        return {
            'return': 0,
            'annualized_return': 0,
            'max_drawdown': 0,
            'sharpe': 0,
            'volatility': 0,
            'trend_days': 0
        }

    close = df['adj_close']
    returns = close.pct_change().dropna()

    # 总收益
    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100

    # 年化收益
    trading_days = len(df)
    years = trading_days / 252
    annualized_return = ((1 + total_return/100) ** (1/years) - 1) * 100 if years > 0 else 0

    # 最大回撤
    cummax = close.cummax()
    drawdown = (close - cummax) / cummax
    max_drawdown = drawdown.min() * 100

    # 夏普比率（假设无风险利率2%）
    if len(returns) > 1:
        excess_returns = returns - 0.02/252
        sharpe = np.sqrt(252) * excess_returns.mean() / (returns.std() + 1e-10)
    else:
        sharpe = 0

    # 波动率（年化）
    volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 1 else 0

    # 趋势持续天数（ADX > 25的天数）
    if 'adx' in df.columns:
        trend_days = (df['adx'] > 25).sum()
    else:
        trend_days = 0

    return {
        'return': total_return,
        'annualized_return': annualized_return,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'volatility': volatility,
        'trend_days': trend_days
    }


def plot_candlestick(ax, df: pd.DataFrame, title: str = ""):
    """绘制K线蜡烛图"""
    if df.empty:
        ax.text(0.5, 0.5, "No Data", ha='center', va='center', transform=ax.transAxes, fontsize=14)
        return

    dates = df.index
    opens = df['adj_open']
    highs = df['adj_high']
    lows = df['adj_low']
    closes = df['adj_close']

    # 计算K线宽度
    width = 0.6
    width2 = 0.1

    # 上涨和下跌的颜色
    up_color = '#E74C3C'  # 红色（中国市场习惯）
    down_color = '#27AE60'  # 绿色

    for i, (date, o, h, l, c) in enumerate(zip(dates, opens, highs, lows, closes)):
        color = up_color if c >= o else down_color

        # 绘制影线
        ax.plot([i, i], [l, h], color=color, linewidth=0.8)

        # 绘制实体
        body_bottom = min(o, c)
        body_height = abs(c - o)
        rect = Rectangle((i - width/2, body_bottom), width, body_height,
                         facecolor=color, edgecolor=color, linewidth=0.5)
        ax.add_patch(rect)

    # 设置X轴
    ax.set_xlim(-1, len(dates))

    # 设置刻度
    tick_positions = np.linspace(0, len(dates)-1, min(6, len(dates))).astype(int)
    tick_labels = [dates[i].strftime('%Y-%m') for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=8)

    ax.set_ylabel('Price', fontsize=9)
    if title:
        ax.set_title(title, fontsize=10, fontweight='bold')


def plot_moving_averages(ax, df: pd.DataFrame):
    """叠加均线"""
    if df.empty or len(df) < 60:
        return

    close = df['adj_close']
    ma20 = close.rolling(window=20).mean()
    ma60 = close.rolling(window=60).mean()

    x = np.arange(len(df))
    ax.plot(x, ma20, color='#3498DB', linewidth=1.2, label='MA20', alpha=0.8)
    ax.plot(x, ma60, color='#9B59B6', linewidth=1.2, label='MA60', alpha=0.8)
    ax.legend(loc='upper left', fontsize=7, framealpha=0.7)


def plot_adx(ax, df: pd.DataFrame):
    """绘制ADX指标"""
    if df.empty or 'adx' not in df.columns:
        ax.text(0.5, 0.5, "ADX N/A", ha='center', va='center', transform=ax.transAxes)
        return

    x = np.arange(len(df))
    adx = df['adx']

    # 绘制ADX线
    ax.plot(x, adx, color='#E67E22', linewidth=1.2, label='ADX')

    # 绘制25阈值线
    ax.axhline(y=25, color='#95A5A6', linestyle='--', linewidth=0.8, label='Threshold=25')

    # 填充ADX>25的区域
    ax.fill_between(x, 0, adx, where=adx > 25, color='#E67E22', alpha=0.3)

    ax.set_ylim(0, max(60, adx.max() * 1.1) if not adx.isna().all() else 60)
    ax.set_ylabel('ADX', fontsize=9)
    ax.legend(loc='upper right', fontsize=7, framealpha=0.7)

    # 设置X轴
    tick_positions = np.linspace(0, len(df)-1, min(6, len(df))).astype(int)
    tick_labels = [df.index[i].strftime('%Y-%m') for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=8)


def add_stats_panel(ax, stats_base: Dict, stats_future: Dict, score: float, rank: int):
    """添加统计指标面板"""
    ax.axis('off')

    # 使用英文标签
    text = f"[Selection Info]\n"
    text += f"  Score: {score:.4f}  Rank: #{rank}\n\n"

    text += f"[Base Period Stats]\n"
    text += f"  Return: {stats_base['return']:+.2f}%\n"
    text += f"  Annual: {stats_base['annualized_return']:+.2f}%\n"
    text += f"  MaxDD: {stats_base['max_drawdown']:.2f}%\n"
    text += f"  Sharpe: {stats_base['sharpe']:.2f}\n"
    text += f"  Volatility: {stats_base['volatility']:.1f}%\n"
    text += f"  Trend Days: {stats_base['trend_days']}\n\n"

    text += f"[Future Period Stats]\n"
    text += f"  Return: {stats_future['return']:+.2f}%\n"
    text += f"  Annual: {stats_future['annualized_return']:+.2f}%\n"
    text += f"  MaxDD: {stats_future['max_drawdown']:.2f}%\n"
    text += f"  Sharpe: {stats_future['sharpe']:.2f}\n"
    text += f"  Volatility: {stats_future['volatility']:.1f}%\n"
    text += f"  Trend Days: {stats_future['trend_days']}"

    ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#F8F9FA', edgecolor='#DEE2E6', alpha=0.9))


def generate_etf_chart(
    ts_code: str,
    name: str,
    score: float,
    rank: int,
    base_start: str,
    base_end: str,
    future_start: str,
    future_end: str,
    output_path: Path,
    score_type: str
):
    """生成单个ETF的完整图表"""

    # 读取数据
    data_file = DATA_DIR / f"{ts_code}.csv"
    if not data_file.exists():
        print(f"  [SKIP] 数据文件不存在: {ts_code}")
        return False

    df = pd.read_csv(data_file)
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('trade_date').sort_index()

    # 计算ADX
    df['adx'] = calculate_adx(df)

    # 分割基准期和未来期数据
    base_start_dt = pd.to_datetime(base_start)
    base_end_dt = pd.to_datetime(base_end)
    future_start_dt = pd.to_datetime(future_start)
    future_end_dt = pd.to_datetime(future_end)

    df_base = df[(df.index >= base_start_dt) & (df.index <= base_end_dt)].copy()
    df_future = df[(df.index >= future_start_dt) & (df.index <= future_end_dt)].copy()

    if df_base.empty and df_future.empty:
        print(f"  [SKIP] 无有效数据: {ts_code}")
        return False

    # 计算统计指标
    stats_base = calculate_stats(df_base)
    stats_future = calculate_stats(df_future)

    # 创建图表
    fig = plt.figure(figsize=(19.2, 10.8))  # 1920x1080

    # 使用GridSpec布局
    gs = gridspec.GridSpec(4, 3, height_ratios=[3, 1, 3, 1], width_ratios=[1, 1, 0.4],
                           hspace=0.3, wspace=0.15)

    # 基准期K线
    ax_kline_base = fig.add_subplot(gs[0, 0:2])
    plot_candlestick(ax_kline_base, df_base, f"Base Period ({base_start[:4]}-{base_end[:4]})")
    plot_moving_averages(ax_kline_base, df_base)

    # 基准期ADX
    ax_adx_base = fig.add_subplot(gs[1, 0:2])
    plot_adx(ax_adx_base, df_base)

    # 未来期K线
    ax_kline_future = fig.add_subplot(gs[2, 0:2])
    plot_candlestick(ax_kline_future, df_future, f"Future Period ({future_start[:4]}-{future_end[:4]})")
    plot_moving_averages(ax_kline_future, df_future)

    # 未来期ADX
    ax_adx_future = fig.add_subplot(gs[3, 0:2])
    plot_adx(ax_adx_future, df_future)

    # 统计面板
    ax_stats = fig.add_subplot(gs[:, 2])
    add_stats_panel(ax_stats, stats_base, stats_future, score, rank)

    # 总标题 - 使用ts_code代替中文名称
    fig.suptitle(
        f"{ts_code} - {score_type}\n"
        f"Base: {base_start} ~ {base_end}  |  Future: {future_start} ~ {future_end}",
        fontsize=12, fontweight='bold', y=0.98
    )

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='white')
    plt.close()

    return True


def parse_pool_info(csv_path: Path) -> Tuple[str, str, str]:
    """
    从CSV文件名解析分数类型和年份范围
    例如: single_adx_score_pool_2019_2021.csv -> ('single_adx_score', '2019', '2021')
    """
    filename = csv_path.stem

    # 匹配模式: xxx_pool_YYYY_YYYY
    match = re.match(r'(.+)_pool_(\d{4})_(\d{4})', filename)
    if match:
        score_type = match.group(1)
        start_year = match.group(2)
        end_year = match.group(3)
        return score_type, start_year, end_year

    return None, None, None


def get_future_period(base_end_year: str) -> Tuple[str, str]:
    """
    根据基准期结束年份计算未来2年周期
    例如: 2021 -> (2022, 2023), 2022 -> (2023, 2024)
    """
    end_year = int(base_end_year)
    future_start = str(end_year + 1)
    future_end = str(end_year + 2)
    return future_start, future_end


def process_pool_csv(csv_path: Path, pool_dir_name: str):
    """处理单个池子CSV文件，为Top20生成图表"""

    score_type, start_year, end_year = parse_pool_info(csv_path)
    if not score_type:
        print(f"  [SKIP] 无法解析文件名: {csv_path.name}")
        return

    # 读取CSV
    df = pd.read_csv(csv_path)

    # 取前20行（按CSV原顺序）
    top20 = df.head(20)

    if top20.empty:
        print(f"  [SKIP] CSV为空: {csv_path.name}")
        return

    # 确定时间范围
    base_start = f"{start_year}0101"
    base_end = f"{end_year}1231"
    future_start_year, future_end_year = get_future_period(end_year)
    future_start = f"{future_start_year}0101"
    future_end = f"{future_end_year}1231"

    # 创建输出目录
    output_subdir = OUTPUT_DIR / pool_dir_name / score_type
    output_subdir.mkdir(parents=True, exist_ok=True)

    print(f"\n处理: {score_type} ({start_year}-{end_year} -> {future_start_year}-{future_end_year})")
    print(f"  输出目录: {output_subdir}")

    success_count = 0
    for idx, row in top20.iterrows():
        ts_code = row['ts_code']
        name = row['name']
        score = row['final_score']
        rank = idx + 1

        output_path = output_subdir / f"rank{rank:02d}_{ts_code.replace('.', '_')}.png"

        print(f"  [{rank:02d}/20] {ts_code} {name}...", end=" ")

        if generate_etf_chart(
            ts_code=ts_code,
            name=name,
            score=score,
            rank=rank,
            base_start=base_start,
            base_end=base_end,
            future_start=future_start,
            future_end=future_end,
            output_path=output_path,
            score_type=score_type
        ):
            print("OK")
            success_count += 1
        else:
            print("SKIPPED")

    print(f"  完成: {success_count}/20")
    return success_count


def generate_summary_scatter(pool_dir: Path, pool_dir_name: str):
    """生成池子级别的汇总散点图（分数 vs 未来收益）"""

    print(f"\n生成汇总分析图: {pool_dir_name}")

    # 收集所有池子的数据
    csv_files = list(pool_dir.glob("single_*_pool_*.csv"))
    csv_files = [f for f in csv_files if "_all_scores" not in f.name]

    if not csv_files:
        print("  [SKIP] 无有效CSV文件")
        return

    summary_data = []

    for csv_path in csv_files:
        score_type, start_year, end_year = parse_pool_info(csv_path)
        if not score_type:
            continue

        df = pd.read_csv(csv_path).head(20)
        future_start_year, future_end_year = get_future_period(end_year)

        for idx, row in df.iterrows():
            ts_code = row['ts_code']
            score = row['final_score']

            # 读取价格数据计算未来收益
            data_file = DATA_DIR / f"{ts_code}.csv"
            if not data_file.exists():
                continue

            price_df = pd.read_csv(data_file)
            price_df['trade_date'] = pd.to_datetime(price_df['trade_date'], format='%Y%m%d')
            price_df = price_df.set_index('trade_date').sort_index()

            future_start = pd.to_datetime(f"{future_start_year}0101")
            future_end = pd.to_datetime(f"{future_end_year}1231")
            df_future = price_df[(price_df.index >= future_start) & (price_df.index <= future_end)]

            if len(df_future) < 10:
                continue

            # 计算未来收益
            future_return = (df_future['adj_close'].iloc[-1] / df_future['adj_close'].iloc[0] - 1) * 100

            summary_data.append({
                'score_type': score_type,
                'ts_code': ts_code,
                'score': score,
                'future_return': future_return,
                'rank': idx + 1
            })

    if not summary_data:
        print("  [SKIP] 无有效数据")
        return

    summary_df = pd.DataFrame(summary_data)

    # 按分数类型分组绘图
    score_types = summary_df['score_type'].unique()
    n_types = len(score_types)

    cols = min(3, n_types)
    rows = (n_types + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 5 * rows))
    if n_types == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for i, score_type in enumerate(score_types):
        ax = axes[i]
        data = summary_df[summary_df['score_type'] == score_type]

        # 绘制散点
        scatter = ax.scatter(data['score'], data['future_return'],
                            c=data['rank'], cmap='RdYlGn_r',
                            s=60, alpha=0.7, edgecolors='white', linewidth=0.5)

        # 添加趋势线
        z = np.polyfit(data['score'], data['future_return'], 1)
        p = np.poly1d(z)
        x_line = np.linspace(data['score'].min(), data['score'].max(), 100)
        ax.plot(x_line, p(x_line), 'r--', alpha=0.7, linewidth=1.5, label='Trend')

        # 计算相关系数
        corr = data['score'].corr(data['future_return'])

        ax.set_xlabel('Score', fontsize=10)
        ax.set_ylabel('Future Return (%)', fontsize=10)
        ax.set_title(f'{score_type}\nCorr: {corr:.3f}', fontsize=11, fontweight='bold')
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=8)

        plt.colorbar(scatter, ax=ax, label='排名')

    # 隐藏多余的子图
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(f'Score vs Future Return Analysis ({pool_dir_name})', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    # 保存
    output_path = OUTPUT_DIR / pool_dir_name / "summary_score_vs_future_return.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  保存: {output_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("ETF趋势可视化工具")
    print("=" * 60)

    # 处理 pool 目录 (2019-2021/2022 基准期)
    pool_dir = SELECTOR_SCORE_DIR / "pool"
    if pool_dir.exists():
        print(f"\n\n{'='*60}")
        print(f"处理目录: pool")
        print(f"{'='*60}")

        csv_files = list(pool_dir.glob("single_*_pool_*.csv"))
        csv_files = [f for f in csv_files if "_all_scores" not in f.name]

        for csv_path in csv_files:
            process_pool_csv(csv_path, "pool")

        generate_summary_scatter(pool_dir, "pool")

    # 处理 pool_2022_2023 目录
    pool_2022_2023_dir = SELECTOR_SCORE_DIR / "pool_2022_2023"
    if pool_2022_2023_dir.exists():
        print(f"\n\n{'='*60}")
        print(f"处理目录: pool_2022_2023")
        print(f"{'='*60}")

        csv_files = list(pool_2022_2023_dir.glob("single_*_pool_*.csv"))
        csv_files = [f for f in csv_files if "_all_scores" not in f.name]

        for csv_path in csv_files:
            process_pool_csv(csv_path, "pool_2022_2023")

        generate_summary_scatter(pool_2022_2023_dir, "pool_2022_2023")

    print(f"\n\n{'='*60}")
    print("全部完成!")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
