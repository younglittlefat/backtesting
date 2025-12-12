"""
Scoring module for ETF trend following system.

This module calculates momentum scores using multi-period volatility-weighted
returns, applies hysteresis (buffer zones), score inertia for existing holdings,
and generates trading signals based on ranking.

Key Features:
- Multi-period volatility-weighted momentum scoring
- Hysteresis mechanism (buy top N, hold until rank M)
- Score inertia bonus for existing holdings to reduce turnover
- Rolling historical score calculation for backtesting
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def calculate_momentum_score(
    df: pd.DataFrame,
    as_of_date: Optional[pd.Timestamp] = None,
    periods: List[int] = [20, 60, 120],
    weights: List[float] = [0.4, 0.3, 0.3],
    min_periods_required: Optional[int] = None
) -> float:
    """
    Calculate momentum score for a single ETF using multi-period volatility-weighted returns.

    Score = Σ(weight_i × return_i / volatility_i)

    Args:
        df: DataFrame with datetime index and 'close' column
        as_of_date: Reference date for calculation (uses latest if None)
        periods: List of lookback periods in days [20, 60, 120]
        weights: Corresponding weights for each period [0.4, 0.3, 0.3]
        min_periods_required: Minimum periods needed (defaults to shortest period)

    Returns:
        Momentum score (float), or np.nan if insufficient data

    Raises:
        ValueError: If weights don't sum to 1.0 or lengths mismatch
    """
    # Validate inputs
    if len(periods) != len(weights):
        raise ValueError(
            f"periods length ({len(periods)}) != weights length ({len(weights)})"
        )

    if not np.isclose(sum(weights), 1.0, atol=1e-6):
        raise ValueError(f"weights must sum to 1.0, got {sum(weights)}")

    if df.empty or 'close' not in df.columns:
        logger.warning("Empty DataFrame or missing 'close' column")
        return np.nan

    # Determine as_of_date
    if as_of_date is None:
        as_of_date = df.index[-1]
    else:
        as_of_date = pd.to_datetime(as_of_date)

    # Filter data up to as_of_date
    df_filtered = df[df.index <= as_of_date].copy()

    if df_filtered.empty:
        logger.debug(f"No data up to {as_of_date}")
        return np.nan

    # Set minimum required periods
    if min_periods_required is None:
        min_periods_required = min(periods)

    if len(df_filtered) < min_periods_required:
        logger.debug(
            f"Insufficient data: {len(df_filtered)} < {min_periods_required}"
        )
        return np.nan

    # Calculate score components
    score = 0.0
    valid_components = 0

    for period, weight in zip(periods, weights):
        # Need at least period+1 data points to calculate period-day return
        if len(df_filtered) < period + 1:
            logger.debug(f"Skipping period {period}: insufficient data")
            continue

        # Get the most recent close and close from 'period' days ago
        recent_close = df_filtered['close'].iloc[-1]
        past_close = df_filtered['close'].iloc[-(period + 1)]

        # Calculate return
        period_return = (recent_close / past_close) - 1.0

        # Calculate annualized volatility for the period
        # Use log returns for volatility calculation
        period_data = df_filtered.tail(period)
        log_returns = np.log(period_data['close'] / period_data['close'].shift(1))
        log_returns = log_returns.dropna()

        if len(log_returns) < 2:
            logger.debug(f"Skipping period {period}: insufficient returns")
            continue

        daily_vol = log_returns.std()

        # Annualize volatility (252 trading days per year)
        annualized_vol = daily_vol * np.sqrt(252)

        # Avoid division by zero
        if annualized_vol < 1e-8:
            logger.debug(f"Skipping period {period}: zero volatility")
            continue

        # Risk-adjusted return component
        component = weight * (period_return / annualized_vol)
        score += component
        valid_components += 1

        logger.debug(
            f"Period {period}: return={period_return:.4f}, "
            f"vol={annualized_vol:.4f}, component={component:.4f}"
        )

    # Return NaN if no valid components
    if valid_components == 0:
        logger.debug("No valid score components")
        return np.nan

    return score


def calculate_universe_scores(
    data_dict: Dict[str, pd.DataFrame],
    as_of_date: str,
    periods: List[int] = [20, 60, 120],
    weights: List[float] = [0.4, 0.3, 0.3],
    min_periods_required: Optional[int] = None
) -> pd.DataFrame:
    """
    Calculate momentum scores for all ETFs in the universe.

    Args:
        data_dict: Dictionary mapping symbol -> OHLCV DataFrame
        as_of_date: Reference date for calculation (YYYY-MM-DD)
        periods: List of lookback periods in days
        weights: Corresponding weights for each period
        min_periods_required: Minimum periods needed for scoring

    Returns:
        DataFrame with columns: symbol, raw_score, rank
        Sorted by rank (1 = highest score)
    """
    as_of_dt = pd.to_datetime(as_of_date)

    scores = []
    for symbol, df in data_dict.items():
        try:
            score = calculate_momentum_score(
                df=df,
                as_of_date=as_of_dt,
                periods=periods,
                weights=weights,
                min_periods_required=min_periods_required
            )
            scores.append({'symbol': symbol, 'raw_score': score})
        except Exception as e:
            logger.warning(f"Failed to score {symbol}: {e}")
            scores.append({'symbol': symbol, 'raw_score': np.nan})

    # Create DataFrame
    scores_df = pd.DataFrame(scores)

    # Drop symbols with NaN scores
    valid_count = scores_df['raw_score'].notna().sum()
    scores_df = scores_df.dropna(subset=['raw_score'])

    if scores_df.empty:
        logger.warning(f"No valid scores calculated for {as_of_date}")
        return pd.DataFrame(columns=['symbol', 'raw_score', 'rank'])

    # Rank by score (1 = highest, descending)
    scores_df = scores_df.sort_values('raw_score', ascending=False).reset_index(drop=True)
    scores_df['rank'] = range(1, len(scores_df) + 1)

    logger.info(
        f"Calculated scores for {as_of_date}: "
        f"{len(scores_df)}/{len(data_dict)} valid ({valid_count} before NaN filter)"
    )

    return scores_df


def apply_inertia_bonus(
    scores_df: pd.DataFrame,
    current_holdings: List[str],
    bonus_pct: float = 0.1,
    bonus_mode: str = 'multiplicative'
) -> pd.DataFrame:
    """
    Apply inertia bonus to existing holdings to reduce turnover.

    Args:
        scores_df: DataFrame with columns: symbol, raw_score, rank
        current_holdings: List of currently held symbols
        bonus_pct: Bonus percentage (default 0.1 = 10% boost)
        bonus_mode: 'multiplicative' (score × (1 + bonus)) or
                    'additive' (score + bonus_pct)

    Returns:
        DataFrame with additional columns: has_inertia, adjusted_score, adjusted_rank
    """
    if scores_df.empty:
        return scores_df

    result_df = scores_df.copy()

    # Mark holdings
    result_df['has_inertia'] = result_df['symbol'].isin(current_holdings)

    # Apply bonus
    if bonus_mode == 'multiplicative':
        result_df['adjusted_score'] = result_df.apply(
            lambda row: row['raw_score'] * (1 + bonus_pct) if row['has_inertia']
            else row['raw_score'],
            axis=1
        )
    elif bonus_mode == 'additive':
        result_df['adjusted_score'] = result_df.apply(
            lambda row: row['raw_score'] + bonus_pct if row['has_inertia']
            else row['raw_score'],
            axis=1
        )
    else:
        raise ValueError(
            f"Invalid bonus_mode: {bonus_mode}. Use 'multiplicative' or 'additive'"
        )

    # Re-rank by adjusted score
    result_df = result_df.sort_values('adjusted_score', ascending=False).reset_index(drop=True)
    result_df['adjusted_rank'] = range(1, len(result_df) + 1)

    inertia_count = result_df['has_inertia'].sum()
    logger.info(
        f"Applied inertia bonus ({bonus_mode}, {bonus_pct:.1%}) to "
        f"{inertia_count}/{len(current_holdings)} holdings "
        f"(some may have dropped out of scoring universe)"
    )

    return result_df


def get_trading_signals(
    scores_df: pd.DataFrame,
    current_holdings: List[str],
    buy_top_n: int = 10,
    hold_until_rank: int = 15,
    stop_loss_symbols: Optional[List[str]] = None,
    use_adjusted_rank: bool = True
) -> dict:
    """
    Generate trading signals using hysteresis (buffer zone) mechanism.

    Hysteresis Logic:
    - Buy: Enter top N (buy_top_n)
    - Hold: Stay in as long as rank <= M (hold_until_rank)
    - Sell: Exit when rank > M or triggered by stop loss

    Args:
        scores_df: DataFrame with symbol, raw_score, rank, and optionally adjusted_rank
        current_holdings: List of currently held symbols
        buy_top_n: Top N to buy (e.g., 10)
        hold_until_rank: Hold until rank drops below this (e.g., 15)
        stop_loss_symbols: List of symbols to force sell (stop loss triggered)
        use_adjusted_rank: Use adjusted_rank (with inertia) if available

    Returns:
        Dictionary with keys:
        - 'to_buy': List of symbols to buy
        - 'to_hold': List of symbols to continue holding
        - 'to_sell': List of symbols to sell (rank degradation or stop loss)
        - 'final_holdings': List of final holdings after applying signals
        - 'metadata': Additional info (buy_reasons, sell_reasons)
    """
    if scores_df.empty:
        logger.warning("Empty scores_df, selling all holdings")
        return {
            'to_buy': [],
            'to_hold': [],
            'to_sell': list(current_holdings),
            'final_holdings': [],
            'metadata': {
                'buy_reasons': {},
                'sell_reasons': {s: 'no_scores' for s in current_holdings}
            }
        }

    # Determine which rank column to use
    rank_col = 'adjusted_rank' if use_adjusted_rank and 'adjusted_rank' in scores_df.columns else 'rank'

    # Create a symbol-to-rank mapping
    symbol_rank = dict(zip(scores_df['symbol'], scores_df[rank_col]))

    # Initialize stop_loss_symbols
    if stop_loss_symbols is None:
        stop_loss_symbols = []

    # Process holdings
    to_hold = []
    to_sell = []
    sell_reasons = {}

    for symbol in current_holdings:
        if symbol in stop_loss_symbols:
            to_sell.append(symbol)
            sell_reasons[symbol] = 'stop_loss'
            continue

        # Check if symbol is still in scoring universe
        if symbol not in symbol_rank:
            to_sell.append(symbol)
            sell_reasons[symbol] = 'dropped_from_universe'
            continue

        # Check hysteresis condition
        rank = symbol_rank[symbol]
        if rank <= hold_until_rank:
            to_hold.append(symbol)
        else:
            to_sell.append(symbol)
            sell_reasons[symbol] = f'rank_degraded_to_{rank}'

    # Determine new buys
    # Buy from top N that are not already held
    top_symbols = scores_df[scores_df[rank_col] <= buy_top_n]['symbol'].tolist()
    to_buy = [s for s in top_symbols if s not in current_holdings]
    buy_reasons = {s: f'new_entry_rank_{symbol_rank[s]}' for s in to_buy}

    # Final holdings
    final_holdings = to_hold + to_buy

    # Logging
    logger.info(
        f"Trading signals: Buy={len(to_buy)}, Hold={len(to_hold)}, "
        f"Sell={len(to_sell)} (Stop Loss: {len(stop_loss_symbols)})"
    )

    return {
        'to_buy': to_buy,
        'to_hold': to_hold,
        'to_sell': to_sell,
        'final_holdings': final_holdings,
        'metadata': {
            'buy_reasons': buy_reasons,
            'sell_reasons': sell_reasons,
            'rank_column_used': rank_col
        }
    }


def calculate_historical_scores(
    data_dict: Dict[str, pd.DataFrame],
    start_date: str,
    end_date: str,
    periods: List[int] = [20, 60, 120],
    weights: List[float] = [0.4, 0.3, 0.3],
    min_periods_required: Optional[int] = None,
    frequency: str = 'daily'
) -> pd.DataFrame:
    """
    Calculate historical scores for backtesting (rolling calculation).

    This function calculates scores for each date in the range using only
    data available up to that date, avoiding look-ahead bias.

    Args:
        data_dict: Dictionary mapping symbol -> OHLCV DataFrame
        start_date: Start date for scoring (YYYY-MM-DD)
        end_date: End date for scoring (YYYY-MM-DD)
        periods: List of lookback periods in days
        weights: Corresponding weights for each period
        min_periods_required: Minimum periods needed for scoring
        frequency: 'daily' or 'weekly' (weekly uses Fridays or last trading day)

    Returns:
        DataFrame with MultiIndex (date, symbol) and columns: raw_score, rank
        Each date contains scores for all symbols calculated using data up to that date
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    # Get all available dates across universe
    all_dates = set()
    for df in data_dict.values():
        all_dates.update(df.index)

    # Filter to date range
    valid_dates = sorted([d for d in all_dates if start_dt <= d <= end_dt])

    if not valid_dates:
        logger.warning(f"No valid dates in range [{start_date}, {end_date}]")
        return pd.DataFrame(columns=['date', 'symbol', 'raw_score', 'rank'])

    # Apply frequency filter
    if frequency == 'weekly':
        # Keep only Fridays or last trading day of each week
        weekly_dates = []
        current_week = None
        for date in valid_dates:
            week_key = (date.year, date.isocalendar()[1])
            if week_key != current_week:
                if current_week is not None:
                    # Add last date of previous week
                    weekly_dates.append(valid_dates[valid_dates.index(date) - 1])
                current_week = week_key
        # Add the last date
        if valid_dates:
            weekly_dates.append(valid_dates[-1])
        valid_dates = weekly_dates
        logger.info(f"Weekly frequency: {len(valid_dates)} scoring dates")
    else:
        logger.info(f"Daily frequency: {len(valid_dates)} scoring dates")

    # Calculate scores for each date
    all_scores = []

    for i, date in enumerate(valid_dates):
        date_str = date.strftime('%Y-%m-%d')

        # Calculate universe scores for this date
        scores_df = calculate_universe_scores(
            data_dict=data_dict,
            as_of_date=date_str,
            periods=periods,
            weights=weights,
            min_periods_required=min_periods_required
        )

        if not scores_df.empty:
            scores_df['date'] = date
            all_scores.append(scores_df)

        # Progress logging
        if (i + 1) % 50 == 0 or (i + 1) == len(valid_dates):
            logger.info(f"Processed {i + 1}/{len(valid_dates)} dates")

    if not all_scores:
        logger.warning("No valid scores calculated for any date")
        return pd.DataFrame(columns=['date', 'symbol', 'raw_score', 'rank'])

    # Combine all dates
    result_df = pd.concat(all_scores, ignore_index=True)

    # Reorder columns
    result_df = result_df[['date', 'symbol', 'raw_score', 'rank']]

    # Set MultiIndex
    result_df = result_df.set_index(['date', 'symbol'])

    logger.info(
        f"Historical scores calculated: {len(valid_dates)} dates, "
        f"{len(result_df)} total symbol-date pairs"
    )

    return result_df


