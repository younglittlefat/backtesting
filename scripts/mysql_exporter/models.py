"""
核心数据模型定义

定义了MySQL导出器各模块间通信使用的数据结构
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class ExportConfig:
    """导出配置"""
    output_dir: Path
    batch_size: int
    start_date: str
    end_date: str
    data_types: List[str]
    ts_code: Optional[str] = None
    export_basic: bool = False
    export_daily: bool = False
    export_metadata: bool = False

    # 过滤阈值
    min_history_days: int = 180
    min_annual_vol: float = 0.02
    min_avg_turnover_yuan: float = 5000.0

    # 数据库配置
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "qlib_data"
    db_name: str = "qlib_data"

    def __post_init__(self):
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir).expanduser()


@dataclass
class FilterThresholds:
    """过滤阈值配置"""
    min_history_days: int = 180
    min_annual_vol: float = 0.02
    min_avg_turnover_yuan: float = 5000.0


@dataclass
class FilterResult:
    """单个标的的过滤结果"""
    ts_code: str
    passed: bool
    count_days: int
    first_trade_date: Optional[str]
    last_trade_date: Optional[str]
    annual_vol: float
    avg_turnover_yuan: Optional[float]
    fail_reasons: List[str] = field(default_factory=list)


@dataclass
class FilterStatistics:
    """过滤统计信息"""
    total_candidates: int = 0
    passed: int = 0
    filtered: int = 0
    fail_insufficient_history: int = 0
    fail_low_volatility: int = 0
    fail_low_turnover: int = 0


@dataclass
class FilteredRecord:
    """被过滤的记录详情（用于输出CSV）"""
    data_type: str
    ts_code: str
    instrument_name: str
    admission_start_date: Optional[str]
    end_date: str
    sample_trading_days: int
    annual_volatility: float
    avg_turnover_yuan: Optional[float]
    fail_reasons: str
    threshold_min_history_days: int
    threshold_min_annual_vol: float
    threshold_min_avg_turnover_yuan: Optional[float]


@dataclass
class DailyExportStats:
    """日线数据导出统计"""
    instrument_count: int = 0
    daily_records: int = 0
    date_range: List[Optional[str]] = field(default_factory=lambda: [None, None])
    filter_statistics: Optional[FilterStatistics] = None
    filter_thresholds: Optional[FilterThresholds] = None


@dataclass
class ExportMetadata:
    """导出元数据"""
    export_time: str
    start_date: str
    end_date: str
    data_types: List[str]
    export_basic: bool
    export_daily: bool
    statistics: Dict[str, Dict[str, Any]]
    output_dir: str
    database: Dict[str, Any]
    disk_free_gb: float
    filters: Optional[Dict[str, Any]] = None
    filter_statistics: Optional[Dict[str, Any]] = None


# 列定义常量
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
    "adj_factor",
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
        "adj_open",
        "adj_high",
        "adj_low",
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
        "adj_open",
        "adj_high",
        "adj_low",
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
