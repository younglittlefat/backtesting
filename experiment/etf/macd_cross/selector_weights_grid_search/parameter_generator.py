#!/usr/bin/env python3
"""
无偏权重参数生成器

生成所有符合约束的无偏权重组合，用于方案B实验。
"""
import itertools
import yaml
from pathlib import Path
from typing import List, Dict


class UnbiasedWeightsGenerator:
    """无偏权重组合生成器"""

    def __init__(self, config_path: str = None):
        """
        初始化生成器

        Args:
            config_path: 配置文件路径，默认使用unbiased_params.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config" / "unbiased_params.yaml"

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.search_space = self.config['search_space']
        self.tolerance = self.config['constraints']['tolerance']

    def generate_combinations(self) -> List[Dict[str, float]]:
        """
        生成所有符合约束的无偏权重组合

        Returns:
            权重组合列表
        """
        combinations = []

        # 生成所有可能的组合
        for adx_w in self.search_space['adx_weight']:
            for trend_w in self.search_space['trend_consistency_weight']:
                for price_w in self.search_space['price_efficiency_weight']:
                    for liq_w in self.search_space['liquidity_weight']:
                        # 验证权重和为1
                        weight_sum = adx_w + trend_w + price_w + liq_w
                        if abs(weight_sum - 1.0) < self.tolerance:
                            combination = {
                                'adx_weight': adx_w,
                                'trend_consistency_weight': trend_w,
                                'price_efficiency_weight': price_w,
                                'liquidity_weight': liq_w,
                                'momentum_3m_weight': self.search_space['momentum_3m_weight'],
                                'momentum_12m_weight': self.search_space['momentum_12m_weight'],
                                'primary_weight': 1.0,
                                'secondary_weight': 0.0,
                            }
                            combinations.append(combination)

        return combinations

    def save_combinations(self, output_path: str = None):
        """
        保存生成的组合到文件

        Args:
            output_path: 输出文件路径
        """
        if output_path is None:
            output_path = Path(__file__).parent / "results" / "unbiased_weight_combinations.yaml"

        combinations = self.generate_combinations()

        # 创建输出目录
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存到YAML
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump({
                'total_combinations': len(combinations),
                'combinations': combinations
            }, f, default_flow_style=False, allow_unicode=True)

        print(f"✓ 生成了 {len(combinations)} 个无偏权重组合")
        print(f"✓ 已保存到: {output_path}")

        return combinations


if __name__ == '__main__':
    generator = UnbiasedWeightsGenerator()
    combinations = generator.save_combinations()

    # 显示前3个组合示例
    print("\n前3个组合示例:")
    for i, combo in enumerate(combinations[:3], 1):
        print(f"\n组合 {i}:")
        print(f"  ADX权重: {combo['adx_weight']:.2f}")
        print(f"  趋势一致性权重: {combo['trend_consistency_weight']:.2f}")
        print(f"  价格效率权重: {combo['price_efficiency_weight']:.2f}")
        print(f"  流动性权重: {combo['liquidity_weight']:.2f}")
        print(f"  动量权重: {combo['momentum_3m_weight']:.2f} (3M), {combo['momentum_12m_weight']:.2f} (12M)")
