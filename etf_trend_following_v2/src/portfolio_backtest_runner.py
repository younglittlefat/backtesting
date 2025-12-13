"""
Portfolio-level backtesting runner for ETF Trend Following v2.

This runner implements the "TopN + buffer(hysteresis) + clustering limit + inverse volatility sizing"
portfolio simulation that backtesting.py cannot natively support (single-instrument engine).

Key design goals:
- Avoid look-ahead bias: all signals/scores/clusters/volatility use data up to decision date.
- Support realistic execution timing: decision on close, execute either same close or next open.
- Model costs: commission + fixed slippage (bps).
- Produce artifacts for analysis: equity curve, fills, positions, cluster exposure, summary stats.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .clustering import get_cluster_assignments, get_cluster_exposure
from .config_loader import Config, KAMAStrategyConfig, MACDStrategyConfig
from .data_loader import filter_by_liquidity, load_universe, load_universe_from_file
from .portfolio import Portfolio, TradeOrder
from .position_sizing import calculate_portfolio_positions
from .risk import check_stop_loss, check_time_stop
from .scoring import apply_inertia_bonus, calculate_universe_scores
from .strategies.combo import ComboSignalGenerator
from .strategies.kama import KAMASignalGenerator
from .strategies.macd import MACDSignalGenerator

logger = logging.getLogger(__name__)


def _to_ohlcv_caps(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with backtesting-style OHLCV column capitalization."""
    df2 = df.copy()
    mapping = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    for src, dst in mapping.items():
        if src in df2.columns and dst not in df2.columns:
            df2.rename(columns={src: dst}, inplace=True)
    return df2


def _build_trend_state(signal_events: pd.Series) -> pd.Series:
    """
    Convert event signals (1/-1/0) into trend state (1=trend on, 0=trend off).

    Trend is considered "on" after the last buy event, and "off" after the last sell event.
    """
    if signal_events.empty:
        return signal_events.copy()

    last_event = signal_events.replace(0, np.nan).ffill().fillna(0)
    # Buy=1 keeps 1; Sell=-1 converts to 0 (trend off)
    return last_event.replace(-1, 0).astype(int)


def _slippage_adjusted_price(price: float, action: str, slippage_bps: float) -> float:
    """Apply fixed slippage to a base price."""
    if price <= 0 or not np.isfinite(price):
        return price
    slippage = slippage_bps / 10000.0
    if action == "buy":
        return price * (1.0 + slippage)
    if action == "sell":
        return price * (1.0 - slippage)
    return price


def _commission(amount: float, commission_rate: float, min_commission: float) -> float:
    """Commission model consistent with src/portfolio.py."""
    if amount <= 0:
        return 0.0
    return max(amount * commission_rate, min_commission)


