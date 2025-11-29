"""
数据增强模块

负责为导出数据添加额外信息（名称、复权因子等）
"""

import logging
from typing import Dict, Optional

import pandas as pd

from ..models import DAILY_COLUMN_LAYOUT


class DataEnrichment:
    """
    数据增强类

    负责添加标的名称、计算复权价格等
    """

    def __init__(
        self, db_manager, logger: Optional[logging.Logger] = None
    ) -> None:
        """
        初始化数据增强器

        Args:
            db_manager: 数据库管理器
            logger: 日志记录器
        """
        self.db_manager = db_manager
        self.logger = logger or logging.getLogger(__name__)
        self._instrument_name_cache: Dict[str, Dict[str, str]] = {}

    def load_instrument_names(self, data_type: str) -> Dict[str, str]:
        """
        预加载指定数据类型的标的名称到缓存

        Args:
            data_type: 标的类别，如 'etf', 'index', 'fund'

        Returns:
            Dict[str, str]: ts_code到名称的映射
        """
        if not self.db_manager:
            self._instrument_name_cache[data_type] = {}
            return {}

        try:
            records = self.db_manager.get_instrument_basic(data_type=data_type)
        except Exception as exc:
            self.logger.warning("加载%s基础信息失败: %s", data_type, exc)
            records = []

        mapping: Dict[str, str] = {}
        for record in records or []:
            ts_code = record.get("ts_code")
            if not ts_code:
                continue
            mapping[ts_code] = record.get("name") or ""

        self._instrument_name_cache[data_type] = mapping
        return mapping

    def resolve_instrument_name(self, data_type: str, ts_code: str) -> str:
        """
        解析标的中文名称

        Args:
            data_type: 标的类别
            ts_code: 标的代码

        Returns:
            str: 标的名称，未找到时返回空字符串
        """
        if not ts_code:
            return ""

        cache = self._instrument_name_cache.get(data_type)
        if cache is None:
            cache = self.load_instrument_names(data_type)

        if ts_code in cache:
            return cache[ts_code]

        if not self.db_manager:
            cache[ts_code] = ""
            return ""

        try:
            records = self.db_manager.get_instrument_basic(
                data_type=data_type, ts_code=ts_code
            )
        except Exception as exc:
            self.logger.warning("查询%s(%s)名称失败: %s", data_type, ts_code, exc)
            cache[ts_code] = ""
            return ""

        if records:
            name = records[0].get("name") or ""
            cache[ts_code] = name
            return name

        cache[ts_code] = ""
        return ""

    def compute_adjustment_columns(
        self, data_type: str, frame: pd.DataFrame
    ) -> Dict[str, pd.Series]:
        """
        计算复权相关列

        Args:
            data_type: 数据类型
            frame: 转换后的日线数据

        Returns:
            Dict[str, pd.Series]: 列名到计算结果的映射
        """
        adjustments: Dict[str, pd.Series] = {}
        if frame.empty:
            return adjustments

        if data_type in {"etf", "index"}:
            # 优先使用数据库中的 adj_factor
            if "adj_factor" in frame.columns and frame["adj_factor"].notna().any():
                adj_factor = pd.to_numeric(frame["adj_factor"], errors="coerce")
                self.logger.debug("使用数据库中的adj_factor字段")
            elif "pct_chg" in frame.columns:
                # 回退：向后复权（无向前看偏差）
                pct = pd.to_numeric(frame["pct_chg"], errors="coerce").fillna(0.0)
                adj_factor = (pct / 100.0 + 1.0).cumprod()
                self.logger.debug("adj_factor缺失，使用向后复权作为回退")
            else:
                return adjustments

            # 计算复权价格
            if adj_factor.notna().any():
                adjustments["adj_factor"] = adj_factor

                # 计算复权 OHLC
                for col, adj_col in [
                    ("close", "adj_close"),
                    ("open", "adj_open"),
                    ("high", "adj_high"),
                    ("low", "adj_low"),
                ]:
                    if col in frame.columns:
                        price = pd.to_numeric(frame[col], errors="coerce")
                        adjustments[adj_col] = price * adj_factor

        elif data_type == "fund":
            if "unit_nav" in frame.columns and "adj_nav" in frame.columns:
                unit_nav = pd.to_numeric(frame["unit_nav"], errors="coerce")
                adj_nav = pd.to_numeric(frame["adj_nav"], errors="coerce")
                factor = pd.Series([float("nan")] * len(frame), index=frame.index)
                valid = unit_nav.notna() & adj_nav.notna() & (unit_nav != 0)
                if valid.any():
                    factor.loc[valid] = (
                        adj_nav.loc[valid] / unit_nav.loc[valid]
                    ).astype(float)
                if factor.notna().any():
                    adjustments["adj_factor"] = factor
                if adj_nav.notna().any():
                    adjustments["adj_close"] = adj_nav.astype(float)

        return adjustments

    def enrich_daily_output(
        self, data_type: str, ts_code: str, frame: pd.DataFrame
    ) -> pd.DataFrame:
        """
        为日线数据添加标的名称和复权列

        Args:
            data_type: 数据类型
            ts_code: 标的代码
            frame: 已转换的日线数据

        Returns:
            pd.DataFrame: 增强后的数据
        """
        instrument_name = self.resolve_instrument_name(data_type, ts_code)
        enriched = frame.copy()
        enriched.insert(1, "instrument_name", instrument_name)

        adjustments = self.compute_adjustment_columns(data_type, enriched)
        for column, values in adjustments.items():
            enriched[column] = values

        layout = DAILY_COLUMN_LAYOUT.get(data_type)
        if layout:
            for column in layout:
                if column not in enriched.columns:
                    enriched[column] = pd.NA
            enriched = enriched[layout]
        return enriched
