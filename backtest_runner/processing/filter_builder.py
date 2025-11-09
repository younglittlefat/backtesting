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

    return filter_params if filter_params else None


def _build_macd_filter_params(args: argparse.Namespace) -> Optional[Dict]:
    """
    构建MACD策略的过滤器参数

    Args:
        args: 命令行参数

    Returns:
        过滤器参数字典，如果没有启用任何过滤器则返回None
    """
    filter_params = {}

    # MACD过滤器开关及参数
    if args.enable_macd_adx_filter:
        filter_params['enable_adx_filter'] = True
        filter_params['adx_period'] = args.macd_adx_period
        filter_params['adx_threshold'] = args.macd_adx_threshold

    if args.enable_macd_volume_filter:
        filter_params['enable_volume_filter'] = True
        filter_params['volume_period'] = args.macd_volume_period
        filter_params['volume_ratio'] = args.macd_volume_ratio

    if args.enable_macd_slope_filter:
        filter_params['enable_slope_filter'] = True
        filter_params['slope_lookback'] = args.macd_slope_lookback

    if args.enable_macd_confirm_filter:
        filter_params['enable_confirm_filter'] = True
        filter_params['confirm_bars'] = args.macd_confirm_bars

    # MACD止损保护参数
    if args.enable_macd_loss_protection:
        filter_params['enable_loss_protection'] = True
        filter_params['max_consecutive_losses'] = args.macd_max_consecutive_losses
        filter_params['pause_bars'] = args.macd_pause_bars

    if args.macd_debug_loss_protection:
        filter_params['debug_loss_protection'] = True

    # MACD跟踪止损参数
    if args.enable_macd_trailing_stop:
        filter_params['enable_trailing_stop'] = True
        filter_params['trailing_stop_pct'] = args.macd_trailing_stop_pct

    return filter_params if filter_params else None
