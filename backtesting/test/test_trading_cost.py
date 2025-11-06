"""
交易成本配置和计算器的单元测试

测试不同市场的交易成本配置是否正确计算费用。
"""

import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.trading_cost import (
    TradingCostConfig,
    TradingCostCalculator,
    PRESET_CONFIGS,
    get_cost_summary,
)


class TestTradingCostConfig(unittest.TestCase):
    """测试交易成本配置类"""

    def test_get_preset_default(self):
        """测试获取框架缺省预设配置"""
        config = TradingCostConfig.get_preset('default')
        self.assertEqual(config.name, '框架缺省')
        self.assertEqual(config.commission_rate, 0.0)
        self.assertEqual(config.spread, 0.0)
        self.assertEqual(config.stamp_duty, 0.0)
        self.assertEqual(config.min_commission, 0.0)
        self.assertEqual(config.transfer_fee, 0.0)
        self.assertEqual(config.sec_fee, 0.0)

    def test_get_preset_cn_etf(self):
        """测试获取中国ETF预设配置"""
        config = TradingCostConfig.get_preset('cn_etf')
        self.assertEqual(config.name, '中国A股ETF')
        self.assertEqual(config.commission_rate, 0.0005)
        self.assertEqual(config.spread, 0.0001)
        self.assertEqual(config.stamp_duty, 0.0)
        self.assertEqual(config.min_commission, 0.0)

    def test_get_preset_cn_stock(self):
        """测试获取中国个股预设配置"""
        config = TradingCostConfig.get_preset('cn_stock')
        self.assertEqual(config.name, '中国A股个股')
        self.assertEqual(config.commission_rate, 0.0003)
        self.assertEqual(config.spread, 0.0002)
        self.assertEqual(config.stamp_duty, 0.001)
        self.assertEqual(config.stamp_duty_side, 'sell')
        self.assertEqual(config.transfer_fee, 0.00001)
        self.assertEqual(config.min_commission, 5.0)

    def test_get_preset_us_stock(self):
        """测试获取美股预设配置"""
        config = TradingCostConfig.get_preset('us_stock')
        self.assertEqual(config.name, '美国股票')
        self.assertEqual(config.commission_rate, 0.0)
        self.assertEqual(config.spread, 0.0001)
        self.assertEqual(config.sec_fee, 0.0000278)
        self.assertEqual(config.min_commission, 0.0)

    def test_get_preset_invalid(self):
        """测试获取不存在的预设配置"""
        with self.assertRaises(ValueError):
            TradingCostConfig.get_preset('invalid_model')

    def test_preset_configs_completeness(self):
        """测试预设配置是否完整"""
        expected_models = ['default', 'cn_etf', 'cn_stock', 'us_stock']
        for model in expected_models:
            self.assertIn(model, PRESET_CONFIGS)


