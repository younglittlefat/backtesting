#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MySQL数据导出至CSV脚本

用于根据需求文档，将MySQL数据库中的ETF、指数、基金数据导出为CSV文件。
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import shutil

import pandas as pd

# 将项目根目录加入路径，确保可以导入公共模块
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.mysql_manager import MySQLManager  # noqa: E402


class MySQLToCSVExporter:
    """
    MySQL数据导出至CSV的核心类

    负责连接数据库、查询数据、按类型导出CSV文件，并在需要时生成元数据。
    """

    PRICE_COLUMNS = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "pre_close",
        "change_amount",
        "pct_change",
        "volume",
        "amount",
    ]

    FUND_COLUMNS = [
        "unit_nav",
        "accum_nav",
        "adj_nav",
        "accum_div",
        "net_asset",
        "total_netasset",
    ]
    DAILY_COLUMN_LAYOUT: Dict[str, List[str]] = {
        "etf": [
            "trade_date",
            "instrument_name",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "volume",
            "amount",
            "adj_factor",
            "adj_close",
        ],
        "index": [
            "trade_date",
            "instrument_name",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "volume",
            "amount",
            "adj_factor",
            "adj_close",
        ],
        "fund": [
            "trade_date",
            "instrument_name",
            "unit_nav",
            "accum_nav",
            "adj_nav",
            "accum_div",
            "net_asset",
            "total_netasset",
            "adj_factor",
            "adj_close",
        ],
    }

    def __init__(
        self,
        output_dir: str,
        batch_size: int = 10000,
        logger: Optional[logging.Logger] = None,
        db_manager: Optional[MySQLManager] = None,
    ) -> None:
        """
        初始化导出器

        Args:
            output_dir: CSV输出根目录
            batch_size: 数据库查询批次大小
            logger: 可选，外部传入的日志记录器
            db_manager: 可选，外部传入的MySQL管理器实例

        Raises:
            ValueError: 当批次大小不是正整数时抛出
        """
        if batch_size <= 0:
            raise ValueError("batch_size必须为正整数")

        self.logger = logger or logging.getLogger(__name__)
        self.db_manager = db_manager or MySQLManager()
        self.output_dir = Path(output_dir).expanduser()
        self.batch_size = batch_size

        self.basic_dir = self.output_dir / "basic_info"
        self.daily_dir = self.output_dir / "daily"
        self._instrument_name_cache: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def validate_date(date_str: str, label: str) -> str:
        """
        校验日期格式并返回原始字符串

        Args:
            date_str: 待校验的日期字符串
            label: 字段含义标签，用于错误提示

        Returns:
            str: 原始日期字符串

        Raises:
            ValueError: 当日期格式不是YYYYMMDD时抛出
        """
        try:
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError as exc:
            raise ValueError(f"{label}格式错误，应为YYYYMMDD: {date_str}") from exc
        return date_str

    @staticmethod
    def parse_data_types(data_type: str) -> List[str]:
        """
        将用户输入的类型字符串解析为标准列表

        Args:
            data_type: 用户输入的类型参数，可为'all'或逗号分隔的多个类型

        Returns:
            List[str]: 解析后的类型列表

        Raises:
            ValueError: 当出现未支持的类型时抛出
        """
        valid_types = {"etf", "index", "fund"}
        if not data_type:
            raise ValueError("数据类型参数不能为空")

        if data_type.lower() == "all":
            return ["etf", "index", "fund"]

        result = []
        for item in data_type.split(","):
            dtype = item.strip().lower()
            if not dtype:
                continue
            if dtype not in valid_types:
                raise ValueError(f"不支持的数据类型: {dtype}")
            if dtype not in result:
                result.append(dtype)

        if not result:
            raise ValueError("至少需要指定一个有效的数据类型")

        return result

    def _ensure_directories(
        self, need_basic: bool, daily_types: Iterable[str]
    ) -> None:
        """
        根据导出需求创建必要的目录结构

        Args:
            need_basic: 是否需要导出基础信息
            daily_types: 需要导出日线数据的类型集合

        Returns:
            None

        Raises:
            OSError: 当目录创建失败时抛出
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if need_basic:
            self.basic_dir.mkdir(parents=True, exist_ok=True)

        has_daily = False
        for dtype in daily_types:
            has_daily = True
            (self.daily_dir / dtype).mkdir(parents=True, exist_ok=True)

        if has_daily:
            self.daily_dir.mkdir(parents=True, exist_ok=True)

    def _load_instrument_names(self, data_type: str) -> Dict[str, str]:
        """
        Preload instrument names for the given data type into an internal cache.

        Args:
            data_type: Instrument category, e.g. 'etf', 'index', or 'fund'.

        Returns:
            Dict[str, str]: Mapping from ts_code to instrument name.
        """
        if not self.db_manager:
            self._instrument_name_cache[data_type] = {}
            return {}

        try:
            records = self.db_manager.get_instrument_basic(data_type=data_type)
        except Exception as exc:  # pragma: no cover - defensive logging
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

    def _resolve_instrument_name(self, data_type: str, ts_code: str) -> str:
        """
        Resolve the Chinese instrument name for a given code.

        Args:
            data_type: Instrument category.
            ts_code: Touchstone security code.

        Returns:
            str: Instrument name if available, otherwise empty string.
        """
        if not ts_code:
            return ""

        cache = self._instrument_name_cache.get(data_type)
        if cache is None:
            cache = self._load_instrument_names(data_type)

        if ts_code in cache:
            return cache[ts_code]

        if not self.db_manager:
            cache[ts_code] = ""
            return ""

        try:
            records = self.db_manager.get_instrument_basic(
                data_type=data_type, ts_code=ts_code
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.warning("查询%s(%s)名称失败: %s", data_type, ts_code, exc)
            cache[ts_code] = ""
            return ""

        if records:
            name = records[0].get("name") or ""
            cache[ts_code] = name
            return name

        cache[ts_code] = ""
        return ""

    def _compute_adjustment_columns(
        self, data_type: str, frame: pd.DataFrame
    ) -> Dict[str, pd.Series]:
        """
        Compute adjustment-related columns for the provided frame.

        Args:
            data_type: Instrument category.
            frame: Transformed daily data.

        Returns:
            Dict[str, pd.Series]: Mapping of column names to computed series.
        """
        adjustments: Dict[str, pd.Series] = {}
        if frame.empty:
            return adjustments

        if data_type in {"etf", "index"}:
            if "pct_chg" in frame.columns and "close" in frame.columns:
                pct = pd.to_numeric(frame["pct_chg"], errors="coerce")
                close = pd.to_numeric(frame["close"], errors="coerce")
                if not close.empty:
                    cumulative = pct.fillna(0.0).div(100.0).add(1.0).cumprod()
                    last_value = cumulative.iloc[-1]
                    if pd.notna(last_value) and last_value != 0:
                        adj_factor = cumulative / last_value
                        adjustments["adj_factor"] = adj_factor
                        adjustments["adj_close"] = close * adj_factor
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

    def _enrich_daily_output(
        self, data_type: str, ts_code: str, frame: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Attach instrument metadata and adjustment columns to the daily frame.

        Args:
            data_type: Instrument category.
            ts_code: Instrument identifier.
            frame: Already transformed daily data.

        Returns:
            pd.DataFrame: Frame with instrument name and adjustment metrics.
        """
        instrument_name = self._resolve_instrument_name(data_type, ts_code)
        enriched = frame.copy()
        enriched.insert(1, "instrument_name", instrument_name)

        adjustments = self._compute_adjustment_columns(data_type, enriched)
        for column, values in adjustments.items():
            enriched[column] = values

        layout = self.DAILY_COLUMN_LAYOUT.get(data_type)
        if layout:
            for column in layout:
                if column not in enriched.columns:
                    enriched[column] = pd.NA
            enriched = enriched[layout]
        return enriched

    def _prepare_basic_dataframe(
        self, data_type: str, records: List[Dict]
    ) -> pd.DataFrame:
        """
        将基础信息记录转换为指定字段顺序的DataFrame

        Args:
            data_type: 数据类型
            records: 从数据库查询得到的记录列表

        Returns:
            pd.DataFrame: 已按字段顺序整理的DataFrame

        Raises:
            ValueError: 当传入未知的数据类型时抛出
        """
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if data_type == "etf":
            columns = [
                "ts_code",
                "symbol",
                "name",
                "fullname",
                "market",
                "tracking_index",
                "management",
                "fund_type",
                "list_date",
                "found_date",
                "status",
            ]
        elif data_type == "index":
            columns = [
                "ts_code",
                "symbol",
                "name",
                "fullname",
                "market",
                "publisher",
                "index_type",
                "category",
                "base_date",
                "base_point",
                "list_date",
                "status",
            ]
        elif data_type == "fund":
            columns = [
                "ts_code",
                "symbol",
                "name",
                "fullname",
                "market",
                "management",
                "custodian",
                "fund_type",
                "invest_type",
                "m_fee",
                "c_fee",
                "found_date",
                "status",
            ]
        else:
            raise ValueError(f"未支持的基础信息类型: {data_type}")

        df = df.reindex(columns=columns)
        df = df.sort_values(by="ts_code")
        return df

    def _build_daily_query(
        self,
        data_type: str,
        start_date: str,
        end_date: str,
        ts_code: Optional[str] = None,
    ) -> Tuple[str, List]:
        """
        构建日线数据查询SQL及参数

        Args:
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期
            ts_code: 可选，指定的单个标的代码

        Returns:
            Tuple[str, List]: SQL语句与参数列表

        Raises:
            ValueError: 当数据类型未支持时抛出
        """
        base_columns = ["ts_code", "trade_date"]
        if data_type in {"etf", "index"}:
            selected = base_columns + self.PRICE_COLUMNS
        elif data_type == "fund":
            selected = base_columns + self.FUND_COLUMNS
        else:
            raise ValueError(f"未支持的数据类型: {data_type}")

        column_sql = ", ".join(selected)
        sql = f"""
            SELECT {column_sql}
            FROM instrument_daily
            WHERE data_type = %s
        """.strip()

        params: List = [data_type]

        if ts_code:
            sql += " AND ts_code = %s"
            params.append(ts_code)

        if start_date:
            sql += " AND trade_date >= %s"
            params.append(start_date)

        if end_date:
            sql += " AND trade_date <= %s"
            params.append(end_date)

        sql += " ORDER BY ts_code, trade_date"
        return sql, params

    def _transform_daily_frame(
        self, data_type: str, frame: pd.DataFrame
    ) -> pd.DataFrame:
        """
        将数据库数据转换为导出所需的列结构

        Args:
            data_type: 数据类型
            frame: 单个标的的行情数据DataFrame

        Returns:
            pd.DataFrame: 整理后的DataFrame

        Raises:
            ValueError: 当数据类型未支持时抛出
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

    @staticmethod
    def _update_date_range(
        current_range: List[Optional[str]],
        new_min: str,
        new_max: str,
    ) -> List[Optional[str]]:
        """
        更新统计用的日期范围

        Args:
            current_range: 当前保存的最小、最大日期
            new_min: 新批次的最小日期
            new_max: 新批次的最大日期

        Returns:
            List[Optional[str]]: 更新后的日期范围
        """
        start, end = current_range
        start = new_min if start is None else min(start, new_min)
        end = new_max if end is None else max(end, new_max)
        return [start, end]

    def export_basic_info(
        self, data_types: Iterable[str], ts_code: Optional[str] = None
    ) -> Dict[str, int]:
        """
        导出指定类型的基础信息

        Args:
            data_types: 需要处理的数据类型集合
            ts_code: 可选，指定单个标的代码

        Returns:
            Dict[str, int]: 每个类型导出的记录数

        Raises:
            RuntimeError: 当数据库查询失败时抛出
        """
        self._ensure_directories(need_basic=True, daily_types=[])
        stats: Dict[str, int] = {}

        for dtype in data_types:
            try:
                records = self.db_manager.get_instrument_basic(
                    data_type=dtype, ts_code=ts_code
                )
            except Exception as exc:
                self.logger.error("查询基础信息失败: %s", exc)
                raise RuntimeError("基础信息查询失败") from exc

            df = self._prepare_basic_dataframe(dtype, records)
            if df.empty:
                self.logger.warning(
                    "未查询到基础信息: data_type=%s ts_code=%s",
                    dtype,
                    ts_code or "全部",
                )
                stats[dtype] = 0
                continue

            output_path = self.basic_dir / f"{dtype}_basic_info.csv"
            df.to_csv(output_path, index=False, encoding="utf-8", na_rep="")
            self.logger.info(
                "基础信息导出完成: %s -> %s (记录数=%d)",
                dtype,
                output_path,
                len(df),
            )
            stats[dtype] = len(df)

        return stats

    def export_daily_data(
        self,
        data_types: Iterable[str],
        start_date: str,
        end_date: str,
        ts_code: Optional[str] = None,
    ) -> Dict[str, Dict[str, object]]:
        """
        导出日线数据到CSV文件

        Args:
            data_types: 需要处理的数据类型集合
            start_date: 开始日期
            end_date: 结束日期
            ts_code: 可选，指定的单个标的代码

        Returns:
            Dict[str, Dict[str, object]]: 各类型的导出统计信息

        Raises:
            RuntimeError: 当数据库查询或写入文件失败时抛出
        """
        self._ensure_directories(need_basic=False, daily_types=data_types)
        stats: Dict[str, Dict[str, object]] = {}

        for dtype in data_types:
            sql, params = self._build_daily_query(dtype, start_date, end_date, ts_code)
            dtype_dir = self.daily_dir / dtype
            exported_codes: set = set()
            dtype_stats = {
                "instrument_count": 0,
                "daily_records": 0,
                "date_range": [None, None],  # type: ignore[list-item]
            }
            has_data = False

            try:
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, params)

                    while True:
                        rows = cursor.fetchmany(self.batch_size)
                        if not rows:
                            break

                        chunk = pd.DataFrame(rows)
                        if chunk.empty:
                            continue

                        has_data = True
                        chunk.sort_values(by=["ts_code", "trade_date"], inplace=True)

                        for code, group in chunk.groupby("ts_code", sort=False):
                            transformed = self._transform_daily_frame(dtype, group)
                            if transformed.empty:
                                continue

                            enriched = self._enrich_daily_output(
                                data_type=dtype, ts_code=code, frame=transformed
                            )

                            file_path = dtype_dir / f"{code}.csv"
                            write_header = not file_path.exists()
                            mode = "w" if write_header else "a"
                            enriched.to_csv(
                                file_path,
                                index=False,
                                encoding="utf-8",
                                na_rep="",
                                mode=mode,
                                header=write_header,
                            )

                            dtype_stats["daily_records"] += len(enriched)
                            date_min = enriched["trade_date"].min()
                            date_max = enriched["trade_date"].max()
                            dtype_stats["date_range"] = self._update_date_range(
                                dtype_stats["date_range"], date_min, date_max
                            )

                            if code not in exported_codes:
                                exported_codes.add(code)
                                dtype_stats["instrument_count"] += 1

            except Exception as exc:
                self.logger.error("导出日线数据失败: %s", exc)
                raise RuntimeError("日线数据导出失败") from exc

            if not has_data:
                self.logger.warning(
                    "未查询到日线数据: data_type=%s ts_code=%s 日期范围=%s-%s",
                    dtype,
                    ts_code or "全部",
                    start_date,
                    end_date,
                )

            date_range = dtype_stats["date_range"]
            if date_range[0] is None or date_range[1] is None:
                dtype_stats["date_range"] = []
            else:
                dtype_stats["date_range"] = [date_range[0], date_range[1]]

            stats[dtype] = dtype_stats
            self.logger.info(
                "日线数据导出完成: 类型=%s 标的数=%d 记录数=%d",
                dtype,
                dtype_stats["instrument_count"],
                dtype_stats["daily_records"],
            )

        return stats

    def _generate_metadata(
        self,
        start_date: str,
        end_date: str,
        data_types: List[str],
        export_basic: bool,
        export_daily: bool,
        basic_stats: Dict[str, int],
        daily_stats: Dict[str, Dict[str, object]],
    ) -> Dict[str, object]:
        """
        生成导出任务的元数据字典

        Args:
            start_date: 导出范围的开始日期
            end_date: 导出范围的结束日期
            data_types: 实际处理的数据类型列表
            export_basic: 是否导出基础信息
            export_daily: 是否导出日线数据
            basic_stats: 按类型统计的基础信息条数
            daily_stats: 按类型统计的日线数据结果

        Returns:
            Dict[str, object]: 元数据内容
        """
        statistics: Dict[str, Dict[str, object]] = {}
        for dtype in data_types:
            daily_info = daily_stats.get(
                dtype, {"instrument_count": 0, "daily_records": 0, "date_range": []}
            )
            statistics[dtype] = {
                "instrument_count": daily_info.get("instrument_count", 0),
                "daily_records": daily_info.get("daily_records", 0),
                "date_range": daily_info.get("date_range", []),
            }
            if export_basic:
                statistics[dtype]["basic_records"] = basic_stats.get(dtype, 0)

        metadata = {
            "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": start_date,
            "end_date": end_date,
            "data_types": data_types,
            "export_basic": export_basic,
            "export_daily": export_daily,
            "statistics": statistics,
            "output_dir": str(self.output_dir.resolve()),
            "database": {
                "host": getattr(self.db_manager, "host", "unknown"),
                "database": getattr(self.db_manager, "database", "unknown"),
                "port": getattr(self.db_manager, "port", None),
                "user": getattr(self.db_manager, "user", None),
            },
            "disk_free_gb": round(self._query_disk_free_gb(), 2),
        }
        return metadata

    def _query_disk_free_gb(self) -> float:
        """
        查询输出目录所在磁盘的剩余空间

        Returns:
            float: 可用空间（GB）
        """
        target = self.output_dir
        if not target.exists():
            target = target.parent if target.parent.exists() else Path(".")
        usage = shutil.disk_usage(target)
        return usage.free / (1024 ** 3)

    def save_metadata(self, metadata: Dict[str, object]) -> Path:
        """
        将元数据写入JSON文件

        Args:
            metadata: 已生成的元数据内容

        Returns:
            Path: 元数据文件路径

        Raises:
            OSError: 当文件写入失败时抛出
        """
        metadata_path = self.output_dir / "export_metadata.json"
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=4)
        self.logger.info("元数据已写入: %s", metadata_path)
        return metadata_path


def configure_logging(log_level: str) -> None:
    """
    配置全局日志

    Args:
        log_level: 日志级别字符串

    Returns:
        None
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数

    Returns:
        argparse.Namespace: 参数命名空间

    Raises:
        ValueError: 当缺少导出选项时抛出
    """
    parser = argparse.ArgumentParser(
        description="MySQL数据导出至CSV脚本",
    )
    parser.add_argument("--start_date", required=True, help="开始日期(YYYYMMDD)")
    parser.add_argument("--end_date", required=True, help="结束日期(YYYYMMDD)")
    parser.add_argument(
        "--data_type",
        default="all",
        help="数据类型(etf/index/fund/all或逗号分隔组合)",
    )
    parser.add_argument(
        "--output_dir",
        default="data/csv",
        help="导出结果保存的目录",
    )
    parser.add_argument(
        "--ts_code",
        default=None,
        help="可选，指定单个标的代码",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=10000,
        help="数据库查询批次大小",
    )
    parser.add_argument(
        "--export_basic",
        action="store_true",
        help="是否导出基础信息",
    )
    parser.add_argument(
        "--export_daily",
        action="store_true",
        help="是否导出日线数据",
    )
    parser.add_argument(
        "--export_metadata",
        action="store_true",
        help="是否导出元数据文件",
    )
    parser.add_argument(
        "--log_level",
        default="INFO",
        help="日志级别，默认INFO",
    )
    parser.add_argument(
        "--db_host",
        default="localhost",
        help="MySQL主机地址，默认localhost",
    )
    parser.add_argument(
        "--db_port",
        type=int,
        default=3306,
        help="MySQL端口，默认3306",
    )
    parser.add_argument(
        "--db_user",
        default="root",
        help="MySQL用户名，默认root",
    )
    parser.add_argument(
        "--db_password",
        default="qlib",
        help="MySQL密码，默认qlib",
    )
    parser.add_argument(
        "--db_name",
        default="qlib_data",
        help="MySQL数据库名称，默认qlib_data",
    )

    args = parser.parse_args()
    if not args.export_basic and not args.export_daily and not args.export_metadata:
        raise ValueError("至少需要指定一个导出选项，如--export_basic或--export_daily或--export_metadata")
    return args


def main() -> None:
    """
    脚本入口函数

    Returns:
        None
    """
    args = parse_arguments()
    configure_logging(args.log_level)
    logger = logging.getLogger("export_mysql_to_csv")

    start_date = MySQLToCSVExporter.validate_date(args.start_date, "start_date")
    end_date = MySQLToCSVExporter.validate_date(args.end_date, "end_date")
    if start_date > end_date:
        raise ValueError("start_date不能晚于end_date")

    data_types = MySQLToCSVExporter.parse_data_types(args.data_type)
    ts_code = args.ts_code.strip() if args.ts_code else None

    db_manager = MySQLManager(
        host=args.db_host,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        port=args.db_port,
    )

    exporter = MySQLToCSVExporter(
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        logger=logger,
        db_manager=db_manager,
    )

    if ts_code:
        basic_info = exporter.db_manager.get_instrument_basic(ts_code=ts_code)
        if not basic_info:
            raise ValueError(f"未在数据库中找到标的代码: {ts_code}")
        instrument_type = basic_info[0]["data_type"]
        if instrument_type not in data_types:
            raise ValueError(
                f"标的代码{ts_code}的数据类型为{instrument_type}，与指定的数据类型不匹配"
            )
        data_types = [instrument_type]

    exporter._ensure_directories(
        need_basic=args.export_basic,
        daily_types=data_types if args.export_daily else [],
    )

    basic_stats: Dict[str, int] = {}
    daily_stats: Dict[str, Dict[str, object]] = {}

    if args.export_basic:
        logger.info("开始导出基础信息...")
        basic_stats = exporter.export_basic_info(data_types, ts_code=ts_code)

    if args.export_daily:
        logger.info("开始导出日线数据...")
        daily_stats = exporter.export_daily_data(
            data_types=data_types,
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
        )

    if args.export_metadata:
        logger.info("生成导出元数据...")
        metadata = exporter._generate_metadata(
            start_date=start_date,
            end_date=end_date,
            data_types=data_types,
            export_basic=args.export_basic,
            export_daily=args.export_daily,
            basic_stats=basic_stats,
            daily_stats=daily_stats,
        )
        exporter.save_metadata(metadata)

    logger.info("导出流程全部完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger(__name__).error("用户中断执行")
        sys.exit(1)
    except Exception as exc:  # pylint: disable=broad-except
        logging.getLogger(__name__).exception("导出过程出现异常: %s", exc)
        sys.exit(1)
