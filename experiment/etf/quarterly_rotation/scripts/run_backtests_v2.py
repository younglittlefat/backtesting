#!/usr/bin/env python3
"""
v2版本：分季度独立回测

核心改进：
1. 轮动组：每个季度独立回测，只使用该季度池子的ETF
2. 固定组：完整时间段一次性回测（复用v1结果或重新运行）
3. 避免前视偏差：每季度回测时只能交易该季度的20只ETF

执行流程：
- 轮动组：8次独立回测（每季度一次）
- 固定组：1次完整回测
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

# 季度定义
QUARTERS = {
    "2024Q1": {"start": "2024-01-01", "end": "2024-03-31"},
    "2024Q2": {"start": "2024-04-01", "end": "2024-06-30"},
    "2024Q3": {"start": "2024-07-01", "end": "2024-09-30"},
    "2024Q4": {"start": "2024-10-01", "end": "2024-12-31"},
    "2025Q1": {"start": "2025-01-01", "end": "2025-03-31"},
    "2025Q2": {"start": "2025-04-01", "end": "2025-06-30"},
    "2025Q3": {"start": "2025-07-01", "end": "2025-09-30"},
    "2025Q4": {"start": "2025-10-01", "end": "2025-11-30"},
}

# 输出目录
ROTATION_V2_DIR = EXPERIMENT_DIR / "results" / "rotation_v2"
STATIC_RESULTS_DIR = EXPERIMENT_DIR / "results" / "static"
COMPARISON_V2_DIR = EXPERIMENT_DIR / "results" / "comparison_v2"


def build_backtest_command(
    stock_list_path: Path,
    output_dir: Path,
    start_date: str,
    end_date: str
) -> list:
    """
    构建回测命令

    Args:
        stock_list_path: 标的列表文件路径
        output_dir: 输出目录
        start_date: 回测开始日期
        end_date: 回测结束日期

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
        "--start-date", start_date,
        "--end-date", end_date,
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


def run_backtest(
    name: str,
    stock_list_path: Path,
    output_dir: Path,
    start_date: str,
    end_date: str
) -> bool:
    """
    运行单次回测

    Args:
        name: 回测名称
        stock_list_path: 标的列表文件路径
        output_dir: 输出目录
        start_date: 回测开始日期
        end_date: 回测结束日期

    Returns:
        bool: 是否成功
    """
    print(f"\n{'='*60}")
    print(f"[{name}] 开始回测")
    print(f"{'='*60}")
    print(f"标的列表: {stock_list_path}")
    print(f"输出目录: {output_dir}")
    print(f"回测期间: {start_date} ~ {end_date}")

    # 读取标的数量
    try:
        df = pd.read_csv(stock_list_path, encoding='utf-8-sig')
        print(f"标的数量: {len(df)}")
    except Exception as e:
        print(f"警告: 无法读取标的列表 - {e}")

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建命令
    cmd = build_backtest_command(stock_list_path, output_dir, start_date, end_date)
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
    if len(output_lines) > 10:
        print("\n输出摘要（最后10行）:")
        for line in output_lines[-10:]:
            print(f"  {line}")
    else:
        print(f"\n输出:\n{result.stdout}")

    return True


def run_rotation_backtests():
    """
    运行轮动组的分季度回测

    每个季度独立回测，使用该季度的池子
    """
    print("\n" + "=" * 70)
    print("轮动组 v2 回测：分季度独立回测")
    print("=" * 70)

    # 加载轮动表
    schedule_path = EXPERIMENT_DIR / "pool_rotation_schedule.json"
    if not schedule_path.exists():
        raise FileNotFoundError(f"轮动表不存在: {schedule_path}\n请先运行 generate_pools.py")

    with open(schedule_path, 'r', encoding='utf-8') as f:
        schedule = json.load(f)

    results = {}

    for quarter, dates in QUARTERS.items():
        print(f"\n{'='*60}")
        print(f"季度: {quarter}")
        print(f"{'='*60}")

        # 获取该季度的池子文件
        pool_info = schedule.get(quarter, {})
        pool_file = pool_info.get("pool_file", "")

        if not pool_file:
            raise ValueError(f"轮动表中缺少 {quarter} 的池子信息")

        pool_path = EXPERIMENT_DIR / pool_file
        if not pool_path.exists():
            raise FileNotFoundError(f"池子文件不存在: {pool_path}")

        # 该季度的输出目录
        quarter_output_dir = ROTATION_V2_DIR / quarter

        # 运行该季度的回测
        try:
            run_backtest(
                name=f"轮动组-{quarter}",
                stock_list_path=pool_path,
                output_dir=quarter_output_dir,
                start_date=dates["start"],
                end_date=dates["end"]
            )
            results[quarter] = {
                "status": "success",
                "pool_file": str(pool_path),
                "output_dir": str(quarter_output_dir),
                "start_date": dates["start"],
                "end_date": dates["end"],
            }
        except Exception as e:
            print(f"错误: {quarter} 回测失败 - {e}")
            results[quarter] = {
                "status": "failed",
                "error": str(e),
            }
            raise  # 不做妥协，直接抛出

    return results