def get_scores_for_date(
    historical_scores: pd.DataFrame,
    date: str
) -> pd.DataFrame:
    """
    Extract scores for a specific date from historical scores DataFrame.

    Args:
        historical_scores: DataFrame with MultiIndex (date, symbol)
        date: Date to extract (YYYY-MM-DD)

    Returns:
        DataFrame with columns: symbol, raw_score, rank (sorted by rank)
    """
    date_dt = pd.to_datetime(date)

    if historical_scores.empty:
        return pd.DataFrame(columns=['symbol', 'raw_score', 'rank'])

    try:
        # Extract for the specific date
        date_scores = historical_scores.loc[date_dt].reset_index()

        # Ensure we have the right columns
        if 'symbol' not in date_scores.columns:
            # If symbol is still in index (shouldn't happen after reset_index)
            date_scores = date_scores.reset_index()

        date_scores = date_scores[['symbol', 'raw_score', 'rank']]
        date_scores = date_scores.sort_values('rank').reset_index(drop=True)

        return date_scores

    except KeyError:
        logger.warning(f"No scores found for date {date}")
        return pd.DataFrame(columns=['symbol', 'raw_score', 'rank'])


def validate_scoring_params(
    periods: List[int],
    weights: List[float],
    buy_top_n: int,
    hold_until_rank: int
) -> Tuple[bool, Optional[str]]:
    """
    Validate scoring parameters for consistency.

    Args:
        periods: List of lookback periods
        weights: List of weights for each period
        buy_top_n: Number of top-ranked symbols to buy
        hold_until_rank: Rank threshold for holding

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check lengths match
    if len(periods) != len(weights):
        return False, f"periods length ({len(periods)}) != weights length ({len(weights)})"

    # Check weights sum to 1.0
    if not np.isclose(sum(weights), 1.0, atol=1e-6):
        return False, f"weights must sum to 1.0, got {sum(weights)}"

    # Check all weights are positive
    if any(w <= 0 for w in weights):
        return False, "All weights must be positive"

    # Check all periods are positive
    if any(p <= 0 for p in periods):
        return False, "All periods must be positive"

    # Check periods are sorted (optional but recommended)
    if periods != sorted(periods):
        logger.warning("Periods are not sorted in ascending order")

    # Check hysteresis parameters
    if buy_top_n <= 0:
        return False, f"buy_top_n must be positive, got {buy_top_n}"

    if hold_until_rank <= 0:
        return False, f"hold_until_rank must be positive, got {hold_until_rank}"

    if hold_until_rank < buy_top_n:
        return False, (
            f"hold_until_rank ({hold_until_rank}) should be >= buy_top_n ({buy_top_n}) "
            f"for hysteresis to work properly"
        )

    return True, None
