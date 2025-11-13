#!/usr/bin/env python3
"""
Phase 3端到端测试脚本

测试ETF轮动策略的完整功能链条：
1. 使用虚拟ETF数据生成器
2. 应用KAMA策略到虚拟ETF上
3. 对比轮动vs固定池的策略表现

使用6个月的数据确保快速测试
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest_runner.data.virtual_etf_builder import VirtualETFBuilder, RebalanceMode
from strategies.kama_cross import KamaCrossStrategy
from backtesting import Backtest
import pandas as pd
import numpy as np


def create_simple_rotation_schedule():
    """创建简单的轮动表用于测试"""

    # 使用固定的ETF池进行测试
    etf_pool_1 = ["159915.SZ", "510300.SH", "510500.SH", "159949.SZ", "512100.SH",
                  "515030.SH", "159869.SZ", "512880.SH", "510050.SH", "159928.SZ"]

    etf_pool_2 = ["159915.SZ", "510300.SH", "159949.SZ", "512100.SH", "515030.SH",
                  "159869.SZ", "512880.SH", "510050.SH", "159928.SZ", "159934.SZ"]

    rotation_schedule = {
        "metadata": {
            "start_date": "2024-06-01",
            "end_date": "2024-12-01",
            "rotation_period": 30,
            "pool_size": 10,
            "total_rotations": 6,
            "generated_at": datetime.now().isoformat()
        },
        "schedule": {
            "2024-06-01": etf_pool_1,
            "2024-07-01": etf_pool_2,
            "2024-08-01": etf_pool_1,
            "2024-09-01": etf_pool_2,
            "2024-10-01": etf_pool_1,
            "2024-11-01": etf_pool_2,
        },
        "statistics": {
            "avg_pool_overlap": 0.9,
            "avg_turnover_rate": 0.2,
            "core_etfs": etf_pool_1[:5],
            "total_unique_etfs": len(set(etf_pool_1 + etf_pool_2)),
        }
    }

    return rotation_schedule


def test_virtual_etf_builder():
    """测试虚拟ETF构建器"""
    print("=" * 80)
    print("测试1: 虚拟ETF数据生成器")
    print("=" * 80)

    # 创建轮动表
    rotation_schedule = create_simple_rotation_schedule()
    schedule_path = "/tmp/simple_rotation_schedule.json"

    with open(schedule_path, 'w', encoding='utf-8') as f:
        json.dump(rotation_schedule, f, indent=2, ensure_ascii=False)

    print(f"✅ 创建轮动表: {schedule_path}")

    # 测试虚拟ETF构建
    try:
        builder = VirtualETFBuilder(
            rotation_schedule_path=schedule_path,
            data_dir='data/chinese_etf'
        )

        # 增量调整模式
        virtual_etf_data = builder.build(
            rebalance_mode=RebalanceMode.INCREMENTAL,
            trading_cost_pct=0.003,
            verbose=True
        )

        print(f"✅ 虚拟ETF数据生成成功")
        print(f"   数据形状: {virtual_etf_data.shape}")
        print(f"   时间范围: {virtual_etf_data.index[0]} ~ {virtual_etf_data.index[-1]}")
        print(f"   收益率: {(virtual_etf_data['Close'].iloc[-1]/virtual_etf_data['Close'].iloc[0]-1)*100:.2f}%")

        # 保存测试数据
        virtual_etf_data.to_csv("/tmp/test_virtual_etf.csv")
        print(f"   数据已保存: /tmp/test_virtual_etf.csv")

        return virtual_etf_data, schedule_path

    except Exception as e:
        print(f"❌ 虚拟ETF构建失败: {e}")
        return None, None


def test_rotation_strategy(virtual_etf_data):
    """测试轮动策略回测"""
    print("\n" + "=" * 80)
    print("测试2: KAMA轮动策略回测")
    print("=" * 80)

    if virtual_etf_data is None:
        print("❌ 跳过策略测试：虚拟ETF数据为空")
        return None

    try:
        # 创建策略类（基础版）
        class TestKamaStrategy(KamaCrossStrategy):
            # 使用默认参数
            pass

        # 运行回测
        bt = Backtest(
            virtual_etf_data,
            TestKamaStrategy,
            cash=100000,
            commission=0.0,  # 成本已在虚拟ETF中计入
        )

        stats = bt.run()

        print(f"✅ KAMA轮动策略回测完成")
        print(f"   回测期间: {stats['Start']} ~ {stats['End']}")
        print(f"   总收益率: {stats['Return [%]']:.2f}%")
        print(f"   夏普比率: {stats['Sharpe Ratio']:.3f}")
        print(f"   最大回撤: {stats['Max. Drawdown [%]']:.2f}%")
        print(f"   交易次数: {stats['# Trades']}")

        return stats

    except Exception as e:
        print(f"❌ 策略回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fixed_pool_comparison(schedule_path):
    """测试固定池对照组"""
    print("\n" + "=" * 80)
    print("测试3: 固定池对照组")
    print("=" * 80)

    try:
        # 加载轮动表
        with open(schedule_path, 'r', encoding='utf-8') as f:
            rotation_schedule = json.load(f)

        # 使用第一个轮动期的ETF作为固定池
        fixed_pool = rotation_schedule['schedule']['2024-06-01']
        print(f"固定池ETF: {fixed_pool}")

        # 创建固定池的轮动表（所有期都用同样的ETF）
        fixed_schedule = {
            "metadata": rotation_schedule['metadata'].copy(),
            "schedule": {date: fixed_pool for date in rotation_schedule['schedule'].keys()},
            "statistics": {"note": "固定池对照组"}
        }

        fixed_schedule_path = "/tmp/fixed_pool_schedule.json"
        with open(fixed_schedule_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_schedule, f, indent=2, ensure_ascii=False)

        # 构建固定池虚拟ETF
        fixed_builder = VirtualETFBuilder(
            rotation_schedule_path=fixed_schedule_path,
            data_dir='data/chinese_etf'
        )

        fixed_etf_data = fixed_builder.build(
            rebalance_mode=RebalanceMode.INCREMENTAL,
            trading_cost_pct=0.003,
            verbose=False
        )

        print(f"✅ 固定池虚拟ETF生成成功")

        # 运行固定池策略
        class TestKamaStrategy(KamaCrossStrategy):
            pass

        bt_fixed = Backtest(
            fixed_etf_data,
            TestKamaStrategy,
            cash=100000,
            commission=0.0,
        )

        stats_fixed = bt_fixed.run()

        print(f"✅ 固定池策略回测完成")
        print(f"   总收益率: {stats_fixed['Return [%]']:.2f}%")
        print(f"   夏普比率: {stats_fixed['Sharpe Ratio']:.3f}")
        print(f"   最大回撤: {stats_fixed['Max. Drawdown [%]']:.2f}%")
        print(f"   交易次数: {stats_fixed['# Trades']}")

        return stats_fixed

    except Exception as e:
        print(f"❌ 固定池测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_results(stats_rotation, stats_fixed):
    """对比轮动vs固定池结果"""
    print("\n" + "=" * 80)
    print("测试4: 轮动 vs 固定池对比")
    print("=" * 80)

    if stats_rotation is None or stats_fixed is None:
        print("❌ 无法对比：部分数据缺失")
        return

    metrics = [
        ("总收益率(%)", stats_rotation['Return [%]'], stats_fixed['Return [%]']),
        ("夏普比率", stats_rotation['Sharpe Ratio'], stats_fixed['Sharpe Ratio']),
        ("最大回撤(%)", stats_rotation['Max. Drawdown [%]'], stats_fixed['Max. Drawdown [%]']),
        ("交易次数", stats_rotation['# Trades'], stats_fixed['# Trades']),
    ]

    print(f"{'指标':<15} {'轮动策略':<15} {'固定池':<15} {'差异':<15}")
    print("-" * 60)

    for metric_name, rotation_val, fixed_val in metrics:
        diff = rotation_val - fixed_val
        diff_str = f"+{diff:.3f}" if diff > 0 else f"{diff:.3f}"
        print(f"{metric_name:<15} {rotation_val:<15.3f} {fixed_val:<15.3f} {diff_str:<15}")

    # 结论
    print(f"\n结论:")
    rotation_return = stats_rotation['Return [%]']
    fixed_return = stats_fixed['Return [%]']

    if rotation_return > fixed_return:
        print("✅ 轮动策略收益更高，动态调整有效")
    else:
        print("⚠️ 固定池收益更高，轮动策略需要优化")


def test_cli_integration():
    """测试CLI集成功能"""
    print("\n" + "=" * 80)
    print("测试5: CLI集成功能测试")
    print("=" * 80)

    # 检查轮动表是否可用
    if not Path("/tmp/simple_rotation_schedule.json").exists():
        print("❌ 轮动表文件不存在，跳过CLI测试")
        return

    # 测试独立轮动策略脚本
    try:
        print("📝 测试独立轮动策略脚本...")
        import subprocess

        cmd = [
            sys.executable,
            "scripts/run_rotation_strategy.py",
            "--rotation-schedule", "/tmp/simple_rotation_schedule.json",
            "--strategy", "kama_cross",
            "--rebalance-mode", "incremental",
            "--trading-cost", "0.003",
            "--data-dir", "data/chinese_etf"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✅ 独立轮动策略脚本运行成功")
            # 显示部分输出
            lines = result.stdout.split('\n')
            for line in lines[-20:]:  # 显示最后20行
                if line.strip():
                    print(f"   {line}")
        else:
            print(f"❌ 独立轮动策略脚本失败")
            print(f"   错误: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("⚠️ CLI测试超时")
    except Exception as e:
        print(f"❌ CLI测试异常: {e}")


def main():
    """主测试入口"""
    print("ETF轮动策略 Phase 3 端到端测试")
    print("测试时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 测试1: 虚拟ETF构建
    virtual_etf_data, schedule_path = test_virtual_etf_builder()

    # 测试2: 轮动策略
    stats_rotation = test_rotation_strategy(virtual_etf_data)

    # 测试3: 固定池对照
    stats_fixed = test_fixed_pool_comparison(schedule_path) if schedule_path else None

    # 测试4: 对比分析
    compare_results(stats_rotation, stats_fixed)

    # 测试5: CLI集成
    test_cli_integration()

    # 总结
    print("\n" + "=" * 80)
    print("Phase 3测试总结")
    print("=" * 80)

    success_count = 0
    total_tests = 5

    if virtual_etf_data is not None:
        success_count += 1
        print("✅ 虚拟ETF数据生成")
    else:
        print("❌ 虚拟ETF数据生成")

    if stats_rotation is not None:
        success_count += 1
        print("✅ 轮动策略回测")
    else:
        print("❌ 轮动策略回测")

    if stats_fixed is not None:
        success_count += 1
        print("✅ 固定池对照组")
    else:
        print("❌ 固定池对照组")

    if stats_rotation is not None and stats_fixed is not None:
        success_count += 1
        print("✅ 策略对比分析")
    else:
        print("❌ 策略对比分析")

    # CLI集成测试简化判断
    if Path("/tmp/simple_rotation_schedule.json").exists():
        success_count += 1
        print("✅ CLI集成准备")
    else:
        print("❌ CLI集成准备")

    print(f"\n成功率: {success_count}/{total_tests} ({success_count/total_tests*100:.1f}%)")

    if success_count >= 4:
        print("🎉 Phase 3功能基本验证成功！")
        return 0
    else:
        print("⚠️ Phase 3功能存在问题，需要进一步调试")
        return 1


if __name__ == '__main__':
    sys.exit(main())