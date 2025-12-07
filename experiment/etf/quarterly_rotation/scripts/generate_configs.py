#!/usr/bin/env python3
"""
生成8个季度的ETF筛选配置文件

基于 pool_2022_2023/single_adx_score.json 模板，为每个季度生成评分配置。

季度安排:
- 2024Q1: 评分期 2022-01-01 ~ 2023-12-31
- 2024Q2: 评分期 2022-04-01 ~ 2024-03-31
- 2024Q3: 评分期 2022-07-01 ~ 2024-06-30
- 2024Q4: 评分期 2022-10-01 ~ 2024-09-30
- 2025Q1: 评分期 2023-01-01 ~ 2024-12-31
- 2025Q2: 评分期 2023-04-01 ~ 2025-03-31
- 2025Q3: 评分期 2023-07-01 ~ 2025-06-30
- 2025Q4: 评分期 2023-10-01 ~ 2025-09-30
"""

import json
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
EXPERIMENT_DIR = PROJECT_ROOT / "experiment" / "etf" / "quarterly_rotation"

# 模板文件路径
TEMPLATE_PATH = PROJECT_ROOT / "experiment" / "etf" / "selector_score" / "pool_2022_2023" / "single_adx_score.json"

# 输出目录
CONFIGS_DIR = EXPERIMENT_DIR / "configs"
POOLS_DIR = EXPERIMENT_DIR / "pools"


def get_quarter_schedule():
    """
    生成8个季度的时间安排

    Returns:
        list: 每个季度的配置字典
    """
    quarters = []

    # 定义8个季度
    quarter_defs = [
        ("2024Q1", "2024-01-01", "2024-03-31"),
        ("2024Q2", "2024-04-01", "2024-06-30"),
        ("2024Q3", "2024-07-01", "2024-09-30"),
        ("2024Q4", "2024-10-01", "2024-12-31"),
        ("2025Q1", "2025-01-01", "2025-03-31"),
        ("2025Q2", "2025-04-01", "2025-06-30"),
        ("2025Q3", "2025-07-01", "2025-09-30"),
        ("2025Q4", "2025-10-01", "2025-11-30"),  # 2个月
    ]

    for quarter_name, backtest_start, backtest_end in quarter_defs:
        # 评分期: 回测开始日期前2年
        backtest_start_dt = datetime.strptime(backtest_start, "%Y-%m-%d")
        scoring_start_dt = backtest_start_dt - relativedelta(years=2)
        scoring_end_dt = backtest_start_dt - relativedelta(days=1)

        quarters.append({
            "quarter": quarter_name,
            "scoring_start": scoring_start_dt.strftime("%Y%m%d"),
            "scoring_end": scoring_end_dt.strftime("%Y%m%d"),
            "backtest_start": backtest_start,
            "backtest_end": backtest_end,
        })

    return quarters


def generate_config(template: dict, quarter: dict) -> dict:
    """
    基于模板生成单个季度的配置

    Args:
        template: 模板配置
        quarter: 季度信息

    Returns:
        dict: 新配置
    """
    config = json.loads(json.dumps(template))  # 深拷贝

    # 修改时间范围
    config["time_range"]["start_date"] = quarter["scoring_start"]
    config["time_range"]["end_date"] = quarter["scoring_end"]

    # 修改输出路径
    pool_filename = f"{quarter['quarter']}_adx_pool.csv"
    config["paths"]["output_path"] = f"experiment/etf/quarterly_rotation/pools/{pool_filename}"

    # 更新描述
    config["description"] = f"ADX评分配置 - {quarter['quarter']} (评分期: {quarter['scoring_start']} ~ {quarter['scoring_end']})"

    return config


def main():
    """主函数"""
    # 确保目录存在
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    POOLS_DIR.mkdir(parents=True, exist_ok=True)

    # 读取模板
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_PATH}")

    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = json.load(f)

    # 获取季度安排
    quarters = get_quarter_schedule()

    print("=" * 60)
    print("季度轮动ETF池配置生成")
    print("=" * 60)
    print(f"模板文件: {TEMPLATE_PATH}")
    print(f"输出目录: {CONFIGS_DIR}")
    print("=" * 60)

    # 生成每个季度的配置
    for quarter in quarters:
        config = generate_config(template, quarter)

        # 保存配置
        config_filename = f"{quarter['quarter']}_adx_score.json"
        config_path = CONFIGS_DIR / config_filename

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        print(f"[{quarter['quarter']}] 评分期: {quarter['scoring_start']} ~ {quarter['scoring_end']}")
        print(f"         回测期: {quarter['backtest_start']} ~ {quarter['backtest_end']}")
        print(f"         配置文件: {config_path.name}")
        print()

    # 保存轮动表
    rotation_schedule = {}
    for quarter in quarters:
        rotation_schedule[quarter["quarter"]] = {
            "start": quarter["backtest_start"],
            "end": quarter["backtest_end"],
            "scoring_start": quarter["scoring_start"],
            "scoring_end": quarter["scoring_end"],
            "pool_file": f"pools/{quarter['quarter']}_adx_pool.csv",
            "config_file": f"configs/{quarter['quarter']}_adx_score.json",
            "etfs": []  # 将在生成池子后填充
        }

    schedule_path = EXPERIMENT_DIR / "pool_rotation_schedule.json"
    with open(schedule_path, 'w', encoding='utf-8') as f:
        json.dump(rotation_schedule, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"生成完成！共 {len(quarters)} 个季度配置")
    print(f"轮动表: {schedule_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
