"""
核心数据模型定义

定义了回测执行器各模块间通信使用的数据结构
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
import pandas as pd

from utils.data_loader import InstrumentInfo
from utils.trading_cost import TradingCostConfig


@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_name: str
    instruments: List[InstrumentInfo]
    cash: float
    cost_config: TradingCostConfig
    optimize: bool
    filter_params: Optional[Dict[str, Any]]
    date_range: Optional[Tuple[str, str]]
    output_dir: str
    verbose: bool
    data_dir: str
    save_params_path: Optional[str] = None
    plot_results: bool = False
    apply_low_vol_filter: bool = False
    low_vol_config: Optional[Any] = None  # LowVolatilityConfig
    blacklist: List[str] = field(default_factory=list)
    strategy_params_config: Optional[str] = None

    # 优化相关
    optimize_params: Optional[Dict[str, Any]] = None
    constraint: Optional[Any] = None
    maximize: str = 'Sharpe Ratio'


@dataclass
class BacktestResult:
    """单次回测结果"""
    instrument: InstrumentInfo
    strategy: str
    stats: pd.Series
    optimized_params: Optional[Dict[str, Any]]
    cost_model: str
    skipped: bool = False
    skip_reason: Optional[str] = None

    # 可选的额外数据
    trades: Optional[pd.DataFrame] = None
    bt_instance: Optional[Any] = None  # Backtest实例


@dataclass
class BacktestResults:
    """批量回测结果"""
    results: List[BacktestResult]
    skipped: List[Dict[str, Any]]  # 低波动跳过的标的
    config: BacktestConfig
    aggregate_stats: Optional[pd.DataFrame] = None

    def successful_results(self) -> List[BacktestResult]:
        """返回成功的回测结果"""
        return [r for r in self.results if not r.skipped]

    def failed_results(self) -> List[BacktestResult]:
        """返回失败的回测结果"""
        return [r for r in self.results if r.skipped]


@dataclass
class RobustParamsResult:
    """稳健参数优化结果"""
    best_params: Dict[str, Any]
    metrics: Dict[str, float]
    analysis: Optional[pd.DataFrame] = None
    all_results: Optional[List[BacktestResult]] = None

    # 统计信息
    total_combinations: int = 0
    tested_combinations: int = 0
    valid_combinations: int = 0


@dataclass
class InstrumentGroup:
    """标的分组信息（按类别）"""
    category: str
    instruments: List[InstrumentInfo]
    count: int

    def __post_init__(self):
        if self.count == 0:
            self.count = len(self.instruments)


@dataclass
class OptimizationProgress:
    """优化进度信息"""
    current: int
    total: int
    instrument: InstrumentInfo
    elapsed_time: float
    estimated_remaining: Optional[float] = None
