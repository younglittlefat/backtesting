"""
Configuration Loader for ETF Trend Following V2 System

This module provides configuration loading, validation, and management
for the ETF trend following system with hierarchical JSON configuration support.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Literal
from datetime import datetime


# ============================================================================
# Environment Configuration
# ============================================================================

@dataclass
class EnvConfig:
    """Environment and path configuration"""
    root_dir: str
    data_dir: str = "data/chinese_etf/daily"
    results_dir: str = "results"
    log_dir: str = "logs"
    timezone: str = "Asia/Shanghai"
    trading_calendar: str = "SSE"  # Shanghai Stock Exchange

    def validate(self) -> List[str]:
        """Validate environment configuration"""
        errors = []
        if not self.root_dir:
            errors.append("env.root_dir is required")
        if self.timezone not in ["Asia/Shanghai", "UTC", "America/New_York"]:
            errors.append(f"env.timezone '{self.timezone}' not supported")
        if self.trading_calendar not in ["SSE", "NYSE", "NASDAQ"]:
            errors.append(f"env.trading_calendar '{self.trading_calendar}' not supported")
        return errors


# ============================================================================
# Mode Configuration
# ============================================================================

@dataclass
class ModesConfig:
    """Operating mode configuration"""
    run_mode: Literal["backtest", "signal", "live-dryrun"] = "backtest"
    as_of_date: Optional[str] = None  # YYYY-MM-DD format, None means today
    lookback_days: int = 500
    calendar_offsets: Dict[str, int] = field(default_factory=lambda: {
        "signal_generation": -1,  # T-1 for signal generation
        "execution": 0  # T for execution
    })

    def validate(self) -> List[str]:
        """Validate modes configuration"""
        errors = []
        if self.run_mode not in ["backtest", "signal", "live-dryrun"]:
            errors.append(f"modes.run_mode must be one of backtest/signal/live-dryrun, got '{self.run_mode}'")

        if self.as_of_date:
            try:
                datetime.strptime(self.as_of_date, "%Y-%m-%d")
            except ValueError:
                errors.append(f"modes.as_of_date must be in YYYY-MM-DD format, got '{self.as_of_date}'")

        if self.lookback_days < 1:
            errors.append(f"modes.lookback_days must be positive, got {self.lookback_days}")

        return errors


# ============================================================================
# Universe Configuration
# ============================================================================

@dataclass
class UniverseConfig:
    """Trading universe configuration"""
    pool_file: Optional[str] = None  # Path to CSV file with stock list
    pool_list: Optional[List[str]] = None  # Direct list of stock codes
    liquidity_threshold: Dict[str, float] = field(default_factory=lambda: {
        "min_avg_volume": 1000000,  # Minimum average daily volume
        "min_avg_amount": 5000000,  # Minimum average daily amount (CNY)
        "min_turnover_rate": 0.001  # Minimum turnover rate
    })
    blacklist: List[str] = field(default_factory=list)
    handle_delisted: Literal["exclude", "keep_until_delist", "warn"] = "exclude"
    # Dynamic pool configuration
    dynamic_pool: bool = False  # If True, dynamically filter ETFs by liquidity on each rebalance day
    all_etf_data_dir: Optional[str] = None  # Directory containing all ETF data for dynamic filtering
    min_listing_days: int = 60  # Minimum listing days for dynamic pool (default: 60 days)

    def validate(self, require_pool: bool = True) -> List[str]:
        """Validate universe configuration"""
        errors = []

        # If dynamic_pool is enabled, pool_file and pool_list are optional
        if not self.dynamic_pool:
            if require_pool and not self.pool_file and not self.pool_list:
                errors.append("universe.pool_file or universe.pool_list must be specified when dynamic_pool is False")
        else:
            # Dynamic pool mode: all_etf_data_dir is required
            if not self.all_etf_data_dir:
                errors.append("universe.all_etf_data_dir is required when dynamic_pool is True")

        if self.pool_file and self.pool_list:
            errors.append("universe.pool_file and universe.pool_list are mutually exclusive")

        if self.liquidity_threshold.get("min_avg_volume", 0) < 0:
            errors.append("universe.liquidity_threshold.min_avg_volume must be non-negative")

        if self.liquidity_threshold.get("min_avg_amount", 0) < 0:
            errors.append("universe.liquidity_threshold.min_avg_amount must be non-negative")

        if not 0 <= self.liquidity_threshold.get("min_turnover_rate", 0) <= 1:
            errors.append("universe.liquidity_threshold.min_turnover_rate must be in [0, 1]")

        if self.min_listing_days < 0:
            errors.append(f"universe.min_listing_days must be non-negative, got {self.min_listing_days}")

        return errors


# ============================================================================
# Rotation Configuration
# ============================================================================

@dataclass
class RotationConfig:
    """Dynamic rotation schedule configuration"""
    enabled: bool = False
    schedule_path: Optional[str] = None
    period_days: int = 5
    pool_size: int = 20

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.enabled and not self.schedule_path:
            errors.append("rotation.schedule_path is required when rotation.enabled is true")
        if self.period_days is not None and self.period_days < 1:
            errors.append(f"rotation.period_days must be positive, got {self.period_days}")
        if self.pool_size is not None and self.pool_size < 1:
            errors.append(f"rotation.pool_size must be positive, got {self.pool_size}")
        return errors


# ============================================================================
# Strategy Configuration
# ============================================================================

@dataclass
class MACDStrategyConfig:
    """MACD strategy configuration"""
    type: Literal["macd"] = "macd"
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    # Phase 2: Filter switches
    enable_adx_filter: bool = False
    adx_period: int = 14
    adx_threshold: float = 25.0
    enable_volume_filter: bool = False
    volume_period: int = 20
    volume_ratio: float = 1.2
    enable_slope_filter: bool = False
    slope_lookback: int = 5
    enable_confirm_filter: bool = False
    confirm_bars: int = 2
    # Phase 3: Loss protection
    enable_loss_protection: bool = False
    max_consecutive_losses: int = 3
    pause_bars: int = 10
    # Trailing stop
    enable_trailing_stop: bool = False
    trailing_stop_pct: float = 0.05
    # Anti-Whipsaw features
    enable_hysteresis: bool = False
    hysteresis_mode: str = 'std'  # 'std' or 'abs'
    hysteresis_k: float = 0.5
    hysteresis_window: int = 20
    hysteresis_abs: float = 0.001
    confirm_bars_sell: int = 0
    min_hold_bars: int = 0
    enable_zero_axis: bool = False
    zero_axis_mode: str = 'symmetric'
    # Long-only mode (A-share market does not allow short selling)
    long_only: bool = True

    def validate(self) -> List[str]:
        """Validate MACD strategy configuration"""
        errors = []
        if self.fast_period >= self.slow_period:
            errors.append(f"MACD fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})")
        if self.signal_period < 1:
            errors.append(f"MACD signal_period must be positive, got {self.signal_period}")
        if self.adx_period < 1:
            errors.append(f"MACD adx_period must be positive, got {self.adx_period}")
        if self.adx_threshold < 0:
            errors.append(f"MACD adx_threshold must be non-negative, got {self.adx_threshold}")
        if self.volume_period < 1:
            errors.append(f"MACD volume_period must be positive, got {self.volume_period}")
        if self.volume_ratio < 0:
            errors.append(f"MACD volume_ratio must be non-negative, got {self.volume_ratio}")
        if self.trailing_stop_pct <= 0 or self.trailing_stop_pct >= 1:
            errors.append(f"MACD trailing_stop_pct must be in (0, 1), got {self.trailing_stop_pct}")
        if self.max_consecutive_losses < 1:
            errors.append(f"MACD max_consecutive_losses must be positive, got {self.max_consecutive_losses}")
        return errors


@dataclass
class KAMAStrategyConfig:
    """KAMA strategy configuration"""
    type: Literal["kama"] = "kama"
    kama_period: int = 20
    kama_fast: int = 2
    kama_slow: int = 30
    # Phase 1: KAMA-specific filters
    enable_efficiency_filter: bool = False
    min_efficiency_ratio: float = 0.3
    enable_slope_confirmation: bool = False
    min_slope_periods: int = 3
    # Phase 2: Generic filters
    enable_slope_filter: bool = False
    slope_lookback: int = 5
    enable_adx_filter: bool = False
    adx_period: int = 14
    adx_threshold: float = 25.0
    enable_volume_filter: bool = False
    volume_period: int = 20
    volume_ratio: float = 1.2
    # Phase 3: Loss protection
    enable_loss_protection: bool = False
    max_consecutive_losses: int = 3
    pause_bars: int = 10
    # Long-only mode (A-share market does not allow short selling)
    long_only: bool = True

    def validate(self) -> List[str]:
        """Validate KAMA strategy configuration"""
        errors = []
        if self.kama_period < 1:
            errors.append(f"KAMA kama_period must be positive, got {self.kama_period}")
        if self.kama_fast < 1:
            errors.append(f"KAMA kama_fast must be positive, got {self.kama_fast}")
        if self.kama_slow < 1:
            errors.append(f"KAMA kama_slow must be positive, got {self.kama_slow}")
        if self.kama_fast >= self.kama_slow:
            errors.append(f"KAMA kama_fast ({self.kama_fast}) must be < kama_slow ({self.kama_slow})")
        if not 0 <= self.min_efficiency_ratio <= 1:
            errors.append(f"KAMA min_efficiency_ratio must be in [0, 1], got {self.min_efficiency_ratio}")
        if self.max_consecutive_losses < 1:
            errors.append(f"KAMA max_consecutive_losses must be positive, got {self.max_consecutive_losses}")
        return errors


@dataclass
class ComboStrategyConfig:
    """Combo strategy configuration"""
    type: Literal["combo"] = "combo"
    mode: Literal["or", "and", "split"] = "or"
    strategies: List[Union[MACDStrategyConfig, KAMAStrategyConfig]] = field(default_factory=list)
    weights: Optional[Dict[str, float]] = None  # For split mode
    conflict_resolution: Literal["first", "majority", "weighted"] = "majority"

    def validate(self) -> List[str]:
        """Validate combo strategy configuration"""
        errors = []
        if not self.strategies:
            errors.append("Combo strategy must have at least one sub-strategy")

        if self.mode == "split" and not self.weights:
            errors.append("Combo strategy in 'split' mode requires weights")

        if self.weights:
            total_weight = sum(self.weights.values())
            if abs(total_weight - 1.0) > 0.01:
                errors.append(f"Combo strategy weights must sum to 1.0, got {total_weight}")

        for i, strategy in enumerate(self.strategies):
            sub_errors = strategy.validate()
            errors.extend([f"Combo strategy[{i}]: {e}" for e in sub_errors])

        return errors


StrategyConfig = Union[MACDStrategyConfig, KAMAStrategyConfig, ComboStrategyConfig]


# ============================================================================
# Scoring Configuration
# ============================================================================

@dataclass
class ScoringConfig:
    """Multi-period momentum scoring configuration"""
    momentum_weights: Dict[str, float] = field(default_factory=lambda: {
        "20d": 0.3,
        "60d": 0.4,
        "120d": 0.3
    })
    buffer_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "buy_top_n": 10,
        "hold_until_rank": 15
    })
    inertia_bonus: float = 0.05  # Bonus coefficient for existing positions
    rebalance_frequency: int = 5  # Days between rebalancing

    def validate(self) -> List[str]:
        """Validate scoring configuration"""
        errors = []

        # Validate momentum weights sum to 1.0
        total_weight = sum(self.momentum_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            errors.append(f"scoring.momentum_weights must sum to 1.0, got {total_weight}")

        # Validate buffer thresholds
        buy_top_n = self.buffer_thresholds.get("buy_top_n", 0)
        hold_until_rank = self.buffer_thresholds.get("hold_until_rank", 0)

        if buy_top_n < 1:
            errors.append(f"scoring.buffer_thresholds.buy_top_n must be positive, got {buy_top_n}")

        if hold_until_rank < buy_top_n:
            errors.append(f"scoring.buffer_thresholds.hold_until_rank ({hold_until_rank}) must be >= buy_top_n ({buy_top_n})")

        if self.inertia_bonus < 0:
            errors.append(f"scoring.inertia_bonus must be non-negative, got {self.inertia_bonus}")

        if self.rebalance_frequency < 1:
            errors.append(f"scoring.rebalance_frequency must be positive, got {self.rebalance_frequency}")

        return errors


# ============================================================================
# Clustering Configuration
# ============================================================================

@dataclass
class ClusteringConfig:
    """Correlation-based clustering configuration"""
    correlation_window: int = 60  # Days for correlation calculation
    distance_metric: Literal["correlation", "euclidean", "dtw"] = "correlation"
    linkage_method: Literal["single", "complete", "average", "ward"] = "average"
    cut_threshold: float = 0.5  # Distance threshold for cutting dendrogram
    max_positions_per_cluster: int = 2
    update_frequency: int = 20  # Days between cluster updates

    def validate(self) -> List[str]:
        """Validate clustering configuration"""
        errors = []

        if self.correlation_window < 10:
            errors.append(f"clustering.correlation_window must be >= 10, got {self.correlation_window}")

        if not 0 <= self.cut_threshold <= 1:
            errors.append(f"clustering.cut_threshold must be in [0, 1], got {self.cut_threshold}")

        if self.max_positions_per_cluster < 1:
            errors.append(f"clustering.max_positions_per_cluster must be positive, got {self.max_positions_per_cluster}")

        if self.update_frequency < 1:
            errors.append(f"clustering.update_frequency must be positive, got {self.update_frequency}")

        return errors


# ============================================================================
# Risk Management Configuration
# ============================================================================

@dataclass
class RiskConfig:
    """Risk management configuration"""
    atr_window: int = 14
    atr_multiplier: float = 2.0
    time_stop_days: int = 60
    time_stop_threshold: float = -0.05  # -5% loss threshold for time stop
    circuit_breaker_threshold: float = -0.10  # -10% daily loss triggers circuit breaker
    min_liquidity_threshold: float = 1000000  # Minimum daily volume
    enable_t1_restriction: bool = True  # T+1 trading restriction for China

    def validate(self) -> List[str]:
        """Validate risk configuration"""
        errors = []

        if self.atr_window < 1:
            errors.append(f"risk.atr_window must be positive, got {self.atr_window}")

        if self.atr_multiplier <= 0:
            errors.append(f"risk.atr_multiplier must be positive, got {self.atr_multiplier}")

        if self.time_stop_days < 1:
            errors.append(f"risk.time_stop_days must be positive, got {self.time_stop_days}")

        if self.time_stop_threshold > 0:
            errors.append(f"risk.time_stop_threshold should be negative (loss), got {self.time_stop_threshold}")

        if self.circuit_breaker_threshold > 0:
            errors.append(f"risk.circuit_breaker_threshold should be negative (loss), got {self.circuit_breaker_threshold}")

        if self.min_liquidity_threshold < 0:
            errors.append(f"risk.min_liquidity_threshold must be non-negative, got {self.min_liquidity_threshold}")

        return errors


# ============================================================================
# Position Sizing Configuration
# ============================================================================

@dataclass
class PositionSizingConfig:
    """Position sizing and portfolio constraints configuration"""
    target_risk_per_position: float = 0.02  # 2% risk per position
    volatility_method: Literal["std", "ewma", "atr"] = "ewma"
    ewma_lambda: float = 0.94  # For EWMA volatility estimation
    max_positions: int = 20
    max_position_size: float = 0.15  # 15% max per position
    max_cluster_size: float = 0.30  # 30% max per cluster
    max_total_exposure: float = 0.95  # 95% max total exposure
    min_cash_reserve: float = 0.05  # 5% minimum cash reserve
    commission_rate: float = 0.0003  # 0.03% commission
    slippage_bps: float = 5.0  # 5 bps slippage

    def validate(self) -> List[str]:
        """Validate position sizing configuration"""
        errors = []

        if not 0 < self.target_risk_per_position <= 0.1:
            errors.append(f"position_sizing.target_risk_per_position must be in (0, 0.1], got {self.target_risk_per_position}")

        if self.volatility_method == "ewma" and not 0 < self.ewma_lambda < 1:
            errors.append(f"position_sizing.ewma_lambda must be in (0, 1), got {self.ewma_lambda}")

        if self.max_positions < 1:
            errors.append(f"position_sizing.max_positions must be positive, got {self.max_positions}")

        if not 0 < self.max_position_size <= 1:
            errors.append(f"position_sizing.max_position_size must be in (0, 1], got {self.max_position_size}")

        if not 0 < self.max_cluster_size <= 1:
            errors.append(f"position_sizing.max_cluster_size must be in (0, 1], got {self.max_cluster_size}")

        if not 0 < self.max_total_exposure <= 1:
            errors.append(f"position_sizing.max_total_exposure must be in (0, 1], got {self.max_total_exposure}")

        if not 0 <= self.min_cash_reserve < 1:
            errors.append(f"position_sizing.min_cash_reserve must be in [0, 1), got {self.min_cash_reserve}")

        if self.max_total_exposure + self.min_cash_reserve > 1.01:
            errors.append(f"position_sizing.max_total_exposure + min_cash_reserve must be <= 1.0")

        if self.commission_rate < 0:
            errors.append(f"position_sizing.commission_rate must be non-negative, got {self.commission_rate}")

        if self.slippage_bps < 0:
            errors.append(f"position_sizing.slippage_bps must be non-negative, got {self.slippage_bps}")

        return errors


# ============================================================================
# Execution Configuration
# ============================================================================

@dataclass
class ExecutionConfig:
    """Order execution configuration"""
    order_time_strategy: Literal["open", "close", "vwap", "twap"] = "close"
    matching_assumption: Literal["immediate", "next_bar", "realistic"] = "next_bar"
    slippage_model: Literal["fixed", "volume_based", "spread_based"] = "fixed"
    handle_t1_restriction: bool = True  # Handle T+1 restriction for China market

    def validate(self) -> List[str]:
        """Validate execution configuration"""
        errors = []
        # All fields have literal types with valid defaults, minimal validation needed
        return errors


# ============================================================================
# I/O Configuration
# ============================================================================

@dataclass
class IOConfig:
    """Input/Output configuration"""
    signal_output_path: str = "signals/signals_{date}.csv"
    position_snapshot_path: str = "positions/positions_{date}.json"
    performance_report_path: str = "reports/performance_{date}.html"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    save_intermediate_results: bool = True

    def validate(self) -> List[str]:
        """Validate I/O configuration"""
        errors = []

        if not self.signal_output_path:
            errors.append("io.signal_output_path is required")

        if not self.position_snapshot_path:
            errors.append("io.position_snapshot_path is required")

        if not self.performance_report_path:
            errors.append("io.performance_report_path is required")

        return errors


# ============================================================================
# Main Configuration
# ============================================================================

@dataclass
class Config:
    """Main configuration container"""
    env: EnvConfig
    modes: ModesConfig
    universe: UniverseConfig
    strategies: List[StrategyConfig]
    scoring: ScoringConfig
    clustering: ClusteringConfig
    risk: RiskConfig
    position_sizing: PositionSizingConfig
    execution: ExecutionConfig
    io: IOConfig
    rotation: RotationConfig = field(default_factory=RotationConfig)

    def validate(self) -> List[str]:
        """Validate entire configuration"""
        errors = []

        # Validate each section
        errors.extend([f"env: {e}" for e in self.env.validate()])
        errors.extend([f"modes: {e}" for e in self.modes.validate()])
        # Allow no pool requirement if rotation or dynamic_pool is enabled
        require_pool = not (getattr(self.rotation, "enabled", False) or getattr(self.universe, "dynamic_pool", False))
        universe_errors = self.universe.validate(require_pool=require_pool)
        errors.extend([f"universe: {e}" for e in universe_errors])
        errors.extend([f"rotation: {e}" for e in self.rotation.validate()])
        errors.extend([f"scoring: {e}" for e in self.scoring.validate()])
        errors.extend([f"clustering: {e}" for e in self.clustering.validate()])
        errors.extend([f"risk: {e}" for e in self.risk.validate()])
        errors.extend([f"position_sizing: {e}" for e in self.position_sizing.validate()])
        errors.extend([f"execution: {e}" for e in self.execution.validate()])
        errors.extend([f"io: {e}" for e in self.io.validate()])

        # Validate strategies
        if not self.strategies:
            errors.append("strategies: At least one strategy must be configured")

        for i, strategy in enumerate(self.strategies):
            strategy_errors = strategy.validate()
            errors.extend([f"strategies[{i}]: {e}" for e in strategy_errors])

        # Cross-section validations
        if self.scoring.buffer_thresholds["buy_top_n"] > self.position_sizing.max_positions:
            errors.append(
                f"scoring.buy_top_n ({self.scoring.buffer_thresholds['buy_top_n']}) "
                f"should not exceed position_sizing.max_positions ({self.position_sizing.max_positions})"
            )

        if getattr(self.rotation, "enabled", False):
            if self.universe.pool_file or self.universe.pool_list:
                errors.append("rotation.enabled is true: universe.pool_file/pool_list must be omitted")
            if not self.rotation.schedule_path:
                errors.append("rotation.enabled is true: rotation.schedule_path is required")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)


# ============================================================================
# Configuration Loading Functions
# ============================================================================

def _parse_strategy(strategy_dict: Dict[str, Any]) -> StrategyConfig:
    """Parse strategy configuration from dictionary"""
    strategy_type = strategy_dict.get("type", "macd")

    if strategy_type == "macd":
        return MACDStrategyConfig(**strategy_dict)
    elif strategy_type == "kama":
        return KAMAStrategyConfig(**strategy_dict)
    elif strategy_type == "combo":
        # Parse sub-strategies recursively
        sub_strategies = [
            _parse_strategy(s) for s in strategy_dict.get("strategies", [])
        ]
        strategy_dict_copy = strategy_dict.copy()
        strategy_dict_copy["strategies"] = sub_strategies
        return ComboStrategyConfig(**strategy_dict_copy)
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")


def load_config(path: Union[str, Path]) -> Config:
    """
    Load configuration from JSON file

    Args:
        path: Path to configuration JSON file

    Returns:
        Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        json.JSONDecodeError: If JSON is malformed
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        config_dict = json.load(f)

    # Parse each section
    env = EnvConfig(**config_dict.get("env", {}))
    modes = ModesConfig(**config_dict.get("modes", {}))
    universe = UniverseConfig(**config_dict.get("universe", {}))
    rotation = RotationConfig(**config_dict.get("rotation", {}))

    # Parse strategies
    strategies_list = config_dict.get("strategies", [])
    if not strategies_list:
        raise ValueError("Configuration must contain at least one strategy")

    strategies = [_parse_strategy(s) for s in strategies_list]

    # Parse other sections with defaults
    scoring = ScoringConfig(**config_dict.get("scoring", {}))
    clustering = ClusteringConfig(**config_dict.get("clustering", {}))
    risk = RiskConfig(**config_dict.get("risk", {}))
    position_sizing = PositionSizingConfig(**config_dict.get("position_sizing", {}))
    execution = ExecutionConfig(**config_dict.get("execution", {}))
    io = IOConfig(**config_dict.get("io", {}))

    # Create config object
    config = Config(
        env=env,
        modes=modes,
        universe=universe,
        rotation=rotation,
        strategies=strategies,
        scoring=scoring,
        clustering=clustering,
        risk=risk,
        position_sizing=position_sizing,
        execution=execution,
        io=io
    )

    return config


