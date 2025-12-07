#!/usr/bin/env python3
"""
生成8个季度的ETF池子

调用 etf_selector 模块，根据每个季度的配置文件生成 ETF 池子。
同时更新 pool_rotation_schedule.json 中的 ETF 列表。
"""

import json
import subprocess
import sys
from pathlib import Path
import pandas as pd


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
EXPERIMENT_DIR = PROJECT_ROOT / "experiment" / "etf" / "quarterly_rotation"

# 目录
CONFIGS_DIR = EXPERIMENT_DIR / "configs"
POOLS_DIR = EXPERIMENT_DIR / "pools"
SCHEDULE_PATH = EXPERIMENT_DIR / "pool_rotation_schedule.json"

# Python 解释器路径
PYTHON_PATH = "/home/zijunliu/miniforge3/envs/backtesting/bin/python"


def run_etf_selector(config_path: Path) -> bool:
    """
    运行 ETF 选择器生成池子

    Args:
        config_path: 配置文件路径

    Returns:
        bool: 是否成功
    """
    cmd = [
        PYTHON_PATH,
        "-m", "etf_selector.main",
        "--config", str(config_path)
    ]

    print(f"  执行命令: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  错误: {result.stderr}")
        raise RuntimeError(f"ETF选择器执行失败: {config_path}")

    print(f"  完成")
    return True


def read_pool_etfs(pool_path: Path) -> list:
    """
    读取池子中的ETF列表

    Args:
        pool_path: 池子CSV文件路径

    Returns:
        list: ETF代码列表
    """
    if not pool_path.exists():
        raise FileNotFoundError(f"池子文件不存在: {pool_path}")

    df = pd.read_csv(pool_path, encoding='utf-8-sig')
    if 'ts_code' not in df.columns:
        raise ValueError(f"池子文件缺少ts_code列: {pool_path}")

    return df['ts_code'].dropna().unique().tolist()


def analyze_pool_changes(schedule: dict) -> dict:
    """
    分析池子变化情况

    Args:
        schedule: 轮动表

    Returns:
        dict: 变化统计
    """
    quarters = list(schedule.keys())
    changes = {}

    for i, quarter in enumerate(quarters):
        current_etfs = set(schedule[quarter]["etfs"])

        if i == 0:
            changes[quarter] = {
                "new_count": len(current_etfs),
                "removed_count": 0,
                "overlap_count": 0,
                "new_etfs": list(current_etfs),
                "removed_etfs": [],
                "overlap_ratio": 0.0
            }
        else:
            prev_quarter = quarters[i - 1]
            prev_etfs = set(schedule[prev_quarter]["etfs"])

            new_etfs = current_etfs - prev_etfs
            removed_etfs = prev_etfs - current_etfs
            overlap = current_etfs & prev_etfs

            overlap_ratio = len(overlap) / len(prev_etfs) if prev_etfs else 0.0

            changes[quarter] = {
                "new_count": len(new_etfs),
                "removed_count": len(removed_etfs),
                "overlap_count": len(overlap),
                "new_etfs": list(new_etfs),
                "removed_etfs": list(removed_etfs),
                "overlap_ratio": round(overlap_ratio, 4)
            }

    return changes


def main():
    """主函数"""
    print("=" * 60)
    print("季度轮动ETF池生成")
    print("=" * 60)

    # 检查配置文件目录
    if not CONFIGS_DIR.exists():
        raise FileNotFoundError(f"配置目录不存在: {CONFIGS_DIR}")

    # 读取轮动表
    if not SCHEDULE_PATH.exists():
        raise FileNotFoundError(f"轮动表不存在: {SCHEDULE_PATH}")

    with open(SCHEDULE_PATH, 'r', encoding='utf-8') as f:
        schedule = json.load(f)

    # 获取所有季度的配置文件
    config_files = sorted(CONFIGS_DIR.glob("*_adx_score.json"))

    if len(config_files) == 0:
        raise FileNotFoundError(f"未找到配置文件: {CONFIGS_DIR}/*_adx_score.json")

    print(f"找到 {len(config_files)} 个配置文件")
    print("=" * 60)

    # 逐个生成池子
    for config_path in config_files:
        quarter = config_path.stem.replace("_adx_score", "")
        print(f"\n[{quarter}] 生成池子...")

        # 运行 ETF 选择器
        run_etf_selector(config_path)

        # 读取生成的池子
        pool_filename = f"{quarter}_adx_pool.csv"
        pool_path = POOLS_DIR / pool_filename

        etfs = read_pool_etfs(pool_path)
        print(f"  池子大小: {len(etfs)} 只ETF")

        # 更新轮动表
        if quarter in schedule:
            schedule[quarter]["etfs"] = etfs

    # 分析池子变化
    print("\n" + "=" * 60)
    print("池子变化分析")
    print("=" * 60)

    changes = analyze_pool_changes(schedule)

    for quarter, change in changes.items():
        print(f"\n[{quarter}]")
        print(f"  池子大小: {len(schedule[quarter]['etfs'])} 只")
        print(f"  新增: {change['new_count']} 只")
        print(f"  移除: {change['removed_count']} 只")
        print(f"  重叠: {change['overlap_count']} 只 ({change['overlap_ratio']*100:.1f}%)")

    # 保存更新后的轮动表
    with open(SCHEDULE_PATH, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

    # 保存池子变化统计
    changes_path = EXPERIMENT_DIR / "pool_changes.json"
    with open(changes_path, 'w', encoding='utf-8') as f:
        json.dump(changes, f, ensure_ascii=False, indent=2)

    # 收集所有出现过的ETF（全量标的集合）
    all_etfs = set()
    for quarter_data in schedule.values():
        all_etfs.update(quarter_data["etfs"])

    print("\n" + "=" * 60)
    print(f"全量标的集合: {len(all_etfs)} 只ETF")
    print("=" * 60)

    # 保存全量标的列表
    all_etfs_df = pd.DataFrame({"ts_code": sorted(all_etfs)})
    all_etfs_path = EXPERIMENT_DIR / "all_rotation_etfs.csv"
    all_etfs_df.to_csv(all_etfs_path, index=False, encoding='utf-8-sig')
    print(f"全量标的列表: {all_etfs_path}")

    print("\n生成完成！")


if __name__ == "__main__":
    main()
