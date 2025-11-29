"""
MySQL数据导出器核心类

负责连接数据库、查询数据、按类型导出CSV文件
"""

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ..models import (
    DAILY_COLUMN_LAYOUT,
    PRICE_COLUMNS,
    FUND_COLUMNS,
    DailyExportStats,
    FilterThresholds,
)
from .filtering import FilteringEngine
from ..processing.transform import DailyDataTransformer
from ..processing.enrichment import DataEnrichment


class MySQLToCSVExporter:
    """
    MySQL数据导出至CSV的核心类

    负责连接数据库、查询数据、按类型导出CSV文件，并在需要时生成元数据。
    """

    def __init__(
        self,
        output_dir: str,
        batch_size: int = 10000,
        logger: Optional[logging.Logger] = None,
        db_manager=None,
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
        self.db_manager = db_manager
        self.output_dir = Path(output_dir).expanduser()
        self.batch_size = batch_size

        self.basic_dir = self.output_dir / "basic_info"
        self.daily_dir = self.output_dir / "daily"

        # 初始化子组件
        self._enrichment = DataEnrichment(db_manager, logger)
        self._transformer = DailyDataTransformer()
        self._filtering = FilteringEngine(
            db_manager=db_manager,
            transformer=self._transformer,
            enrichment=self._enrichment,
            batch_size=batch_size,
            logger=logger,
        )

        # 缓存过滤结果写入状态
        self._filter_csv_written: bool = False

    def _ensure_directories(
        self, need_basic: bool, daily_types: Iterable[str]
    ) -> None:
        """
        根据导出需求创建必要的目录结构

        Args:
            need_basic: 是否需要导出基础信息
            daily_types: 需要导出日线数据的类型集合
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
        """
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if data_type == "etf":
            columns = [
                "ts_code", "symbol", "name", "fullname", "market",
                "tracking_index", "management", "fund_type", "list_date",
                "found_date", "status",
            ]
        elif data_type == "index":
            columns = [
                "ts_code", "symbol", "name", "fullname", "market",
                "publisher", "index_type", "category", "base_date",
                "base_point", "list_date", "status",
            ]
        elif data_type == "fund":
            columns = [
                "ts_code", "symbol", "name", "fullname", "market",
                "management", "custodian", "fund_type", "invest_type",
                "m_fee", "c_fee", "found_date", "status",
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
        """
        base_columns = ["ts_code", "trade_date"]
        if data_type in {"etf", "index"}:
            selected = base_columns + PRICE_COLUMNS
        elif data_type == "fund":
            selected = base_columns + FUND_COLUMNS
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

    def export_basic_info(
        self,
        data_types: Iterable[str],
        ts_code: Optional[str] = None,
        whitelist_by_type: Optional[Dict[str, set]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        thresholds: Optional[FilterThresholds] = None,
    ) -> Dict[str, int]:
        """
        导出指定类型的基础信息（可选：按白名单过滤）

        Args:
            data_types: 需要处理的数据类型集合
            ts_code: 可选，指定单个标的代码
            whitelist_by_type: 可选，按类型分组的白名单集合
            start_date: 可选，过滤计算起始日期
            end_date: 可选，过滤计算结束日期
            thresholds: 可选，过滤阈值配置

        Returns:
            Dict[str, int]: 每个类型导出的记录数
        """
        self._ensure_directories(need_basic=True, daily_types=[])
        stats: Dict[str, int] = {}

        # 若未提供白名单但提供了日期参数，则计算筛选白名单
        computed_whitelist: Optional[Dict[str, set]] = None
        if whitelist_by_type is None and start_date and end_date:
            filter_result = self._filtering.compute_filtering(
                data_types=list(data_types),
                start_date=start_date,
                end_date=end_date,
                ts_code=ts_code,
                thresholds=thresholds,
            )
            # 写出过滤明细（仅写一次）
            if filter_result.filtered_rows and not self._filter_csv_written:
                filtered_df = pd.DataFrame([
                    vars(r) for r in filter_result.filtered_rows
                ])
                filtered_csv = self.output_dir / "filtered_out.csv"
                filtered_df.to_csv(filtered_csv, index=False, encoding="utf-8", na_rep="")
                self.logger.info("已输出过滤明细: %s (共%d条)", filtered_csv, len(filtered_df))
                self._filter_csv_written = True

            # 生成白名单集合
            computed_whitelist = {
                dtype: {
                    code for code, result in filter_result.metrics_by_type.get(dtype, {}).items()
                    if result.passed
                }
                for dtype in data_types
            }

        for dtype in data_types:
            try:
                records = self.db_manager.get_instrument_basic(
                    data_type=dtype, ts_code=ts_code
                )
            except Exception as exc:
                self.logger.error("查询基础信息失败: %s", exc)
                raise RuntimeError("基础信息查询失败") from exc

            # 应用白名单过滤（仅对 etf/fund；index 保持不变）
            if (whitelist_by_type or computed_whitelist) and dtype in {"etf", "fund"}:
                wl = (whitelist_by_type or computed_whitelist or {}).get(dtype, set())
                if wl:
                    filtered_records = [r for r in (records or []) if r.get("ts_code") in wl]
                else:
                    filtered_records = []
                df = self._prepare_basic_dataframe(dtype, filtered_records)
            else:
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
        thresholds: Optional[FilterThresholds] = None,
    ) -> Dict[str, Dict[str, object]]:
        """
        导出日线数据到CSV文件

        Args:
            data_types: 需要处理的数据类型集合
            start_date: 开始日期
            end_date: 结束日期
            ts_code: 可选，指定的单个标的代码
            thresholds: 可选，过滤阈值配置

        Returns:
            Dict[str, Dict[str, object]]: 各类型的导出统计信息
        """
        self._ensure_directories(need_basic=False, daily_types=data_types)
        stats: Dict[str, Dict[str, object]] = {}

        # 1) 计算过滤白名单与统计
        filter_result = self._filtering.compute_filtering(
            data_types=list(data_types),
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
            thresholds=thresholds,
        )

        # 输出过滤明细CSV（如有且未写过）
        if filter_result.filtered_rows and not self._filter_csv_written:
            filtered_df = pd.DataFrame([vars(r) for r in filter_result.filtered_rows])
            filtered_csv = self.output_dir / "filtered_out.csv"
            filtered_df.to_csv(filtered_csv, index=False, encoding="utf-8", na_rep="")
            self.logger.info("已输出过滤明细: %s (共%d条)", filtered_csv, len(filtered_df))
            self._filter_csv_written = True

        # 2) 执行实际导出，仅导出通过的标的
        for dtype in data_types:
            sql, params = self._build_daily_query(dtype, start_date, end_date, ts_code)
            dtype_dir = self.daily_dir / dtype
            exported_codes: set = set()
            dtype_stats = DailyExportStats(
                filter_statistics=filter_result.stats_by_type.get(dtype),
                filter_thresholds=thresholds,
            )
            has_data = False

            # 已通过过滤的白名单
            passed_codes: Optional[set] = None
            if dtype in filter_result.metrics_by_type:
                passed_codes = {
                    code for code, result in filter_result.metrics_by_type[dtype].items()
                    if result.passed
                }

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
                            # 不在白名单的标的不导出
                            if passed_codes is not None and code not in passed_codes:
                                continue

                            transformed = self._transformer.transform_daily_frame(
                                dtype, group
                            )
                            if transformed.empty:
                                continue

                            enriched = self._enrichment.enrich_daily_output(
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

                            dtype_stats.daily_records += len(enriched)
                            date_min = enriched["trade_date"].min()
                            date_max = enriched["trade_date"].max()
                            dtype_stats.date_range = self._update_date_range(
                                dtype_stats.date_range, date_min, date_max
                            )

                            if code not in exported_codes:
                                exported_codes.add(code)
                                dtype_stats.instrument_count += 1

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

            # 整理日期范围
            if dtype_stats.date_range[0] is None or dtype_stats.date_range[1] is None:
                dtype_stats.date_range = []
            else:
                dtype_stats.date_range = [
                    dtype_stats.date_range[0],
                    dtype_stats.date_range[1],
                ]

            stats[dtype] = {
                "instrument_count": dtype_stats.instrument_count,
                "daily_records": dtype_stats.daily_records,
                "date_range": dtype_stats.date_range,
                "filter_statistics": vars(dtype_stats.filter_statistics) if dtype_stats.filter_statistics else {},
                "filter_thresholds": vars(dtype_stats.filter_thresholds) if dtype_stats.filter_thresholds else {},
            }
            self.logger.info(
                "日线数据导出完成: 类型=%s 标的数=%d 记录数=%d",
                dtype,
                dtype_stats.instrument_count,
                dtype_stats.daily_records,
            )

        return stats

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
