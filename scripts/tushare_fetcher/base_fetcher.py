"""
基础数据获取器

提供所有数据获取器的公共基础功能
"""

import logging
from typing import List, Dict, Optional
import pandas as pd
import tushare as ts


class BaseFetcher:
    """基础抓取器，提供通用功能"""

    # 基金公司白名单
    FUND_COMPANY_WHITELIST = [
        "易方达", "华夏", "南方", "嘉实", "博时",
        "广发", "招商", "富国", "汇添富", "中欧", "银河"
    ]

    def __init__(self, pro_api, db_manager, logger: logging.Logger = None):
        """
        初始化基础抓取器

        Args:
            pro_api: Tushare Pro API实例
            db_manager: 数据库管理器实例
            logger: 日志记录器
        """
        self.pro = pro_api
        self.db_manager = db_manager
        self.logger = logger or logging.getLogger(__name__)

    def get_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日历

        Args:
            start_date: 开始日期(YYYYMMDD)
            end_date: 结束日期(YYYYMMDD)

        Returns:
            List[str]: 交易日期列表
        """
        try:
            self.logger.info(f"获取交易日历: {start_date} - {end_date}")

            df = self.pro.trade_cal(
                exchange='SSE',
                is_open='1',
                start_date=start_date,
                end_date=end_date,
                fields='cal_date'
            )

            if df.empty:
                self.logger.warning("未获取到交易日期")
                return []

            trading_dates = df['cal_date'].tolist()
            self.logger.info(f"获取到{len(trading_dates)}个交易日")
            return trading_dates

        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            return []

    def _is_whitelisted_fund_company(self, management: str) -> bool:
        """
        判断基金公司是否在白名单中

        Args:
            management: 基金管理公司名称

        Returns:
            bool: 是否在白名单中
        """
        if not management:
            return False

        management = str(management).strip()
        for company in self.FUND_COMPANY_WHITELIST:
            if company in management:
                return True
        return False

    def _get_fund_management_from_db(self, ts_code: str) -> Optional[str]:
        """
        从数据库获取基金管理公司信息

        Args:
            ts_code: 基金代码

        Returns:
            Optional[str]: 基金管理公司名称，如果未找到返回None
        """
        try:
            result = self.db_manager.get_instrument_basic(data_type='fund', ts_code=ts_code)
            if result and 'management' in result:
                return result['management']
            return None
        except Exception as e:
            self.logger.error(f"获取基金管理公司信息失败 {ts_code}: {e}")
            return None

    def _clean_data(self, data: Dict) -> Dict:
        """
        清理数据，去除None值和NaN值

        Args:
            data: 待清理的数据字典

        Returns:
            Dict: 清理后的数据字典
        """
        cleaned_data = {}
        for k, v in data.items():
            if v is not None and v != '':
                if isinstance(v, float) and pd.isna(v):
                    continue
                cleaned_data[k] = v
        return cleaned_data

    def _safe_concat_dataframes(self, df_list: List[pd.DataFrame]) -> pd.DataFrame:
        """
        安全地合并DataFrame列表，过滤掉空的DataFrame以避免FutureWarning

        Args:
            df_list: DataFrame列表

        Returns:
            pd.DataFrame: 合并后的DataFrame，如果所有都为空则返回空DataFrame
        """
        if not df_list:
            return pd.DataFrame()

        # 过滤掉空的DataFrame
        non_empty_dfs = [df for df in df_list if not df.empty]

        if not non_empty_dfs:
            # 如果所有DataFrame都为空，返回空DataFrame
            return pd.DataFrame()

        # 只合并非空的DataFrame，避免FutureWarning
        return pd.concat(non_empty_dfs, axis=0, ignore_index=True)