class TestTradingCostCalculator(unittest.TestCase):
    """测试交易成本计算器"""

    def test_default_buy_cost(self):
        """测试框架缺省配置买入成本（应为0）"""
        config = TradingCostConfig.get_preset('default')
        calc = TradingCostCalculator(config)

        # 买入100股，每股100元，总金额10000元
        # 预期成本: 0元（零佣金、零滑点）
        cost = calc(100, 100.0)
        self.assertAlmostEqual(cost, 0.0, places=2)

    def test_default_sell_cost(self):
        """测试框架缺省配置卖出成本（应为0）"""
        config = TradingCostConfig.get_preset('default')
        calc = TradingCostCalculator(config)

        # 卖出100股，每股100元
        # 预期成本: 0元
        cost = calc(-100, 100.0)
        self.assertAlmostEqual(cost, 0.0, places=2)

    def test_cn_etf_buy_cost(self):
        """测试中国ETF买入成本"""
        config = TradingCostConfig.get_preset('cn_etf')
        calc = TradingCostCalculator(config)

        # 买入100股，每股100元，总金额10000元
        # 预期佣金: 10000 * 0.0005 = 5元
        cost = calc(100, 100.0)
        self.assertAlmostEqual(cost, 5.0, places=2)

    def test_cn_etf_sell_cost(self):
        """测试中国ETF卖出成本（应该和买入一样，无印花税）"""
        config = TradingCostConfig.get_preset('cn_etf')
        calc = TradingCostCalculator(config)

        # 卖出100股，每股100元
        cost = calc(-100, 100.0)
        self.assertAlmostEqual(cost, 5.0, places=2)

    def test_cn_stock_buy_cost(self):
        """测试中国个股买入成本"""
        config = TradingCostConfig.get_preset('cn_stock')
        calc = TradingCostCalculator(config)

        # 买入100股，每股100元，总金额10000元
        # 佣金: 10000 * 0.0003 = 3元，但最低5元
        # 过户费: 10000 * 0.00001 = 0.1元
        # 总成本: 5 + 0.1 = 5.1元
        cost = calc(100, 100.0)
        self.assertAlmostEqual(cost, 5.1, places=2)

    def test_cn_stock_sell_cost(self):
        """测试中国个股卖出成本（包含印花税）"""
        config = TradingCostConfig.get_preset('cn_stock')
        calc = TradingCostCalculator(config)

        # 卖出100股，每股100元，总金额10000元
        # 佣金: 10000 * 0.0003 = 3元，但最低5元
        # 印花税: 10000 * 0.001 = 10元（仅卖出收取）
        # 过户费: 10000 * 0.00001 = 0.1元
        # 总成本: 5 + 10 + 0.1 = 15.1元
        cost = calc(-100, 100.0)
        self.assertAlmostEqual(cost, 15.1, places=2)

    def test_cn_stock_stamp_duty_only_on_sell(self):
        """验证印花税仅在卖出时收取"""
        config = TradingCostConfig.get_preset('cn_stock')
        calc = TradingCostCalculator(config)

        buy_cost = calc(100, 100.0)
        sell_cost = calc(-100, 100.0)

        # 卖出成本应该比买入多10元（印花税）
        self.assertAlmostEqual(sell_cost - buy_cost, 10.0, places=2)

    def test_cn_stock_min_commission(self):
        """验证最低佣金5元"""
        config = TradingCostConfig.get_preset('cn_stock')
        calc = TradingCostCalculator(config)

        # 小额交易：1股 * 100元 = 100元
        # 佣金: 100 * 0.0003 = 0.03元，但最低5元
        # 过户费: 100 * 0.00001 = 0.001元
        # 总成本: 5 + 0.001 ≈ 5.001元
        cost = calc(1, 100.0)
        self.assertGreaterEqual(cost, 5.0)

    def test_cn_stock_large_order(self):
        """测试大额订单（佣金超过最低限制）"""
        config = TradingCostConfig.get_preset('cn_stock')
        calc = TradingCostCalculator(config)

        # 大额交易：10000股 * 100元 = 1000000元
        # 佣金: 1000000 * 0.0003 = 300元（超过最低5元）
        # 印花税（卖出）: 1000000 * 0.001 = 1000元
        # 过户费: 1000000 * 0.00001 = 10元
        # 卖出总成本: 300 + 1000 + 10 = 1310元
        sell_cost = calc(-10000, 100.0)
        self.assertAlmostEqual(sell_cost, 1310.0, places=2)

    def test_us_stock_buy_cost(self):
        """测试美股买入成本"""
        config = TradingCostConfig.get_preset('us_stock')
        calc = TradingCostCalculator(config)

        # 买入100股，每股100美元，总金额10000美元
        # 佣金: 0（零佣金）
        # SEC费: 0（仅卖出收取）
        # 总成本: 0
        cost = calc(100, 100.0)
        self.assertAlmostEqual(cost, 0.0, places=2)

    def test_us_stock_sell_cost(self):
        """测试美股卖出成本（包含SEC费）"""
        config = TradingCostConfig.get_preset('us_stock')
        calc = TradingCostCalculator(config)

        # 卖出100股，每股100美元，总金额10000美元
        # 佣金: 0
        # SEC费: 10000 * 0.0000278 = 0.278美元
        # 总成本: 0.278美元
        cost = calc(-100, 100.0)
        self.assertAlmostEqual(cost, 0.278, places=3)

    def test_custom_config(self):
        """测试自定义配置"""
        config = TradingCostConfig(
            name='custom',
            commission_rate=0.002,
            spread=0.001,
            min_commission=10.0,
        )
        calc = TradingCostCalculator(config)

        # 买入100股，每股100元
        # 佣金: 10000 * 0.002 = 20元（超过最低10元）
        cost = calc(100, 100.0)
        self.assertAlmostEqual(cost, 20.0, places=2)

    def test_calculator_repr(self):
        """测试计算器的字符串表示"""
        config = TradingCostConfig.get_preset('cn_etf')
        calc = TradingCostCalculator(config)
        repr_str = repr(calc)
        # 验证包含模型名称和费率信息
        self.assertIn('中国A股ETF', repr_str)
        self.assertIn('0.0500%', repr_str)
        self.assertIn('0.0100%', repr_str)


class TestCostSummary(unittest.TestCase):
    """测试费用摘要功能"""

    def test_get_cost_summary_cn_etf(self):
        """测试中国ETF费用摘要"""
        config = TradingCostConfig.get_preset('cn_etf')
        summary = get_cost_summary(config)
        self.assertIn('中国A股ETF', summary)
        self.assertIn('0.0500%', summary)  # 佣金率
        self.assertIn('0.0100%', summary)  # 滑点

    def test_get_cost_summary_cn_stock(self):
        """测试中国个股费用摘要"""
        config = TradingCostConfig.get_preset('cn_stock')
        summary = get_cost_summary(config)
        self.assertIn('中国A股个股', summary)
        self.assertIn('印花税', summary)
        self.assertIn('sell', summary)
        self.assertIn('过户费', summary)
        self.assertIn('最低佣金: 5.00元', summary)

    def test_get_cost_summary_us_stock(self):
        """测试美股费用摘要"""
        config = TradingCostConfig.get_preset('us_stock')
        summary = get_cost_summary(config)
        self.assertIn('美国股票', summary)
        self.assertIn('SEC费', summary)


if __name__ == '__main__':
    unittest.main()
