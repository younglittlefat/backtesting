"""
交易成本配置和计算模块

提供不同市场和标的类型的交易成本配置，包括：
- 框架缺省 (default) - backtesting.py的原始默认设置
- 中国A股ETF (cn_etf)
- 中国A股个股 (cn_stock)
- 美国股票 (us_stock)
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class TradingCostConfig:
    """
    交易成本配置类

    Attributes:
        name: 配置名称
        commission_rate: 基础佣金率（比例，例如 0.0005 表示 0.05%）
        spread: 滑点/价差（比例）
        stamp_duty: 印花税率（比例，例如 0.001 表示 0.1%）
        stamp_duty_side: 印花税收取方向 ('buy', 'sell', 'both')
        transfer_fee: 过户费率（比例，双向收取）
        sec_fee: SEC费率（比例，通常仅卖出收取）
        min_commission: 最低佣金金额（元/美元）
    """
    name: str
    commission_rate: float
    spread: float
    stamp_duty: float = 0.0
    stamp_duty_side: Literal['buy', 'sell', 'both'] = 'sell'
    transfer_fee: float = 0.0
    sec_fee: float = 0.0
    min_commission: float = 0.0

    @classmethod
    def get_preset(cls, model_name: str) -> 'TradingCostConfig':
        """
        获取预设配置

        Args:
            model_name: 预设模型名称 ('default', 'cn_etf', 'cn_stock', 'us_stock')

        Returns:
            TradingCostConfig: 对应的配置对象

        Raises:
            ValueError: 如果模型名称不存在
        """
        if model_name not in PRESET_CONFIGS:
            available = ', '.join(PRESET_CONFIGS.keys())
            raise ValueError(
                f"未知的费用模型: {model_name}. "
                f"可用模型: {available}"
            )
        return PRESET_CONFIGS[model_name]


class TradingCostCalculator:
    """
    交易成本计算器

    计算实际交易成本，兼容 backtesting.py 的 commission 参数。
    可作为 callable 传入: Backtest(..., commission=calculator)

    Attributes:
        config: 交易成本配置对象
    """

    def __init__(self, config: TradingCostConfig):
        """
        初始化计算器

        Args:
            config: TradingCostConfig 配置对象
        """
        self.config = config

    def __call__(self, size: float, price: float) -> float:
        """
        计算订单的总成本

        Args:
            size: 订单数量（正数=买入，负数=卖出）
            price: 成交价格

        Returns:
            float: 成本金额（backtesting.py会自动处理正负号）

        Notes:
            - 返回的成本总是正数
            - 包含佣金、印花税、过户费、SEC费等所有费用
            - 不包含滑点（滑点通过 Backtest 的 spread 参数单独设置）
        """
        is_sell = size < 0
        order_value = abs(size) * price

        # 1. 基础佣金
        commission = order_value * self.config.commission_rate
        commission = max(commission, self.config.min_commission)

        # 2. 印花税（可能是单向的）
        stamp_duty = 0.0
        if self.config.stamp_duty > 0:
            if (is_sell and self.config.stamp_duty_side == 'sell') or \
               (not is_sell and self.config.stamp_duty_side == 'buy') or \
               self.config.stamp_duty_side == 'both':
                stamp_duty = order_value * self.config.stamp_duty

        # 3. 过户费（双向）
        transfer_fee = order_value * self.config.transfer_fee

        # 4. SEC费（仅卖出）
        sec_fee = 0.0
        if is_sell and self.config.sec_fee > 0:
            sec_fee = order_value * self.config.sec_fee

        total_cost = commission + stamp_duty + transfer_fee + sec_fee

        return total_cost

    def __repr__(self) -> str:
        """返回可读的字符串表示"""
        return (
            f"TradingCostCalculator(model={self.config.name}, "
            f"commission={self.config.commission_rate:.4%}, "
            f"spread={self.config.spread:.4%})"
        )


# 预设配置定义
PRESET_CONFIGS = {
    'default': TradingCostConfig(
        name='框架缺省',
        commission_rate=0.0,        # 零佣金
        spread=0.0,                 # 零滑点
        stamp_duty=0.0,             # 无印花税
        stamp_duty_side='sell',
        transfer_fee=0.0,           # 无过户费
        sec_fee=0.0,                # 无SEC费
        min_commission=0.0,         # 无最低佣金
    ),
    'cn_etf': TradingCostConfig(
        name='中国A股ETF',
        commission_rate=0.0005,     # 万五
        spread=0.0001,              # 0.01%
        stamp_duty=0.0,             # 免印花税
        stamp_duty_side='sell',
        transfer_fee=0.0,           # 通常不收取
        min_commission=0.0,         # 通常无最低佣金
    ),
    'cn_stock': TradingCostConfig(
        name='中国A股个股',
        commission_rate=0.0003,     # 万三
        spread=0.0002,              # 0.02%
        stamp_duty=0.001,           # 0.1%（千分之一）
        stamp_duty_side='sell',     # 仅卖出收取
        transfer_fee=0.00001,       # 0.001%（万分之一）
        min_commission=5.0,         # 最低5元
    ),
    'us_stock': TradingCostConfig(
        name='美国股票',
        commission_rate=0.0,        # 零佣金
        spread=0.0001,              # 0.01%
        stamp_duty=0.0,
        stamp_duty_side='sell',
        transfer_fee=0.0,
        sec_fee=0.0000278,          # $27.8 per $1M
        min_commission=0.0,         # 无最低佣金
    ),
}


def get_cost_summary(config: TradingCostConfig) -> str:
    """
    获取费用配置的可读摘要

    Args:
        config: 交易成本配置

    Returns:
        str: 格式化的费用摘要
    """
    lines = [
        f"费用模型: {config.name}",
        f"  佣金率: {config.commission_rate:.4%}",
        f"  滑点: {config.spread:.4%}",
    ]

    if config.stamp_duty > 0:
        lines.append(f"  印花税: {config.stamp_duty:.4%} ({config.stamp_duty_side})")

    if config.transfer_fee > 0:
        lines.append(f"  过户费: {config.transfer_fee:.4%}")

    if config.sec_fee > 0:
        lines.append(f"  SEC费: {config.sec_fee:.6%}")

    if config.min_commission > 0:
        lines.append(f"  最低佣金: {config.min_commission:.2f}元")

    return "\n".join(lines)
