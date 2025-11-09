"""
筛选系统配置参数
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FilterConfig:
    """筛选参数配置"""

    # 第一级：初级筛选
    min_turnover: float = 100_000_000  # 最小日均成交额（元），默认1亿
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

    # 第三级：组合优化
    max_correlation: float = 0.7  # 最大相关系数
    target_portfolio_size: int = 20  # 目标组合数量
    min_industries: int = 3  # 最少行业数量

    # 新增：无偏指标配置（去偏差优化）
    enable_unbiased_scoring: bool = True  # 是否启用无偏评分系统
    trend_consistency_window: int = 63  # 趋势一致性计算窗口（3个月）
    price_efficiency_window: int = 252  # 价格效率计算窗口（1年）
    liquidity_score_window: int = 30  # 流动性评分计算窗口

    # 评分权重配置
    primary_weight: float = 0.80  # 主要指标（无偏）总权重
    secondary_weight: float = 0.20  # 次要指标（动量）总权重

    # 主要指标权重分配（相对于primary_weight）
    adx_score_weight: float = 0.40  # ADX趋势强度
    trend_consistency_weight: float = 0.30  # 趋势一致性
    price_efficiency_weight: float = 0.20  # 价格效率
    liquidity_score_weight: float = 0.10  # 流动性评分

    # 次要指标权重分配（相对于secondary_weight）
    momentum_3m_score_weight: float = 0.30  # 3个月动量
    momentum_12m_score_weight: float = 0.70  # 12个月动量

    # 数据路径
    data_dir: str = 'data/csv'

    # 输出路径
    output_dir: str = 'results/selector'

    def __post_init__(self):
        """初始化后处理"""
        if self.momentum_periods is None:
            self.momentum_periods = [63, 252]  # 3个月、12个月


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
