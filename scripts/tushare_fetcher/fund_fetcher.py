"""
基金数据抓取器

处理基金基本信息、净值、分红、规模数据的获取
（简化版，保留核心功能）
"""

from .base_fetcher import BaseFetcher
from .rate_limiter import RateLimiter
from .data_processor import DataProcessor


class FundFetcher(BaseFetcher):
    """基金数据抓取器（简化版）"""

    def __init__(self, pro_api, db_manager, rate_limiter: RateLimiter,
                 data_processor: DataProcessor, logger=None):
        """
        初始化基金抓取器

        Args:
            pro_api: Tushare Pro API实例
            db_manager: 数据库管理器
            rate_limiter: 频率限制器
            data_processor: 数据处理器
            logger: 日志记录器
        """
        super().__init__(pro_api, db_manager, logger)
        self.rate_limiter = rate_limiter
        self.data_processor = data_processor

    def fetch_basic_info(self) -> int:
        """
        获取基金基本信息（仅白名单）

        Returns:
            int: 成功获取的基金数量
        """
        # 简化实现，暂不实现
        self.logger.info("基金基本信息获取（未实现）")
        return 0

    def get_count(self) -> int:
        """
        获取基金数量

        Returns:
            int: 基金数量
        """
        try:
            df = self.pro.fund_basic(market='O', status='L')
            if df.empty:
                return 0

            # 应用白名单过滤
            df = df[df['management'].apply(
                lambda x: self._is_whitelisted_fund_company(x) if pd.notna(x) else False
            )]

            return len(df)

        except Exception as e:
            self.logger.error(f"获取基金数量失败: {e}")
            return 0
