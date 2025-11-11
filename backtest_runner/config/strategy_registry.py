"""策略注册表"""

from typing import Dict, List, Type, Optional


class StrategyRegistry:
    """策略注册表，管理可用的交易策略"""

    def __init__(self):
        """初始化策略注册表"""
        self._strategies: Dict[str, Type] = {}

    def register(self, name: str, strategy_class: Type) -> None:
        """
        注册策略

        Args:
            name: 策略名称
            strategy_class: 策略类
        """
        self._strategies[name] = strategy_class

    def get(self, name: str) -> Optional[Type]:
        """
        获取策略类

        Args:
            name: 策略名称

        Returns:
            策略类，如果不存在则返回None
        """
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        """
        列出所有已注册的策略名称

        Returns:
            策略名称列表
        """
        return list(self._strategies.keys())

    def has_strategy(self, name: str) -> bool:
        """
        检查策略是否存在

        Args:
            name: 策略名称

        Returns:
            是否存在
        """
        return name in self._strategies

    def get_strategies_dict(self) -> Dict[str, Type]:
        """
        获取策略字典（用于向后兼容）

        Returns:
            策略名称到策略类的映射
        """
        return self._strategies.copy()


# 全局策略注册表实例
_global_registry = StrategyRegistry()


def get_global_registry() -> StrategyRegistry:
    """获取全局策略注册表"""
    return _global_registry


def register_default_strategies() -> None:
    """注册默认策略"""
    from strategies.sma_cross import SmaCross
    from strategies.sma_cross_enhanced import SmaCrossEnhanced
    from strategies.macd_cross import MacdCross
    from strategies.kama_cross import KamaCrossStrategy

    registry = get_global_registry()
    registry.register('sma_cross', SmaCross)
    registry.register('sma_cross_enhanced', SmaCrossEnhanced)
    registry.register('macd_cross', MacdCross)
    registry.register('kama_cross', KamaCrossStrategy)


# 自动注册默认策略
register_default_strategies()


# 可用的策略映射（向后兼容）
STRATEGIES = get_global_registry().get_strategies_dict()
