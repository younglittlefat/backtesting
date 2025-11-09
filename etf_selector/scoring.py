"""
综合评分算法模块

实现去偏差的ETF综合评分系统，降低动量指标权重，
增加无偏技术指标权重，以减少选择性偏差。

评分体系：
- 主要指标（80%）：ADX、趋势一致性、价格效率、流动性
- 次要指标（20%）：动量（3个月、12个月）
"""
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class ScoringWeights:
    """评分权重配置"""

    # 主要指标权重（无偏技术指标）
    primary_weight: float = 0.80  # 主要指标总权重80%
    adx_weight: float = 0.40  # ADX趋势强度
    trend_consistency_weight: float = 0.30  # 趋势一致性
    price_efficiency_weight: float = 0.20  # 价格效率
    liquidity_weight: float = 0.10  # 流动性评分

    # 次要指标权重（动量指标，权重降低）
    secondary_weight: float = 0.20  # 次要指标总权重20%
    momentum_3m_weight: float = 0.30  # 3个月动量
    momentum_12m_weight: float = 0.70  # 12个月动量

    def __post_init__(self):
        """验证权重和为1"""
        # 验证主要指标权重和
        primary_sum = (
            self.adx_weight +
            self.trend_consistency_weight +
            self.price_efficiency_weight +
            self.liquidity_weight
        )
        assert abs(primary_sum - 1.0) < 0.01, f"主要指标权重和应为1，实际为{primary_sum}"

        # 验证次要指标权重和
        secondary_sum = self.momentum_3m_weight + self.momentum_12m_weight
        assert abs(secondary_sum - 1.0) < 0.01, f"次要指标权重和应为1，实际为{secondary_sum}"

        # 验证总权重和
        total_sum = self.primary_weight + self.secondary_weight
        assert abs(total_sum - 1.0) < 0.01, f"总权重和应为1，实际为{total_sum}"


class UnbiasedScorer:
    """无偏综合评分器"""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        初始化评分器

        Args:
            weights: 评分权重配置，默认None使用默认权重
        """
        self.weights = weights if weights is not None else ScoringWeights()

    def calculate_primary_score(self, indicators: Dict[str, float]) -> float:
        """
        计算主要指标评分（无偏技术指标）

        Args:
            indicators: 指标字典，包含：
                - adx_mean_normalized: 标准化后的ADX均值 (0-1)
                - trend_consistency: 趋势一致性评分 (0-1)
                - price_efficiency: 价格效率评分 (0-1)
                - liquidity_score: 流动性评分 (0-1)

        Returns:
            主要指标综合评分 (0-1)
        """
        # 获取并验证指标值
        adx = self._get_valid_score(indicators.get('adx_mean_normalized', 0.0))
        trend = self._get_valid_score(indicators.get('trend_consistency', 0.0))
        efficiency = self._get_valid_score(indicators.get('price_efficiency', 0.0))
        liquidity = self._get_valid_score(indicators.get('liquidity_score', 0.0))

        # 加权平均
        primary_score = (
            self.weights.adx_weight * adx +
            self.weights.trend_consistency_weight * trend +
            self.weights.price_efficiency_weight * efficiency +
            self.weights.liquidity_weight * liquidity
        )

        return float(primary_score)

    def calculate_secondary_score(self, indicators: Dict[str, float]) -> float:
        """
        计算次要指标评分（动量指标，权重降低）

        Args:
            indicators: 指标字典，包含：
                - momentum_3m_normalized: 标准化后的3个月动量 (0-1)
                - momentum_12m_normalized: 标准化后的12个月动量 (0-1)

        Returns:
            次要指标综合评分 (0-1)
        """
        momentum_3m = self._get_valid_score(indicators.get('momentum_3m_normalized', 0.0))
        momentum_12m = self._get_valid_score(indicators.get('momentum_12m_normalized', 0.0))

        # 加权平均
        secondary_score = (
            self.weights.momentum_3m_weight * momentum_3m +
            self.weights.momentum_12m_weight * momentum_12m
        )

        return float(secondary_score)

    def calculate_final_score(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """
        计算最终综合评分

        Args:
            indicators: 包含所有指标的字典

        Returns:
            评分结果字典，包含：
                - primary_score: 主要指标评分
                - secondary_score: 次要指标评分
                - final_score: 最终综合评分
        """
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

    @staticmethod
    def _get_valid_score(value: float) -> float:
        """验证并返回有效的评分值"""
        if pd.isna(value) or np.isnan(value) or np.isinf(value):
            return 0.0
        return float(np.clip(value, 0.0, 1.0))


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
        scorer = UnbiasedScorer()

    # 需要标准化的列
    columns_to_normalize = [
        'adx_mean',
        'trend_consistency',
        'price_efficiency',
        'liquidity_score',
        'momentum_3m',
        'momentum_12m'
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
            'adx_mean_normalized': row.get('adx_mean_normalized', 0.0),
            'trend_consistency': row.get('trend_consistency', 0.0),
            'price_efficiency': row.get('price_efficiency', 0.0),
            'liquidity_score': row.get('liquidity_score', 0.0),
            'momentum_3m_normalized': row.get('momentum_3m_normalized', 0.0),
            'momentum_12m_normalized': row.get('momentum_12m_normalized', 0.0),
        }

        score_dict = scorer.calculate_final_score(indicators)
        scores.append(score_dict)

    # 添加评分列
    df_normalized['primary_score'] = [s['primary_score'] for s in scores]
    df_normalized['secondary_score'] = [s['secondary_score'] for s in scores]
    df_normalized['final_score'] = [s['final_score'] for s in scores]

    # 按最终评分排序
    df_normalized = df_normalized.sort_values('final_score', ascending=False).reset_index(drop=True)

    return df_normalized


def create_custom_scorer(
    primary_weight: float = 0.80,
    adx_weight: float = 0.40,
    trend_consistency_weight: float = 0.30,
    price_efficiency_weight: float = 0.20,
    liquidity_weight: float = 0.10,
    momentum_3m_weight: float = 0.30,
    momentum_12m_weight: float = 0.70
) -> UnbiasedScorer:
    """
    创建自定义权重的评分器

    Args:
        primary_weight: 主要指标总权重
        adx_weight: ADX权重（相对于主要指标）
        trend_consistency_weight: 趋势一致性权重（相对于主要指标）
        price_efficiency_weight: 价格效率权重（相对于主要指标）
        liquidity_weight: 流动性权重（相对于主要指标）
        momentum_3m_weight: 3个月动量权重（相对于次要指标）
        momentum_12m_weight: 12个月动量权重（相对于次要指标）

    Returns:
        配置好的评分器实例
    """
    weights = ScoringWeights(
        primary_weight=primary_weight,
        adx_weight=adx_weight,
        trend_consistency_weight=trend_consistency_weight,
        price_efficiency_weight=price_efficiency_weight,
        liquidity_weight=liquidity_weight,
        secondary_weight=1 - primary_weight,
        momentum_3m_weight=momentum_3m_weight,
        momentum_12m_weight=momentum_12m_weight
    )

    return UnbiasedScorer(weights)
