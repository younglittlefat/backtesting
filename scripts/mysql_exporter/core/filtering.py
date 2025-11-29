"""
过滤引擎

负责根据配置的阈值条件过滤标的
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from ..models import (
    FilterResult,
    FilterStatistics,
    FilterThresholds,
    FilteredRecord,
    PRICE_COLUMNS,
    FUND_COLUMNS,
)


@dataclass
class FilteringResult:
    """过滤计算结果"""
    metrics_by_type: Dict[str, Dict[str, FilterResult]] = field(default_factory=dict)
    stats_by_type: Dict[str, FilterStatistics] = field(default_factory=dict)
    filtered_rows: List[FilteredRecord] = field(default_factory=list)
    thresholds: Optional[FilterThresholds] = None


class FilteringEngine:
    """
    过滤引擎类

    负责计算各标的的过滤指标并判断是否通过
    """

    # 需要应用过滤的数据类型
    FILTER_APPLICABLE_TYPES = {"etf", "fund"}

    def __init__(
        self,
        db_manager,
        transformer,
        enrichment,
        batch_size: int = 10000,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        初始化过滤引擎

        Args:
            db_manager: 数据库管理器
            transformer: 数据转换器
            enrichment: 数据增强器
            batch_size: 批量查询大小
            logger: 日志记录器
        """
        self.db_manager = db_manager
        self.transformer = transformer
        self.enrichment = enrichment
        self.batch_size = batch_size
        self.logger = logger or logging.getLogger(__name__)

    def compute_filtering(
        self,
        data_types: List[str],
        start_date: str,
        end_date: str,
        ts_code: Optional[str] = None,
        thresholds: Optional[FilterThresholds] = None,
    ) -> FilteringResult:
        """
        计算过滤所需指标与白名单

        Args:
            data_types: 数据类型列表
            start_date: 开始日期
            end_date: 结束日期
            ts_code: 可选，指定单个标的代码
            thresholds: 过滤阈值配置

        Returns:
            FilteringResult: 过滤计算结果
        """
        if thresholds is None:
            thresholds = FilterThresholds()

        result = FilteringResult(thresholds=thresholds)

        for dtype in data_types:
            sql, params = self._build_query(dtype, start_date, end_date, ts_code)
            per_code_agg: Dict[str, Dict] = {}
            stats = FilterStatistics()
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
                            transformed = self.transformer.transform_daily_frame(dtype, group)
                            if transformed.empty:
                                continue

                            agg = per_code_agg.get(code)
                            if agg is None:
                                agg = self._init_aggregation()
                                per_code_agg[code] = agg

                            self._update_aggregation(agg, dtype, transformed)

            except Exception as exc:
                self.logger.error("过滤统计失败: %s", exc)
                raise RuntimeError("过滤统计失败") from exc

            # 汇总通过/失败情况
            metrics_per_code: Dict[str, FilterResult] = {}
            for code, agg in per_code_agg.items():
                filter_result, fail_reasons = self._evaluate_filter(
                    dtype, agg, thresholds
                )
                metrics_per_code[code] = filter_result

                # 更新统计
                stats.total_candidates += 1
                if filter_result.passed:
                    stats.passed += 1
                else:
                    stats.filtered += 1
                    for reason in fail_reasons:
                        if reason == "insufficient_history":
                            stats.fail_insufficient_history += 1
                        elif reason == "low_volatility":
                            stats.fail_low_volatility += 1
                        elif reason == "low_turnover":
                            stats.fail_low_turnover += 1

                # 记录被过滤的标的详情
                if not filter_result.passed and dtype in self.FILTER_APPLICABLE_TYPES:
                    instrument_name = self.enrichment.resolve_instrument_name(dtype, code)
                    result.filtered_rows.append(FilteredRecord(
                        data_type=dtype,
                        ts_code=code,
                        instrument_name=instrument_name,
                        admission_start_date=agg["first_trade_date"],
                        end_date=end_date,
                        sample_trading_days=agg["count_days"],
                        annual_volatility=round(filter_result.annual_vol, 6),
                        avg_turnover_yuan=(
                            round(filter_result.avg_turnover_yuan, 2)
                            if filter_result.avg_turnover_yuan is not None else None
                        ),
                        fail_reasons="|".join(fail_reasons),
                        threshold_min_history_days=thresholds.min_history_days,
                        threshold_min_annual_vol=thresholds.min_annual_vol,
                        threshold_min_avg_turnover_yuan=(
                            thresholds.min_avg_turnover_yuan if dtype == "etf" else None
                        ),
                    ))

            result.metrics_by_type[dtype] = metrics_per_code
            result.stats_by_type[dtype] = stats

            if not has_data:
                self.logger.warning(
                    "未查询到日线数据用于过滤: data_type=%s ts_code=%s 日期范围=%s-%s",
                    dtype,
                    ts_code or "全部",
                    start_date,
                    end_date,
                )

        return result

    def _build_query(
        self,
        data_type: str,
        start_date: str,
        end_date: str,
        ts_code: Optional[str] = None,
    ) -> tuple:
        """构建查询SQL"""
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

    @staticmethod
    def _init_aggregation() -> Dict:
        """初始化聚合数据结构"""
        return {
            "count_days": 0,
            "first_trade_date": None,
            "last_trade_date": None,
            "ret_count": 0,
            "ret_mean": 0.0,
            "ret_m2": 0.0,
            "prev_price": None,
            "amount_sum_thousand": 0.0,
        }

    def _update_aggregation(
        self, agg: Dict, data_type: str, transformed: pd.DataFrame
    ) -> None:
        """更新聚合数据"""
        for _, row in transformed.iterrows():
            trade_date = str(row["trade_date"])
            agg["count_days"] += 1
            if agg["first_trade_date"] is None:
                agg["first_trade_date"] = trade_date
            agg["last_trade_date"] = trade_date

            if data_type == "etf":
                amt = row.get("amount", None)
                try:
                    amt_v = float(amt) if amt is not None and amt == amt else 0.0
                except Exception:
                    amt_v = 0.0
                agg["amount_sum_thousand"] += amt_v

            ret_val = self._calculate_return(data_type, row, agg)
            if ret_val is not None:
                # Welford's online algorithm for variance
                agg["ret_count"] += 1
                delta = ret_val - agg["ret_mean"]
                agg["ret_mean"] += delta / agg["ret_count"]
                delta2 = ret_val - agg["ret_mean"]
                agg["ret_m2"] += delta2 * delta

    def _calculate_return(
        self, data_type: str, row: pd.Series, agg: Dict
    ) -> Optional[float]:
        """计算收益率"""
        ret_val: Optional[float] = None

        if data_type == "etf":
            pct = row.get("pct_chg", None)
            if pct is not None and pct == pct:
                try:
                    ret_val = float(pct) / 100.0
                except Exception:
                    ret_val = None
            if ret_val is None:
                close = row.get("close", None)
                if close is not None and close == close:
                    try:
                        close_v = float(close)
                        if agg["prev_price"] is not None:
                            prev = agg["prev_price"]
                            if prev and prev != 0:
                                ret_val = close_v / prev - 1.0
                        agg["prev_price"] = close_v
                    except Exception:
                        pass
        elif data_type == "fund":
            price = row.get("adj_nav", None)
            if price is None or not (price == price):
                price = row.get("unit_nav", None)
            if price is not None and price == price:
                try:
                    price_v = float(price)
                    if agg["prev_price"] is not None:
                        prev = agg["prev_price"]
                        if prev and prev != 0:
                            ret_val = price_v / prev - 1.0
                    agg["prev_price"] = price_v
                except Exception:
                    pass

        return ret_val

    def _evaluate_filter(
        self, data_type: str, agg: Dict, thresholds: FilterThresholds
    ) -> tuple:
        """评估过滤条件"""
        apply_filter = data_type in self.FILTER_APPLICABLE_TYPES
        count_days = int(agg["count_days"])

        # 计算年化波动率
        if agg["ret_count"] > 1:
            var = agg["ret_m2"] / (agg["ret_count"] - 1)
            daily_std = math.sqrt(var) if var > 0 else 0.0
            annual_vol = daily_std * math.sqrt(252.0)
        else:
            annual_vol = 0.0

        # 计算日均成交额
        avg_turnover_yuan: Optional[float] = None
        if data_type == "etf" and count_days > 0:
            avg_thousand = float(agg["amount_sum_thousand"]) / float(count_days)
            avg_turnover_yuan = avg_thousand * 1000.0

        # 评估过滤条件
        fail_reasons: List[str] = []
        if apply_filter:
            if not (count_days > thresholds.min_history_days):
                fail_reasons.append("insufficient_history")
            if not (annual_vol > thresholds.min_annual_vol):
                fail_reasons.append("low_volatility")
            if data_type == "etf":
                if avg_turnover_yuan is None or not (avg_turnover_yuan > thresholds.min_avg_turnover_yuan):
                    fail_reasons.append("low_turnover")

        passed = (len(fail_reasons) == 0) if apply_filter else True

        filter_result = FilterResult(
            ts_code="",  # 由调用方设置
            passed=passed,
            count_days=count_days,
            first_trade_date=agg["first_trade_date"],
            last_trade_date=agg["last_trade_date"],
            annual_vol=annual_vol,
            avg_turnover_yuan=avg_turnover_yuan,
            fail_reasons=fail_reasons,
        )

        return filter_result, fail_reasons
