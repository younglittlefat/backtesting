"""
策略契约基类 (Strategy Contract Base Classes)

定义策略必须实现的运行时参数导出接口，确保回测和实盘信号生成的一致性。

核心设计:
1. RuntimeConfigurable: 抽象接口，强制策略实现运行时参数导出
2. BaseEnhancedStrategy: 增强型策略基类，自动集成过滤器、止损保护等功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from backtesting import Strategy


class RuntimeConfigurable(ABC):
    """
    运行时参数可导出接口

    所有支持运行时参数（过滤器、止损保护等）的策略必须实现此接口

    目的:
    - 确保回测时使用的运行时参数能够保存到配置文件
    - 确保实盘信号生成时能够复现回测环境
    - 通过强制接口避免参数遗漏导致的信号错误
    """

    @abstractmethod
    def get_runtime_config(self) -> Dict[str, Any]:
        """
        导出当前策略的运行时配置

        Returns:
            dict: 运行时配置字典，格式如下:
            {
                "filters": {
                    "enable_adx_filter": bool,
                    "adx_threshold": int,
                    ...
                },
                "loss_protection": {
                    "enable_loss_protection": bool,
                    "max_consecutive_losses": int,
                    "pause_bars": int
                },
                "strategy_specific": {
                    # 策略特有的运行时参数
                }
            }
        """
        pass

    @abstractmethod
    def get_runtime_config_schema(self) -> Dict[str, Any]:
        """
        返回运行时配置的结构定义（用于验证）

        Returns:
            dict: 配置结构定义，格式如下:
            {
                "filters": {
                    "enable_adx_filter": {"type": "bool", "default": False},
                    "adx_threshold": {"type": "int", "default": 25, "range": [10, 50]},
                    ...
                },
                "loss_protection": {
                    "enable_loss_protection": {"type": "bool", "default": False},
                    "max_consecutive_losses": {"type": "int", "default": 3, "range": [1, 10]},
                    "pause_bars": {"type": "int", "default": 10, "range": [1, 50]}
                }
            }
        """
        pass


class BaseEnhancedStrategy(Strategy, RuntimeConfigurable):
    """
    增强型策略基类

    所有新策略应该继承此类，自动获得:
    - 过滤器支持（ADX、成交量、斜率、确认）
    - 止损保护功能
    - 运行时参数导出能力

    子类可以:
    - 覆盖默认参数值
    - 扩展 get_runtime_config() 添加策略特有参数
    - 覆盖 get_runtime_config_schema() 添加参数验证规则

    示例:
        class MyStrategy(BaseEnhancedStrategy):
            # 定义优化参数
            n1 = 10
            n2 = 20

            # 覆盖止损保护默认值
            max_consecutive_losses = 5
            pause_bars = 15

            def init(self):
                # 策略初始化
                pass

            def next(self):
                # 策略逻辑
                pass
    """

    # 过滤器开关（子类可覆盖）
    enable_slope_filter = False
    enable_adx_filter = False
    enable_volume_filter = False
    enable_confirm_filter = False

    # 过滤器参数（子类可覆盖）
    slope_lookback = 5
    adx_period = 14
    adx_threshold = 25
    volume_period = 20
    volume_ratio = 1.2
    confirm_bars = 3

    # 止损保护开关（子类可覆盖）
    enable_loss_protection = False

    # 止损保护参数（子类可覆盖，基于实验推荐值）
    max_consecutive_losses = 3
    pause_bars = 10

    # ATR自适应止损开关（子类可覆盖）
    enable_atr_stop = False

    # ATR止损参数（子类可覆盖，基于需求文档推荐值）
    atr_period = 14          # ATR计算周期，推荐14天
    atr_multiplier = 2.5     # ATR倍数，推荐2.5（中期趋势跟踪）

    # 传统跟踪止损开关（向后兼容）
    enable_trailing_stop = False

    # 传统跟踪止损参数（向后兼容）
    trailing_stop_pct = 0.05  # 5%固定百分比

    def get_runtime_config(self) -> Dict[str, Any]:
        """
        默认实现：导出所有运行时参数

        子类可以扩展此方法添加策略特有参数:
            def get_runtime_config(self):
                config = super().get_runtime_config()
                config["strategy_specific"] = {
                    "my_param": self.my_param
                }
                return config
        """
        return {
            "filters": {
                "enable_slope_filter": self.enable_slope_filter,
                "enable_adx_filter": self.enable_adx_filter,
                "enable_volume_filter": self.enable_volume_filter,
                "enable_confirm_filter": self.enable_confirm_filter,
                "slope_lookback": self.slope_lookback,
                "adx_period": self.adx_period,
                "adx_threshold": self.adx_threshold,
                "volume_period": self.volume_period,
                "volume_ratio": self.volume_ratio,
                "confirm_bars": self.confirm_bars,
            },
            "loss_protection": {
                "enable_loss_protection": self.enable_loss_protection,
                "max_consecutive_losses": self.max_consecutive_losses,
                "pause_bars": self.pause_bars,
            },
            "stop_loss": {
                "enable_atr_stop": self.enable_atr_stop,
                "atr_period": self.atr_period,
                "atr_multiplier": self.atr_multiplier,
                "enable_trailing_stop": self.enable_trailing_stop,
                "trailing_stop_pct": self.trailing_stop_pct,
            }
        }

    def get_runtime_config_schema(self) -> Dict[str, Any]:
        """
        默认配置结构定义

        子类可以扩展此方法添加策略特有参数验证规则
        """
        return {
            "filters": {
                "enable_slope_filter": {"type": "bool", "default": False},
                "enable_adx_filter": {"type": "bool", "default": False},
                "enable_volume_filter": {"type": "bool", "default": False},
                "enable_confirm_filter": {"type": "bool", "default": False},
                "slope_lookback": {"type": "int", "default": 5, "range": [1, 20]},
                "adx_period": {"type": "int", "default": 14, "range": [7, 30]},
                "adx_threshold": {"type": "int", "default": 25, "range": [10, 50]},
                "volume_period": {"type": "int", "default": 20, "range": [5, 50]},
                "volume_ratio": {"type": "float", "default": 1.2, "range": [1.0, 3.0]},
                "confirm_bars": {"type": "int", "default": 3, "range": [1, 10]},
            },
            "loss_protection": {
                "enable_loss_protection": {"type": "bool", "default": False},
                "max_consecutive_losses": {"type": "int", "default": 3, "range": [1, 10]},
                "pause_bars": {"type": "int", "default": 10, "range": [1, 50]},
            },
            "stop_loss": {
                "enable_atr_stop": {"type": "bool", "default": False},
                "atr_period": {"type": "int", "default": 14, "range": [7, 30]},
                "atr_multiplier": {"type": "float", "default": 2.5, "range": [1.5, 5.0]},
                "enable_trailing_stop": {"type": "bool", "default": False},
                "trailing_stop_pct": {"type": "float", "default": 0.05, "range": [0.01, 0.20]},
            }
        }


def get_strategy_runtime_config(strategy_instance):
    """
    安全获取策略运行时配置，支持向后兼容

    如果策略不支持 RuntimeConfigurable，返回默认配置

    Args:
        strategy_instance: 策略实例

    Returns:
        dict: 运行时配置
    """
    if hasattr(strategy_instance, 'get_runtime_config'):
        return strategy_instance.get_runtime_config()
    else:
        # 旧策略，返回默认值
        return {
            "filters": {
                "enable_slope_filter": False,
                "enable_adx_filter": False,
                "enable_volume_filter": False,
                "enable_confirm_filter": False,
                "slope_lookback": 5,
                "adx_period": 14,
                "adx_threshold": 25,
                "volume_period": 20,
                "volume_ratio": 1.2,
                "confirm_bars": 3,
            },
            "loss_protection": {
                "enable_loss_protection": False,
                "max_consecutive_losses": 3,
                "pause_bars": 10,
            },
            "stop_loss": {
                "enable_atr_stop": False,
                "atr_period": 14,
                "atr_multiplier": 2.5,
                "enable_trailing_stop": False,
                "trailing_stop_pct": 0.05,
            }
        }


def validate_strategy_contract(strategy_class):
    """
    验证策略是否实现了必要的接口

    如果策略不符合契约，抛出异常并给出明确提示

    Args:
        strategy_class: 策略类（非实例）

    Raises:
        TypeError: 策略未继承 RuntimeConfigurable
        NotImplementedError: 策略未实现必要的方法
    """
    if not issubclass(strategy_class, RuntimeConfigurable):
        raise TypeError(
            f"策略 {strategy_class.__name__} 必须继承 RuntimeConfigurable 接口！\n"
            f"请修改策略定义为:\n"
            f"  class {strategy_class.__name__}(BaseEnhancedStrategy):\n"
            f"      ...\n"
            f"\n"
            f"或手动实现以下方法:\n"
            f"  - get_runtime_config()\n"
            f"  - get_runtime_config_schema()\n"
            f"\n"
            f"参考文档: requirement_docs/20251109_save_runtime_params_enhancement.md"
        )

    # 验证方法实现
    if not hasattr(strategy_class, 'get_runtime_config'):
        raise NotImplementedError(
            f"策略 {strategy_class.__name__} 未实现 get_runtime_config() 方法"
        )

    if not hasattr(strategy_class, 'get_runtime_config_schema'):
        raise NotImplementedError(
            f"策略 {strategy_class.__name__} 未实现 get_runtime_config_schema() 方法"
        )
