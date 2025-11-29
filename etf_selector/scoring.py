"""
综合评分算法模块

实现面向A股快速轮动特性的综合评分，突出超额收益、趋势质量、趋势强度和资金动能。

评分体系（Q&A2优化版）：
- 核心趋势（40%）：20/60日超额收益（相对沪深300或基准ETF）
- 趋势质量（35%）：60日对数价格回归R^2，可与趋势一致性、价格效率融合
- 趋势强度（15%）：ADX
- 资金动能（10%）：成交量趋势（20日均量 / 60日均量）
"""
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class ScoringWeights:
    """评分权重配置（优化版）"""

    # 顶层权重
    core_trend_weight: float = 0.40
    trend_quality_weight: float = 0.35
    strength_weight: float = 0.15
    volume_weight: float = 0.10
    idr_weight: float = 0.0  # IDR权重，默认0（不启用）

    # 核心趋势子权重（20日 / 60日超额收益）
    excess_return_20d_weight: float = 0.40
    excess_return_60d_weight: float = 0.60

    def __post_init__(self):
        """验证权重约束"""
        top_level_sum = (
            self.core_trend_weight +
            self.trend_quality_weight +
            self.strength_weight +
            self.volume_weight +
            self.idr_weight
        )
        assert abs(top_level_sum - 1.0) < 0.01, f"总权重应为1，实际为{top_level_sum}"

        core_trend_sum = self.excess_return_20d_weight + self.excess_return_60d_weight
        assert abs(core_trend_sum - 1.0) < 0.01, f"核心趋势子权重应为1，实际为{core_trend_sum}"


class UnbiasedScorer:
    """无偏综合评分器"""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        初始化评分器

        Args:
            weights: 评分权重配置，默认None使用默认权重
        """
        self.weights = weights if weights is not None else ScoringWeights()

    def calculate_core_trend_score(self, indicators: Dict[str, float]) -> float:
        """核心趋势：20/60日超额收益加权。"""
        short_excess = self._get_valid_score(indicators.get('excess_return_20d_normalized', 0.0))
        long_excess = self._get_valid_score(indicators.get('excess_return_60d_normalized', 0.0))

        core_trend_score = (
            self.weights.excess_return_20d_weight * short_excess +
            self.weights.excess_return_60d_weight * long_excess
        )
        return float(core_trend_score)

    def calculate_trend_quality_score(self, indicators: Dict[str, float]) -> float:
        """趋势质量：60日R^2/趋势一致性/价格效率融合后标准化的分数。"""
        return self._get_valid_score(indicators.get('trend_quality_normalized', 0.0))

    def calculate_strength_score(self, indicators: Dict[str, float]) -> float:
        """趋势强度：ADX标准化分数。"""
        return self._get_valid_score(indicators.get('adx_mean_normalized', 0.0))

    def calculate_volume_score(self, indicators: Dict[str, float]) -> float:
        """资金动能：成交量趋势标准化分数。"""
        return self._get_valid_score(indicators.get('volume_trend_normalized', 0.0))

    def calculate_idr_score(self, indicators: Dict[str, float]) -> float:
        """IDR：风险调整后超额收益标准化分数。"""
        return self._get_valid_score(indicators.get('idr_normalized', 0.0))

    def calculate_final_score(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """
        计算最终综合评分

        Args:
            indicators: 包含所有标准化指标的字典

        Returns:
            评分结果字典，包含：
                - core_trend_score: 核心趋势评分
                - trend_quality_score: 趋势质量评分
                - strength_score: 趋势强度评分
                - volume_score: 资金动能评分
                - idr_score: IDR评分（风险调整后超额收益）
                - final_score: 综合评分
        """
        core_trend_score = self.calculate_core_trend_score(indicators)
        trend_quality_score = self.calculate_trend_quality_score(indicators)
        strength_score = self.calculate_strength_score(indicators)
        volume_score = self.calculate_volume_score(indicators)
        idr_score = self.calculate_idr_score(indicators)

        final_score = (
            self.weights.core_trend_weight * core_trend_score +
            self.weights.trend_quality_weight * trend_quality_score +
            self.weights.strength_weight * strength_score +
            self.weights.volume_weight * volume_score +
            self.weights.idr_weight * idr_score
        )

        return {
            'core_trend_score': core_trend_score,
            'trend_quality_score': trend_quality_score,
            'strength_score': strength_score,
            'volume_score': volume_score,
            'idr_score': idr_score,
            'final_score': final_score
        }

    @staticmethod
    def _get_valid_score(value: float) -> float:
        """验证并返回有效的评分值"""
        if pd.isna(value) or np.isnan(value) or np.isinf(value):
            return 0.0
        return float(np.clip(value, 0.0, 1.0))


@dataclass
class LegacyScoringWeights:
    """旧版评分权重配置（原ADx+趋势一致性+效率+流动性 + 3M/12M动量）"""

    primary_weight: float = 0.80
    secondary_weight: float = 0.20
    adx_weight: float = 0.40
    trend_consistency_weight: float = 0.30
    price_efficiency_weight: float = 0.20
    liquidity_weight: float = 0.10
    momentum_3m_weight: float = 0.30
    momentum_12m_weight: float = 0.70

    def __post_init__(self):
        """验证权重和为1"""
        primary_sum = (
            self.adx_weight +
            self.trend_consistency_weight +
            self.price_efficiency_weight +
            self.liquidity_weight
        )
        assert abs(primary_sum - 1.0) < 0.01, f"主要指标权重和应为1，实际为{primary_sum}"

        secondary_sum = self.momentum_3m_weight + self.momentum_12m_weight
        assert abs(secondary_sum - 1.0) < 0.01, f"次要指标权重和应为1，实际为{secondary_sum}"

        total_sum = self.primary_weight + self.secondary_weight
        assert abs(total_sum - 1.0) < 0.01, f"总权重和应为1，实际为{total_sum}"


class LegacyUnbiasedScorer:
    """旧版无偏综合评分器（保持与原公式兼容）"""

    def __init__(self, weights: Optional[LegacyScoringWeights] = None):
        self.weights = weights if weights is not None else LegacyScoringWeights()

    def calculate_primary_score(self, indicators: Dict[str, float]) -> float:
        adx = UnbiasedScorer._get_valid_score(indicators.get('adx_mean_normalized', 0.0))
        trend = UnbiasedScorer._get_valid_score(indicators.get('trend_consistency', 0.0))
        efficiency = UnbiasedScorer._get_valid_score(indicators.get('price_efficiency', 0.0))
        liquidity = UnbiasedScorer._get_valid_score(indicators.get('liquidity_score', 0.0))

        primary_score = (
            self.weights.adx_weight * adx +
            self.weights.trend_consistency_weight * trend +
            self.weights.price_efficiency_weight * efficiency +
            self.weights.liquidity_weight * liquidity
        )
        return float(primary_score)

    def calculate_secondary_score(self, indicators: Dict[str, float]) -> float:
        momentum_3m = UnbiasedScorer._get_valid_score(indicators.get('momentum_3m_normalized', 0.0))
        momentum_12m = UnbiasedScorer._get_valid_score(indicators.get('momentum_12m_normalized', 0.0))

        secondary_score = (
            self.weights.momentum_3m_weight * momentum_3m +
            self.weights.momentum_12m_weight * momentum_12m
        )
        return float(secondary_score)

    def calculate_final_score(self, indicators: Dict[str, float]) -> Dict[str, float]:
        primary_score = self.calculate_primary_score(indicators)
        secondary_score = self.calculate_secondary_score(indicators)

        final_score = (
            self.weights.primary_weight * primary_score +
            self.weights.secondary_weight * secondary_score
        )

        return {
            'primary_score': primary_score,
            'secondary_score': secondary_score,
            'final_score': final_score
        }


def normalize_indicators(
    df: pd.DataFrame,
    columns: list,
    method: str = 'minmax'
) -> pd.DataFrame:
    """
    标准化指标到0-1区间

    Args:
        df: 包含指标的DataFrame
        columns: 需要标准化的列名列表
        method: 标准化方法
            - 'minmax': 最小-最大标准化
            - 'percentile': 百分位标准化
            - 'zscore': Z-score标准化后映射到0-1

    Returns:
        标准化后的DataFrame（新增_normalized后缀的列）
    """
    df_normalized = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        values = df[col].values
        valid_values = values[~np.isnan(values)]

        if len(valid_values) == 0:
            df_normalized[f'{col}_normalized'] = 0.0
            continue

        if method == 'minmax':
            # 最小-最大标准化
            min_val = valid_values.min()
            max_val = valid_values.max()

            if max_val > min_val:
                normalized = (values - min_val) / (max_val - min_val)
            else:
                normalized = np.full_like(values, 0.5, dtype=float)

        elif method == 'percentile':
            # 百分位标准化（基于排名）
            normalized = np.array([
                np.sum(valid_values <= v) / len(valid_values)
                if not np.isnan(v) else np.nan
                for v in values
            ])

        elif method == 'zscore':
            # Z-score标准化后使用sigmoid映射到0-1
            mean = valid_values.mean()
            std = valid_values.std()

            if std > 0:
                z_scores = (values - mean) / std
                # Sigmoid: 1 / (1 + exp(-z))
                normalized = 1 / (1 + np.exp(-z_scores))
            else:
                normalized = np.full_like(values, 0.5, dtype=float)

        else:
            raise ValueError(f"Unknown normalization method: {method}")

        df_normalized[f'{col}_normalized'] = normalized

    return df_normalized


def calculate_etf_scores(
    metrics_df: pd.DataFrame,
    scorer: Optional[UnbiasedScorer] = None,
    normalize_method: str = 'percentile'
) -> pd.DataFrame:
    """
    批量计算ETF的综合评分

    Args:
        metrics_df: 包含所有指标的DataFrame，必须包含以下列：
            - excess_return_20d: 20日超额收益
            - excess_return_60d: 60日超额收益
            - trend_quality: 趋势质量（R^2等融合指标）
            - adx_mean: ADX均值
            - volume_trend: 成交量趋势（20日均量/60日均量）
            - idr: IDR指标（可选，风险调整后超额收益）
        scorer: 评分器实例，默认None使用默认权重
        normalize_method: 标准化方法

    Returns:
        添加了评分列的DataFrame
    """
    if scorer is None:
        scorer = UnbiasedScorer()

    # 需要标准化的列
    columns_to_normalize = [
        'excess_return_20d',
        'excess_return_60d',
        'trend_quality',
        'adx_mean',
        'volume_trend',
        'idr'
    ]

    # 标准化指标
    df_normalized = normalize_indicators(
        metrics_df,
        columns=columns_to_normalize,
        method=normalize_method
    )

    # 计算评分
    scores = []
    for _, row in df_normalized.iterrows():
        indicators = {
            'excess_return_20d_normalized': row.get('excess_return_20d_normalized', 0.0),
            'excess_return_60d_normalized': row.get('excess_return_60d_normalized', 0.0),
            'trend_quality_normalized': row.get('trend_quality_normalized', 0.0),
            'adx_mean_normalized': row.get('adx_mean_normalized', 0.0),
            'volume_trend_normalized': row.get('volume_trend_normalized', 0.0),
            'idr_normalized': row.get('idr_normalized', 0.0),
        }

        score_dict = scorer.calculate_final_score(indicators)
        scores.append(score_dict)

    # 添加评分列
    df_normalized['core_trend_score'] = [s['core_trend_score'] for s in scores]
    df_normalized['trend_quality_score'] = [s['trend_quality_score'] for s in scores]
    df_normalized['strength_score'] = [s['strength_score'] for s in scores]
    df_normalized['volume_score'] = [s['volume_score'] for s in scores]
    df_normalized['idr_score'] = [s['idr_score'] for s in scores]
    df_normalized['final_score'] = [s['final_score'] for s in scores]

    # 按最终评分排序
    df_normalized = df_normalized.sort_values('final_score', ascending=False).reset_index(drop=True)

    return df_normalized


def calculate_legacy_etf_scores(
    metrics_df: pd.DataFrame,
    scorer: Optional[LegacyUnbiasedScorer] = None,
    normalize_method: str = 'percentile'
) -> pd.DataFrame:
    """
    批量计算ETF的综合评分（旧版公式）

    Args:
        metrics_df: 包含所有指标的DataFrame，必须包含以下列：
            - adx_mean: ADX均值
            - trend_consistency: 趋势一致性
            - price_efficiency: 价格效率
            - liquidity_score: 流动性评分
            - momentum_3m: 3个月动量
            - momentum_12m: 12个月动量
        scorer: 评分器实例，默认None使用默认权重
        normalize_method: 标准化方法

    Returns:
        添加了评分列的DataFrame
    """
    if scorer is None:
        scorer = LegacyUnbiasedScorer()

    columns_to_normalize = [
        'adx_mean',
        'trend_consistency',
        'price_efficiency',
        'liquidity_score',
        'momentum_3m',
        'momentum_12m'
    ]

    df_normalized = normalize_indicators(
        metrics_df,
        columns=columns_to_normalize,
        method=normalize_method
    )

    scores = []
    for _, row in df_normalized.iterrows():
        indicators = {
            'adx_mean_normalized': row.get('adx_mean_normalized', 0.0),
            'trend_consistency': row.get('trend_consistency', 0.0),
            'price_efficiency': row.get('price_efficiency', 0.0),
            'liquidity_score': row.get('liquidity_score', 0.0),
            'momentum_3m_normalized': row.get('momentum_3m_normalized', 0.0),
            'momentum_12m_normalized': row.get('momentum_12m_normalized', 0.0),
        }

        score_dict = scorer.calculate_final_score(indicators)
        scores.append(score_dict)

    df_normalized['primary_score'] = [s['primary_score'] for s in scores]
    df_normalized['secondary_score'] = [s['secondary_score'] for s in scores]
    df_normalized['final_score'] = [s['final_score'] for s in scores]

    df_normalized = df_normalized.sort_values('final_score', ascending=False).reset_index(drop=True)
    return df_normalized


def create_custom_scorer(
    core_trend_weight: float = 0.40,
    trend_quality_weight: float = 0.35,
    strength_weight: float = 0.15,
    volume_weight: float = 0.10,
    idr_weight: float = 0.0,
    excess_return_20d_weight: float = 0.40,
    excess_return_60d_weight: float = 0.60
) -> UnbiasedScorer:
    """
    创建自定义权重的评分器

    Args:
        core_trend_weight: 核心趋势权重
        trend_quality_weight: 趋势质量权重
        strength_weight: 趋势强度权重
        volume_weight: 资金动能权重
        idr_weight: IDR权重（风险调整后超额收益）
        excess_return_20d_weight: 核心趋势中20日超额收益权重
        excess_return_60d_weight: 核心趋势中60日超额收益权重

    Returns:
        配置好的评分器实例
    """
    weights = ScoringWeights(
        core_trend_weight=core_trend_weight,
        trend_quality_weight=trend_quality_weight,
        strength_weight=strength_weight,
        volume_weight=volume_weight,
        idr_weight=idr_weight,
        excess_return_20d_weight=excess_return_20d_weight,
        excess_return_60d_weight=excess_return_60d_weight
    )

    return UnbiasedScorer(weights)


def create_legacy_scorer(
    primary_weight: float = 0.80,
    secondary_weight: float = 0.20,
    adx_weight: float = 0.40,
    trend_consistency_weight: float = 0.30,
    price_efficiency_weight: float = 0.20,
    liquidity_weight: float = 0.10,
    momentum_3m_weight: float = 0.30,
    momentum_12m_weight: float = 0.70
) -> LegacyUnbiasedScorer:
    """创建旧版公式的评分器。"""
    weights = LegacyScoringWeights(
        primary_weight=primary_weight,
        secondary_weight=secondary_weight,
        adx_weight=adx_weight,
        trend_consistency_weight=trend_consistency_weight,
        price_efficiency_weight=price_efficiency_weight,
        liquidity_weight=liquidity_weight,
        momentum_3m_weight=momentum_3m_weight,
        momentum_12m_weight=momentum_12m_weight
    )
    return LegacyUnbiasedScorer(weights)
