#!/usr/bin/env python3
"""
测试脚本：运行1个实验来验证流程
"""
import sys
from pathlib import Path

# 添加项目根目录到path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from experiment.etf.macd_cross.selector_weights_grid_search.unbiased_optimizer import UnbiasedOptimizer

def main():
    print("开始测试实验流程...")

    optimizer = UnbiasedOptimizer()

    # 获取第一个权重组合
    combinations = optimizer.generator.generate_combinations()
    print(f"共有 {len(combinations)} 个权重组合")

    # 只测试第一个
    test_weights = combinations[0]
    print(f"\n测试权重配置:")
    print(f"  ADX: {test_weights['adx_weight']:.2f}")
    print(f"  趋势一致性: {test_weights['trend_consistency_weight']:.2f}")
    print(f"  价格效率: {test_weights['price_efficiency_weight']:.2f}")
    print(f"  流动性: {test_weights['liquidity_weight']:.2f}")

    # 运行单个实验
    result = optimizer.run_single_experiment(0, test_weights)

    print(f"\n实验结果:")
    print(f"  状态: {result['status']}")
    if result['status'] == 'success':
        print(f"  ETF数量: {result['etf_count']}")
        print(f"  夏普比率: {result['sharpe_ratio']:.3f}")
        print(f"  年化收益: {result['annual_return']:.2%}")
        print(f"  最大回撤: {result['max_drawdown']:.2%}")
        print(f"  胜率: {result['win_rate']:.2%}")
    else:
        print(f"  错误: {result['error']}")

    print("\n测试完成！")

if __name__ == '__main__':
    main()
