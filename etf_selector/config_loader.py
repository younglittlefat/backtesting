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
        'paths.output_dir': 'output_dir',
        'paths.output_filename': 'output_filename',

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

        # Scoring system
        'scoring_system.enable_unbiased_scoring': 'enable_unbiased_scoring',
        'scoring_system.mode': 'score_mode',  # Special: convert to use_optimized_score
        'scoring_system.benchmark.ts_code': 'benchmark_ts_code',

        # Scoring windows
        'scoring_system.windows.excess_return_short': 'excess_return_short_window',
        'scoring_system.windows.excess_return_long': 'excess_return_long_window',
        'scoring_system.windows.trend_quality': 'trend_quality_window',
        'scoring_system.windows.trend_consistency': 'trend_consistency_window',
        'scoring_system.windows.price_efficiency': 'price_efficiency_window',
        'scoring_system.windows.volume_short': 'volume_short_window',
        'scoring_system.windows.volume_long': 'volume_long_window',
        'scoring_system.windows.liquidity_score': 'liquidity_score_window',

        # Weights V2 (optimized mode)
        'scoring_system.weights_v2.core_trend': 'core_trend_weight',
        'scoring_system.weights_v2.trend_quality': 'trend_quality_weight',
        'scoring_system.weights_v2.strength': 'strength_weight',
        'scoring_system.weights_v2.volume': 'volume_weight',
        'scoring_system.weights_v2.idr': 'idr_weight',
        'scoring_system.weights_v2.core_trend_sub.excess_return_20d': 'excess_return_20d_weight',
        'scoring_system.weights_v2.core_trend_sub.excess_return_60d': 'excess_return_60d_weight',

        # Weights V1 (legacy mode)
        'scoring_system.weights_v1_legacy.primary': 'primary_weight',
        'scoring_system.weights_v1_legacy.secondary': 'secondary_weight',
        'scoring_system.weights_v1_legacy.adx_score': 'adx_score_weight',
        'scoring_system.weights_v1_legacy.trend_consistency': 'trend_consistency_weight',
        'scoring_system.weights_v1_legacy.price_efficiency': 'price_efficiency_weight',
        'scoring_system.weights_v1_legacy.liquidity_score': 'liquidity_score_weight',
        'scoring_system.weights_v1_legacy.momentum_3m': 'momentum_3m_score_weight',
        'scoring_system.weights_v1_legacy.momentum_12m': 'momentum_12m_score_weight',

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

        Args:
            nested_dict: 嵌套字典
            parent_key: 父键前缀
            sep: 分隔符

        Returns:
            扁平化后的字典
        """
        items = []
        for k, v in nested_dict.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            # 特殊处理：keywords字典、core_trend_sub需要保持嵌套
            if isinstance(v, dict) and k not in ['keywords', 'core_trend_sub']:
                items.extend(ConfigLoader._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))

        return dict(items)

    @staticmethod
    def _map_json_keys(flat_dict: Dict) -> Dict:
        """将JSON键映射到FilterConfig字段名

        Args:
            flat_dict: 扁平化后的字典

        Returns:
            映射后的字典，键为FilterConfig字段名
        """
        result = {}

        for json_key, value in flat_dict.items():
            # Skip metadata fields
            if json_key in ['version', 'description']:
                continue

            # Skip industry keywords (not part of FilterConfig, uses DEFAULT_INDUSTRY_KEYWORDS instead)
            if json_key == 'industry_classification.keywords':
                continue

            # Map using KEY_MAPPING
            if json_key in ConfigLoader.KEY_MAPPING:
                config_field = ConfigLoader.KEY_MAPPING[json_key]

                # Special handling for score_mode
                if config_field == 'score_mode':
                    result['use_optimized_score'] = (value == 'optimized')
                else:
                    result[config_field] = value
            else:
                # Unknown key - print warning but don't fail
                print(f"⚠️ 未知配置键: {json_key}")

        return result

    @staticmethod
    def validate(config: FilterConfig):
        """验证配置参数

        Raises:
            ValueError: 配置验证失败
        """
        errors = []

        # Validate V2 weights (if using optimized mode)
        if config.use_optimized_score:
            v2_weights_sum = (
                config.core_trend_weight +
                config.trend_quality_weight +
                config.strength_weight +
                config.volume_weight +
                config.idr_weight
            )
            if abs(v2_weights_sum - 1.0) > 0.01:
                errors.append(
                    f"V2权重总和必须为1.0，当前为{v2_weights_sum:.4f}"
                )

            core_trend_sub_sum = (
                config.excess_return_20d_weight +
                config.excess_return_60d_weight
            )
            if abs(core_trend_sub_sum - 1.0) > 0.01:
                errors.append(
                    f"核心趋势子权重总和必须为1.0，当前为{core_trend_sub_sum:.4f}"
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
        """将CLI参数合并到配置中（CLI优先级最高）

        Args:
            config: 基础配置对象
            args: argparse.Namespace命令行参数

        Returns:
            合并后的配置对象
        """
        # CLI参数覆盖（使用getattr安全获取）
        # 使用argparse.SUPPRESS后，未显式传递的参数不会出现在args中，getattr返回None
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

        if hasattr(args, 'score_mode') and args.score_mode:
            config.use_optimized_score = (args.score_mode == 'optimized')

        if getattr(args, 'momentum_min_positive', False):
            config.momentum_min_positive = True

        if getattr(args, 'skip_stage2_filtering', False):
            config.skip_stage2_percentile_filtering = True

        # diversify_v2是action='store_true'，所以直接检查
        if getattr(args, 'diversify_v2', False):
            config.diversify_v2 = True

        # Re-validate after merge
        ConfigLoader.validate(config)

        return config

    @staticmethod
    def print_all_params(config: FilterConfig, title: str = "完整配置参数"):
        """打印所有配置参数（用于调试和验收）

        Args:
            config: 配置对象
            title: 标题
        """
        print("=" * 80)
        print(f" {title}")
        print("=" * 80)
        print()

        print("📁 路径配置:")
        print(f"  data_dir: {config.data_dir}")
        print(f"  output_dir: {config.output_dir}")
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
        print(f"    percentile: {config.adx_percentile}% (保留前{100-config.adx_percentile:.0f}%)")
        print(f"  双均线回测:")
        print(f"    enable: {config.enable_ma_backtest_filter}")
        print(f"    ma_short: {config.ma_short}")
        print(f"    ma_long: {config.ma_long}")
        print(f"    ret_dd_percentile: {config.ret_dd_percentile}%")
        print(f"  波动率:")
        print(f"    min: {config.min_volatility:.2f}")
        print(f"    max: {config.max_volatility:.2f}")
        print(f"    lookback_days: {config.volatility_lookback_days}")
        print(f"  动量:")
        print(f"    periods: {config.momentum_periods}")
        print(f"    min_positive: {config.momentum_min_positive}")
        print(f"  筛选模式:")
        print(f"    skip_stage2_percentile_filtering: {config.skip_stage2_percentile_filtering}")
        print(f"    skip_stage2_range_filtering: {config.skip_stage2_range_filtering}")
        print()

        print("📊 评分系统:")
        print(f"  enable_unbiased_scoring: {config.enable_unbiased_scoring}")
        print(f"  mode: {'optimized' if config.use_optimized_score else 'legacy'}")
        print(f"  benchmark_ts_code: {config.benchmark_ts_code}")
        print(f"  窗口参数:")
        print(f"    excess_return_short_window: {config.excess_return_short_window}")
        print(f"    excess_return_long_window: {config.excess_return_long_window}")
        print(f"    trend_quality_window: {config.trend_quality_window}")
        print(f"    trend_consistency_window: {config.trend_consistency_window}")
        print(f"    price_efficiency_window: {config.price_efficiency_window}")
        print(f"    volume_short_window: {config.volume_short_window}")
        print(f"    volume_long_window: {config.volume_long_window}")
        print(f"    liquidity_score_window: {config.liquidity_score_window}")

        if config.use_optimized_score:
            print(f"  V2权重 (优化版):")
            print(f"    core_trend_weight: {config.core_trend_weight:.2f}")
            print(f"    trend_quality_weight: {config.trend_quality_weight:.2f}")
            print(f"    strength_weight: {config.strength_weight:.2f}")
            print(f"    volume_weight: {config.volume_weight:.2f}")
            print(f"    idr_weight: {config.idr_weight:.2f}")
            print(f"    核心趋势子权重:")
            print(f"      excess_return_20d_weight: {config.excess_return_20d_weight:.2f}")
            print(f"      excess_return_60d_weight: {config.excess_return_60d_weight:.2f}")
        else:
            print(f"  V1权重 (旧版):")
            print(f"    primary_weight: {config.primary_weight:.2f}")
            print(f"    secondary_weight: {config.secondary_weight:.2f}")
            print(f"    adx_score_weight: {config.adx_score_weight:.2f}")
            print(f"    trend_consistency_weight: {config.trend_consistency_weight:.2f}")
            print(f"    price_efficiency_weight: {config.price_efficiency_weight:.2f}")
            print(f"    liquidity_score_weight: {config.liquidity_score_weight:.2f}")
            print(f"    momentum_3m_score_weight: {config.momentum_3m_score_weight:.2f}")
            print(f"    momentum_12m_score_weight: {config.momentum_12m_score_weight:.2f}")
        print()

        print("🎲 第三级 - 分散化参数:")
        print(f"  target_portfolio_size: {config.target_portfolio_size}")
        print(f"  max_correlation: {config.max_correlation}")
        print(f"  min_industries: {config.min_industries}")

        # 如果有dedup_thresholds属性（新增字段）
        if hasattr(config, 'enable_deduplication'):
            print(f"  去重:")
            print(f"    enable: {config.enable_deduplication}")
            if hasattr(config, 'dedup_min_ratio'):
                print(f"    min_ratio: {config.dedup_min_ratio}")
            if hasattr(config, 'dedup_thresholds'):
                print(f"    thresholds: {config.dedup_thresholds}")

        if hasattr(config, 'diversify_v2'):
            print(f"  V2分散逻辑:")
            print(f"    enable: {config.diversify_v2}")
            if hasattr(config, 'score_diff_threshold'):
                print(f"    score_diff_threshold: {config.score_diff_threshold}")

        if hasattr(config, 'balance_industries'):
            print(f"  balance_industries: {config.balance_industries}")

        print()
        print("=" * 80)