def run_static_backtest(force_rerun: bool = False):
    """
    运行固定组回测

    固定组使用完整时间段，只需运行一次
    如果已有结果且不强制重跑，则跳过

    Args:
        force_rerun: 是否强制重新运行
    """
    print("\n" + "=" * 70)
    print("固定组回测：完整时间段")
    print("=" * 70)

    # 检查是否已有结果
    summary_pattern = STATIC_RESULTS_DIR / "summary" / "backtest_summary_*.csv"
    existing_summaries = list(STATIC_RESULTS_DIR.glob("summary/backtest_summary_*.csv"))

    if existing_summaries and not force_rerun:
        print(f"发现已有结果: {len(existing_summaries)} 个汇总文件")
        print("跳过固定组回测（使用已有结果）")
        print("如需重新运行，请设置 force_rerun=True")
        return {"status": "skipped", "reason": "existing_results"}

    # 固定组池子路径
    static_pool_path = (
        PROJECT_ROOT / "experiment" / "etf" / "selector_score" /
        "pool_2022_2023" / "single_adx_score_pool_2022_2023.csv"
    )

    if not static_pool_path.exists():
        raise FileNotFoundError(f"固定池子不存在: {static_pool_path}")

    # 完整回测时间段
    start_date = "2024-01-01"
    end_date = "2025-11-30"

    run_backtest(
        name="固定组",
        stock_list_path=static_pool_path,
        output_dir=STATIC_RESULTS_DIR,
        start_date=start_date,
        end_date=end_date
    )

    return {
        "status": "success",
        "pool_file": str(static_pool_path),
        "output_dir": str(STATIC_RESULTS_DIR),
        "start_date": start_date,
        "end_date": end_date,
    }


def save_metadata(rotation_results: dict, static_result: dict):
    """保存实验元数据"""
    COMPARISON_V2_DIR.mkdir(parents=True, exist_ok=True)

    metadata = {
        "version": "v2",
        "timestamp": datetime.now().isoformat(),
        "description": "分季度独立回测，避免前视偏差",
        "strategy_config": STRATEGY_CONFIG,
        "quarters": QUARTERS,
        "rotation_results": rotation_results,
        "static_result": static_result,
    }

    metadata_path = COMPARISON_V2_DIR / "metadata_v2.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n元数据已保存: {metadata_path}")


def main():
    """主函数"""
    print("=" * 70)
    print("季度轮动ETF池实验 v2")
    print("分季度独立回测 - 避免前视偏差")
    print("=" * 70)
    print(f"策略: {STRATEGY_CONFIG['strategy']}")
    print(f"季度数: {len(QUARTERS)}")
    print("=" * 70)

    # 运行轮动组分季度回测
    rotation_results = run_rotation_backtests()

    # 运行固定组回测（如果已有结果则跳过）
    static_result = run_static_backtest(force_rerun=False)

    # 保存元数据
    save_metadata(rotation_results, static_result)

    print("\n" + "=" * 70)
    print("所有回测完成！")
    print("=" * 70)
    print(f"\n轮动组结果: {ROTATION_V2_DIR}")
    print(f"固定组结果: {STATIC_RESULTS_DIR}")
    print(f"对比结果: {COMPARISON_V2_DIR}")
    print("\n下一步: 运行 analyze_results_v2.py 进行结果分析")


if __name__ == "__main__":
    main()