def validate_config(config: Config) -> List[str]:
    """
    Validate configuration and return list of errors

    Args:
        config: Configuration object to validate

    Returns:
        List of error messages (empty if valid)
    """
    return config.validate()


def save_config(config: Config, path: Union[str, Path]) -> None:
    """
    Save configuration to JSON file

    Args:
        config: Configuration object to save
        path: Path to output JSON file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    config_dict = config.to_dict()

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)


def create_default_config(root_dir: str = ".") -> Config:
    """
    Create a default configuration with sensible defaults

    Args:
        root_dir: Root directory for the project

    Returns:
        Config object with default values
    """
    return Config(
        env=EnvConfig(root_dir=root_dir),
        modes=ModesConfig(),
        universe=UniverseConfig(pool_file="results/trend_etf_pool.csv"),
        rotation=RotationConfig(),
        strategies=[
            KAMAStrategyConfig()  # KAMA is recommended based on experiments
        ],
        scoring=ScoringConfig(),
        clustering=ClusteringConfig(),
        risk=RiskConfig(),
        position_sizing=PositionSizingConfig(),
        execution=ExecutionConfig(),
        io=IOConfig()
    )


# ============================================================================
# Utility Functions
# ============================================================================

def merge_configs(base: Config, override: Dict[str, Any]) -> Config:
    """
    Merge override dictionary into base configuration

    Args:
        base: Base configuration
        override: Dictionary with override values

    Returns:
        New Config object with merged values
    """
    base_dict = base.to_dict()

    # Deep merge
    def deep_merge(d1: Dict, d2: Dict) -> Dict:
        result = d1.copy()
        for key, value in d2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged_dict = deep_merge(base_dict, override)

    # Reconstruct config from merged dictionary
    # This is a simplified approach - in production you'd want more robust merging
    return load_config_from_dict(merged_dict)


def load_config_from_dict(config_dict: Dict[str, Any]) -> Config:
    """
    Load configuration from dictionary (useful for testing and merging)

    Args:
        config_dict: Configuration dictionary

    Returns:
        Config object
    """
    env = EnvConfig(**config_dict.get("env", {}))
    modes = ModesConfig(**config_dict.get("modes", {}))
    universe = UniverseConfig(**config_dict.get("universe", {}))
    rotation = RotationConfig(**config_dict.get("rotation", {}))

    strategies_list = config_dict.get("strategies", [])
    strategies = [_parse_strategy(s) for s in strategies_list]

    scoring = ScoringConfig(**config_dict.get("scoring", {}))
    clustering = ClusteringConfig(**config_dict.get("clustering", {}))
    risk = RiskConfig(**config_dict.get("risk", {}))
    position_sizing = PositionSizingConfig(**config_dict.get("position_sizing", {}))
    execution = ExecutionConfig(**config_dict.get("execution", {}))
    io = IOConfig(**config_dict.get("io", {}))

    return Config(
        env=env,
        modes=modes,
        universe=universe,
        rotation=rotation,
        strategies=strategies,
        scoring=scoring,
        clustering=clustering,
        risk=risk,
        position_sizing=position_sizing,
        execution=execution,
        io=io
    )


if __name__ == "__main__":
    # Example usage
    print("Creating default configuration...")
    config = create_default_config(root_dir="/mnt/d/git/backtesting")

    print("\nValidating configuration...")
    errors = validate_config(config)

    if errors:
        print("Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Configuration is valid!")

    print("\nSaving example configuration...")
    save_config(config, "config/example_config.json")
    print("Example configuration saved to config/example_config.json")
