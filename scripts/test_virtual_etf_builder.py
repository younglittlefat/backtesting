#!/usr/bin/env python3
"""
虚拟ETF数据生成器测试脚本

测试虚拟ETF数据生成器的功能，验证数据质量和成本计算逻辑
"""

import sys
from pathlib import Path

import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest_runner.data.virtual_etf_builder import (
    RebalanceMode,
    VirtualETFBuilder,
)


def test_virtual_etf_builder():
    """测试虚拟ETF数据生成器"""

    print("=" * 80)
    print("虚拟ETF数据生成器测试")
    print("=" * 80)

    # 使用Phase 1生成的轮动表
    rotation_schedule_path = 'results/rotation_schedules/rotation_30d.json'
    data_dir = 'data/chinese_etf'

    # 测试1: 全平仓模式
    print("\n" + "=" * 80)
    print("测试1: 全平仓模式 (FULL_LIQUIDATION)")
    print("=" * 80)

    try:
        builder = VirtualETFBuilder(
            rotation_schedule_path=rotation_schedule_path,
            data_dir=data_dir
        )

        virtual_etf_full = builder.build(
            rebalance_mode=RebalanceMode.FULL_LIQUIDATION,
            trading_cost_pct=0.003,
            base_price=1000.0,
            verbose=True
        )

        # 数据质量检查
        print("\n" + "-" * 80)
        print("数据质量检查:")
        print("-" * 80)
        print(f"数据形状: {virtual_etf_full.shape}")
        print(f"日期范围: {virtual_etf_full.index[0]} ~ {virtual_etf_full.index[-1]}")
        print(f"缺失值统计:\n{virtual_etf_full.isna().sum()}")

        # 价格统计
        print("\n" + "-" * 80)
        print("价格统计:")
        print("-" * 80)
        print(virtual_etf_full[['Open', 'High', 'Low', 'Close', 'Volume']].describe())

        # 轮动成本统计
        print("\n" + "-" * 80)
        print("轮动成本统计:")
        print("-" * 80)
        rebalance_days = virtual_etf_full[virtual_etf_full['rebalance_cost'] > 0]
        print(f"轮动次数: {len(rebalance_days)}")
        if len(rebalance_days) > 0:
            print(f"轮动日期:\n{rebalance_days[['Close', 'rebalance_cost', 'active_etf_count']]}")

        # 保存数据
        output_path = Path('results/virtual_etf/virtual_etf_full_liquidation.csv')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        virtual_etf_full.to_csv(output_path)
        print(f"\n数据已保存到: {output_path}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试2: 增量调整模式
    print("\n\n" + "=" * 80)
    print("测试2: 增量调整模式 (INCREMENTAL)")
    print("=" * 80)

    try:
        builder = VirtualETFBuilder(
            rotation_schedule_path=rotation_schedule_path,
            data_dir=data_dir
        )

        virtual_etf_inc = builder.build(
            rebalance_mode=RebalanceMode.INCREMENTAL,
            trading_cost_pct=0.003,
            base_price=1000.0,
            verbose=True
        )

        # 保存数据
        output_path = Path('results/virtual_etf/virtual_etf_incremental.csv')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        virtual_etf_inc.to_csv(output_path)
        print(f"\n数据已保存到: {output_path}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试3: 对比两种模式
    print("\n\n" + "=" * 80)
    print("测试3: 两种模式对比")
    print("=" * 80)

    try:
        print("\n初始价格:")
        print(f"  全平仓: {virtual_etf_full['Close'].iloc[0]:.2f}")
        print(f"  增量调整: {virtual_etf_inc['Close'].iloc[0]:.2f}")

        print("\n最终价格:")
        print(f"  全平仓: {virtual_etf_full['Close'].iloc[-1]:.2f}")
        print(f"  增量调整: {virtual_etf_inc['Close'].iloc[-1]:.2f}")

        print("\n总收益率:")
        full_return = (virtual_etf_full['Close'].iloc[-1] / virtual_etf_full['Close'].iloc[0] - 1) * 100
        inc_return = (virtual_etf_inc['Close'].iloc[-1] / virtual_etf_inc['Close'].iloc[0] - 1) * 100
        print(f"  全平仓: {full_return:.2f}%")
        print(f"  增量调整: {inc_return:.2f}%")
        print(f"  差异: {inc_return - full_return:.2f}% (增量调整 - 全平仓)")

        print("\n累计成本:")
        full_cost = virtual_etf_full['rebalance_cost'].sum() * 100
        inc_cost = virtual_etf_inc['rebalance_cost'].sum() * 100
        print(f"  全平仓: {full_cost:.2f}%")
        print(f"  增量调整: {inc_cost:.2f}%")
        print(f"  节省: {full_cost - inc_cost:.2f}% (全平仓 - 增量调整)")

    except Exception as e:
        print(f"\n❌ 对比失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ 所有测试通过!")
    print("=" * 80)

    return True


if __name__ == '__main__':
    success = test_virtual_etf_builder()
    sys.exit(0 if success else 1)
