#!/usr/bin/env python
"""监控回测完成进度"""
import time
from pathlib import Path
from datetime import datetime
from backtest_config import RESULTS_DIR

def check_completion():
    """检查完成情况"""
    summary_dirs = list(RESULTS_DIR.glob("*/summary/"))
    completed_pools = [d.parent.name for d in summary_dirs]
    return len(completed_pools), sorted(completed_pools)

def main():
    print("开始监控回测进度...")
    print("="*60)

    total_pools = 11
    last_count = 0

    while True:
        count, completed = check_completion()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if count != last_count:
            print(f"{timestamp} - 已完成 {count}/{total_pools} 个池子")
            if completed:
                print(f"  已完成: {', '.join(completed[:3])}" + ("..." if len(completed) > 3 else ""))
            last_count = count

        if count >= total_pools:
            print("\n" + "="*60)
            print("所有回测已完成！")
            print("="*60)
            for i, pool in enumerate(completed, 1):
                print(f"  {i:2d}. {pool}")
            break

        time.sleep(60)  # 每60秒检查一次

if __name__ == "__main__":
    main()
