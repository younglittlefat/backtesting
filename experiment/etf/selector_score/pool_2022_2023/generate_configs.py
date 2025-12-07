#!/usr/bin/env python
"""批量生成2022-2023评分配置文件"""
import json
from pathlib import Path

# 源配置目录和目标配置目录
SOURCE_DIR = Path("/mnt/d/git/backtesting/experiment/etf/selector_score/pool")
TARGET_DIR = Path("/mnt/d/git/backtesting/experiment/etf/selector_score/pool_2022_2023")

# 需要修改的配置文件列表
CONFIG_FILES = [
    "single_adx_score.json",
    "single_liquidity_score.json",
    "single_momentum_12m.json",
    "single_momentum_3m.json",
    "single_price_efficiency.json",
    "single_trend_consistency.json",
    "single_trend_quality.json",
    "single_volume.json",
    "single_core_trend_excess_return_20d.json",
    "single_core_trend_excess_return_60d.json",
    "single_idr.json",
]

def modify_config(config_data: dict, filename: str) -> dict:
    """修改配置文件的时间范围和输出路径"""
    # 修改时间范围
    config_data["time_range"] = {
        "start_date": "20220101",
        "end_date": "20231231"
    }

    # 修改输出路径
    old_output = config_data["paths"]["output_path"]
    # 替换pool/为pool_2022_2023/，并更新所有可能的时间戳格式
    new_output = old_output.replace("pool/", "pool_2022_2023/")
    new_output = new_output.replace("_2019_2021", "_2022_2023")
    new_output = new_output.replace("_2019_2022", "_2022_2023")
    config_data["paths"]["output_path"] = new_output

    return config_data

def main():
    print(f"源目录: {SOURCE_DIR}")
    print(f"目标目录: {TARGET_DIR}")
    print(f"共需处理 {len(CONFIG_FILES)} 个配置文件\n")

    success_count = 0
    for filename in CONFIG_FILES:
        source_file = SOURCE_DIR / filename
        target_file = TARGET_DIR / filename

        if not source_file.exists():
            print(f"✗ 源文件不存在: {filename}")
            continue

        # 读取原始配置
        with open(source_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 修改配置
        modified_config = modify_config(config, filename)

        # 保存到目标目录
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(modified_config, f, indent=2, ensure_ascii=False)

        print(f"✓ 已生成: {filename}")
        print(f"  时间范围: 2022-01-01 至 2023-12-31")
        print(f"  输出路径: {modified_config['paths']['output_path']}\n")
        success_count += 1

    print(f"\n{'='*60}")
    print(f"配置文件生成完成: {success_count}/{len(CONFIG_FILES)}")

if __name__ == "__main__":
    main()
