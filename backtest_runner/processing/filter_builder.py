"""过滤器参数构建模块"""

from typing import Dict, Optional
import argparse


def build_filter_params(
    strategy_name: str,
    args: argparse.Namespace
) -> Optional[Dict]:
    """
    根据策略名称和命令行参数构建过滤器参数

    Args:
        strategy_name: 策略名称
        args: 命令行参数

    Returns:
        过滤器参数字典，如果没有启用任何过滤器则返回None
    """
    if strategy_name == 'sma_cross_enhanced':
        return _build_sma_filter_params(args)
    elif strategy_name == 'macd_cross':
        return _build_macd_filter_params(args)
    elif strategy_name == 'kama_cross':
        return _build_kama_filter_params(args)
    else:
        return None


def _build_sma_filter_params(args: argparse.Namespace) -> Optional[Dict]:
    """
    构建双均线增强策略的过滤器参数

    Args:
        args: 命令行参数

    Returns:
        过滤器参数字典，如果没有启用任何过滤器则返回None
    """
    filter_params = {}

    # 过滤器开关及参数
    if args.enable_slope_filter:
        filter_params['enable_slope_filter'] = True
        filter_params['slope_lookback'] = args.slope_lookback

    if args.enable_adx_filter:
        filter_params['enable_adx_filter'] = True
        filter_params['adx_period'] = args.adx_period
        filter_params['adx_threshold'] = args.adx_threshold

    if args.enable_volume_filter:
        filter_params['enable_volume_filter'] = True
        filter_params['volume_period'] = args.volume_period
        filter_params['volume_ratio'] = args.volume_ratio

    if args.enable_confirm_filter:
        filter_params['enable_confirm_filter'] = True
        filter_params['confirm_bars'] = args.confirm_bars

    if args.enable_loss_protection:
        filter_params['enable_loss_protection'] = True
        filter_params['max_consecutive_losses'] = args.max_consecutive_losses
        filter_params['pause_bars'] = args.pause_bars

    if args.enable_atr_stop:
        filter_params['enable_atr_stop'] = True
        filter_params['atr_period'] = args.atr_period
        filter_params['atr_multiplier'] = args.atr_multiplier

    return filter_params if filter_params else None


def _build_macd_filter_params(args: argparse.Namespace) -> Optional[Dict]:
    """
    构建MACD策略的过滤器参数（使用统一的参数名）

    Args:
        args: 命令行参数

    Returns:
        过滤器参数字典，如果没有启用任何过滤器则返回None
    """
    filter_params = {}

    # MACD过滤器开关及参数（使用统一的参数名）
    if args.enable_adx_filter:
        filter_params['enable_adx_filter'] = True
        filter_params['adx_period'] = args.adx_period
        filter_params['adx_threshold'] = args.adx_threshold

    if args.enable_volume_filter:
        filter_params['enable_volume_filter'] = True
        filter_params['volume_period'] = args.volume_period
        filter_params['volume_ratio'] = args.volume_ratio

    if args.enable_slope_filter:
        filter_params['enable_slope_filter'] = True
        filter_params['slope_lookback'] = args.slope_lookback

    if args.enable_confirm_filter:
        filter_params['enable_confirm_filter'] = True
        filter_params['confirm_bars'] = args.confirm_bars

    # MACD止损保护参数（使用统一的参数名）
    if args.enable_loss_protection:
        filter_params['enable_loss_protection'] = True
        filter_params['max_consecutive_losses'] = args.max_consecutive_losses
        filter_params['pause_bars'] = args.pause_bars

    if args.debug_loss_protection:
        filter_params['debug_loss_protection'] = True

    # MACD跟踪止损参数（使用统一的参数名）
    if args.enable_trailing_stop:
        filter_params['enable_trailing_stop'] = True
        filter_params['trailing_stop_pct'] = args.trailing_stop_pct

    # ATR自适应止损参数
    if args.enable_atr_stop:
        filter_params['enable_atr_stop'] = True
        filter_params['atr_period'] = args.atr_period
        filter_params['atr_multiplier'] = args.atr_multiplier

    # Anti-Whipsaw（贴线反复抑制）与零轴约束
    if getattr(args, 'enable_hysteresis', False):
        filter_params['enable_hysteresis'] = True
        if getattr(args, 'hysteresis_mode', None) is not None:
            filter_params['hysteresis_mode'] = args.hysteresis_mode
        if getattr(args, 'hysteresis_k', None) is not None:
            filter_params['hysteresis_k'] = args.hysteresis_k
        if getattr(args, 'hysteresis_window', None) is not None:
            filter_params['hysteresis_window'] = args.hysteresis_window
        if getattr(args, 'hysteresis_abs', None) is not None:
            filter_params['hysteresis_abs'] = args.hysteresis_abs
    # 卖出确认、最短持有
    if getattr(args, 'confirm_bars_sell', None) is not None:
        filter_params['confirm_bars_sell'] = args.confirm_bars_sell
    if getattr(args, 'min_hold_bars', None) is not None:
        filter_params['min_hold_bars'] = args.min_hold_bars
    # 零轴约束
    if getattr(args, 'enable_zero_axis', False):
        filter_params['enable_zero_axis'] = True
        if getattr(args, 'zero_axis_mode', None) is not None:
            filter_params['zero_axis_mode'] = args.zero_axis_mode

    return filter_params if filter_params else None


