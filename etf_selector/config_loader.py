"""
配置文件加载器

支持从JSON配置文件加载完整参数，并与CLI参数合并
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from etf_selector.config import FilterConfig, IndustryKeywords


class ConfigLoader:
    """配置文件加载器"""

    # JSON key → FilterConfig field 映射表
    KEY_MAPPING = {
        # Paths
        'paths.data_dir': 'data_dir',
        'paths.output_path': 'output_path',

        # Time range
        'time_range.start_date': 'start_date',
        'time_range.end_date': 'end_date',

        # Stage 1: Initial filter
        'stage1_initial_filter.min_turnover': 'min_turnover',
        'stage1_initial_filter.min_listing_days': 'min_listing_days',
        'stage1_initial_filter.turnover_lookback_days': 'turnover_lookback_days',

        # Stage 2: Core filter - ADX
        'stage2_core_filter.adx.period': 'adx_period',
        'stage2_core_filter.adx.lookback_days': 'adx_lookback_days',
        'stage2_core_filter.adx.percentile': 'adx_percentile',

        # Stage 2: Core filter - MA backtest
        'stage2_core_filter.ma_backtest.enable': 'enable_ma_backtest_filter',
        'stage2_core_filter.ma_backtest.short_period': 'ma_short',
        'stage2_core_filter.ma_backtest.long_period': 'ma_long',
        'stage2_core_filter.ma_backtest.ret_dd_percentile': 'ret_dd_percentile',

        # Stage 2: Core filter - Volatility
        'stage2_core_filter.volatility.min': 'min_volatility',
        'stage2_core_filter.volatility.max': 'max_volatility',
        'stage2_core_filter.volatility.lookback_days': 'volatility_lookback_days',

        # Stage 2: Core filter - Momentum
        'stage2_core_filter.momentum.periods': 'momentum_periods',
        'stage2_core_filter.momentum.min_positive': 'momentum_min_positive',

        # Stage 2: Filter mode control
        'stage2_core_filter.filter_mode.skip_percentile_filtering': 'skip_stage2_percentile_filtering',
        'stage2_core_filter.filter_mode.skip_range_filtering': 'skip_stage2_range_filtering',

        # Scoring system - basic
        'scoring_system.enable_unbiased_scoring': 'enable_unbiased_scoring',
        'scoring_system.benchmark.ts_code': 'benchmark_ts_code',

        # Scoring windows
        'scoring_system.windows.excess_return.short': 'excess_return_short_window',
        'scoring_system.windows.excess_return.long': 'excess_return_long_window',
        'scoring_system.windows.volume.short': 'volume_short_window',
        'scoring_system.windows.volume.long': 'volume_long_window',
        'scoring_system.windows.trend_quality': 'trend_quality_window',
        'scoring_system.windows.trend_consistency': 'trend_consistency_window',
        'scoring_system.windows.price_efficiency': 'price_efficiency_window',
        'scoring_system.windows.liquidity_score': 'liquidity_score_window',

        # ====================================================================
        # 统一权重配置（新版）
        # ====================================================================
        # 趋势类
        'scoring_system.weights.adx_score': 'weight_adx_score',
        'scoring_system.weights.trend_consistency': 'weight_trend_consistency',
        'scoring_system.weights.trend_quality': 'weight_trend_quality',
        # 收益类
        'scoring_system.weights.momentum_3m': 'weight_momentum_3m',
        'scoring_system.weights.momentum_12m': 'weight_momentum_12m',
        'scoring_system.weights.excess_return_20d': 'weight_excess_return_20d',
        'scoring_system.weights.excess_return_60d': 'weight_excess_return_60d',
        # 流动性/成交量类
        'scoring_system.weights.liquidity_score': 'weight_liquidity_score',
        'scoring_system.weights.price_efficiency': 'weight_price_efficiency',
        'scoring_system.weights.volume_trend': 'weight_volume_trend',
        # 风险调整类
        'scoring_system.weights.idr': 'weight_idr',

        # ====================================================================
        # 向后兼容：旧版权重配置（已废弃，但仍支持加载）
        # ====================================================================
        'scoring_system.mode': 'score_mode',  # 特殊处理
        # V2 旧版
        'scoring_system.weights_v2.core_trend': 'core_trend_weight',
        'scoring_system.weights_v2.trend_quality': 'trend_quality_weight',
        'scoring_system.weights_v2.strength': 'strength_weight',
        'scoring_system.weights_v2.volume': 'volume_weight',
        'scoring_system.weights_v2.idr': 'idr_weight',
        'scoring_system.weights_v2.core_trend_sub.excess_return_20d': 'excess_return_20d_weight',
        'scoring_system.weights_v2.core_trend_sub.excess_return_60d': 'excess_return_60d_weight',
        # V1 旧版
        'scoring_system.weights_v1_legacy.primary.weight': 'primary_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.adx_score': 'adx_score_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.trend_consistency': 'trend_consistency_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.price_efficiency': 'price_efficiency_weight',
        'scoring_system.weights_v1_legacy.primary.sub_weights.liquidity_score': 'liquidity_score_weight',
        'scoring_system.weights_v1_legacy.secondary.weight': 'secondary_weight',
        'scoring_system.weights_v1_legacy.secondary.sub_weights.momentum_3m': 'momentum_3m_score_weight',
        'scoring_system.weights_v1_legacy.secondary.sub_weights.momentum_12m': 'momentum_12m_score_weight',

        # Stage 3: Diversification
        'stage3_diversification.target_portfolio_size': 'target_portfolio_size',
        'stage3_diversification.max_correlation': 'max_correlation',
        'stage3_diversification.min_industries': 'min_industries',

        # Stage 3: Deduplication
        'stage3_diversification.deduplication.enable': 'enable_deduplication',
        'stage3_diversification.deduplication.min_ratio': 'dedup_min_ratio',
        'stage3_diversification.deduplication.thresholds': 'dedup_thresholds',

        # Stage 3: Diversify V2
        'stage3_diversification.diversify_v2.enable': 'diversify_v2',
        'stage3_diversification.diversify_v2.score_diff_threshold': 'score_diff_threshold',

        # Stage 3: Clustering selection (数据驱动的行业分类)
        'stage3_diversification.clustering.enable': 'enable_clustering_selection',
        'stage3_diversification.clustering.method': 'clustering_method',
        'stage3_diversification.clustering.min_score_percentile': 'clustering_min_score_percentile',

        # Stage 3: Industry balance
        'stage3_diversification.balance_industries': 'balance_industries',

        # Output options
        'output_options.verbose': 'verbose',
        'output_options.with_analysis': 'with_analysis',
        'output_options.skip_portfolio_optimization': 'skip_portfolio_optimization',
    }

    @staticmethod
    def load_from_json(json_path: str) -> FilterConfig:
        """从JSON文件加载配置

        Args:
            json_path: JSON配置文件路径

        Returns:
            FilterConfig对象

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误或验证失败
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {json_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件JSON格式错误: {e}")

        # Flatten nested dictionary
        flat_dict = ConfigLoader._flatten_dict(config_dict)

        # Map JSON keys to FilterConfig fields
        mapped_dict = ConfigLoader._map_json_keys(flat_dict)

        # 处理旧版配置到新版的转换
        mapped_dict = ConfigLoader._convert_legacy_weights(mapped_dict, flat_dict)

        # Create config object
        try:
            config = FilterConfig(**mapped_dict)
        except TypeError as e:
            raise ValueError(f"配置参数错误: {e}")

        # Validate configuration
        ConfigLoader.validate(config)

        return config

    @staticmethod
    def _flatten_dict(nested_dict: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        """扁平化嵌套字典

        Example:
            {'stage1': {'min_turnover': 50000}}
            → {'stage1.min_turnover': 50000}
        """
        items = []
        for k, v in nested_dict.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            # 特殊处理：keywords字典需要保持嵌套（行业分类用）
            if isinstance(v, dict) and k not in ['keywords']:
                items.extend(ConfigLoader._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))

        return dict(items)

    @staticmethod
    def _map_json_keys(flat_dict: Dict) -> Dict:
        """将JSON键映射到FilterConfig字段名"""
        result = {}

        for json_key, value in flat_dict.items():
            # Skip metadata fields
            if json_key in ['version', 'description']:
                continue

            # Skip industry keywords
            if json_key == 'industry_classification.keywords':
                continue

            # Map using KEY_MAPPING
            if json_key in ConfigLoader.KEY_MAPPING:
                config_field = ConfigLoader.KEY_MAPPING[json_key]

                # Special handling for score_mode (旧版兼容)
                if config_field == 'score_mode':
                    result['use_optimized_score'] = (value == 'optimized')
                else:
                    result[config_field] = value
            else:
                # Unknown key - print warning but don't fail
                print(f"⚠️ 未知配置键: {json_key}")

        return result

    @staticmethod
    def _convert_legacy_weights(mapped_dict: Dict, flat_dict: Dict) -> Dict:
        """将各种权重配置格式转换为统一的扁平权重

        支持三种格式：
        1. 新版层级格式（V3）: weights.trend.weight + weights.trend.sub_weights.*
        2. 新版扁平格式: weights.adx_score 等直接设置
        3. 旧版V1/V2格式: weights_v1_legacy.* 或 weights_v2.*
        """
        # 检查是否已设置新版扁平权重
        new_flat_weights_set = any(
            mapped_dict.get(f'weight_{ind}', 0) > 0
            for ind in ['adx_score', 'trend_consistency', 'trend_quality',
                       'momentum_3m', 'momentum_12m', 'excess_return_20d',
                       'excess_return_60d', 'liquidity_score', 'price_efficiency',
                       'volume_trend', 'idr']
        )

        if new_flat_weights_set:
            # 已设置新版扁平权重，跳过转换
            return mapped_dict

        # 检查是否使用新版层级格式（V3）
        has_v3_weights = any(
            k.startswith('scoring_system.weights.') and '.weight' in k
            for k in flat_dict.keys()
        )

        if has_v3_weights:
            # 解析V3层级权重格式
            groups = ['trend', 'return', 'liquidity', 'risk_adjusted']
            indicator_groups = {
                'trend': ['adx_score', 'trend_consistency', 'trend_quality'],
                'return': ['momentum_3m', 'momentum_12m', 'excess_return_20d', 'excess_return_60d'],
                'liquidity': ['liquidity_score', 'price_efficiency', 'volume_trend'],
                'risk_adjusted': ['idr'],
            }

            for group in groups:
                group_weight = flat_dict.get(f'scoring_system.weights.{group}.weight', 0.0)
                if group_weight > 0:
                    for indicator in indicator_groups[group]:
                        sub_weight = flat_dict.get(
                            f'scoring_system.weights.{group}.sub_weights.{indicator}', 0.0
                        )
                        final_weight = group_weight * sub_weight
                        if final_weight > 0:
                            mapped_dict[f'weight_{indicator}'] = final_weight

            return mapped_dict

        # 检查是否使用旧版V1/V2配置
        mode = flat_dict.get('scoring_system.mode', 'legacy')

        if mode == 'legacy':
            # 转换V1旧版权重到新版
            primary_w = mapped_dict.get('primary_weight', 0.80)
            secondary_w = mapped_dict.get('secondary_weight', 0.20)
            adx_w = mapped_dict.get('adx_score_weight', 0.40)
            tc_w = mapped_dict.get('trend_consistency_weight', 0.30)
            pe_w = mapped_dict.get('price_efficiency_weight', 0.20)
            liq_w = mapped_dict.get('liquidity_score_weight', 0.10)
            m3_w = mapped_dict.get('momentum_3m_score_weight', 0.30)
            m12_w = mapped_dict.get('momentum_12m_score_weight', 0.70)

            mapped_dict['weight_adx_score'] = primary_w * adx_w
            mapped_dict['weight_trend_consistency'] = primary_w * tc_w
            mapped_dict['weight_price_efficiency'] = primary_w * pe_w
            mapped_dict['weight_liquidity_score'] = primary_w * liq_w
            mapped_dict['weight_momentum_3m'] = secondary_w * m3_w
            mapped_dict['weight_momentum_12m'] = secondary_w * m12_w

        elif mode == 'optimized':
            # 转换V2旧版权重到新版
            core_trend_w = mapped_dict.get('core_trend_weight', 0.40)
            tq_w = mapped_dict.get('trend_quality_weight', 0.35)
            strength_w = mapped_dict.get('strength_weight', 0.15)
            volume_w = mapped_dict.get('volume_weight', 0.10)
            idr_w = mapped_dict.get('idr_weight', 0.0)
            er20_sub = mapped_dict.get('excess_return_20d_weight', 0.40)
            er60_sub = mapped_dict.get('excess_return_60d_weight', 0.60)

            mapped_dict['weight_adx_score'] = strength_w
            mapped_dict['weight_trend_quality'] = tq_w
            mapped_dict['weight_excess_return_20d'] = core_trend_w * er20_sub
            mapped_dict['weight_excess_return_60d'] = core_trend_w * er60_sub
            mapped_dict['weight_volume_trend'] = volume_w
            mapped_dict['weight_idr'] = idr_w

        return mapped_dict

    @staticmethod
    def validate(config: FilterConfig):
        """验证配置参数

        Raises:
            ValueError: 配置验证失败
        """
        errors = []

        # 验证统一权重
        total_weight = config.get_total_weight()
        if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
            errors.append(
                f"评分权重总和必须为1.0，当前为{total_weight:.4f}"
            )

        # Validate percentile ranges
        if not (0 <= config.adx_percentile <= 100):
            errors.append(
                f"adx_percentile必须在[0, 100]范围内，当前为{config.adx_percentile}"
            )

        if not (0 <= config.ret_dd_percentile <= 100):
            errors.append(
                f"ret_dd_percentile必须在[0, 100]范围内，当前为{config.ret_dd_percentile}"
            )

        # Validate MA periods
        if config.ma_short >= config.ma_long:
            errors.append(
                f"ma_short ({config.ma_short})必须小于ma_long ({config.ma_long})"
            )

        # Validate volatility range
        if config.min_volatility >= config.max_volatility:
            errors.append(
                f"min_volatility ({config.min_volatility})必须小于max_volatility ({config.max_volatility})"
            )

        # Validate correlation threshold
        if not (0 <= config.max_correlation <= 1):
            errors.append(
                f"max_correlation必须在[0, 1]范围内，当前为{config.max_correlation}"
            )

        # Validate positive integers
        if config.target_portfolio_size <= 0:
            errors.append(f"target_portfolio_size必须大于0，当前为{config.target_portfolio_size}")

        if config.min_listing_days < 0:
            errors.append(f"min_listing_days不能为负数，当前为{config.min_listing_days}")

        if errors:
            raise ValueError("配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors))

    @staticmethod
    def merge_with_cli_args(config: FilterConfig, args) -> FilterConfig:
        """将CLI参数合并到配置中（CLI优先级最高）"""
        cli_overrides = {
            'min_turnover': getattr(args, 'min_turnover', None),
            'min_listing_days': getattr(args, 'min_listing_days', None),
            'adx_percentile': getattr(args, 'adx_percentile', None),
            'ret_dd_percentile': getattr(args, 'ret_dd_percentile', None),
            'min_volatility': getattr(args, 'min_volatility', None),
            'max_volatility': getattr(args, 'max_volatility', None),
            'ma_short': getattr(args, 'ma_short', None),
            'ma_long': getattr(args, 'ma_long', None),
            'adx_period': getattr(args, 'adx_period', None),
            'target_portfolio_size': getattr(args, 'target_size', None),
            'max_correlation': getattr(args, 'max_correlation', None),
            'data_dir': getattr(args, 'data_dir', None),
            'dedup_min_ratio': getattr(args, 'dedup_min_ratio', None),
            'score_diff_threshold': getattr(args, 'score_diff_threshold', None),
        }

        # Apply overrides
        for key, value in cli_overrides.items():
            if value is not None:
                setattr(config, key, value)

        # Handle boolean flags
        if getattr(args, 'enable_ma_filter', False):
            config.enable_ma_backtest_filter = True
        elif getattr(args, 'disable_ma_filter', False):
            config.enable_ma_backtest_filter = False

        if getattr(args, 'disable_unbiased_scoring', False):
            config.enable_unbiased_scoring = False
        elif getattr(args, 'enable_unbiased_scoring', False):
            config.enable_unbiased_scoring = True

        if getattr(args, 'momentum_min_positive', False):
            config.momentum_min_positive = True

        if getattr(args, 'skip_stage2_filtering', False):
            config.skip_stage2_percentile_filtering = True

        if getattr(args, 'diversify_v2', False):
            config.diversify_v2 = True

        # Re-validate after merge
        ConfigLoader.validate(config)

        return config

    @staticmethod
    def print_all_params(config: FilterConfig, title: str = "完整配置参数"):
        """打印所有配置参数（用于调试和验收）"""
        print("=" * 80)
        print(f" {title}")
        print("=" * 80)
        print()

        print("📁 路径配置:")
        print(f"  data_dir: {config.data_dir}")
        print(f"  output_path: {config.output_path}")
        print()

        print("🔍 第一级 - 初筛参数:")
        print(f"  min_turnover: {config.min_turnover:,.0f} 元")
        print(f"  min_listing_days: {config.min_listing_days} 天")
        print(f"  turnover_lookback_days: {config.turnover_lookback_days} 天")
        print()

        print("🎯 第二级 - 核心筛选参数:")
        print(f"  ADX:")
        print(f"    period: {config.adx_period}")
        print(f"    lookback_days: {config.adx_lookback_days}")
        print(f"    percentile: {config.adx_percentile}%")
        print(f"  双均线回测:")
        print(f"    enable: {config.enable_ma_backtest_filter}")
        print(f"    ma_short: {config.ma_short}")
        print(f"    ma_long: {config.ma_long}")
        print(f"  波动率:")
        print(f"    min: {config.min_volatility:.2f}")
        print(f"    max: {config.max_volatility:.2f}")
        print(f"  筛选模式:")
        print(f"    skip_stage2_percentile_filtering: {config.skip_stage2_percentile_filtering}")
        print(f"    skip_stage2_range_filtering: {config.skip_stage2_range_filtering}")
        print()

        print("📊 评分系统:")
        print(f"  enable_unbiased_scoring: {config.enable_unbiased_scoring}")
        print(f"  benchmark_ts_code: {config.benchmark_ts_code}")
        print(f"  窗口参数:")
        print(f"    excess_return_short: {config.excess_return_short_window}")
        print(f"    excess_return_long: {config.excess_return_long_window}")
        print(f"    trend_quality: {config.trend_quality_window}")
        print(f"    trend_consistency: {config.trend_consistency_window}")
        print(f"    price_efficiency: {config.price_efficiency_window}")
        print(f"    liquidity_score: {config.liquidity_score_window}")
        print(f"    volume_short: {config.volume_short_window}")
        print(f"    volume_long: {config.volume_long_window}")
        print()

        print("⚖️ 评分权重（统一配置）:")
        weights = config.get_scoring_weights()
        active_weights = {k: v for k, v in weights.items() if v > 0}
        if active_weights:
            for name, weight in active_weights.items():
                print(f"    {name}: {weight:.2%}")
            print(f"  总和: {config.get_total_weight():.2%}")
        else:
            print("    (未配置权重)")
        print()

        if config.needs_benchmark():
            print(f"  📌 需要基准数据: 是 (超额收益类指标已启用)")
        print()

        print("🎲 第三级 - 分散化参数:")
        print(f"  target_portfolio_size: {config.target_portfolio_size}")
        print(f"  max_correlation: {config.max_correlation}")
        print(f"  min_industries: {config.min_industries}")
        print(f"  去重:")
        print(f"    enable: {config.enable_deduplication}")
        print(f"    min_ratio: {config.dedup_min_ratio}")
        print(f"    thresholds: {config.dedup_thresholds}")
        print(f"  V2分散逻辑:")
        print(f"    enable: {config.diversify_v2}")
        print(f"    score_diff_threshold: {config.score_diff_threshold}")
        print(f"  聚类选择:")
        print(f"    enable: {config.enable_clustering_selection}")
        print(f"    method: {config.clustering_method}")
        print(f"    min_score_percentile: {config.clustering_min_score_percentile}")
        print(f"  balance_industries: {config.balance_industries}")
        print()
        print("=" * 80)
