#!/usr/bin/env python
"""运行所有2022-2023评分池子的牛市回测"""
import subprocess
import sys
from pathlib import Path
from backtest_config import (
    get_pool_files, DATA_DIR, RESULTS_DIR,
    START_DATE, END_DATE, STRATEGY, PROJECT_ROOT
)

def run_single_pool_backtest(pool_name: str, pool_file: Path):
    """运行单个池子的回测"""
    output_dir = RESULTS_DIR / pool_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # 使用项目的run_backtest.sh脚本
    run_backtest_sh = PROJECT_ROOT / "run_backtest.sh"

    cmd = [
        str(run_backtest_sh),
        "--stock-list", str(pool_file),
        "-t", STRATEGY,
        "--data-dir", str(DATA_DIR),
        "--output-dir", str(output_dir),
        "--start-date", START_DATE,
        "--end-date", END_DATE,
    ]

    print(f"\n{'='*60}")
    print(f"回测池子: {pool_name}")
    print(f"池子文件: {pool_file}")
    print(f"输出目录: {output_dir}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0

def main():
    pools = get_pool_files()
    print(f"发现 {len(pools)} 个池子待回测")
    print(f"回测期间: {START_DATE} 至 {END_DATE}")
    print(f"策略: {STRATEGY}")
    print(f"数据目录: {DATA_DIR}")
    print(f"结果目录: {RESULTS_DIR}")

    results = {}
    for name, path in sorted(pools.items()):
        success = run_single_pool_backtest(name, path)
        results[name] = "✓" if success else "✗"

    print("\n" + "="*60)
    print("回测完成汇总:")
    for name, status in results.items():
        print(f"  {status} {name}")

    success_count = sum(1 for s in results.values() if s == "✓")
    print(f"\n成功: {success_count}/{len(results)}")

if __name__ == "__main__":
    main()
