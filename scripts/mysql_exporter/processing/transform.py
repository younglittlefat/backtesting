"""
数据转换模块

负责将数据库数据转换为导出所需的列结构
"""

import pandas as pd


class DailyDataTransformer:
    """
    日线数据转换器

    负责将数据库原始数据转换为标准导出格式
    """

    def transform_daily_frame(
        self, data_type: str, frame: pd.DataFrame
    ) -> pd.DataFrame:
        """
        将数据库数据转换为导出所需的列结构

        Args:
            data_type: 数据类型
            frame: 单个标的的行情数据DataFrame

        Returns:
            pd.DataFrame: 整理后的DataFrame
        """
        if frame.empty:
            return frame

        frame = frame.copy()
        frame["trade_date"] = frame["trade_date"].astype(str)

        if data_type in {"etf", "index"}:
            rename_map = {
                "open_price": "open",
                "high_price": "high",
                "low_price": "low",
                "close_price": "close",
                "pre_close": "pre_close",
                "change_amount": "change",
                "pct_change": "pct_chg",
                "volume": "volume",
                "amount": "amount",
            }
            columns = ["trade_date"] + list(rename_map.values())
            frame = frame.rename(columns=rename_map)
            frame = frame[columns]
        elif data_type == "fund":
            columns = [
                "trade_date",
                "unit_nav",
                "accum_nav",
                "adj_nav",
                "accum_div",
                "net_asset",
                "total_netasset",
            ]
            frame = frame[columns]
        else:
            raise ValueError(f"未支持的日线数据类型: {data_type}")

        frame = frame.sort_values(by="trade_date")
        frame = frame.drop_duplicates(subset=["trade_date"], keep="last")
        return frame