def _build_kama_filter_params(args: argparse.Namespace) -> Optional[Dict]:
    """
    构建KAMA策略的过滤器参数

    Args:
        args: 命令行参数

    Returns:
        过滤器参数字典，如果没有启用任何过滤器则返回None
    """
    filter_params = {}

    # KAMA过滤器开关及参数（通用）
    if args.enable_adx_filter:
        filter_params['enable_adx_filter'] = True
        filter_params['adx_period'] = args.adx_period
        filter_params['adx_threshold'] = args.adx_threshold

    if args.enable_volume_filter:
        filter_params['enable_volume_filter'] = True
        filter_params['volume_period'] = args.volume_period
        filter_params['volume_ratio'] = args.volume_ratio

    if args.enable_slope_filter:
        filter_params['enable_slope_filter'] = True
        filter_params['slope_lookback'] = args.slope_lookback

    if args.enable_confirm_filter:
        filter_params['enable_confirm_filter'] = True
        filter_params['confirm_bars'] = args.confirm_bars

    # KAMA止损保护参数
    if args.enable_loss_protection:
        filter_params['enable_loss_protection'] = True
        filter_params['max_consecutive_losses'] = args.max_consecutive_losses
        filter_params['pause_bars'] = args.pause_bars

    if args.debug_loss_protection:
        filter_params['debug_loss_protection'] = True

    # KAMA跟踪止损参数（向后兼容）
    if args.enable_trailing_stop:
        filter_params['enable_trailing_stop'] = True
        filter_params['trailing_stop_pct'] = args.trailing_stop_pct

    # ATR 自适应止损参数
    if args.enable_atr_stop:
        filter_params['enable_atr_stop'] = True
        filter_params['atr_period'] = args.atr_period
        filter_params['atr_multiplier'] = args.atr_multiplier

    # KAMA策略特有参数（核心 & 特有过滤器）
    if getattr(args, 'kama_period', None) is not None:
        filter_params['kama_period'] = args.kama_period
    if getattr(args, 'kama_fast', None) is not None:
        filter_params['kama_fast'] = args.kama_fast
    if getattr(args, 'kama_slow', None) is not None:
        filter_params['kama_slow'] = args.kama_slow
    if getattr(args, 'enable_efficiency_filter', False):
        filter_params['enable_efficiency_filter'] = True
    if getattr(args, 'min_efficiency_ratio', None) is not None:
        filter_params['min_efficiency_ratio'] = args.min_efficiency_ratio
    if getattr(args, 'enable_slope_confirmation', False):
        filter_params['enable_slope_confirmation'] = True
    if getattr(args, 'min_slope_periods', None) is not None:
        filter_params['min_slope_periods'] = args.min_slope_periods

    return filter_params if filter_params else None
