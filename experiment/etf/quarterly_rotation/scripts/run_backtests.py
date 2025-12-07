#!/usr/bin/env python3
"""
运行季度轮动回测

对两组进行回测：
1. 轮动组：使用全量标的（所有曾出现在任一季度池子中的ETF）
2. 固定组：使用固定池子（2022-2023评分的ADX池子）

策略配置来自 POOL_COMPARISON_PLAN.md 的 4.1 节：
- kama_cross 策略
- enable_adx_filter, enable_atr_stop, enable_slope_confirmation
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
EXPERIMENT_DIR = PROJECT_ROOT / "experiment" / "etf" / "quarterly_rotation"

# Python 解释器路径
PYTHON_PATH = "/home/zijunliu/miniforge3/envs/backtesting/bin/python"

# 策略配置（来自 POOL_COMPARISON_PLAN.md 4.1节）
STRATEGY_CONFIG = {
    'strategy': 'kama_cross',
    'kama_period': 20,
    'kama_fast': 2,
    'kama_slow': 30,
    'enable_adx_filter': True,
    'adx_period': 14,
    'adx_threshold': 25.0,
    'enable_atr_stop': True,
    'atr_period': 14,
    'atr_multiplier': 2.5,
    'enable_slope_confirmation': True,
    'min_slope_periods': 3,
}

# 回测时间范围
BACKTEST_START = "2024-01-01"
BACKTEST_END = "2025-11-30"

# 输出目录
ROTATION_RESULTS_DIR = EXPERIMENT_DIR / "results" / "rotation"
STATIC_RESULTS_DIR = EXPERIMENT_DIR / "results" / "static"


def build_backtest_command(stock_list_path: Path, output_dir: Path) -> list:
    """
    构建回测命令

    Args:
        stock_list_path: 标的列表文件路径
        output_dir: 输出目录

    Returns:
        list: 命令参数列表
    """
    cmd = [
        PYTHON_PATH,
        str(PROJECT_ROOT / "backtest_runner" / "cli.py"),
        "--stock-list", str(stock_list_path),
        "--strategy", STRATEGY_CONFIG['strategy'],
        "--data-dir", "data/chinese_etf/daily",
        "--output-dir", str(output_dir),
        "--cost-model", "cn_etf",
        "--start-date", BACKTEST_START,
        "--end-date", BACKTEST_END,
        # KAMA 参数
        "--kama-period", str(STRATEGY_CONFIG['kama_period']),
        "--kama-fast", str(STRATEGY_CONFIG['kama_fast']),
        "--kama-slow", str(STRATEGY_CONFIG['kama_slow']),
        # 过滤器参数
        "--enable-adx-filter",
        "--adx-period", str(STRATEGY_CONFIG['adx_period']),
        "--adx-threshold", str(STRATEGY_CONFIG['adx_threshold']),
        "--enable-atr-stop",
        "--atr-period", str(STRATEGY_CONFIG['atr_period']),
        "--atr-multiplier", str(STRATEGY_CONFIG['atr_multiplier']),
        "--enable-slope-confirmation",
        "--min-slope-periods", str(STRATEGY_CONFIG['min_slope_periods']),
    ]

    return cmd


def run_backtest(name: str, stock_list_path: Path, output_dir: Path) -> bool:
    """
    运行单次回测

    Args:
        name: 回测名称
        stock_list_path: 标的列表文件路径
        output_dir: 输出目录

    Returns:
        bool: 是否成功
    """
    print(f"\n{'='*60}")
    print(f"[{name}] 开始回测")
    print(f"{'='*60}")
    print(f"标的列表: {stock_list_path}")
    print(f"输出目录: {output_dir}")
    print(f"回测期间: {BACKTEST_START} ~ {BACKTEST_END}")

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建命令
    cmd = build_backtest_command(stock_list_path, output_dir)
    print(f"\n执行命令: {' '.join(cmd[:10])}...")

    # 运行回测
    start_time = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    elapsed = (datetime.now() - start_time).total_seconds()

    if result.returncode != 0:
        print(f"\n错误输出:\n{result.stderr}")
        raise RuntimeError(f"回测失败: {name}")

    print(f"\n回测完成！耗时: {elapsed:.1f}秒")

    # 显示部分输出
    output_lines = result.stdout.strip().split('\n')
    if len(output_lines) > 20:
        print("\n输出摘要（最后20行）:")
        for line in output_lines[-20:]:
            print(f"  {line}")
    else:
        print(f"\n输出:\n{result.stdout}")

    return True


def main():
    """主函数"""
    print("=" * 60)
    print("季度轮动ETF池回测")
    print("=" * 60)
    print(f"策略: {STRATEGY_CONFIG['strategy']}")
    print(f"回测期间: {BACKTEST_START} ~ {BACKTEST_END}")
    print("=" * 60)

    # 检查必要文件
    all_etfs_path = EXPERIMENT_DIR / "all_rotation_etfs.csv"
    static_pool_path = PROJECT_ROOT / "experiment" / "etf" / "selector_score" / "pool_2022_2023" / "single_adx_score_pool_2022_2023.csv"

    if not all_etfs_path.exists():
        raise FileNotFoundError(f"全量标的列表不存在: {all_etfs_path}\n请先运行 generate_pools.py")

    if not static_pool_path.exists():
        raise FileNotFoundError(f"固定池子不存在: {static_pool_path}")

    # 读取标的数量
    rotation_etfs = pd.read_csv(all_etfs_path)
    static_etfs = pd.read_csv(static_pool_path, encoding='utf-8-sig')

    print(f"\n轮动组标的数: {len(rotation_etfs)}")
    print(f"固定组标的数: {len(static_etfs)}")

    # 运行轮动组回测
    run_backtest(
        name="轮动组",
        stock_list_path=all_etfs_path,
        output_dir=ROTATION_RESULTS_DIR
    )

    # 运行固定组回测
    run_backtest(
        name="固定组",
        stock_list_path=static_pool_path,
        output_dir=STATIC_RESULTS_DIR
    )

    # 保存元数据
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "backtest_start": BACKTEST_START,
        "backtest_end": BACKTEST_END,
        "strategy_config": STRATEGY_CONFIG,
        "rotation_etf_count": len(rotation_etfs),
        "static_etf_count": len(static_etfs),
        "rotation_stock_list": str(all_etfs_path),
        "static_stock_list": str(static_pool_path),
    }

    metadata_path = EXPERIMENT_DIR / "results" / "comparison" / "metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("所有回测完成！")
    print(f"元数据: {metadata_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
