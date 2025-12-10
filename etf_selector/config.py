"""
筛选系统配置参数
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FilterConfig:
    """筛选参数配置"""

    # 第一级：初级筛选
    min_turnover: float = 50_000  # 最小日均成交额（元），默认5万元
    min_listing_days: int = 180  # 最小上市天数，默认180天（6个月）
    turnover_lookback_days: int = 30  # 计算日均成交额的回看天数

    # 第二级：核心筛选
    adx_period: int = 14  # ADX计算周期
    adx_lookback_days: int = 250  # ADX均值计算窗口（交易日）
    adx_percentile: float = 80  # ADX排名百分位（保留前20%）

    ma_short: int = 20  # 双均线短周期
    ma_long: int = 50  # 双均线长周期
    ret_dd_percentile: float = 70  # 收益回撤比排名百分位（保留前30%）
    enable_ma_backtest_filter: bool = False  # 是否启用双均线回测过滤（默认禁用）

    min_volatility: float = 0.20  # 最小年化波动率
    max_volatility: float = 0.60  # 最大年化波动率
    volatility_lookback_days: int = 252  # 波动率计算窗口

    momentum_periods: List[int] = None  # 动量计算周期，默认[63, 252]
    momentum_min_positive: bool = True  # 是否要求动量为正

    # 二级筛选模式控制
    skip_stage2_percentile_filtering: bool = True  # 是否跳过第二级的百分位筛选
    skip_stage2_range_filtering: bool = True  # 是否跳过第二级的范围过滤

    # 第三级：组合优化
    max_correlation: float = 0.7  # 最大相关系数
    target_portfolio_size: int = 20  # 目标组合数量
    min_industries: int = 3  # 最少行业数量

    # 去重配置
    enable_deduplication: bool = True  # 是否启用智能去重
    dedup_min_ratio: float = 0.8  # 去重后最小保留比例
    dedup_thresholds: List[float] = None  # 去重相关性阈值序列

    # V2分散逻辑
    diversify_v2: bool = False  # 是否启用V2分散逻辑
    score_diff_threshold: float = 0.05  # Score差异阈值

    # 聚类选择（替代贪心算法的数据驱动行业分类）
    enable_clustering_selection: bool = False  # 是否启用聚类选择（默认关闭）
    clustering_method: str = 'ward'  # 聚类方法：ward, average, complete, single
    clustering_min_score_percentile: float = 20.0  # 最低分数百分位阈值，低于此值的簇留空

    # 行业平衡
    balance_industries: bool = True  # 是否平衡行业分布

    # 评分系统配置
    enable_unbiased_scoring: bool = True  # 是否启用无偏评分系统
    benchmark_ts_code: str = '510300.SH'  # 基准指数或ETF（超额收益类指标自动使用）

    # 指标计算窗口配置
    trend_consistency_window: int = 63  # 趋势一致性计算窗口（3个月）
    price_efficiency_window: int = 252  # 价格效率计算窗口（1年）
    liquidity_score_window: int = 30  # 流动性评分计算窗口
    excess_return_short_window: int = 20  # 短期超额收益窗口
    excess_return_long_window: int = 60  # 中期超额收益窗口
    trend_quality_window: int = 60  # 趋势质量R^2窗口
    volume_short_window: int = 20  # 成交量短均
    volume_long_window: int = 60  # 成交量长均

    # ========================================================================
    # 统一评分权重配置（共11个指标，权重总和必须为1.0）
    # ========================================================================
    # 趋势类指标
    weight_adx_score: float = 0.0  # ADX趋势强度
    weight_trend_consistency: float = 0.0  # 趋势一致性
    weight_trend_quality: float = 0.0  # 趋势质量（R²）

    # 收益类指标
    weight_momentum_3m: float = 0.0  # 3个月动量
    weight_momentum_12m: float = 0.0  # 12个月动量
    weight_excess_return_20d: float = 0.0  # 20日超额收益（需要基准）
    weight_excess_return_60d: float = 0.0  # 60日超额收益（需要基准）

    # 流动性/成交量类指标
    weight_liquidity_score: float = 0.0  # 流动性评分
    weight_price_efficiency: float = 0.0  # 价格效率
    weight_volume_trend: float = 0.0  # 成交量趋势

    # 风险调整类指标
    weight_idr: float = 0.0  # 风险调整后超额收益（需要基准）

    # ========================================================================
    # 向后兼容：旧版权重字段（已废弃，保留以确保旧脚本可运行）
    # ========================================================================
    use_optimized_score: bool = False  # [已废弃] 是否使用V2评分
    primary_weight: float = 0.80  # [已废弃]
    secondary_weight: float = 0.20  # [已废弃]
    adx_score_weight: float = 0.40  # [已废弃]
    trend_consistency_weight: float = 0.30  # [已废弃]
    price_efficiency_weight: float = 0.20  # [已废弃]
    liquidity_score_weight: float = 0.10  # [已废弃]
    momentum_3m_score_weight: float = 0.30  # [已废弃]
    momentum_12m_score_weight: float = 0.70  # [已废弃]
    core_trend_weight: float = 0.40  # [已废弃]
    trend_quality_weight: float = 0.35  # [已废弃]
    strength_weight: float = 0.15  # [已废弃]
    volume_weight: float = 0.10  # [已废弃]
    idr_weight: float = 0.0  # [已废弃]
    excess_return_20d_weight: float = 0.40  # [已废弃]
    excess_return_60d_weight: float = 0.60  # [已废弃]

    # 数据路径
    data_dir: str = 'data/csv'

    # 输出路径（完整路径，如 experiment/etf/xxx.csv，None则自动生成）
    output_path: str = None

    # 时间范围
    start_date: str = None  # 开始日期 (YYYY-MM-DD)
    end_date: str = None  # 结束日期 (YYYY-MM-DD)

    # 输出选项
    verbose: bool = True  # 是否显示详细日志
    with_analysis: bool = False  # 是否生成风险分析报告
    skip_portfolio_optimization: bool = False  # 是否跳过组合优化

    def __post_init__(self):
        """初始化后处理"""
        if self.momentum_periods is None:
            self.momentum_periods = [63, 252]  # 3个月、12个月

        if self.dedup_thresholds is None:
            self.dedup_thresholds = [0.98, 0.95, 0.92, 0.90]  # 默认去重阈值

    def get_scoring_weights(self) -> Dict[str, float]:
        """获取评分权重配置字典"""
        return {
            'adx_score': self.weight_adx_score,
            'trend_consistency': self.weight_trend_consistency,
            'trend_quality': self.weight_trend_quality,
            'momentum_3m': self.weight_momentum_3m,
            'momentum_12m': self.weight_momentum_12m,
            'excess_return_20d': self.weight_excess_return_20d,
            'excess_return_60d': self.weight_excess_return_60d,
            'liquidity_score': self.weight_liquidity_score,
            'price_efficiency': self.weight_price_efficiency,
            'volume_trend': self.weight_volume_trend,
            'idr': self.weight_idr,
        }

    def get_total_weight(self) -> float:
        """获取所有评分权重总和"""
        weights = self.get_scoring_weights()
        return sum(weights.values())

    def needs_benchmark(self) -> bool:
        """是否需要基准数据（超额收益类指标权重>0时自动需要）"""
        return (
            self.weight_excess_return_20d > 0 or
            self.weight_excess_return_60d > 0 or
            self.weight_idr > 0
        )

    def get_active_indicators(self) -> List[str]:
        """获取所有权重>0的指标名称"""
        weights = self.get_scoring_weights()
        return [k for k, v in weights.items() if v > 0]


@dataclass
class IndustryKeywords:
    """行业分类关键词"""

    keywords: Dict[str, List[str]] = None

    def __post_init__(self):
        """初始化行业关键词"""
        if self.keywords is None:
            self.keywords = {
                '科技': ['科技', '半导体', '芯片', '软件', '人工智能', 'AI', '5G', '互联网', '通信'],
                '医药': ['医药', '医疗', '生物', '健康', '制药', 'CXO'],
                '金融': ['金融', '银行', '证券', '保险', '券商'],
                '消费': ['消费', '食品', '白酒', '零售', '商业', '餐饮'],
                '新能源': ['新能源', '光伏', '储能', '锂电', '电池', '风电'],
                '军工': ['军工', '国防', '航空', '航天'],
                '地产': ['地产', '房地产', '建筑', '基建'],
                '周期': ['煤炭', '有色', '钢铁', '化工', '石油', '石化'],
                '制造': ['机械', '设备', '汽车', '制造'],
            }

    def classify(self, etf_name: str) -> str:
        """根据ETF名称分类行业

        Args:
            etf_name: ETF名称

        Returns:
            行业名称，如果未匹配到则返回'其他'
        """
        for industry, keywords in self.keywords.items():
            if any(kw in etf_name for kw in keywords):
                return industry
        return '其他'


# 默认配置实例
DEFAULT_CONFIG = FilterConfig()
DEFAULT_INDUSTRY_KEYWORDS = IndustryKeywords()
