#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Signal Pipeline for ETF Trend Following v2

This module implements the core signal pipeline that orchestrates the complete workflow:
"Full Pool Scan → Signals → Scoring → Portfolio Optimization → Trade Orders"

Design Philosophy (from Gemini discussion):
1. Absolute Trend (Signal) + Relative Momentum (Rank) dual confirmation
2. Filter by trend signal first, then select Top N by momentum ranking
3. Risk management (stop loss) takes priority over ranking optimization
4. Buffer zone mechanism to prevent excessive turnover

Author: Claude
Date: 2025-12-11
Compatible with: Python 3.9+
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timedelta
import json

import pandas as pd
import numpy as np

# Import local modules
from .data_loader import load_single_etf, load_universe
from .config_loader import load_config
from .scoring import (
    calculate_momentum_score,
    calculate_universe_scores,
    apply_inertia_bonus,
)
from .clustering import (
    perform_clustering,
    get_cluster_assignments,
    filter_by_cluster_limit
)
from .position_sizing import (
    calculate_volatility,
    normalize_positions,
    apply_cluster_limits
)
from .strategies.macd import MACDSignalGenerator
from .strategies.kama import KAMASignalGenerator
from .strategies.combo import ComboSignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class TradeOrder:
    """Trade order representation"""
    symbol: str
    action: str  # 'buy' or 'sell'
    shares: int
    reason: str
    signal_strength: float = 0.0
    momentum_score: float = 0.0
    target_weight: float = 0.0
    current_price: float = 0.0
    estimated_value: float = 0.0


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot for state persistence"""
    as_of_date: str
    holdings: Dict[str, Dict[str, Any]]  # {symbol: {shares, cost_basis, entry_date, ...}}
    cash: float
    total_value: float
    cluster_assignments: Dict[str, int]
    metadata: Dict[str, Any]


class SignalPipeline:
    """
    Signal Pipeline: Full Pool Scan → Signals → Scoring → Portfolio Optimization → Trade Orders

    This class orchestrates the complete daily signal generation workflow, integrating:
    - Strategy signal generation (MACD/KAMA/Combo)
    - Momentum scoring and ranking
    - Clustering and diversification
    - Risk management and circuit breakers
    - Position sizing and portfolio construction

    Configuration is loaded from config.json and controls all behavior.
    """

    def __init__(self, config):
        """
        Initialize the signal pipeline

        Args:
            config: Config object loaded from config.json
        """
        self.config = config
        self.data_dict: Dict[str, pd.DataFrame] = {}
        self.cluster_assignments: Dict[str, int] = {}
        self.last_cluster_update: Optional[str] = None

        # Initialize strategy generator based on config
        self.strategy_generator = self._initialize_strategy()

        logger.info(f"SignalPipeline initialized with strategy: {self.strategy_generator}")

    def _initialize_strategy(self):
        """
        Initialize strategy generator based on configuration

        Returns:
            Strategy generator (MACD/KAMA/Combo)
        """
        strategy_configs = self.config.strategies

        if not strategy_configs:
            raise ValueError("No strategy configuration found in config.strategies")

        # For now, use the first strategy (can extend to support multiple)
        strategy_config = strategy_configs[0]
        strategy_type = getattr(strategy_config, 'type', 'macd')

        if strategy_type == 'macd':
            # Convert dataclass to dict for strategy generator
            from dataclasses import asdict
            config_dict = asdict(strategy_config)
            return MACDSignalGenerator(**config_dict)
        elif strategy_type == 'kama':
            from dataclasses import asdict
            config_dict = asdict(strategy_config)
            return KAMASignalGenerator(**config_dict)
        elif strategy_type == 'combo':
            # Combo strategy requires macd_config and kama_config
            mode = getattr(strategy_config, 'mode', 'or')
            weights = getattr(strategy_config, 'weights', {'macd': 0.5, 'kama': 0.5})
            conflict_resolution = getattr(strategy_config, 'conflict_resolution', 'macd_priority')

            # Get sub-strategies from combo config
            sub_strategies = getattr(strategy_config, 'strategies', [])
            macd_config = {}
            kama_config = {}
            for sub in sub_strategies:
                sub_type = getattr(sub, 'type', 'macd')
                from dataclasses import asdict
                if sub_type == 'macd':
                    macd_config = asdict(sub)
                elif sub_type == 'kama':
                    kama_config = asdict(sub)

            return ComboSignalGenerator(
                mode=mode,
                macd_config=macd_config,
                kama_config=kama_config,
                weights=weights,
                conflict_resolution=conflict_resolution
            )
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

    def load_data(
        self,
        data_dir: str,
        symbols: List[str],
        start_date: str,
        end_date: str,
        use_adj: bool = True
    ) -> None:
        """
        Load OHLCV data for all symbols in the pool

        Args:
            data_dir: Directory containing ETF CSV files
            symbols: List of ETF symbols to load
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            use_adj: Whether to use adjusted prices
        """
        logger.info(f"Loading data for {len(symbols)} symbols from {start_date} to {end_date}")

        from .data_loader import load_universe

        self.data_dict = load_universe(
            symbols=symbols,
            data_dir=data_dir,
            start_date=start_date,
            end_date=end_date,
            use_adj=use_adj
        )

        logger.info(f"Successfully loaded data for {len(self.data_dict)} symbols")

    def update_clusters(
        self,
        as_of_date: str,
        force: bool = False
    ) -> None:
        """
        Update clustering assignments (typically weekly or as configured)

        Args:
            as_of_date: Reference date for clustering
            force: Force update even if not due based on update_frequency
        """
        clustering_config = self.config.clustering
        update_frequency = clustering_config.update_frequency  # days

        # Check if update is needed
        if not force and self.last_cluster_update is not None:
            last_update_dt = pd.to_datetime(self.last_cluster_update)
            current_dt = pd.to_datetime(as_of_date)
            days_since_update = (current_dt - last_update_dt).days

            if days_since_update < update_frequency:
                logger.debug(
                    f"Cluster update not needed: {days_since_update} days "
                    f"< {update_frequency} days threshold"
                )
                return

        logger.info(f"Updating clustering as of {as_of_date}")

        # Perform clustering - access dataclass attributes directly
        correlation_window = clustering_config.correlation_window
        distance_metric = clustering_config.distance_metric
        linkage_method = clustering_config.linkage_method
        cut_threshold = clustering_config.cut_threshold

        from .clustering import perform_clustering

        cluster_labels = perform_clustering(
            data_dict=self.data_dict,
            lookback_days=correlation_window,
            distance_metric=distance_metric,
            linkage_method=linkage_method,
            cut_threshold=cut_threshold
        )

        self.cluster_assignments = cluster_labels
        self.last_cluster_update = as_of_date

        # Log cluster distribution
        cluster_counts = {}
        for symbol, cluster_id in cluster_labels.items():
            cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

        logger.info(
            f"Clustering complete: {len(cluster_counts)} clusters, "
            f"distribution: {cluster_counts}"
        )

    def scan_signals(self, as_of_date: str) -> Dict[str, int]:
        """
        Scan signals for all symbols in the pool

        Args:
            as_of_date: Reference date for signal generation

        Returns:
            Dictionary {symbol: signal} where signal = 1 (buy), -1 (sell), 0 (hold)
        """
        logger.info(f"Scanning signals for {len(self.data_dict)} symbols as of {as_of_date}")

        signals = {}

        for symbol, df in self.data_dict.items():
            try:
                # Filter data up to as_of_date
                df_filtered = df[df.index <= as_of_date].copy()

                if df_filtered.empty:
                    logger.warning(f"{symbol}: No data up to {as_of_date}")
                    signals[symbol] = 0
                    continue

                # Capitalize column names for strategy generators (they expect Close, Open, etc.)
                df_filtered = df_filtered.rename(columns={
                    'close': 'Close',
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'volume': 'Volume'
                })

                # Calculate indicators
                df_with_indicators = self.strategy_generator.calculate_indicators(df_filtered)

                # Generate signals
                signal_series = self.strategy_generator.generate_signals(df_with_indicators)

                # Get the signal for the latest date
                if not signal_series.empty:
                    signal = int(signal_series.iloc[-1])
                else:
                    signal = 0

                signals[symbol] = signal

            except Exception as e:
                logger.error(f"Error generating signal for {symbol}: {e}", exc_info=True)
                signals[symbol] = 0

        # Log signal distribution
        buy_count = sum(1 for s in signals.values() if s == 1)
        sell_count = sum(1 for s in signals.values() if s == -1)
        hold_count = sum(1 for s in signals.values() if s == 0)

        logger.info(
            f"Signal scan complete: Buy={buy_count}, Sell={sell_count}, Hold={hold_count}"
        )

        return signals

    def calculate_scores(self, as_of_date: str) -> pd.DataFrame:
        """
        Calculate momentum scores for all symbols

        Args:
            as_of_date: Reference date for score calculation

        Returns:
            DataFrame with columns: symbol, score, rank
        """
        logger.info(f"Calculating momentum scores as of {as_of_date}")

        scoring_config = self.config.scoring
        momentum_weights = scoring_config.momentum_weights

        # Convert momentum_weights to periods and weights
        periods = []
        weights = []
        for period_str, weight in sorted(momentum_weights.items()):
            # Extract number from period string (e.g., '20d' -> 20)
            period_days = int(period_str.replace('d', ''))
            periods.append(period_days)
            weights.append(weight)

        from .scoring import calculate_universe_scores

        scores_df = calculate_universe_scores(
            data_dict=self.data_dict,
            as_of_date=as_of_date,
            periods=periods,
            weights=weights
        )

        logger.info(f"Calculated scores for {len(scores_df)} symbols")

        return scores_df

    def check_risk(
        self,
        portfolio: PortfolioSnapshot,
        as_of_date: str,
        market_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Check risk control status for all holdings

        Args:
            portfolio: Current portfolio snapshot
            as_of_date: Reference date
            market_df: Optional market index data for circuit breaker

        Returns:
            Dictionary {symbol: {'stop_loss': bool, 'time_stop': bool, 'reason': str}}
        """
        logger.info(f"Checking risk controls for {len(portfolio.holdings)} holdings")

        risk_config = self.config.risk
        atr_window = risk_config.atr_window
        atr_multiplier = risk_config.atr_multiplier
        time_stop_days = risk_config.time_stop_days
        time_stop_threshold = risk_config.time_stop_threshold

        risk_status = {}

        for symbol, holding in portfolio.holdings.items():
            if symbol not in self.data_dict:
                logger.warning(f"{symbol}: No data available for risk check")
                continue

            df = self.data_dict[symbol]
            df_filtered = df[df.index <= as_of_date].copy()

            if df_filtered.empty:
                logger.warning(f"{symbol}: No data up to {as_of_date}")
                continue

            result = {
                'stop_loss': False,
                'time_stop': False,
                'reason': ''
            }

            try:
                entry_date_str = holding.get('entry_date', as_of_date)
                entry_date = pd.to_datetime(entry_date_str)
                entry_price = holding.get('cost_basis', 0)
                current_date = pd.to_datetime(as_of_date)
                current_price = df_filtered['close'].iloc[-1]

                # Filter data from entry date onwards for Chandelier Exit calculation
                df_since_entry = df_filtered[df_filtered.index >= entry_date]

                # ATR stop loss check - Chandelier Exit implementation
                # Stop line = Highest_Since_Entry - N × ATR, only moves up
                if len(df_since_entry) >= atr_window:
                    # Calculate ATR
                    high = df_since_entry['high']
                    low = df_since_entry['low']
                    close = df_since_entry['close']

                    tr1 = high - low
                    tr2 = abs(high - close.shift(1))
                    tr3 = abs(low - close.shift(1))
                    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
                    atr = tr.rolling(window=atr_window).mean().iloc[-1]

                    # Chandelier Exit: highest high since entry - N × ATR
                    highest_since_entry = df_since_entry['high'].max()

                    # Get or initialize the trailing stop level from holding
                    prev_stop_level = holding.get('stop_level', 0)
                    new_stop_level = highest_since_entry - (atr * atr_multiplier)

                    # Stop line only moves up, never down (protect profits)
                    stop_loss_level = max(new_stop_level, prev_stop_level)

                    # Update stop level in holding for next check
                    holding['stop_level'] = stop_loss_level

                    if current_price < stop_loss_level:
                        result['stop_loss'] = True
                        result['reason'] = f"Chandelier Exit triggered (price={current_price:.2f}, stop={stop_loss_level:.2f}, highest={highest_since_entry:.2f})"

                # Time stop check - per requirement: held >= N days AND (profit < 1×ATR AND not made new high)
                holding_days = (current_date - entry_date).days

                if holding_days >= time_stop_days and not result['stop_loss']:
                    # Calculate profit in ATR multiples
                    if len(df_since_entry) >= atr_window:
                        profit = current_price - entry_price
                        profit_in_atr = profit / atr if atr > 0 else 0

                        # Check if made new high since entry (any high above entry price counts)
                        highest_since_entry = df_since_entry['high'].max()
                        made_new_high = highest_since_entry > entry_price

                        # Time stop triggers if: profit < 1×ATR AND not made new high
                        # Per requirement: "profit < 1×ATR 且未破高"
                        if profit_in_atr < 1.0 and not made_new_high:
                            result['time_stop'] = True
                            result['reason'] += f" Time stop triggered (days={holding_days}, profit={profit_in_atr:.2f}×ATR, no new high)"
                    else:
                        # Fallback to simple PnL check if not enough data for ATR
                        if entry_price > 0:
                            pnl_pct = (current_price - entry_price) / entry_price
                            if pnl_pct < time_stop_threshold:
                                result['time_stop'] = True
                                result['reason'] += f" Time stop triggered (days={holding_days}, PnL={pnl_pct:.2%})"

                risk_status[symbol] = result

            except Exception as e:
                logger.error(f"Error checking risk for {symbol}: {e}", exc_info=True)

        # Count triggered stops
        stop_loss_count = sum(1 for r in risk_status.values() if r['stop_loss'])
        time_stop_count = sum(1 for r in risk_status.values() if r['time_stop'])

        logger.info(
            f"Risk check complete: ATR stops={stop_loss_count}, Time stops={time_stop_count}"
        )

        return risk_status

    def generate_target_portfolio(
        self,
        signals: Dict[str, int],
        scores: pd.DataFrame,
        current_holdings: Dict[str, Dict[str, Any]],
        risk_exits: Dict[str, Dict[str, Any]],
        as_of_date: str,
        total_capital: float
    ) -> Dict[str, Any]:
        """
        Generate target portfolio based on signals, scores, and risk controls

        Logic:
        1. Sell: Triggered risk exit OR dropped out of buffer zone
        2. Buy: Top N by score AND has buy signal AND cluster limit not exceeded

        Args:
            signals: {symbol: signal} from scan_signals
            scores: DataFrame with symbol, score, rank
            current_holdings: {symbol: holding_info}
            risk_exits: {symbol: risk_status} from check_risk
            as_of_date: Reference date
            total_capital: Total available capital

        Returns:
            Dictionary with keys:
                - to_buy: List[{symbol, shares, reason}]
                - to_sell: List[{symbol, reason}]
                - to_hold: List[str]
                - target_positions: {symbol: {shares, weight}}
        """
        logger.info("Generating target portfolio")

        scoring_config = self.config.scoring
        clustering_config = self.config.clustering
        position_config = self.config.position_sizing

        # Access dataclass attributes directly
        buy_top_n = scoring_config.buffer_thresholds.get('buy_top_n', 10)
        hold_until_rank = scoring_config.buffer_thresholds.get('hold_until_rank', 15)
        max_positions_per_cluster = clustering_config.max_positions_per_cluster
        max_positions = position_config.max_positions

        to_sell = []
        to_buy = []
        to_hold = []

        # Step 1: Determine sells (risk exits take priority, then strategy reversal, then buffer zone)
        for symbol in current_holdings.keys():
            # Check risk exits first (highest priority)
            if symbol in risk_exits:
                risk_status = risk_exits[symbol]
                if risk_status.get('stop_loss') or risk_status.get('time_stop'):
                    to_sell.append({
                        'symbol': symbol,
                        'reason': risk_status.get('reason', 'Risk exit')
                    })
                    continue

            # Check strategy sell signal (trend reversal) - per requirement
            # If strategy generates sell signal (-1), exit regardless of rank
            if symbol in signals and signals[symbol] == -1:
                to_sell.append({
                    'symbol': symbol,
                    'reason': 'Strategy sell signal (trend reversal)'
                })
                continue

            # Check if dropped out of buffer zone
            symbol_score = scores[scores['symbol'] == symbol]
            if not symbol_score.empty:
                rank = symbol_score['rank'].iloc[0]
                if rank > hold_until_rank:
                    to_sell.append({
                        'symbol': symbol,
                        'reason': f'Dropped out of buffer zone (rank={rank} > {hold_until_rank})'
                    })
                    continue

            # Hold if still in buffer zone
            to_hold.append(symbol)

        # Step 2: Determine buys (Top N with buy signal and cluster limits)
        # Filter for symbols with buy signals
        buy_candidates = [s for s, sig in signals.items() if sig == 1]

        # Filter to Top N by score
        top_n_scores = scores.head(buy_top_n)
        top_n_symbols = set(top_n_scores['symbol'].tolist())

        # Intersect: must be in both buy_candidates AND top_n
        potential_buys = [s for s in buy_candidates if s in top_n_symbols]

        # Sort by score (higher is better)
        potential_buys_with_scores = []
        for symbol in potential_buys:
            if symbol in to_hold:  # Already holding
                continue

            symbol_score = scores[scores['symbol'] == symbol]
            if not symbol_score.empty:
                # Use raw_score or adjusted_score if available
                score_col = 'adjusted_score' if 'adjusted_score' in scores.columns else 'raw_score'
                score_value = symbol_score[score_col].iloc[0]
                potential_buys_with_scores.append((symbol, score_value))

        potential_buys_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Apply cluster limits
        cluster_counts = {}
        for symbol in to_hold:
            if symbol in self.cluster_assignments:
                cluster_id = self.cluster_assignments[symbol]
                cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

        for symbol, score_value in potential_buys_with_scores:
            # Check total position limit
            if len(to_hold) + len(to_buy) >= max_positions:
                logger.info(f"Reached max positions limit ({max_positions})")
                break

            # Check cluster limit
            if symbol in self.cluster_assignments:
                cluster_id = self.cluster_assignments[symbol]
                current_count = cluster_counts.get(cluster_id, 0)

                if current_count >= max_positions_per_cluster:
                    logger.debug(
                        f"Skipping {symbol}: cluster {cluster_id} "
                        f"limit reached ({current_count}/{max_positions_per_cluster})"
                    )
                    continue

                cluster_counts[cluster_id] = current_count + 1

            to_buy.append({
                'symbol': symbol,
                'shares': 0,  # Will be calculated in position sizing
                'reason': f'Top N buy signal (score={score_value:.4f})'
            })

        # Step 3: Calculate position sizes for target portfolio
        target_symbols = to_hold + [b['symbol'] for b in to_buy]

        if not target_symbols:
            logger.info("No target positions - empty portfolio")
            return {
                'to_buy': to_buy,
                'to_sell': to_sell,
                'to_hold': to_hold,
                'target_positions': {}
            }

        # Calculate volatility-weighted positions - access dataclass attributes directly
        volatility_method = position_config.volatility_method
        ewma_lambda = position_config.ewma_lambda
        max_position_size = position_config.max_position_size
        max_total_exposure = position_config.max_total_exposure

        volatilities = {}
        prices = {}

        for symbol in target_symbols:
            if symbol not in self.data_dict:
                logger.warning(f"{symbol}: No data for position sizing")
                continue

            df = self.data_dict[symbol]
            df_filtered = df[df.index <= as_of_date]

            if df_filtered.empty:
                continue

            # Calculate volatility
            vol = calculate_volatility(
                df=df_filtered,
                method=volatility_method,
                ewma_lambda=ewma_lambda
            )

            if not np.isnan(vol) and vol > 0:
                volatilities[symbol] = vol
                prices[symbol] = df_filtered['close'].iloc[-1]

        if not volatilities:
            logger.warning("No valid volatilities calculated - cannot size positions")
            return {
                'to_buy': to_buy,
                'to_sell': to_sell,
                'to_hold': to_hold,
                'target_positions': {}
            }

        # Calculate inverse volatility weights
        inv_vol = {s: 1.0 / v for s, v in volatilities.items()}
        total_inv_vol = sum(inv_vol.values())
        weights = {s: v / total_inv_vol for s, v in inv_vol.items()}

        # Apply position constraints
        constrained_weights = weights.copy()

        # Apply single position limit
        for symbol in constrained_weights:
            if constrained_weights[symbol] > max_position_size:
                constrained_weights[symbol] = max_position_size

        # Apply cluster limits
        from .position_sizing import apply_cluster_limits
        constrained_weights = apply_cluster_limits(
            positions=constrained_weights,
            cluster_assignments=self.cluster_assignments,
            max_cluster_pct=position_config.max_cluster_size,
            total_capital=1.0  # Using weights, so total is 1.0
        )

        # Normalize to max_total_exposure
        total_weight = sum(constrained_weights.values())
        if total_weight > max_total_exposure:
            scale = max_total_exposure / total_weight
            constrained_weights = {s: w * scale for s, w in constrained_weights.items()}

        # Calculate target positions
        target_positions = {}
        available_capital = total_capital * max_total_exposure

        for symbol, weight in constrained_weights.items():
            if symbol not in prices:
                continue

            price = prices[symbol]
            position_value = available_capital * weight
            shares = int(position_value / price / 100) * 100  # Round to lot size (100 shares)

            if shares > 0:
                target_positions[symbol] = {
                    'shares': shares,
                    'weight': weight,
                    'price': price,
                    'value': shares * price
                }

        # Update to_buy with calculated shares
        for buy_order in to_buy:
            symbol = buy_order['symbol']
            if symbol in target_positions:
                buy_order['shares'] = target_positions[symbol]['shares']
                buy_order['target_weight'] = target_positions[symbol]['weight']

        logger.info(
            f"Target portfolio generated: "
            f"To Buy={len(to_buy)}, To Sell={len(to_sell)}, To Hold={len(to_hold)}"
        )

        return {
            'to_buy': to_buy,
            'to_sell': to_sell,
            'to_hold': to_hold,
            'target_positions': target_positions
        }

    def run(
        self,
        portfolio: PortfolioSnapshot,
        as_of_date: str,
        market_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete signal pipeline for a given date

        Args:
            portfolio: Current portfolio snapshot
            as_of_date: Reference date for signal generation
            market_df: Optional market index data for circuit breaker

        Returns:
            Dictionary with:
                - signals: {symbol: signal}
                - scores: DataFrame
                - risk_status: {symbol: risk_info}
                - target_portfolio: {to_buy, to_sell, to_hold, target_positions}
                - orders: List[TradeOrder]
                - circuit_breaker: bool
                - metadata: {execution_time, as_of_date, ...}
        """
        start_time = datetime.now()
        logger.info(f"=" * 80)
        logger.info(f"Running signal pipeline for {as_of_date}")
        logger.info(f"=" * 80)

        # Step 1: Update clusters if needed
        self.update_clusters(as_of_date, force=False)

        # Step 2: Scan signals
        signals = self.scan_signals(as_of_date)

        # Step 3: Calculate scores
        scores = self.calculate_scores(as_of_date)

        # Apply score inertia for existing holdings
        inertia_bonus = self.config.scoring.inertia_bonus
        current_symbols = list(portfolio.holdings.keys())

        if inertia_bonus > 0 and current_symbols:
            from .scoring import apply_inertia_bonus
            scores = apply_inertia_bonus(
                scores_df=scores,
                current_holdings=current_symbols,
                bonus_pct=inertia_bonus
            )

        # Rank by score (scores already have 'rank' column from calculate_universe_scores)
        # If inertia was applied, re-rank by adjusted_score
        if 'adjusted_score' in scores.columns:
            scores = scores.sort_values('adjusted_score', ascending=False).reset_index(drop=True)
            scores['rank'] = range(1, len(scores) + 1)

        # Step 4: Check risk controls
        risk_status = self.check_risk(portfolio, as_of_date, market_df)

        # Step 5: Check circuit breaker
        circuit_breaker = False
        circuit_breaker_threshold = self.config.risk.circuit_breaker_threshold

        if market_df is not None and not market_df.empty:
            # Simple circuit breaker: market drawdown check
            market_df_filtered = market_df[market_df.index <= as_of_date]
            if len(market_df_filtered) >= 20:
                current_price = market_df_filtered['close'].iloc[-1]
                high_20d = market_df_filtered['high'].tail(20).max()
                drawdown = (current_price - high_20d) / high_20d

                if drawdown < circuit_breaker_threshold:
                    circuit_breaker = True
                    logger.warning(
                        f"Circuit breaker triggered: market drawdown {drawdown:.2%} "
                        f"< threshold {circuit_breaker_threshold:.2%}"
                    )

        # Step 6: Generate target portfolio
        if circuit_breaker:
            # Circuit breaker: no new buys, only risk-based sells
            logger.warning("Circuit breaker active - no new positions allowed")
            target_portfolio = {
                'to_buy': [],
                'to_sell': [
                    {'symbol': s, 'reason': risk_status[s].get('reason', 'Risk exit')}
                    for s in risk_status.keys()
                    if risk_status[s].get('stop_loss') or risk_status[s].get('time_stop')
                ],
                'to_hold': [
                    s for s in portfolio.holdings.keys()
                    if s not in risk_status or not (
                        risk_status[s].get('stop_loss') or risk_status[s].get('time_stop')
                    )
                ],
                'target_positions': {}
            }
        else:
            target_portfolio = self.generate_target_portfolio(
                signals=signals,
                scores=scores,
                current_holdings=portfolio.holdings,
                risk_exits=risk_status,
                as_of_date=as_of_date,
                total_capital=portfolio.total_value
            )

        # Step 7: Generate trade orders with T+1 constraint check
        orders = []
        enable_t1 = self.config.risk.enable_t1_restriction
        current_date = pd.to_datetime(as_of_date)

        # Sell orders
        for sell_info in target_portfolio['to_sell']:
            symbol = sell_info['symbol']
            if symbol in portfolio.holdings:
                holding = portfolio.holdings[symbol]
                shares = holding.get('shares', 0)

                # T+1 constraint check: cannot sell on the same day as buy
                if enable_t1:
                    entry_date_str = holding.get('entry_date', '')
                    if entry_date_str:
                        entry_date = pd.to_datetime(entry_date_str)
                        if entry_date.date() >= current_date.date():
                            # Cannot sell today - bought today (T+1 violation)
                            logger.warning(
                                f"{symbol}: T+1 constraint - cannot sell today "
                                f"(entry_date={entry_date.date()}, as_of_date={current_date.date()})"
                            )
                            # Move back to hold list instead of selling
                            if symbol not in target_portfolio['to_hold']:
                                target_portfolio['to_hold'].append(symbol)
                            continue

                if symbol in self.data_dict:
                    df = self.data_dict[symbol]
                    df_filtered = df[df.index <= as_of_date]
                    if not df_filtered.empty:
                        current_price = df_filtered['close'].iloc[-1]
                    else:
                        current_price = 0.0
                else:
                    current_price = 0.0

                orders.append(TradeOrder(
                    symbol=symbol,
                    action='sell',
                    shares=shares,
                    reason=sell_info['reason'],
                    current_price=current_price,
                    estimated_value=shares * current_price
                ))

        # Buy orders
        for buy_info in target_portfolio['to_buy']:
            symbol = buy_info['symbol']
            shares = buy_info.get('shares', 0)

            if shares > 0:
                if symbol in self.data_dict:
                    df = self.data_dict[symbol]
                    df_filtered = df[df.index <= as_of_date]
                    if not df_filtered.empty:
                        current_price = df_filtered['close'].iloc[-1]
                    else:
                        current_price = 0.0
                else:
                    current_price = 0.0

                # Get score and signal strength
                symbol_score_row = scores[scores['symbol'] == symbol]
                score_col = 'adjusted_score' if 'adjusted_score' in scores.columns else 'raw_score'
                momentum_score = symbol_score_row[score_col].iloc[0] if not symbol_score_row.empty else 0.0
                signal_strength = signals.get(symbol, 0)

                orders.append(TradeOrder(
                    symbol=symbol,
                    action='buy',
                    shares=shares,
                    reason=buy_info['reason'],
                    signal_strength=float(signal_strength),
                    momentum_score=float(momentum_score),
                    target_weight=buy_info.get('target_weight', 0.0),
                    current_price=current_price,
                    estimated_value=shares * current_price
                ))

        # Execution time
        execution_time = (datetime.now() - start_time).total_seconds()

        result = {
            'signals': signals,
            'scores': scores,
            'risk_status': risk_status,
            'target_portfolio': target_portfolio,
            'orders': orders,
            'circuit_breaker': circuit_breaker,
            'metadata': {
                'as_of_date': as_of_date,
                'execution_time': execution_time,
                'total_symbols': len(self.data_dict),
                'buy_signals': sum(1 for s in signals.values() if s == 1),
                'sell_signals': sum(1 for s in signals.values() if s == -1),
                'num_buy_orders': len([o for o in orders if o.action == 'buy']),
                'num_sell_orders': len([o for o in orders if o.action == 'sell']),
                'cluster_count': len(set(self.cluster_assignments.values())) if self.cluster_assignments else 0
            }
        }

        logger.info(f"=" * 80)
        logger.info(f"Signal pipeline complete: {execution_time:.2f}s")
        logger.info(f"Orders: {result['metadata']['num_buy_orders']} buys, {result['metadata']['num_sell_orders']} sells")
        logger.info(f"=" * 80)

        return result


def run_daily_signal(
    config_path: str,
    as_of_date: Optional[str] = None,
    portfolio_snapshot: Optional[str] = None,
    market_data_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Daily signal generation entry point function

    This is the main entry point for daily signal generation, typically called
    by scripts/generate_signal.sh or other automation.

    Workflow:
    1. Load configuration from config.json
    2. Restore or initialize portfolio state
    3. Load market data
    4. Run signal pipeline
    5. Output signals, orders, and updated portfolio snapshot

    Args:
        config_path: Path to config.json
        as_of_date: Reference date (YYYY-MM-DD), None = today
        portfolio_snapshot: Path to portfolio snapshot JSON, None = initialize empty
        market_data_path: Path to market index data CSV (for circuit breaker)
        output_dir: Directory for output files, None = use config.io settings
        dry_run: If True, don't write output files (default: True)

    Returns:
        Dictionary with:
            - result: Pipeline execution result
            - portfolio_updated: Updated portfolio snapshot
            - output_files: {signals, orders, portfolio, report}
    """
    logger.info("=" * 80)
    logger.info("Starting daily signal generation")
    logger.info("=" * 80)

    # Step 1: Load configuration
    config = load_config(config_path)
    logger.info(f"Configuration loaded from {config_path}")

    # Determine as_of_date
    if as_of_date is None:
        as_of_date = datetime.now().strftime('%Y-%m-%d')

    logger.info(f"Signal generation date: {as_of_date}")

    # Step 2: Restore or initialize portfolio
    if portfolio_snapshot and Path(portfolio_snapshot).exists():
        logger.info(f"Loading portfolio snapshot from {portfolio_snapshot}")
        with open(portfolio_snapshot, 'r') as f:
            portfolio_data = json.load(f)

        portfolio = PortfolioSnapshot(
            as_of_date=portfolio_data['as_of_date'],
            holdings=portfolio_data['holdings'],
            cash=portfolio_data['cash'],
            total_value=portfolio_data['total_value'],
            cluster_assignments=portfolio_data.get('cluster_assignments', {}),
            metadata=portfolio_data.get('metadata', {})
        )
    else:
        logger.info("Initializing empty portfolio")
        initial_capital = 1000000.0  # Default 1M
        portfolio = PortfolioSnapshot(
            as_of_date=as_of_date,
            holdings={},
            cash=initial_capital,
            total_value=initial_capital,
            cluster_assignments={},
            metadata={'initial_capital': initial_capital}
        )

    logger.info(
        f"Portfolio: {len(portfolio.holdings)} holdings, "
        f"cash={portfolio.cash:.2f}, total={portfolio.total_value:.2f}"
    )

    # Step 3: Load market data (optional, for circuit breaker)
    market_df = None
    if market_data_path and Path(market_data_path).exists():
        try:
            market_df = pd.read_csv(market_data_path, index_col=0, parse_dates=True)
            logger.info(f"Market data loaded from {market_data_path}")
        except Exception as e:
            logger.warning(f"Failed to load market data: {e}")

    # Step 4: Initialize pipeline and load data
    pipeline = SignalPipeline(config)

    # Get symbol list from config - access dataclass attributes directly
    universe_config = config.universe
    if universe_config.pool_file:
        pool_file_path = Path(config.env.root_dir) / universe_config.pool_file
        if pool_file_path.exists():
            pool_df = pd.read_csv(pool_file_path)
            # Assume the CSV has a 'ts_code' or 'symbol' column
            if 'ts_code' in pool_df.columns:
                symbols = pool_df['ts_code'].tolist()
            elif 'symbol' in pool_df.columns:
                symbols = pool_df['symbol'].tolist()
            else:
                symbols = pool_df.iloc[:, 0].tolist()
            logger.info(f"Loaded {len(symbols)} symbols from {pool_file_path}")
        else:
            raise FileNotFoundError(f"Pool file not found: {pool_file_path}")
    elif universe_config.pool_list:
        symbols = universe_config.pool_list
        logger.info(f"Using {len(symbols)} symbols from config.universe.pool_list")
    else:
        raise ValueError("No symbol pool specified in config")

    # Load data - access dataclass attributes directly
    data_dir = Path(config.env.root_dir) / config.env.data_dir
    lookback_days = config.modes.lookback_days
    start_date = (pd.to_datetime(as_of_date) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    pipeline.load_data(
        data_dir=str(data_dir),
        symbols=symbols,
        start_date=start_date,
        end_date=as_of_date,
        use_adj=True
    )

    # Step 5: Run signal pipeline
    result = pipeline.run(
        portfolio=portfolio,
        as_of_date=as_of_date,
        market_df=market_df
    )

    # Step 6: Update portfolio snapshot
    # Apply orders to portfolio (simplified - actual execution would be more complex)
    updated_holdings = portfolio.holdings.copy()

    # Process sells
    for order in result['orders']:
        if order.action == 'sell':
            if order.symbol in updated_holdings:
                del updated_holdings[order.symbol]

    # Process buys
    for order in result['orders']:
        if order.action == 'buy' and order.shares > 0:
            updated_holdings[order.symbol] = {
                'shares': order.shares,
                'cost_basis': order.current_price,
                'entry_date': as_of_date,
                'value': order.estimated_value
            }

    # Calculate updated portfolio value (simplified)
    holdings_value = sum(h.get('value', 0) for h in updated_holdings.values())
    updated_cash = portfolio.total_value - holdings_value

    portfolio_updated = PortfolioSnapshot(
        as_of_date=as_of_date,
        holdings=updated_holdings,
        cash=updated_cash,
        total_value=portfolio.total_value,
        cluster_assignments=pipeline.cluster_assignments,
        metadata={
            **portfolio.metadata,
            'last_update': datetime.now().isoformat(),
            'num_orders_executed': len(result['orders'])
        }
    )

    # Step 7: Output results
    output_files = {}

    if not dry_run:
        if output_dir:
            output_path = Path(output_dir)
        else:
            # Access dataclass attributes directly
            output_path = Path(config.env.root_dir) / config.io.signal_output_path
            output_path = output_path.parent

        output_path.mkdir(parents=True, exist_ok=True)

        # Save signals
        signals_file = output_path / f"signals_{as_of_date}.csv"
        signals_df = pd.DataFrame([
            {'symbol': s, 'signal': sig}
            for s, sig in result['signals'].items()
        ])
        signals_df.to_csv(signals_file, index=False)
        output_files['signals'] = str(signals_file)
        logger.info(f"Signals saved to {signals_file}")

        # Save orders
        orders_file = output_path / f"orders_{as_of_date}.csv"
        orders_df = pd.DataFrame([asdict(o) for o in result['orders']])
        if not orders_df.empty:
            orders_df.to_csv(orders_file, index=False)
            output_files['orders'] = str(orders_file)
            logger.info(f"Orders saved to {orders_file}")

        # Save portfolio snapshot
        portfolio_file = output_path / f"portfolio_{as_of_date}.json"
        with open(portfolio_file, 'w') as f:
            json.dump(asdict(portfolio_updated), f, indent=2)
        output_files['portfolio'] = str(portfolio_file)
        logger.info(f"Portfolio snapshot saved to {portfolio_file}")

        # Save scores
        scores_file = output_path / f"scores_{as_of_date}.csv"
        result['scores'].to_csv(scores_file, index=False)
        output_files['scores'] = str(scores_file)
        logger.info(f"Scores saved to {scores_file}")

    logger.info("=" * 80)
    logger.info("Daily signal generation complete")
    logger.info("=" * 80)

    return {
        'result': result,
        'portfolio_updated': portfolio_updated,
        'output_files': output_files
    }


if __name__ == '__main__':
    """
    Test the signal pipeline with sample configuration

    Usage:
        python signal_pipeline.py [--config CONFIG_PATH] [--as-of-date YYYY-MM-DD]
    """
    import argparse

    parser = argparse.ArgumentParser(description='Run ETF Trend Following Signal Pipeline')
    parser.add_argument(
        '--config',
        default='/mnt/d/git/backtesting/etf_trend_following_v2/config/example_config.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--as-of-date',
        default=None,
        help='Signal generation date (YYYY-MM-DD), default: today'
    )
    parser.add_argument(
        '--portfolio',
        default=None,
        help='Path to portfolio snapshot JSON'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory for results'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Dry run mode (no output files)'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        result = run_daily_signal(
            config_path=args.config,
            as_of_date=args.as_of_date,
            portfolio_snapshot=args.portfolio,
            output_dir=args.output_dir,
            dry_run=args.dry_run
        )

        print("\n" + "=" * 80)
        print("SIGNAL PIPELINE SUMMARY")
        print("=" * 80)
        print(f"As of date: {result['result']['metadata']['as_of_date']}")
        print(f"Execution time: {result['result']['metadata']['execution_time']:.2f}s")
        print(f"Total symbols: {result['result']['metadata']['total_symbols']}")
        print(f"Buy signals: {result['result']['metadata']['buy_signals']}")
        print(f"Sell signals: {result['result']['metadata']['sell_signals']}")
        print(f"Buy orders: {result['result']['metadata']['num_buy_orders']}")
        print(f"Sell orders: {result['result']['metadata']['num_sell_orders']}")
        print(f"Circuit breaker: {result['result']['circuit_breaker']}")
        print(f"Holdings after update: {len(result['portfolio_updated'].holdings)}")
        print("=" * 80)

        if result['output_files']:
            print("\nOutput files:")
            for key, path in result['output_files'].items():
                print(f"  {key}: {path}")

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise
