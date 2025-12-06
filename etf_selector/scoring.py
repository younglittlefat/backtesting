"""
统一评分算法模块

将所有可用指标整合到一个评分系统中，通过权重配置灵活组合。

可用指标（共11个）：
├── 趋势类
│   ├── adx_score: ADX趋势强度
│   ├── trend_consistency: 趋势一致性（价格方向占比）
│   └── trend_quality: 趋势质量（R²回归拟合度）
├── 收益类
│   ├── momentum_3m: 3个月动量
│   ├── momentum_12m: 12个月动量
│   ├── excess_return_20d: 20日超额收益（需要基准）
│   └── excess_return_60d: 60日超额收益（需要基准）
├── 流动性/成交量类
│   ├── liquidity_score: 流动性评分
│   ├── price_efficiency: 价格效率
│   └── volume_trend: 成交量趋势
└── 风险调整类
    └── idr: 风险调整后超额收益（需要基准）
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List

import numpy as np
import pandas as pd


@dataclass
class ScoringWeights:
    """统一评分权重配置

    所有11个指标的权重，权重为0表示不使用该指标。
    权重总和必须为1.0。

    指标分组：
    - 趋势类: adx_score, trend_consistency, trend_quality
    - 收益类: momentum_3m, momentum_12m, excess_return_20d, excess_return_60d
    - 流动性类: liquidity_score, price_efficiency, volume_trend
    - 风险调整类: idr
    """

    # 趋势类指标权重
    adx_score: float = 0.0
    trend_consistency: float = 0.0
    trend_quality: float = 0.0

    # 收益类指标权重
    momentum_3m: float = 0.0
    momentum_12m: float = 0.0
    excess_return_20d: float = 0.0
    excess_return_60d: float = 0.0

    # 流动性/成交量类指标权重
    liquidity_score: float = 0.0
    price_efficiency: float = 0.0
    volume_trend: float = 0.0

    # 风险调整类指标权重
    idr: float = 0.0

    def __post_init__(self):
        """验证权重约束"""
        total = self.get_total_weight()
        if total > 0 and abs(total - 1.0) > 0.01:
            raise ValueError(f"权重总和必须为1.0，当前为{total:.4f}")

    def get_total_weight(self) -> float:
        """获取所有权重总和"""
        return (
            self.adx_score +
            self.trend_consistency +
            self.trend_quality +
            self.momentum_3m +
            self.momentum_12m +
            self.excess_return_20d +
            self.excess_return_60d +
            self.liquidity_score +
            self.price_efficiency +
            self.volume_trend +
            self.idr
        )

    def get_active_indicators(self) -> List[str]:
        """获取所有权重>0的指标名称"""
        indicators = []
        if self.adx_score > 0:
            indicators.append('adx_score')
        if self.trend_consistency > 0:
            indicators.append('trend_consistency')
        if self.trend_quality > 0:
            indicators.append('trend_quality')
        if self.momentum_3m > 0:
            indicators.append('momentum_3m')
        if self.momentum_12m > 0:
            indicators.append('momentum_12m')
        if self.excess_return_20d > 0:
            indicators.append('excess_return_20d')
        if self.excess_return_60d > 0:
            indicators.append('excess_return_60d')
        if self.liquidity_score > 0:
            indicators.append('liquidity_score')
        if self.price_efficiency > 0:
            indicators.append('price_efficiency')
        if self.volume_trend > 0:
            indicators.append('volume_trend')
        if self.idr > 0:
            indicators.append('idr')
        return indicators

    def needs_benchmark(self) -> bool:
        """是否需要基准数据（超额收益类指标）"""
        return (
            self.excess_return_20d > 0 or
            self.excess_return_60d > 0 or
            self.idr > 0
        )

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            'adx_score': self.adx_score,
            'trend_consistency': self.trend_consistency,
            'trend_quality': self.trend_quality,
            'momentum_3m': self.momentum_3m,
            'momentum_12m': self.momentum_12m,
            'excess_return_20d': self.excess_return_20d,
            'excess_return_60d': self.excess_return_60d,
            'liquidity_score': self.liquidity_score,
            'price_efficiency': self.price_efficiency,
            'volume_trend': self.volume_trend,
            'idr': self.idr,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'ScoringWeights':
        """从字典创建"""
        return cls(
            adx_score=d.get('adx_score', 0.0),
            trend_consistency=d.get('trend_consistency', 0.0),
            trend_quality=d.get('trend_quality', 0.0),
            momentum_3m=d.get('momentum_3m', 0.0),
            momentum_12m=d.get('momentum_12m', 0.0),
            excess_return_20d=d.get('excess_return_20d', 0.0),
            excess_return_60d=d.get('excess_return_60d', 0.0),
            liquidity_score=d.get('liquidity_score', 0.0),
            price_efficiency=d.get('price_efficiency', 0.0),
            volume_trend=d.get('volume_trend', 0.0),
            idr=d.get('idr', 0.0),
        )


class UnifiedScorer:
    """统一评分器

    将所有11个指标整合到一个评分系统中，通过权重配置灵活组合。
    """

    # 指标到数据列的映射（部分指标名称与数据列名不同）
    INDICATOR_COLUMN_MAP = {
        'adx_score': 'adx_mean',  # adx_score 使用 adx_mean 列
        'trend_consistency': 'trend_consistency',
        'trend_quality': 'trend_quality',
        'momentum_3m': 'momentum_3m',
        'momentum_12m': 'momentum_12m',
        'excess_return_20d': 'excess_return_20d',
        'excess_return_60d': 'excess_return_60d',
        'liquidity_score': 'liquidity_score',
        'price_efficiency': 'price_efficiency',
        'volume_trend': 'volume_trend',
        'idr': 'idr',
    }

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        初始化评分器

        Args:
            weights: 评分权重配置，默认None使用默认权重
        """
        self.weights = weights if weights is not None else ScoringWeights()

    def calculate_score(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """
        计算单个ETF的综合评分

        Args:
            indicators: 包含所有标准化指标的字典，键为指标名_normalized

        Returns:
            评分结果字典，包含：
                - 各指标的单项评分（如 adx_score_component）
                - final_score: 综合评分
        """
        result = {}
        final_score = 0.0

        weights_dict = self.weights.to_dict()
        for indicator_name, weight in weights_dict.items():
            if weight > 0:
                # 获取标准化后的值
                normalized_key = f"{indicator_name}_normalized"
                value = self._get_valid_score(indicators.get(normalized_key, 0.0))
                component_score = weight * value
                result[f"{indicator_name}_component"] = component_score
                final_score += component_score

        result['final_score'] = final_score
        return result

    @staticmethod
    def _get_valid_score(value: float) -> float:
        """验证并返回有效的评分值"""
        if pd.isna(value) or np.isnan(value) or np.isinf(value):
            return 0.0
        return float(np.clip(value, 0.0, 1.0))


def normalize_indicators(
    df: pd.DataFrame,
    columns: list,
    method: str = 'percentile'
) -> pd.DataFrame:
    """
    标准化指标到0-1区间

    Args:
        df: 包含指标的DataFrame
        columns: 需要标准化的列名列表
        method: 标准化方法
            - 'minmax': 最小-最大标准化
            - 'percentile': 百分位标准化（推荐，对异常值鲁棒）
            - 'zscore': Z-score标准化后映射到0-1

    Returns:
        标准化后的DataFrame（新增_normalized后缀的列）
    """
    df_normalized = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        values = df[col].values
        valid_mask = ~np.isnan(values)
        valid_values = values[valid_mask]

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


def calculate_unified_scores(
    metrics_df: pd.DataFrame,
    weights: Optional[ScoringWeights] = None,
    normalize_method: str = 'percentile'
) -> pd.DataFrame:
    """
    批量计算ETF的综合评分

    Args:
        metrics_df: 包含所有指标的DataFrame
        weights: 评分权重配置，默认None使用默认权重
        normalize_method: 标准化方法

    Returns:
        添加了评分列的DataFrame
    """
    if weights is None:
        weights = ScoringWeights()

    scorer = UnifiedScorer(weights)

    # 获取需要标准化的列（只处理权重>0的指标）
    active_indicators = weights.get_active_indicators()
    columns_to_normalize = [
        UnifiedScorer.INDICATOR_COLUMN_MAP.get(ind, ind)
        for ind in active_indicators
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
        # 构建指标字典，统一使用指标名作为键
        indicators = {}
        for indicator_name in active_indicators:
            col_name = UnifiedScorer.INDICATOR_COLUMN_MAP.get(indicator_name, indicator_name)
            normalized_key = f"{col_name}_normalized"
            # 存储时使用统一的指标名
            indicators[f"{indicator_name}_normalized"] = row.get(normalized_key, 0.0)

        score_dict = scorer.calculate_score(indicators)
        scores.append(score_dict)

    # 添加评分列
    if scores:
        for key in scores[0].keys():
            df_normalized[key] = [s[key] for s in scores]

    # 按最终评分排序
    if 'final_score' in df_normalized.columns:
        df_normalized = df_normalized.sort_values('final_score', ascending=False).reset_index(drop=True)

    return df_normalized


def create_scorer_from_config(weights_config: Dict[str, float]) -> UnifiedScorer:
    """
    从配置字典创建评分器

    Args:
        weights_config: 权重配置字典，如 {"adx_score": 0.4, "trend_consistency": 0.3, ...}

    Returns:
        配置好的评分器实例
    """
    weights = ScoringWeights.from_dict(weights_config)
    return UnifiedScorer(weights)


# ============================================================================
# 向后兼容：保留旧版类和函数，标记为废弃
# ============================================================================

class LegacyScoringWeights:
    """[已废弃] 旧版评分权重配置，请使用 ScoringWeights"""

    def __init__(
        self,
        primary_weight: float = 0.80,
        secondary_weight: float = 0.20,
        adx_weight: float = 0.40,
        trend_consistency_weight: float = 0.30,
        price_efficiency_weight: float = 0.20,
        liquidity_weight: float = 0.10,
        momentum_3m_weight: float = 0.30,
        momentum_12m_weight: float = 0.70
    ):
        self.primary_weight = primary_weight
        self.secondary_weight = secondary_weight
        self.adx_weight = adx_weight
        self.trend_consistency_weight = trend_consistency_weight
        self.price_efficiency_weight = price_efficiency_weight
        self.liquidity_weight = liquidity_weight
        self.momentum_3m_weight = momentum_3m_weight
        self.momentum_12m_weight = momentum_12m_weight

    def to_unified_weights(self) -> ScoringWeights:
        """转换为统一权重格式"""
        return ScoringWeights(
            adx_score=self.primary_weight * self.adx_weight,
            trend_consistency=self.primary_weight * self.trend_consistency_weight,
            price_efficiency=self.primary_weight * self.price_efficiency_weight,
            liquidity_score=self.primary_weight * self.liquidity_weight,
            momentum_3m=self.secondary_weight * self.momentum_3m_weight,
            momentum_12m=self.secondary_weight * self.momentum_12m_weight,
        )


class LegacyUnbiasedScorer:
    """[已废弃] 旧版无偏综合评分器，请使用 UnifiedScorer"""

    def __init__(self, weights: Optional[LegacyScoringWeights] = None):
        self.legacy_weights = weights if weights is not None else LegacyScoringWeights()
        self.unified_weights = self.legacy_weights.to_unified_weights()
        self._scorer = UnifiedScorer(self.unified_weights)

    def calculate_primary_score(self, indicators: Dict[str, float]) -> float:
        """计算主要评分（ADX + 趋势一致性 + 价格效率 + 流动性）"""
        adx = UnifiedScorer._get_valid_score(indicators.get('adx_mean_normalized', 0.0))
        trend = UnifiedScorer._get_valid_score(indicators.get('trend_consistency', 0.0))
        efficiency = UnifiedScorer._get_valid_score(indicators.get('price_efficiency', 0.0))
        liquidity = UnifiedScorer._get_valid_score(indicators.get('liquidity_score', 0.0))

        primary_score = (
            self.legacy_weights.adx_weight * adx +
            self.legacy_weights.trend_consistency_weight * trend +
            self.legacy_weights.price_efficiency_weight * efficiency +
            self.legacy_weights.liquidity_weight * liquidity
        )
        return float(primary_score)

    def calculate_secondary_score(self, indicators: Dict[str, float]) -> float:
        """计算次要评分（动量）"""
        momentum_3m = UnifiedScorer._get_valid_score(indicators.get('momentum_3m_normalized', 0.0))
        momentum_12m = UnifiedScorer._get_valid_score(indicators.get('momentum_12m_normalized', 0.0))

        secondary_score = (
            self.legacy_weights.momentum_3m_weight * momentum_3m +
            self.legacy_weights.momentum_12m_weight * momentum_12m
        )
        return float(secondary_score)

    def calculate_final_score(self, indicators: Dict[str, float]) -> Dict[str, float]:
        primary_score = self.calculate_primary_score(indicators)
        secondary_score = self.calculate_secondary_score(indicators)

        final_score = (
            self.legacy_weights.primary_weight * primary_score +
            self.legacy_weights.secondary_weight * secondary_score
        )

        return {
            'primary_score': primary_score,
            'secondary_score': secondary_score,
            'final_score': final_score
        }


def calculate_legacy_etf_scores(
    metrics_df: pd.DataFrame,
    scorer: Optional[LegacyUnbiasedScorer] = None,
    normalize_method: str = 'percentile'
) -> pd.DataFrame:
    """
    [已废弃] 批量计算ETF的综合评分（旧版公式）

    请使用 calculate_unified_scores 替代
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
    """[已废弃] 创建旧版公式的评分器"""
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


# 保留旧版导出以兼容现有代码
def calculate_etf_scores(
    metrics_df: pd.DataFrame,
    scorer=None,
    normalize_method: str = 'percentile'
) -> pd.DataFrame:
    """
    [已废弃] 旧版V2评分函数，请使用 calculate_unified_scores
    """
    # 如果传入了旧版的UnbiasedScorer，转换为统一格式
    if scorer is not None and hasattr(scorer, 'weights'):
        old_weights = scorer.weights
        # 旧版V2权重转换
        weights = ScoringWeights(
            adx_score=getattr(old_weights, 'strength_weight', 0.15),
            trend_quality=getattr(old_weights, 'trend_quality_weight', 0.35),
            excess_return_20d=getattr(old_weights, 'core_trend_weight', 0.40) * getattr(old_weights, 'excess_return_20d_weight', 0.40),
            excess_return_60d=getattr(old_weights, 'core_trend_weight', 0.40) * getattr(old_weights, 'excess_return_60d_weight', 0.60),
            volume_trend=getattr(old_weights, 'volume_weight', 0.10),
            idr=getattr(old_weights, 'idr_weight', 0.0),
        )
    else:
        # 默认使用旧版V2默认权重
        weights = ScoringWeights(
            adx_score=0.15,
            trend_quality=0.35,
            excess_return_20d=0.16,  # 0.40 * 0.40
            excess_return_60d=0.24,  # 0.40 * 0.60
            volume_trend=0.10,
            idr=0.0,
        )

    return calculate_unified_scores(metrics_df, weights, normalize_method)
