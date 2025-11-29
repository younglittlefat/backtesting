"""
策略实例构建器

职责：
- 根据命令行参数动态构建策略类
- 使用声明式配置消除重复的 hasattr/setattr 模式
"""

from typing import Any, Dict, Type


# 策略参数映射表：策略类属性名 -> args 属性名
# 按功能分组，便于维护
STRATEGY_PARAM_MAPPING = {
    # === 过滤器开关 ===
    'enable_slope_filter': 'enable_slope_filter',
    'enable_adx_filter': 'enable_adx_filter',
    'enable_volume_filter': 'enable_volume_filter',
    'enable_confirm_filter': 'enable_confirm_filter',

    # === 过滤器参数 ===
    'slope_lookback': 'slope_lookback',
    'adx_period': 'adx_period',
    'adx_threshold': 'adx_threshold',
    'volume_period': 'volume_period',
    'volume_ratio': 'volume_ratio',
    'confirm_bars': 'confirm_bars',

    # === 止损保护 ===
    'enable_loss_protection': 'enable_loss_protection',
    'max_consecutive_losses': 'max_consecutive_losses',
    'pause_bars': 'pause_bars',

    # === 跟踪止损 ===
    'enable_trailing_stop': 'enable_trailing_stop',
    'trailing_stop_pct': 'trailing_stop_pct',

    # === ATR 自适应止损 ===
    'enable_atr_stop': 'enable_atr_stop',
    'atr_period': 'atr_period',
    'atr_multiplier': 'atr_multiplier',

    # === Anti-Whipsaw 参数 ===
    'enable_hysteresis': 'enable_hysteresis',
    'hysteresis_mode': 'hysteresis_mode',
    'hysteresis_k': 'hysteresis_k',
    'hysteresis_window': 'hysteresis_window',
    'hysteresis_abs': 'hysteresis_abs',
    'confirm_bars_sell': 'confirm_bars_sell',
    'min_hold_bars': 'min_hold_bars',
    'enable_zero_axis': 'enable_zero_axis',
    'zero_axis_mode': 'zero_axis_mode',
}


def build_strategy_instance(strategy_class: Type, args: Any) -> Type:
    """
    根据命令行参数构建带参数的策略类

    Args:
        strategy_class: 原始策略类
        args: argparse 解析后的参数对象

    Returns:
        动态创建的策略子类，包含从 args 中提取的参数
    """
    strategy_params = _extract_strategy_params(strategy_class, args)

    # 动态创建策略子类
    class ParameterizedStrategy(strategy_class):
        pass

    # 设置参数为类属性
    for param_name, param_value in strategy_params.items():
        setattr(ParameterizedStrategy, param_name, param_value)

    return ParameterizedStrategy


def _extract_strategy_params(strategy_class: Type, args: Any) -> Dict[str, Any]:
    """
    从 args 中提取策略支持的参数

    Args:
        strategy_class: 策略类
        args: argparse 解析后的参数对象

    Returns:
        策略参数字典
    """
    params = {}

    for strategy_attr, args_attr in STRATEGY_PARAM_MAPPING.items():
        # 只有当策略类定义了该属性，且 args 中有对应值时才提取
        if hasattr(strategy_class, strategy_attr) and hasattr(args, args_attr):
            params[strategy_attr] = getattr(args, args_attr)

    return params
