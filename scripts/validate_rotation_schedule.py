#!/usr/bin/env python3
"""
轮动表验证脚本

对生成的轮动表进行全面的质量检查和统计分析，确保数据合理性。

验证项目：
1. 文件完整性：JSON格式、必需字段
2. 数据合理性：日期顺序、池子大小、ETF代码格式
3. 统计分析：换手率分布、稳定性分析
4. 可视化：轮动热力图、换手率趋势

使用示例：
    python scripts/validate_rotation_schedule.py results/rotation_schedules/rotation_30d.json
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


def load_schedule(file_path: Path) -> Dict:
    """加载轮动表JSON文件

    Args:
        file_path: JSON文件路径

    Returns:
        轮动表数据字典

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON格式错误
    """
    if not file_path.exists():
        raise FileNotFoundError(f"轮动表文件不存在: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def validate_structure(data: Dict) -> Tuple[bool, List[str]]:
    """验证JSON结构完整性

    Args:
        data: 轮动表数据

    Returns:
        (是否通过, 错误列表)
    """
    errors = []

    # 检查必需字段
    required_keys = ['metadata', 'schedule', 'statistics']
    for key in required_keys:
        if key not in data:
            errors.append(f"缺少必需字段: {key}")

    # 检查metadata字段
    if 'metadata' in data:
        meta = data['metadata']
        meta_required = ['rotation_period', 'pool_size', 'start_date', 'end_date', 'total_rotations']
        for key in meta_required:
            if key not in meta:
                errors.append(f"metadata缺少字段: {key}")

    # 检查schedule非空
    if 'schedule' in data and len(data['schedule']) == 0:
        errors.append("schedule为空")

    return len(errors) == 0, errors


def validate_dates(schedule: Dict[str, List[str]], rotation_period: int) -> Tuple[bool, List[str]]:
    """验证日期序列合理性

    Args:
        schedule: 轮动时间表
        rotation_period: 轮动周期（天）

    Returns:
        (是否通过, 错误列表)
    """
    errors = []
    dates = sorted(schedule.keys())

    # 检查日期格式
    for date_str in dates:
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            errors.append(f"日期格式错误: {date_str}")

    # 检查日期间隔（允许±2天误差，因为可能遇到周末/节假日）
    for i in range(1, len(dates)):
        prev_date = datetime.strptime(dates[i-1], '%Y-%m-%d')
        curr_date = datetime.strptime(dates[i], '%Y-%m-%d')
        delta = (curr_date - prev_date).days

        if abs(delta - rotation_period) > 2:
            errors.append(f"日期间隔异常: {dates[i-1]} → {dates[i]} (间隔{delta}天，预期{rotation_period}天)")

    return len(errors) == 0, errors


def validate_etf_codes(schedule: Dict[str, List[str]], pool_size: int) -> Tuple[bool, List[str]]:
    """验证ETF代码合理性

    Args:
        schedule: 轮动时间表
        pool_size: 目标池子大小

    Returns:
        (是否通过, 错误列表)
    """
    errors = []

    for date, codes in schedule.items():
        # 检查池子大小（允许比目标少1-2只，因为可能退市）
        if len(codes) < pool_size - 2:
            errors.append(f"{date}: 池子过小 ({len(codes)}只，预期{pool_size}只)")

        # 检查代码格式（应为XXXXXX.SZ或XXXXXX.SH）
        for code in codes:
            if not (code.endswith('.SZ') or code.endswith('.SH')):
                errors.append(f"{date}: ETF代码格式错误 ({code})")

        # 检查重复
        if len(codes) != len(set(codes)):
            duplicates = [code for code in codes if codes.count(code) > 1]
            errors.append(f"{date}: 存在重复代码 ({set(duplicates)})")

    return len(errors) == 0, errors


def analyze_statistics(schedule: Dict[str, List[str]]) -> Dict:
    """深入统计分析

    Args:
        schedule: 轮动时间表

    Returns:
        统计结果字典
    """
    dates = sorted(schedule.keys())

    # 换手率序列
    turnover_rates = []
    for i in range(1, len(dates)):
        old_set = set(schedule[dates[i-1]])
        new_set = set(schedule[dates[i]])
        turnover = len(old_set ^ new_set) / (2 * len(old_set))
        turnover_rates.append(turnover)

    # ETF出现频率
    all_etfs = []
    for codes in schedule.values():
        all_etfs.extend(codes)
    etf_counter = Counter(all_etfs)

    # 稳定性分层
    total_rotations = len(dates)
    stability_tiers = {
        '核心池 (>=80%)': [code for code, cnt in etf_counter.items() if cnt >= total_rotations * 0.8],
        '稳定池 (50-80%)': [code for code, cnt in etf_counter.items() if total_rotations * 0.5 <= cnt < total_rotations * 0.8],
        '轮换池 (20-50%)': [code for code, cnt in etf_counter.items() if total_rotations * 0.2 <= cnt < total_rotations * 0.5],
        '边缘池 (<20%)': [code for code, cnt in etf_counter.items() if cnt < total_rotations * 0.2]
    }

    return {
        'turnover_rates': turnover_rates,
        'turnover_mean': sum(turnover_rates) / len(turnover_rates),
        'turnover_std': (sum((x - sum(turnover_rates)/len(turnover_rates))**2 for x in turnover_rates) / len(turnover_rates)) ** 0.5,
        'turnover_min': min(turnover_rates),
        'turnover_max': max(turnover_rates),
        'unique_etfs': len(etf_counter),
        'etf_appearances': dict(etf_counter.most_common(10)),
        'stability_tiers': {k: len(v) for k, v in stability_tiers.items()},
        'stability_tier_details': stability_tiers
    }


def print_validation_report(
    file_path: Path,
    data: Dict,
    structure_ok: bool,
    structure_errors: List[str],
    date_ok: bool,
    date_errors: List[str],
    code_ok: bool,
    code_errors: List[str],
    stats: Dict
):
    """打印验收报告

    Args:
        file_path: 文件路径
        data: 轮动表数据
        structure_ok: 结构验证结果
        structure_errors: 结构错误列表
        date_ok: 日期验证结果
        date_errors: 日期错误列表
        code_ok: 代码验证结果
        code_errors: 代码错误列表
        stats: 统计结果
    """
    print("=" * 80)
    print(f" 轮动表验收报告")
    print("=" * 80)
    print(f"\n📁 文件: {file_path}")
    print(f"📅 生成时间: {data['metadata'].get('generated_at', 'N/A')}")

    # 基本信息
    meta = data['metadata']
    print(f"\n📊 基本信息:")
    print(f"  轮动周期: {meta['rotation_period']} 天")
    print(f"  池子大小: {meta['pool_size']} 只")
    print(f"  回测区间: {meta['start_date']} 至 {meta['end_date']}")
    print(f"  轮动次数: {meta['total_rotations']} 次")

    # 验证结果
    print(f"\n✅ 验证结果:")
    print(f"  结构完整性: {'✅ 通过' if structure_ok else '❌ 失败'}")
    print(f"  日期合理性: {'✅ 通过' if date_ok else '❌ 失败'}")
    print(f"  代码格式: {'✅ 通过' if code_ok else '❌ 失败'}")

    # 错误详情
    if not (structure_ok and date_ok and code_ok):
        print(f"\n❌ 错误详情:")
        for error in structure_errors + date_errors + code_errors:
            print(f"  - {error}")

    # 统计分析
    print(f"\n📈 统计分析:")
    print(f"  唯一ETF数量: {stats['unique_etfs']} 只")
    print(f"  平均换手率: {stats['turnover_mean']:.2%} (±{stats['turnover_std']:.2%})")
    print(f"  换手率范围: {stats['turnover_min']:.2%} - {stats['turnover_max']:.2%}")

    print(f"\n🏆 出现次数Top 5:")
    for i, (code, cnt) in enumerate(list(stats['etf_appearances'].items())[:5], 1):
        pct = cnt / meta['total_rotations']
        print(f"  {i}. {code}: {cnt}/{meta['total_rotations']} 次 ({pct:.0%})")

    print(f"\n🎯 稳定性分层:")
    for tier, count in stats['stability_tiers'].items():
        print(f"  {tier}: {count} 只")
        if count > 0 and count <= 5:
            # 显示具体代码（如果数量不多）
            codes = stats['stability_tier_details'][tier][:5]
            print(f"    {', '.join(codes)}")

    # 健康度评分
    print(f"\n🎓 健康度评估:")
    health_score = 0
    health_items = []

    # 1. 换手率合理性（10-40%为佳）
    if 0.10 <= stats['turnover_mean'] <= 0.40:
        health_score += 25
        health_items.append("✅ 换手率适中")
    else:
        health_items.append(f"⚠️  换手率{'过高' if stats['turnover_mean'] > 0.40 else '过低'}")

    # 2. 稳定性（核心池应占10-30%）
    core_pct = stats['stability_tiers']['核心池 (>=80%)'] / stats['unique_etfs']
    if 0.10 <= core_pct <= 0.30:
        health_score += 25
        health_items.append("✅ 核心池比例合理")
    else:
        health_items.append(f"⚠️  核心池比例{'过高' if core_pct > 0.30 else '过低'}")

    # 3. 多样性（唯一ETF应>池子大小的2倍）
    if stats['unique_etfs'] >= meta['pool_size'] * 2:
        health_score += 25
        health_items.append("✅ ETF多样性充足")
    else:
        health_items.append("⚠️  ETF多样性不足")

    # 4. 验证通过
    if structure_ok and date_ok and code_ok:
        health_score += 25
        health_items.append("✅ 数据质量验证通过")
    else:
        health_items.append("❌ 数据质量验证失败")

    print(f"  总分: {health_score}/100")
    for item in health_items:
        print(f"  {item}")

    # 建议
    print(f"\n💡 建议:")
    if stats['turnover_mean'] > 0.40:
        print("  - 换手率过高可能导致交易成本过大，考虑增加轮动周期")
    elif stats['turnover_mean'] < 0.10:
        print("  - 换手率过低可能无法及时调整池子，考虑减少轮动周期")

    if core_pct > 0.30:
        print("  - 核心池比例过高，池子缺乏灵活性，考虑调整筛选参数")
    elif core_pct < 0.10:
        print("  - 核心池比例过低，池子过于不稳定，可能影响策略连贯性")

    if health_score >= 75:
        print("  ✅ 整体质量优秀，可直接用于回测")
    elif health_score >= 50:
        print("  ⚠️  整体质量尚可，建议优化后使用")
    else:
        print("  ❌ 整体质量较差，建议重新生成")

    print("\n" + "=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='验证轮动表质量')
    parser.add_argument('file', type=str, help='轮动表JSON文件路径')
    parser.add_argument('--verbose', action='store_true', help='显示详细错误信息')

    args = parser.parse_args()
    file_path = Path(args.file)

    # 加载文件
    try:
        data = load_schedule(file_path)
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return 1

    # 验证结构
    structure_ok, structure_errors = validate_structure(data)

    if not structure_ok:
        print("❌ 结构验证失败:")
        for error in structure_errors:
            print(f"  - {error}")
        return 1

    # 提取数据
    schedule = data['schedule']
    metadata = data['metadata']

    # 验证日期
    date_ok, date_errors = validate_dates(schedule, metadata['rotation_period'])

    # 验证ETF代码
    code_ok, code_errors = validate_etf_codes(schedule, metadata['pool_size'])

    # 统计分析
    stats = analyze_statistics(schedule)

    # 打印报告
    print_validation_report(
        file_path, data,
        structure_ok, structure_errors,
        date_ok, date_errors,
        code_ok, code_errors,
        stats
    )

    # 返回码
    if structure_ok and date_ok and code_ok:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