def _calc_drawdown(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return equity.copy()
    return equity / equity.cummax() - 1.0


def _annualized_return(total_return: float, n_days: int, trading_days: int = 252) -> float:
    if n_days <= 0:
        return 0.0
    return (1.0 + total_return) ** (trading_days / n_days) - 1.0


def _sortino_ratio(day_returns: pd.Series, annual_return: float, rf: float = 0.0) -> float:
    if day_returns.empty:
        return 0.0
    downside = day_returns.clip(upper=0)
    downside_std = downside.std(ddof=0)
    if downside_std == 0 or not np.isfinite(downside_std):
        return 0.0
    return (annual_return - rf) / (downside_std * np.sqrt(252))


class PortfolioBacktestRunner:
    """
    Portfolio-level backtest runner.

    The runner simulates a portfolio that holds up to TopN ETFs selected by
    momentum ranking within the "trend-on" universe, with buffer-zone holding
    and cluster diversification constraints.
    """

    def __init__(self, config: Config):
        self.config = config
        self._signal_events: Dict[str, pd.Series] = {}
        self._trend_state: Dict[str, pd.Series] = {}
        self._cluster_assignments: Dict[str, int] = {}
        self._last_cluster_update_idx: Optional[int] = None

        self._strategy_generator = self._init_signal_generator()

    def _init_signal_generator(self):
        if not self.config.strategies:
            raise ValueError("No strategies configured")

        strategy_cfg = self.config.strategies[0]
        if isinstance(strategy_cfg, MACDStrategyConfig):
            return MACDSignalGenerator(**asdict(strategy_cfg))
        if isinstance(strategy_cfg, KAMAStrategyConfig):
            return KAMASignalGenerator(**asdict(strategy_cfg))

        # Combo config is supported for signal gating only.
        # Config schema and generator schema are not fully aligned; best-effort mapping here.
        combo_type = getattr(strategy_cfg, "type", None)
        if combo_type == "combo":
            mode = getattr(strategy_cfg, "mode", "or")
            conflict_resolution = getattr(strategy_cfg, "conflict_resolution", "macd_priority")
            weights = getattr(strategy_cfg, "weights", None)

            macd_config: Dict[str, Any] = {}
            kama_config: Dict[str, Any] = {}
            for sub in getattr(strategy_cfg, "strategies", []):
                sub_type = getattr(sub, "type", None)
                if sub_type == "macd":
                    macd_config = asdict(sub)
                elif sub_type == "kama":
                    kama_config = asdict(sub)

            # Some older configs use different conflict resolution labels.
            if conflict_resolution in {"first", "majority", "weighted"}:
                conflict_resolution = "macd_priority"

            return ComboSignalGenerator(
                mode=mode,
                macd_config=macd_config,
                kama_config=kama_config,
                weights=weights,
                conflict_resolution=conflict_resolution,
            )

        raise ValueError(f"Unsupported strategy config: {type(strategy_cfg)}")

    def _load_data(self, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        start_dt = pd.to_datetime(start_date)
        lookback_days = int(self.config.modes.lookback_days)
        data_start = (start_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        if self.config.universe.pool_file:
            data_dict = load_universe_from_file(
                pool_file=self.config.universe.pool_file,
                data_dir=self.config.env.data_dir,
                start_date=data_start,
                end_date=end_date,
                use_adj=True,
                skip_errors=True,
            )
        elif self.config.universe.pool_list:
            data_dict = load_universe(
                symbols=self.config.universe.pool_list,
                data_dir=self.config.env.data_dir,
                start_date=data_start,
                end_date=end_date,
                use_adj=True,
                skip_errors=True,
            )
        else:
            raise ValueError("No universe configured (pool_file or pool_list required)")

        def _infer_liquidity_scaling(sample_df: pd.DataFrame) -> Tuple[float, float]:
            """
            Infer unit scaling for (volume, amount) columns.

            Many TuShare exports use:
            - volume: hands (1 hand = 100 shares)
            - amount: k_yuan (1 unit = 1,000 yuan)

            We infer this by checking whether close*volume aligns with amount, or close*volume*100
            aligns with amount*1000.
            """
            if sample_df is None or sample_df.empty:
                return 1.0, 1.0
            if "amount" not in sample_df.columns:
                return 1.0, 1.0

            s = sample_df[["close", "volume", "amount"]].dropna()
            s = s[(s["close"] > 0) & (s["volume"] > 0) & (s["amount"] > 0)]
            if s.empty:
                return 1.0, 1.0

            # shares/yuan hypothesis: close*volume ~= amount  -> ratio ~= 1
            ratio1 = (s["close"] * s["volume"] / s["amount"]).median()
            # hands/k_yuan hypothesis: close*volume*100 ~= amount*1000 -> ratio ~= 1
            ratio2 = (s["close"] * s["volume"] * 100 / (s["amount"] * 1000)).median()

            if np.isfinite(ratio1) and 0.5 <= ratio1 <= 2.0:
                return 1.0, 1.0
            if np.isfinite(ratio2) and 0.5 <= ratio2 <= 2.0:
                # Convert config thresholds (shares/yuan) into data units (hands/k_yuan).
                return 1 / 100.0, 1 / 1000.0

            logger.warning(
                "Unable to infer volume/amount units reliably (ratio1=%.3f, ratio2=%.3f); "
                "assuming raw units",
                float(ratio1) if np.isfinite(ratio1) else float("nan"),
                float(ratio2) if np.isfinite(ratio2) else float("nan"),
            )
            return 1.0, 1.0

        # Liquidity filter (static filter based on trailing window of loaded data)
        lt = self.config.universe.liquidity_threshold or {}
        sample_df = next(iter(data_dict.values()), pd.DataFrame())
        vol_scale, amt_scale = _infer_liquidity_scaling(sample_df)

        data_dict = filter_by_liquidity(
            data_dict,
            min_amount=(lt.get("min_avg_amount") * amt_scale if lt.get("min_avg_amount") else None),
            min_volume=(lt.get("min_avg_volume") * vol_scale if lt.get("min_avg_volume") else None),
            lookback_days=20,
            min_valid_days=15,
        )

        return data_dict

    def _precompute_signals(self, data_dict: Dict[str, pd.DataFrame]) -> None:
        self._signal_events.clear()
        self._trend_state.clear()

        for symbol, df in data_dict.items():
            df_sig = _to_ohlcv_caps(df)
            df_ind = self._strategy_generator.calculate_indicators(df_sig)
            events = self._strategy_generator.generate_signals(df_ind)

            # Normalize combo/split signals to {-1, 0, 1}
            if not events.empty and not np.issubdtype(events.dtype, np.integer):
                events = events.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

            events = events.astype(int)
            self._signal_events[symbol] = events
            self._trend_state[symbol] = _build_trend_state(events)

        logger.info(f"Precomputed signals for {len(self._signal_events)} symbols")

    def _get_price(
        self, data_dict: Dict[str, pd.DataFrame], symbol: str, date: pd.Timestamp, field: str
    ) -> float:
        df = data_dict.get(symbol)
        if df is None or df.empty:
            return np.nan
        if date not in df.index:
            return np.nan
        val = df.at[date, field]
        try:
            return float(val)
        except Exception:
            return np.nan

    def _update_clusters_if_needed(
        self,
        data_dict: Dict[str, pd.DataFrame],
        decision_date: pd.Timestamp,
        decision_idx: int,
        force: bool = False,
    ) -> None:
        freq = int(self.config.clustering.update_frequency)
        if not force and self._last_cluster_update_idx is not None:
            if decision_idx - self._last_cluster_update_idx < freq:
                return

        # Use only history up to decision_date (avoid look-ahead).
        sliced = {s: df[df.index <= decision_date] for s, df in data_dict.items()}

        try:
            clusters, _corr = get_cluster_assignments(
                sliced,
                lookback_days=int(self.config.clustering.correlation_window),
                correlation_threshold=float(self.config.clustering.cut_threshold),
                method=str(self.config.clustering.linkage_method),
                price_col="close",
            )
        except Exception as e:
            logger.warning(f"Cluster update failed on {decision_date.date()}: {e}")
            return

        self._cluster_assignments = clusters
        self._last_cluster_update_idx = decision_idx
        logger.info(
            f"Updated clusters on {decision_date.date()}: {len(set(clusters.values()))} clusters"
        )

    def _eligible_symbols(
        self,
        data_dict: Dict[str, pd.DataFrame],
        decision_date: pd.Timestamp,
    ) -> List[str]:
        eligible = []
        for symbol, df in data_dict.items():
            if decision_date not in df.index:
                continue
            state = self._trend_state.get(symbol)
            if state is None or decision_date not in state.index:
                continue
            if int(state.loc[decision_date]) == 1:
                eligible.append(symbol)
        return eligible

    def _forced_sells(
        self,
        portfolio: Portfolio,
        data_dict: Dict[str, pd.DataFrame],
        decision_date: pd.Timestamp,
    ) -> Tuple[List[str], Dict[str, str]]:
        forced: List[str] = []
        reasons: Dict[str, str] = {}
        date_str = decision_date.strftime("%Y-%m-%d")

        for symbol, pos in portfolio.positions.items():
            # Trend gate: if trend is off, request sell.
            state = self._trend_state.get(symbol)
            if state is None or decision_date not in state.index or int(state.loc[decision_date]) == 0:
                forced.append(symbol)
                reasons[symbol] = "trend_off"
                continue

            df = data_dict.get(symbol)
            if df is None or df.empty or decision_date not in df.index:
                # No price today: cannot evaluate stop; keep.
                continue

            # ATR stop
            try:
                atr_res = check_stop_loss(
                    df=df[df.index <= decision_date],
                    entry_date=pos.entry_date,
                    entry_price=pos.entry_price,
                    atr_multiplier=float(self.config.risk.atr_multiplier),
                    atr_period=int(self.config.risk.atr_window),
                    check_until_date=date_str,
                )
                if atr_res.get("triggered", False):
                    forced.append(symbol)
                    reasons[symbol] = "atr_stop"
                    continue
            except Exception as e:
                logger.debug(f"{symbol}: ATR stop check failed: {e}")

            # Time stop (use requirement-aligned ATR multiple threshold)
            try:
                time_res = check_time_stop(
                    df=df[df.index <= decision_date],
                    entry_date=pos.entry_date,
                    entry_price=pos.entry_price,
                    max_hold_days=int(self.config.risk.time_stop_days),
                    min_profit_atr=1.0,
                    atr_period=int(self.config.risk.atr_window),
                    check_until_date=date_str,
                )
                if time_res.get("triggered", False):
                    forced.append(symbol)
                    reasons[symbol] = "time_stop"
                    continue
            except Exception as e:
                logger.debug(f"{symbol}: time stop check failed: {e}")

        return forced, reasons

    def _select_symbols(
        self,
        scores_df: pd.DataFrame,
        current_holdings: List[str],
        forced_sells: List[str],
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Select desired symbols after applying buffer + cluster position limits.

        Returns:
            (final_symbols, sell_reasons)
        """
        buy_top_n = int(self.config.scoring.buffer_thresholds["buy_top_n"])
        hold_until_rank = int(self.config.scoring.buffer_thresholds["hold_until_rank"])
        target_count = min(int(self.config.position_sizing.max_positions), buy_top_n)

        # Decide which rank/score columns are available.
        rank_col = "adjusted_rank" if "adjusted_rank" in scores_df.columns else "rank"
        score_col = "adjusted_score" if "adjusted_score" in scores_df.columns else "raw_score"

        symbol_rank = dict(zip(scores_df["symbol"], scores_df[rank_col]))
        symbol_score = dict(zip(scores_df["symbol"], scores_df[score_col]))

        sell_reasons: Dict[str, str] = {s: "forced_sell" for s in forced_sells}

        # Step 1: Keep holdings within buffer, unless forced to sell.
        keep: List[str] = []
        for sym in current_holdings:
            if sym in forced_sells:
                continue
            rank = symbol_rank.get(sym)
            if rank is None:
                sell_reasons[sym] = "dropped_from_universe"
                continue
            if int(rank) <= hold_until_rank:
                keep.append(sym)
            else:
                sell_reasons[sym] = f"rank_out_{int(rank)}"

        # Step 2: Add new entries from top N.
        top_n_symbols = scores_df[scores_df[rank_col] <= buy_top_n]["symbol"].tolist()
        desired = keep + [s for s in top_n_symbols if s not in keep and s not in forced_sells]

        # Step 3: Apply cluster position limit (count-based) with score tie-breaker.
        max_per_cluster = int(self.config.clustering.max_positions_per_cluster)

        def _cluster_id(sym: str) -> str:
            # Missing cluster → treat as unique (do not constrain).
            cid = self._cluster_assignments.get(sym)
            return f"cid:{cid}" if cid is not None else f"sym:{sym}"

        # Build per-cluster buckets.
        buckets: Dict[str, List[str]] = {}
        for sym in desired:
            buckets.setdefault(_cluster_id(sym), []).append(sym)

        kept: List[str] = []
        for cid, syms in buckets.items():
            if len(syms) <= max_per_cluster:
                kept.extend(syms)
                continue
            syms_sorted = sorted(syms, key=lambda s: float(symbol_score.get(s, -np.inf)), reverse=True)
            kept.extend(syms_sorted[:max_per_cluster])
            dropped = set(syms_sorted[max_per_cluster:])
            for d in dropped:
                if d in current_holdings and d not in sell_reasons:
                    sell_reasons[d] = "cluster_limit"

        # Step 4: Fill remaining slots from the ranked list while respecting cluster limit.
        cluster_counts: Dict[str, int] = {}
        for sym in kept:
            cid = _cluster_id(sym)
            cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

        if len(kept) < target_count:
            for sym in scores_df.sort_values(rank_col)["symbol"].tolist():
                if sym in kept or sym in forced_sells:
                    continue
                cid = _cluster_id(sym)
                if cluster_counts.get(cid, 0) >= max_per_cluster:
                    continue
                kept.append(sym)
                cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
                if len(kept) >= target_count:
                    break

        # Enforce overall cap (could be exceeded if keep > target_count)
        if len(kept) > target_count:
            kept_sorted = sorted(kept, key=lambda s: int(symbol_rank.get(s, 10**9)))
            drop = set(kept_sorted[target_count:])
            kept = kept_sorted[:target_count]
            for d in drop:
                if d in current_holdings and d not in sell_reasons:
                    sell_reasons[d] = "max_positions"

        return kept, sell_reasons

    def run(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run portfolio-level backtest.

        Returns a dict with keys:
        - equity_curve: DataFrame (date index)
        - fills: DataFrame (executed orders with costs)
        - positions: DataFrame (daily position snapshots)
        - cluster_exposure: DataFrame (daily cluster exposure summary)
        - stats: dict (summary statistics)
        """
        data_dict = self._load_data(start_date, end_date)
        if not data_dict:
            raise ValueError("No data loaded after filtering")

        self._precompute_signals(data_dict)

        all_dates = sorted(set().union(*[df.index for df in data_dict.values()]))
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        dates = [d for d in all_dates if start_dt <= d <= end_dt]
        if len(dates) < 2:
            raise ValueError("Insufficient trading dates in backtest window")

        exec_mode = str(self.config.execution.order_time_strategy)
        if exec_mode not in {"close", "open"}:
            raise ValueError(f"Unsupported execution.order_time_strategy: {exec_mode}")

        portfolio = Portfolio(
            initial_cash=float(initial_capital),
            commission_rate=float(self.config.position_sizing.commission_rate),
            stamp_duty_rate=0.0,
            min_commission=5.0,
        )

        rebalance_freq = int(self.config.scoring.rebalance_frequency)
        last_rebalance_idx: Optional[int] = None

        pending_orders: List[TradeOrder] = []

        fills: List[dict] = []
        positions_snapshots: List[dict] = []
        cluster_daily: List[dict] = []

        slippage_bps = float(self.config.position_sizing.slippage_bps)

        for i, date in enumerate(dates):
            date_str = date.strftime("%Y-%m-%d")

            def _valid_prices_for(symbols: List[str], field: str) -> Dict[str, float]:
                out: Dict[str, float] = {}
                for s in symbols:
                    p = self._get_price(data_dict, s, date, field)
                    if np.isfinite(p) and p > 0:
                        out[s] = float(p)
                return out

            # 1) Open-mode: try to execute pending orders at today's open.
            if exec_mode == "open" and pending_orders:
                pre_shares = {s: p.shares for s, p in portfolio.positions.items()}

                executable: List[TradeOrder] = []
                deferred: List[TradeOrder] = []
                exec_prices: Dict[str, float] = {}

                for order in pending_orders:
                    base_open = self._get_price(data_dict, order.symbol, date, "open")
                    if not np.isfinite(base_open) or base_open <= 0:
                        deferred.append(order)
                        continue
                    executable.append(order)
                    exec_prices[order.symbol] = _slippage_adjusted_price(
                        float(base_open), order.action, slippage_bps
                    )

                if executable:
                    results = portfolio.apply_orders(
                        executable,
                        execution_date=date_str,
                        execution_prices=exec_prices,
                        include_costs=True,
                    )

                    for idx, order in enumerate(executable):
                        if results.get(idx) != "executed":
                            # Keep failed orders for retry tomorrow.
                            deferred.append(order)
                            continue
                        price = exec_prices.get(order.symbol, order.price)
                        shares_before = int(pre_shares.get(order.symbol, 0))
                        filled_shares = (
                            min(int(order.shares), shares_before)
                            if order.action == "sell"
                            else int(order.shares)
                        )
                        gross = filled_shares * float(price)
                        comm = _commission(
                            gross, portfolio.commission_rate, portfolio.min_commission
                        )
                        cash_flow = -(gross + comm) if order.action == "buy" else (gross - comm)
                        fills.append(
                            {
                                "date": date_str,
                                "symbol": order.symbol,
                                "action": order.action,
                                "shares": filled_shares,
                                "price": float(price),
                                "gross": gross,
                                "commission": comm,
                                "cash_flow": cash_flow,
                                "reason": order.reason,
                            }
                        )

                pending_orders = deferred

            # 2) Decision on close: build orders.
            # If we still have deferred orders (open-mode), avoid stacking new ones.
            can_generate_new_orders = not (exec_mode == "open" and pending_orders)

            # Open execution cannot place new orders on last date (no next bar).
            if exec_mode == "open" and i == len(dates) - 1:
                can_generate_new_orders = False

            if can_generate_new_orders:
                exec_date = dates[i + 1] if exec_mode == "open" else date
                exec_date_str = exec_date.strftime("%Y-%m-%d")

                is_rebalance_day = last_rebalance_idx is None or (i - last_rebalance_idx) >= rebalance_freq

                forced_sell_syms, forced_sell_reasons = self._forced_sells(
                    portfolio, data_dict, decision_date=date
                )

                # If a position has no close price today, do not trade it (cannot sell/buy).
                close_prices_for_holdings = _valid_prices_for(
                    list(portfolio.positions.keys()), "close"
                )
                forced_sell_syms = [
                    s for s in forced_sell_syms if s in close_prices_for_holdings
                ]
                forced_sell_reasons = {
                    s: r for s, r in forced_sell_reasons.items() if s in set(forced_sell_syms)
                }

                if is_rebalance_day or forced_sell_syms:
                    # Update clusters on rebalance days (or if never computed).
                    if is_rebalance_day or not self._cluster_assignments:
                        self._update_clusters_if_needed(data_dict, date, i)

                    current_holdings = list(portfolio.positions.keys())

                    if not is_rebalance_day:
                        # Forced sells only: keep other holdings unchanged.
                        target_positions = {}
                        for sym, pos in portfolio.positions.items():
                            if sym in forced_sell_syms:
                                continue
                            target_positions[sym] = {
                                "shares": int(pos.shares),
                                "price": float(pos.current_price),
                            }

                        orders = portfolio.generate_orders(
                            target_positions=target_positions,
                            current_date=exec_date_str,
                            current_prices=close_prices_for_holdings,
                            sell_reasons=forced_sell_reasons.copy(),
                        )
                    else:
                        eligible = self._eligible_symbols(data_dict, date)
                        eligible_dict = {s: data_dict[s] for s in eligible}

                        scores_df = calculate_universe_scores(
                            eligible_dict,
                            as_of_date=date_str,
                            periods=[20, 60, 120],
                            weights=[
                                float(self.config.scoring.momentum_weights.get("20d", 0.4)),
                                float(self.config.scoring.momentum_weights.get("60d", 0.3)),
                                float(self.config.scoring.momentum_weights.get("120d", 0.3)),
                            ],
                            min_periods_required=20,
                        )

                        scores_df = apply_inertia_bonus(
                            scores_df,
                            current_holdings=[s for s in current_holdings if s in eligible],
                            bonus_pct=float(self.config.scoring.inertia_bonus),
                            bonus_mode="multiplicative",
                        )

                        desired_syms, sell_reasons = self._select_symbols(
                            scores_df=scores_df,
                            current_holdings=current_holdings,
                            forced_sells=forced_sell_syms,
                        )

                        # Turn selection into position sizing.
                        total_equity = portfolio.get_total_equity()
                        sizing_slice = {
                            s: data_dict[s][data_dict[s].index <= date] for s in desired_syms
                        }
                        positions_cfg = calculate_portfolio_positions(
                            data_dict=sizing_slice,
                            symbols=desired_syms,
                            total_capital=total_equity,
                            target_risk_pct=float(self.config.position_sizing.target_risk_per_position),
                            max_position_pct=float(self.config.position_sizing.max_position_size),
                            max_cluster_pct=float(self.config.position_sizing.max_cluster_size),
                            cluster_assignments=self._cluster_assignments if self._cluster_assignments else None,
                            max_total_pct=float(self.config.position_sizing.max_total_exposure),
                            volatility_method=str(self.config.position_sizing.volatility_method),
                            volatility_window=60,
                            ewma_lambda=float(self.config.position_sizing.ewma_lambda),
                        )

                        target_positions: Dict[str, dict] = {}
                        lot = 100
                        for sym in desired_syms:
                            base_close = self._get_price(data_dict, sym, date, "close")
                            if not np.isfinite(base_close) or base_close <= 0:
                                # If held and missing price, keep unchanged.
                                if sym in portfolio.positions:
                                    pos = portfolio.positions[sym]
                                    target_positions[sym] = {
                                        "shares": int(pos.shares),
                                        "price": float(pos.current_price),
                                    }
                                continue

                            tgt_cap = float(positions_cfg.get(sym, {}).get("target_capital", 0.0))
                            shares = int((tgt_cap / float(base_close)) // lot) * lot
                            if shares <= 0:
                                continue
                            target_positions[sym] = {"shares": shares, "price": float(base_close)}

                        # Forced sells take precedence for reason tagging.
                        sell_reasons.update(forced_sell_reasons)

                        orders = portfolio.generate_orders(
                            target_positions=target_positions,
                            current_date=exec_date_str,
                            current_prices=close_prices_for_holdings,
                            sell_reasons=sell_reasons,
                        )

                        last_rebalance_idx = i

                    if orders:
                        if exec_mode == "close":
                            pre_shares = {s: p.shares for s, p in portfolio.positions.items()}
                            exec_prices_close: Dict[str, float] = {}
                            for order in orders:
                                base_close = self._get_price(data_dict, order.symbol, date, "close")
                                if not np.isfinite(base_close) or base_close <= 0:
                                    continue
                                exec_prices_close[order.symbol] = _slippage_adjusted_price(
                                    float(base_close), order.action, slippage_bps
                                )

                            # Execute only orders with a tradable close today.
                            executable = [o for o in orders if o.symbol in exec_prices_close]
                            if executable:
                                results = portfolio.apply_orders(
                                    executable,
                                    execution_date=date_str,
                                    execution_prices=exec_prices_close,
                                    include_costs=True,
                                )

                                for idx, order in enumerate(executable):
                                    if results.get(idx) != "executed":
                                        continue
                                    price = exec_prices_close.get(order.symbol, order.price)
                                    shares_before = int(pre_shares.get(order.symbol, 0))
                                    filled_shares = (
                                        min(int(order.shares), shares_before)
                                        if order.action == "sell"
                                        else int(order.shares)
                                    )
                                    gross = filled_shares * float(price)
                                    comm = _commission(
                                        gross, portfolio.commission_rate, portfolio.min_commission
                                    )
                                    cash_flow = (
                                        -(gross + comm) if order.action == "buy" else (gross - comm)
                                    )
                                    fills.append(
                                        {
                                            "date": date_str,
                                            "symbol": order.symbol,
                                            "action": order.action,
                                            "shares": filled_shares,
                                            "price": float(price),
                                            "gross": gross,
                                            "commission": comm,
                                            "cash_flow": cash_flow,
                                            "reason": order.reason,
                                        }
                                    )
                        else:
                            pending_orders = orders

            # 3) Record end-of-day equity at close (mark-to-market at close).
            close_prices_eod = _valid_prices_for(list(portfolio.positions.keys()), "close")
            portfolio.record_equity(date_str, close_prices_eod)

            total_equity = portfolio.get_total_equity()
            invested_value = sum(pos.market_value for pos in portfolio.positions.values())

            for sym, pos in portfolio.positions.items():
                positions_snapshots.append(
                    {
                        "date": date_str,
                        "symbol": sym,
                        "shares": int(pos.shares),
                        "entry_date": pos.entry_date,
                        "entry_price": float(pos.entry_price),
                        "close": float(pos.current_price),
                        "market_value": float(pos.market_value),
                        "weight": float(pos.market_value / total_equity) if total_equity > 0 else 0.0,
                    }
                )

            if self._cluster_assignments:
                weights = {
                    sym: float(pos.market_value / total_equity) if total_equity > 0 else 0.0
                    for sym, pos in portfolio.positions.items()
                }
                exposure = get_cluster_exposure(
                    holdings=list(portfolio.positions.keys()),
                    cluster_assignments=self._cluster_assignments,
                    weights=weights,
                )
                max_cluster_w = max((v["weight"] for v in exposure.values()), default=0.0)
                cluster_daily.append(
                    {
                        "date": date_str,
                        "num_clusters": len(exposure),
                        "max_cluster_weight": float(max_cluster_w),
                        "num_positions": len(portfolio.positions),
                        "invested_value": float(invested_value),
                        "equity": float(total_equity),
                    }
                )
            else:
                cluster_daily.append(
                    {
                        "date": date_str,
                        "num_clusters": 0,
                        "max_cluster_weight": 0.0,
                        "num_positions": len(portfolio.positions),
                        "invested_value": float(invested_value),
                        "equity": float(total_equity),
                    }
                )

        equity_df = portfolio.get_equity_history().reset_index()
        equity_df.rename(columns={"date": "Date"}, inplace=True)

        fills_df = pd.DataFrame(fills)
        positions_df = pd.DataFrame(positions_snapshots)
        cluster_df = pd.DataFrame(cluster_daily)

        # Compute summary statistics from equity + trade fills.
        stats = self._compute_stats(equity_df, fills_df, cluster_df, initial_capital)

        results: Dict[str, Any] = {
            "equity_curve": equity_df,
            "fills": fills_df,
            "positions": positions_df,
            "cluster_exposure": cluster_df,
            "stats": stats,
            "metadata": {
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": float(initial_capital),
                "num_symbols": len(data_dict),
                "execution_mode": exec_mode,
                "config": self.config.to_dict(),
            },
        }

        if output_dir:
            self._write_outputs(results, output_dir)

        return results

    def _compute_stats(
        self,
        equity_df: pd.DataFrame,
        fills_df: pd.DataFrame,
        cluster_df: pd.DataFrame,
        initial_capital: float,
    ) -> dict:
        if equity_df.empty:
            return {}

        eq = equity_df.copy()
        eq["Date"] = pd.to_datetime(eq["Date"])
        eq = eq.sort_values("Date")
        equity = eq["equity"].astype(float)
        day_returns = equity.pct_change().fillna(0.0)
        dd = _calc_drawdown(equity)

        total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
        annual_return = float(_annualized_return(total_return, n_days=len(equity) - 1))
        vol = float(day_returns.std(ddof=0) * np.sqrt(252))

        rf = 0.03  # Follow experiment default (3%)
        sharpe = 0.0 if vol == 0 else float((annual_return - rf) / vol)
        sortino = float(_sortino_ratio(day_returns, annual_return, rf=rf))
        max_dd = float(dd.min()) if not dd.empty else 0.0
        calmar = 0.0 if max_dd == 0 else float(annual_return / abs(max_dd))

        # Drawdown start/end dates
        dd_end = None
        dd_start = None
        if not dd.empty and max_dd < 0:
            dd_end_idx = int(dd.idxmin())
            dd_end = eq["Date"].iloc[dd_end_idx].strftime("%Y-%m-%d")
            peak_equity = equity.cummax()
            peak_idx = int(peak_equity[: dd_end_idx + 1].idxmax())
            dd_start = eq["Date"].iloc[peak_idx].strftime("%Y-%m-%d")

        # Trade stats derived from fills (order-level) and FIFO matching (trade-level).
        order_count = int(len(fills_df)) if not fills_df.empty else 0
        turnover = 0.0
        if not fills_df.empty and "gross" in fills_df.columns:
            traded = float(fills_df["gross"].abs().sum())
            avg_invested = (
                float(eq["positions_value"].astype(float).mean())
                if "positions_value" in eq.columns
                else 0.0
            )
            turnover = traded / (2.0 * avg_invested) if avg_invested > 0 else 0.0

        # Cluster exposure summary.
        avg_cluster_exposure = (
            float(cluster_df["max_cluster_weight"].mean()) if not cluster_df.empty else 0.0
        )
        avg_positions = (
            float(eq["num_positions"].astype(float).mean()) if "num_positions" in eq.columns else 0.0
        )
        max_positions = int(eq["num_positions"].max()) if "num_positions" in eq.columns else 0

        trades_df = self._build_round_trips(fills_df)
        num_trades = int(len(trades_df)) if not trades_df.empty else 0
        win_rate = float((trades_df["pnl"] > 0).mean()) if num_trades else 0.0

        gross_profit = float(trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()) if num_trades else 0.0
        gross_loss = float(trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum()) if num_trades else 0.0
        profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0 else 0.0

        avg_trade_pnl = float(trades_df["pnl"].mean()) if num_trades else 0.0
        avg_holding_period = float(trades_df["holding_days"].mean()) if num_trades else 0.0

        return {
            "total_return": total_return,
            "annualized_return": annual_return,
            "volatility": vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "max_drawdown": max_dd,
            "dd_start": dd_start,
            "dd_end": dd_end,
            "equity_final": float(equity.iloc[-1]),
            "equity_peak": float(equity.max()),
            "initial_capital": float(initial_capital),
            "num_orders": order_count,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_trade_pnl": avg_trade_pnl,
            "avg_holding_period": avg_holding_period,
            "turnover_rate": turnover,
            "avg_positions": avg_positions,
            "max_positions": max_positions,
            "avg_cluster_exposure": avg_cluster_exposure,
        }

    @staticmethod
    def _build_round_trips(fills_df: pd.DataFrame) -> pd.DataFrame:
        """
        Build round-trip trades from order-level fills using FIFO matching.

        This is an accounting view used for win-rate/profit-factor/holding-period metrics.
        """
        if fills_df is None or fills_df.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "entry_date",
                    "exit_date",
                    "shares",
                    "entry_price",
                    "exit_price",
                    "pnl",
                    "return_pct",
                    "holding_days",
                    "entry_commission",
                    "exit_commission",
                ]
            )

        df = fills_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

        lots: Dict[str, List[dict]] = {}
        trades: List[dict] = []

        for row in df.itertuples(index=False):
            symbol = str(row.symbol)
            action = str(row.action)
            shares = int(row.shares)
            if shares <= 0:
                continue
            price = float(row.price)
            commission = float(row.commission) if hasattr(row, "commission") else 0.0
            dt = pd.to_datetime(row.date)

            if action == "buy":
                lots.setdefault(symbol, []).append(
                    {
                        "shares": shares,
                        "entry_date": dt,
                        "entry_price": price,
                        "entry_commission_per_share": commission / shares if shares else 0.0,
                    }
                )
                continue

            if action != "sell":
                continue

            if symbol not in lots or not lots[symbol]:
                # Sell without inventory - ignore (should not happen in long-only simulation).
                continue

            exit_comm_per_share = commission / shares if shares else 0.0
            remaining = shares

            while remaining > 0 and lots[symbol]:
                lot = lots[symbol][0]
                lot_shares = int(lot["shares"])
                match = min(lot_shares, remaining)

                entry_comm = float(lot["entry_commission_per_share"]) * match
                exit_comm = exit_comm_per_share * match

                entry_cost_per_share = float(lot["entry_price"]) + float(lot["entry_commission_per_share"])
                exit_proceeds_per_share = price - exit_comm_per_share

                pnl = match * (exit_proceeds_per_share - entry_cost_per_share)
                entry_cost = match * entry_cost_per_share
                ret = pnl / entry_cost if entry_cost > 0 else 0.0

                holding_days = int((dt - lot["entry_date"]).days)

                trades.append(
                    {
                        "symbol": symbol,
                        "entry_date": lot["entry_date"].strftime("%Y-%m-%d"),
                        "exit_date": dt.strftime("%Y-%m-%d"),
                        "shares": match,
                        "entry_price": float(lot["entry_price"]),
                        "exit_price": price,
                        "pnl": pnl,
                        "return_pct": ret,
                        "holding_days": holding_days,
                        "entry_commission": entry_comm,
                        "exit_commission": exit_comm,
                    }
                )

                # Update lot and remaining shares.
                remaining -= match
                lot["shares"] = lot_shares - match
                if lot["shares"] <= 0:
                    lots[symbol].pop(0)

        return pd.DataFrame(trades)

    def _write_outputs(self, results: Dict[str, Any], output_dir: str) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        results["equity_curve"].to_csv(out / "equity_curve.csv", index=False)
        results["fills"].to_csv(out / "trades.csv", index=False)
        results["positions"].to_csv(out / "positions.csv", index=False)
        results["cluster_exposure"].to_csv(out / "cluster_exposure.csv", index=False)

        # performance_summary.json
        import json

        with open(out / "performance_summary.json", "w", encoding="utf-8") as f:
            json.dump(results["stats"], f, ensure_ascii=False, indent=2)


def run_portfolio_backtest(
    config_path: str,
    start_date: str,
    end_date: str,
    output_dir: Optional[str] = None,
    initial_capital: float = 1_000_000,
) -> Dict[str, Any]:
    """Convenience function for CLI/script usage."""
    from .config_loader import load_config

    config = load_config(config_path)
    runner = PortfolioBacktestRunner(config)
    return runner.run(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        output_dir=output_dir,
    )
