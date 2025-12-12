"""
Risk management module for ETF trend following system.

This module provides comprehensive risk control functions including:
- ATR (Average True Range) calculation and Chandelier Exit stop loss
- Time-based stop loss for stagnant positions
- Circuit breaker for market crashes and account drawdowns
- Liquidity checks
- T+1 trading constraint handling

Key Features:
- ATR-based trailing stop loss (Chandelier Exit pattern)
- Time stop to free up capital from non-performing positions
- Market and account-level circuit breakers
- Liquidity validation before trading
- T+1 constraint enforcement for Chinese A-shares/ETFs
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14,
    method: str = 'sma'
) -> pd.Series:
    """
    Calculate Average True Range (ATR) indicator.

    ATR measures market volatility by decomposing the entire range of an asset
    price for that period. It's the average of True Range over a specified period.

    True Range (TR) = max(High - Low, abs(High - Close_prev), abs(Low - Close_prev))

    Args:
        df: DataFrame with datetime index and columns: high, low, close
        period: ATR calculation period (default: 14 days)
        method: Smoothing method - 'sma' (simple moving average) or
                'ema' (exponential moving average, Wilder's smoothing)

    Returns:
        Series with ATR values, same index as input DataFrame

    Raises:
        ValueError: If required columns are missing or period is invalid
    """
    # Validate inputs
    required_cols = ['high', 'low', 'close']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")

    if df.empty or len(df) < 2:
        logger.warning("Insufficient data for ATR calculation")
        return pd.Series(index=df.index, dtype=float)

    # Calculate True Range components
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)

    # TR = max(H-L, |H-C_prev|, |L-C_prev|)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Calculate ATR using specified method
    if method == 'sma':
        # Simple moving average
        atr = true_range.rolling(window=period, min_periods=1).mean()
    elif method == 'ema':
        # Exponential moving average (Wilder's smoothing)
        # alpha = 1/period for Wilder's method
        atr = true_range.ewm(alpha=1.0/period, min_periods=1, adjust=False).mean()
    else:
        raise ValueError(f"Invalid method: {method}. Use 'sma' or 'ema'")

    # First value is NaN (no previous close), handle it
    # For the first bar, TR is undefined due to lack of previous close
    # We'll use the current TR as the initial ATR value
    if len(atr) > 0 and pd.isna(atr.iloc[0]) and not pd.isna(true_range.iloc[0]):
        atr.iloc[0] = true_range.iloc[0]

    return atr


def calculate_stop_line(
    df: pd.DataFrame,
    entry_date: Union[str, pd.Timestamp],
    entry_price: float,
    atr_multiplier: float = 3.0,
    atr_period: int = 14,
    atr_method: str = 'sma'
) -> pd.DataFrame:
    """
    Calculate Chandelier Exit stop loss line (ATR trailing stop).

    The stop line follows the highest price since entry, trailing by N × ATR.
    The stop line can only move up (protecting profits), never down.

    Stop Line = max(Highest_Price_Since_Entry - N × ATR, Previous_Stop_Line)

    Args:
        df: DataFrame with datetime index and OHLC columns
        entry_date: Entry date (position opened)
        entry_price: Entry price
        atr_multiplier: ATR multiplier for stop distance (default: 3.0)
        atr_period: ATR calculation period (default: 14)
        atr_method: ATR smoothing method ('sma' or 'ema')

    Returns:
        DataFrame with columns:
        - date: datetime index
        - close: closing price
        - atr: ATR value
        - highest_since_entry: highest high since entry
        - stop_line: calculated stop loss line

    Raises:
        ValueError: If entry_date not found in data or invalid parameters
    """
    if df.empty:
        raise ValueError("Empty DataFrame")

    # Parse entry date
    entry_dt = pd.to_datetime(entry_date)

    # Check if entry date is in valid range
    if entry_dt < df.index.min():
        raise ValueError(
            f"Entry date {entry_date} is before available data "
            f"(data starts: {df.index.min().date()})"
        )

    # Filter data from entry date onwards
    df_filtered = df[df.index >= entry_dt].copy()

    if df_filtered.empty:
        raise ValueError(f"No data found from entry date {entry_date}")

    # Calculate ATR
    atr = calculate_atr(df_filtered, period=atr_period, method=atr_method)

    # Calculate highest high since entry
    highest_since_entry = df_filtered['high'].expanding(min_periods=1).max()

    # Initialize stop line
    # First stop line = entry_price - atr_multiplier × ATR
    stop_line = pd.Series(index=df_filtered.index, dtype=float)

    for i, idx in enumerate(df_filtered.index):
        current_atr = atr.loc[idx]
        current_highest = highest_since_entry.loc[idx]

        # Calculate potential stop based on highest price
        potential_stop = current_highest - (atr_multiplier * current_atr)

        if i == 0:
            # First day: use entry price or calculated stop, whichever is lower
            # to ensure we don't set stop too tight initially
            initial_stop = min(entry_price - (atr_multiplier * current_atr), entry_price * 0.95)
            stop_line.loc[idx] = initial_stop
        else:
            # Stop line can only move up, never down (protect profits)
            prev_stop = stop_line.iloc[i - 1]
            stop_line.loc[idx] = max(potential_stop, prev_stop)

    # Build result DataFrame
    result = pd.DataFrame({
        'date': df_filtered.index,
        'close': df_filtered['close'],
        'atr': atr,
        'highest_since_entry': highest_since_entry,
        'stop_line': stop_line
    })
    result = result.set_index('date')

    return result


def check_stop_loss(
    df: pd.DataFrame,
    entry_date: Union[str, pd.Timestamp],
    entry_price: float,
    atr_multiplier: float = 3.0,
    atr_period: int = 14,
    check_until_date: Optional[Union[str, pd.Timestamp]] = None
) -> dict:
    """
    Check if ATR trailing stop loss has been triggered.

    Stop loss is triggered when close price drops below the stop line.

    Args:
        df: DataFrame with datetime index and OHLC columns
        entry_date: Entry date (position opened)
        entry_price: Entry price
        atr_multiplier: ATR multiplier for stop distance (default: 3.0)
        atr_period: ATR calculation period (default: 14)
        check_until_date: Check up to this date (inclusive); uses latest if None

    Returns:
        Dictionary with keys:
        - triggered: bool - whether stop loss was triggered
        - trigger_date: str - date when stop was triggered (None if not triggered)
        - trigger_price: float - close price on trigger date (None if not triggered)
        - trigger_reason: str - reason description
        - days_held: int - number of days position was held
        - final_pnl_pct: float - P&L percentage at trigger/current (None if ongoing)

    Raises:
        ValueError: If entry_date not found or invalid parameters
    """
    try:
        # Calculate stop line
        stop_data = calculate_stop_line(
            df=df,
            entry_date=entry_date,
            entry_price=entry_price,
            atr_multiplier=atr_multiplier,
            atr_period=atr_period
        )
    except Exception as e:
        logger.error(f"Failed to calculate stop line: {e}")
        return {
            'triggered': False,
            'trigger_date': None,
            'trigger_price': None,
            'trigger_reason': f'calculation_error: {e}',
            'days_held': 0,
            'final_pnl_pct': None
        }

    # Filter to check_until_date if specified
    if check_until_date is not None:
        check_dt = pd.to_datetime(check_until_date)
        stop_data = stop_data[stop_data.index <= check_dt]

    if stop_data.empty:
        return {
            'triggered': False,
            'trigger_date': None,
            'trigger_price': None,
            'trigger_reason': 'no_data_after_entry',
            'days_held': 0,
            'final_pnl_pct': None
        }

    # Check for stop loss trigger (close < stop_line)
    triggered_mask = stop_data['close'] < stop_data['stop_line']

    if triggered_mask.any():
        # Find first trigger date
        trigger_idx = triggered_mask.idxmax() if triggered_mask.any() else None

        if trigger_idx and triggered_mask.loc[trigger_idx]:
            trigger_date = trigger_idx
            trigger_price = stop_data.loc[trigger_date, 'close']
            days_held = len(stop_data.loc[:trigger_date])
            final_pnl_pct = (trigger_price / entry_price - 1.0) * 100

            return {
                'triggered': True,
                'trigger_date': trigger_date.strftime('%Y-%m-%d'),
                'trigger_price': trigger_price,
                'trigger_reason': f'atr_stop_loss_{atr_multiplier}x',
                'days_held': days_held,
                'final_pnl_pct': final_pnl_pct
            }

    # Not triggered - return current status
    current_date = stop_data.index[-1]
    current_price = stop_data.loc[current_date, 'close']
    days_held = len(stop_data)
    current_pnl_pct = (current_price / entry_price - 1.0) * 100

    return {
        'triggered': False,
        'trigger_date': None,
        'trigger_price': None,
        'trigger_reason': 'not_triggered',
        'days_held': days_held,
        'final_pnl_pct': current_pnl_pct
    }


def check_time_stop(
    df: pd.DataFrame,
    entry_date: Union[str, pd.Timestamp],
    entry_price: float,
    max_hold_days: int = 20,
    min_profit_atr: float = 1.0,
    atr_period: int = 14,
    check_until_date: Optional[Union[str, pd.Timestamp]] = None
) -> dict:
    """
    Check if time-based stop loss should be triggered.

    Time stop is triggered if:
    - Position held for >= max_hold_days AND
    - Profit is less than min_profit_atr × ATR (or hasn't made new high)

    Purpose: Free up capital from stagnant "zombie" positions.

    Args:
        df: DataFrame with datetime index and OHLC columns
        entry_date: Entry date (position opened)
        entry_price: Entry price
        max_hold_days: Maximum holding period in trading days (default: 20)
        min_profit_atr: Minimum profit in ATR multiples to avoid time stop (default: 1.0)
        atr_period: ATR calculation period (default: 14)
        check_until_date: Check up to this date (inclusive); uses latest if None

    Returns:
        Dictionary with keys:
        - triggered: bool - whether time stop was triggered
        - trigger_date: str - date when time stop triggered (None if not triggered)
        - days_held: int - number of days position was held
        - profit_pct: float - profit percentage at check date
        - profit_atr: float - profit in ATR multiples
        - reason: str - detailed reason

    Raises:
        ValueError: If entry_date not found or invalid parameters
    """
    # Parse entry date
    entry_dt = pd.to_datetime(entry_date)

    # Filter data from entry date onwards
    df_filtered = df[df.index >= entry_dt].copy()

    if df_filtered.empty:
        raise ValueError(f"No data found from entry date {entry_date}")

    # Filter to check_until_date if specified
    if check_until_date is not None:
        check_dt = pd.to_datetime(check_until_date)
        df_filtered = df_filtered[df_filtered.index <= check_dt]

    if df_filtered.empty:
        return {
            'triggered': False,
            'trigger_date': None,
            'days_held': 0,
            'profit_pct': 0.0,
            'profit_atr': 0.0,
            'reason': 'no_data_in_check_range'
        }

    # Calculate days held
    days_held = len(df_filtered)

    # Get current status
    current_date = df_filtered.index[-1]
    current_price = df_filtered.loc[current_date, 'close']
    profit_pct = (current_price / entry_price - 1.0) * 100

    # Calculate current ATR
    try:
        atr = calculate_atr(df_filtered, period=atr_period)
        current_atr = atr.iloc[-1]
    except Exception as e:
        logger.warning(f"Failed to calculate ATR for time stop: {e}")
        current_atr = None

    # Calculate profit in ATR multiples
    if current_atr is not None and current_atr > 0:
        profit_atr = (current_price - entry_price) / current_atr
    else:
        profit_atr = 0.0

    # Check if made new high since entry (any high above entry price counts)
    highest_since_entry = df_filtered['high'].max()
    made_new_high = highest_since_entry > entry_price

    # Check if time stop should trigger
    # Per requirement: "profit < 1×ATR 且未破高"
    triggered = False
    reason = 'not_triggered'

    if days_held >= max_hold_days:
        if current_atr is None:
            # Can't calculate ATR, use simple profit check
            # Trigger if no profit AND no new high
            if profit_pct < 0 and not made_new_high:
                triggered = True
                reason = f'held_{days_held}days_no_profit_no_new_high'
        else:
            # Check if profit is below minimum ATR threshold AND no new high
            if profit_atr < min_profit_atr and not made_new_high:
                triggered = True
                reason = f'held_{days_held}days_profit_{profit_atr:.2f}atr_below_{min_profit_atr}atr_no_new_high'

    result = {
        'triggered': triggered,
        'trigger_date': current_date.strftime('%Y-%m-%d') if triggered else None,
        'days_held': days_held,
        'profit_pct': profit_pct,
        'profit_atr': profit_atr,
        'made_new_high': made_new_high,
        'highest_since_entry': highest_since_entry,
        'reason': reason
    }

    return result


def check_circuit_breaker(
    market_df: Optional[pd.DataFrame] = None,
    account_equity: Optional[pd.Series] = None,
    as_of_date: Union[str, pd.Timestamp] = None,
    market_drop_threshold: float = -0.05,
    account_drawdown_threshold: float = -0.03,
    lookback_days: int = 1
) -> dict:
    """
    Check if circuit breaker should be triggered.

    Circuit breaker is triggered when:
    - Market index drops by >= threshold over lookback period, OR
    - Account drawdown from peak exceeds threshold

    When triggered: prohibit opening new positions, optionally force reduce/close positions.

    Args:
        market_df: DataFrame with datetime index and 'close' column for market index
                   (e.g., CSI 300). None to skip market check.
        account_equity: Series with datetime index showing account equity curve.
                        None to skip account drawdown check.
        as_of_date: Reference date for check; uses latest if None
        market_drop_threshold: Market drop threshold to trigger (e.g., -0.05 = -5%)
        account_drawdown_threshold: Account drawdown threshold (e.g., -0.03 = -3%)
        lookback_days: Number of days to look back for market drop (default: 1)

    Returns:
        Dictionary with keys:
        - triggered: bool - whether circuit breaker was triggered
        - reason: str - reason for trigger ('market_drop', 'account_drawdown', 'both', 'none')
        - market_change: float - market change percentage (None if not checked)
        - account_drawdown: float - account drawdown from peak (None if not checked)
        - recommendations: list - recommended actions when triggered

    Raises:
        ValueError: If both market_df and account_equity are None
    """
    if market_df is None and account_equity is None:
        raise ValueError("At least one of market_df or account_equity must be provided")

    # Parse as_of_date
    if as_of_date is not None:
        check_dt = pd.to_datetime(as_of_date)
    else:
        # Use the latest date available
        dates = []
        if market_df is not None:
            dates.append(market_df.index.max())
        if account_equity is not None:
            dates.append(account_equity.index.max())
        check_dt = max(dates)

    triggered = False
    triggers = []
    market_change = None
    account_drawdown = None

    # Check market drop
    if market_df is not None and not market_df.empty:
        market_filtered = market_df[market_df.index <= check_dt]

        if len(market_filtered) > lookback_days:
            current_price = market_filtered.iloc[-1]['close']
            past_price = market_filtered.iloc[-(lookback_days + 1)]['close']

            if past_price > 0:
                market_change = (current_price / past_price - 1.0)

                if market_change <= market_drop_threshold:
                    triggered = True
                    triggers.append('market_drop')
                    logger.warning(
                        f"Market circuit breaker triggered: "
                        f"{market_change:.2%} drop over {lookback_days} days "
                        f"(threshold: {market_drop_threshold:.2%})"
                    )
            else:
                logger.warning("Invalid past market price (zero or negative)")
        else:
            logger.debug(f"Insufficient market data: need {lookback_days + 1} days, have {len(market_filtered)}")

    # Check account drawdown
    if account_equity is not None:
        equity_filtered = account_equity[account_equity.index <= check_dt]

        if len(equity_filtered) >= 2:
            current_equity = equity_filtered.iloc[-1]
            peak_equity = equity_filtered.expanding().max().iloc[-1]

            if peak_equity > 0:
                account_drawdown = (current_equity / peak_equity - 1.0)

                if account_drawdown <= account_drawdown_threshold:
                    triggered = True
                    triggers.append('account_drawdown')
                    logger.warning(
                        f"Account circuit breaker triggered: "
                        f"{account_drawdown:.2%} drawdown from peak "
                        f"(threshold: {account_drawdown_threshold:.2%})"
                    )
        else:
            logger.debug("Insufficient account equity data for circuit breaker check")

    # Determine reason
    if len(triggers) == 0:
        reason = 'none'
    elif len(triggers) == 1:
        reason = triggers[0]
    else:
        reason = 'both'

    # Generate recommendations
    recommendations = []
    if triggered:
        recommendations.append('prohibit_new_positions')
        if 'account_drawdown' in triggers:
            recommendations.append('consider_reducing_positions')
        if 'market_drop' in triggers and market_change is not None and market_change < -0.10:
            recommendations.append('consider_emergency_exit')

    return {
        'triggered': triggered,
        'reason': reason,
        'market_change': market_change,
        'account_drawdown': account_drawdown,
        'recommendations': recommendations
    }


def check_liquidity(
    df: pd.DataFrame,
    min_amount: float = 50_000_000,
    max_spread_pct: Optional[float] = None,
    lookback_days: int = 20,
    as_of_date: Optional[Union[str, pd.Timestamp]] = None
) -> dict:
    """
    Check if ETF has sufficient liquidity for trading.

    Args:
        df: DataFrame with datetime index and 'amount' column (trading amount in yuan).
                Optionally 'bid', 'ask' columns for spread check.
        min_amount: Minimum average daily trading amount (default: 50M yuan)
        max_spread_pct: Maximum bid-ask spread percentage (e.g., 0.005 = 0.5%).
                        None to skip spread check.
        lookback_days: Number of days to calculate average (default: 20)
        as_of_date: Reference date for check; uses latest if None

    Returns:
        Dictionary with keys:
        - sufficient: bool - whether liquidity is sufficient
        - avg_amount: float - average daily trading amount over lookback period
        - recent_amount: float - most recent day's trading amount
        - avg_spread_pct: float - average spread percentage (None if not checked)
        - reason: str - reason if insufficient

    Raises:
        ValueError: If 'amount' column is missing
    """
    if 'amount' not in df.columns:
        raise ValueError("DataFrame must have 'amount' column for liquidity check")

    if df.empty:
        return {
            'sufficient': False,
            'avg_amount': 0.0,
            'recent_amount': 0.0,
            'avg_spread_pct': None,
            'reason': 'no_data'
        }

    # Parse as_of_date
    if as_of_date is not None:
        check_dt = pd.to_datetime(as_of_date)
        df_filtered = df[df.index <= check_dt]
    else:
        df_filtered = df

    if df_filtered.empty:
        return {
            'sufficient': False,
            'avg_amount': 0.0,
            'recent_amount': 0.0,
            'avg_spread_pct': None,
            'reason': 'no_data_before_as_of_date'
        }

    # Get recent data for liquidity calculation
    recent_df = df_filtered.tail(lookback_days)

    if recent_df.empty:
        return {
            'sufficient': False,
            'avg_amount': 0.0,
            'recent_amount': 0.0,
            'avg_spread_pct': None,
            'reason': 'insufficient_data'
        }

    # Calculate average and recent trading amount
    avg_amount = recent_df['amount'].mean()
    recent_amount = recent_df['amount'].iloc[-1]

    # Check spread if columns available and threshold specified
    avg_spread_pct = None
    spread_check_passed = True

    if max_spread_pct is not None and 'bid' in df.columns and 'ask' in df.columns:
        # Calculate bid-ask spread percentage
        mid_price = (recent_df['bid'] + recent_df['ask']) / 2
        spread = recent_df['ask'] - recent_df['bid']
        spread_pct = spread / mid_price

        avg_spread_pct = spread_pct.mean()

        if avg_spread_pct > max_spread_pct:
            spread_check_passed = False

    # Determine if liquidity is sufficient
    sufficient = True
    reasons = []

    if pd.isna(avg_amount) or avg_amount < min_amount:
        sufficient = False
        reasons.append(f'low_amount_{avg_amount:.0f}_below_{min_amount:.0f}')

    if not spread_check_passed:
        sufficient = False
        reasons.append(f'high_spread_{avg_spread_pct:.4f}_above_{max_spread_pct:.4f}')

    reason = '; '.join(reasons) if reasons else 'sufficient'

    return {
        'sufficient': sufficient,
        'avg_amount': avg_amount,
        'recent_amount': recent_amount,
        'avg_spread_pct': avg_spread_pct,
        'reason': reason
    }


def check_t_plus_1(
    entry_date: Union[str, pd.Timestamp],
    check_date: Union[str, pd.Timestamp],
    trading_calendar: Optional[pd.DatetimeIndex] = None
) -> bool:
    """
    Check if T+1 constraint allows selling on check_date for position entered on entry_date.

    In Chinese A-share/ETF markets, shares bought on day T cannot be sold until day T+1.

    Args:
        entry_date: Date when position was entered (bought)
        check_date: Date when we want to check if we can sell
        trading_calendar: Optional trading calendar (DatetimeIndex of valid trading days).
                         If None, uses simple date comparison (not recommended for production).

    Returns:
        bool: True if selling is allowed (check_date > entry_date in trading days),
              False if T+1 constraint prevents selling

    Examples:
        >>> check_t_plus_1('2024-01-15', '2024-01-15')  # Same day
        False
        >>> check_t_plus_1('2024-01-15', '2024-01-16')  # Next day
        True
    """
    entry_dt = pd.to_datetime(entry_date)
    check_dt = pd.to_datetime(check_date)

    # Normalize to date only (ignore time)
    entry_dt = entry_dt.normalize()
    check_dt = check_dt.normalize()

    if trading_calendar is not None:
        # Use trading calendar for accurate T+1 check
        # Normalize calendar dates
        calendar = trading_calendar.normalize()

        # Find entry date in calendar
        if entry_dt not in calendar:
            logger.warning(
                f"Entry date {entry_dt.date()} not in trading calendar, "
                f"using simple date comparison"
            )
            return check_dt > entry_dt

        # Find next trading day after entry
        entry_idx = calendar.get_loc(entry_dt)
        if entry_idx + 1 >= len(calendar):
            # Entry date is the last trading day in calendar
            # Allow selling on any date after entry
            return check_dt > entry_dt

        next_trading_day = calendar[entry_idx + 1]

        # Can sell on next trading day or later
        return check_dt >= next_trading_day
    else:
        # Simple date comparison (assumes all days are trading days)
        # This is not accurate for weekends/holidays but works for quick checks
        return check_dt > entry_dt


class RiskManager:
    """
    Comprehensive risk manager for portfolio positions.

    Integrates all risk control mechanisms:
    - ATR trailing stop loss
    - Time-based stop loss
    - Circuit breaker (market and account level)
    - Liquidity checks
    - T+1 constraint enforcement

    Example:
        >>> config = {
        ...     'atr_multiplier': 3.0,
        ...     'atr_period': 14,
        ...     'time_stop_days': 20,
        ...     'time_stop_min_profit_atr': 1.0,
        ...     'market_drop_threshold': -0.05,
        ...     'account_drawdown_threshold': -0.03,
        ...     'min_liquidity_amount': 50_000_000
        ... }
        >>> rm = RiskManager(config)
        >>> status = rm.check_position_risk('159915.SZ', df, position_info)
    """

    def __init__(self, config: dict):
        """
        Initialize risk manager with configuration.

        Args:
            config: Dictionary with risk parameters:
                - atr_multiplier: float (default: 3.0)
                - atr_period: int (default: 14)
                - time_stop_days: int (default: 20)
                - time_stop_min_profit_atr: float (default: 1.0)
                - market_drop_threshold: float (default: -0.05)
                - account_drawdown_threshold: float (default: -0.03)
                - min_liquidity_amount: float (default: 50_000_000)
                - max_spread_pct: float (optional)
                - circuit_breaker_lookback: int (default: 1)
                - enforce_t_plus_1: bool (default: True)
        """
        self.config = config

        # ATR stop parameters
        self.atr_multiplier = config.get('atr_multiplier', 3.0)
        self.atr_period = config.get('atr_period', 14)

        # Time stop parameters
        self.time_stop_days = config.get('time_stop_days', 20)
        self.time_stop_min_profit_atr = config.get('time_stop_min_profit_atr', 1.0)

        # Circuit breaker parameters
        self.market_drop_threshold = config.get('market_drop_threshold', -0.05)
        self.account_drawdown_threshold = config.get('account_drawdown_threshold', -0.03)
        self.circuit_breaker_lookback = config.get('circuit_breaker_lookback', 1)

        # Liquidity parameters
        self.min_liquidity_amount = config.get('min_liquidity_amount', 50_000_000)
        self.max_spread_pct = config.get('max_spread_pct', None)

        # T+1 enforcement
        self.enforce_t_plus_1 = config.get('enforce_t_plus_1', True)

        logger.info(f"RiskManager initialized with config: {self.config}")

    def check_position_risk(
        self,
        symbol: str,
        df: pd.DataFrame,
        position: dict,
        as_of_date: Optional[Union[str, pd.Timestamp]] = None
    ) -> dict:
        """
        Check all risk controls for a single position.

        Args:
            symbol: ETF symbol
            df: OHLCV DataFrame for the symbol
            position: Dictionary with position info:
                - entry_date: str or Timestamp
                - entry_price: float
                - shares: float (optional, for logging)
            as_of_date: Reference date for checks; uses latest if None

        Returns:
            Dictionary with keys:
            - symbol: str
            - atr_stop: dict - result from check_stop_loss()
            - time_stop: dict - result from check_time_stop()
            - liquidity: dict - result from check_liquidity()
            - can_sell_today: bool - T+1 constraint check
            - actions: list - recommended actions ['hold', 'sell_atr', 'sell_time', etc.]
        """
        entry_date = position['entry_date']
        entry_price = position['entry_price']

        # Determine check date
        if as_of_date is None:
            check_date = df.index[-1]
        else:
            check_date = pd.to_datetime(as_of_date)

        # Check ATR stop loss
        try:
            atr_stop = check_stop_loss(
                df=df,
                entry_date=entry_date,
                entry_price=entry_price,
                atr_multiplier=self.atr_multiplier,
                atr_period=self.atr_period,
                check_until_date=check_date
            )
        except Exception as e:
            logger.error(f"{symbol}: ATR stop check failed: {e}")
            atr_stop = {'triggered': False, 'trigger_reason': f'error: {e}'}

        # Check time stop
        try:
            time_stop = check_time_stop(
                df=df,
                entry_date=entry_date,
                entry_price=entry_price,
                max_hold_days=self.time_stop_days,
                min_profit_atr=self.time_stop_min_profit_atr,
                atr_period=self.atr_period,
                check_until_date=check_date
            )
        except Exception as e:
            logger.error(f"{symbol}: Time stop check failed: {e}")
            time_stop = {'triggered': False, 'reason': f'error: {e}'}

        # Check liquidity
        try:
            liquidity = check_liquidity(
                df=df,
                min_amount=self.min_liquidity_amount,
                max_spread_pct=self.max_spread_pct,
                as_of_date=check_date
            )
        except Exception as e:
            logger.error(f"{symbol}: Liquidity check failed: {e}")
            liquidity = {'sufficient': True, 'reason': f'check_error: {e}'}

        # Check T+1 constraint
        can_sell_today = True
        if self.enforce_t_plus_1:
            can_sell_today = check_t_plus_1(entry_date, check_date)

        # Determine recommended actions
        actions = []

        if atr_stop.get('triggered', False):
            if can_sell_today:
                actions.append('sell_atr_stop')
            else:
                actions.append('sell_atr_stop_tomorrow')
        elif time_stop.get('triggered', False):
            if can_sell_today:
                actions.append('sell_time_stop')
            else:
                actions.append('sell_time_stop_tomorrow')
        else:
            actions.append('hold')

        if not liquidity.get('sufficient', True):
            actions.append('warning_low_liquidity')

        return {
            'symbol': symbol,
            'atr_stop': atr_stop,
            'time_stop': time_stop,
            'liquidity': liquidity,
            'can_sell_today': can_sell_today,
            'actions': actions
        }

    def check_portfolio_risk(
        self,
        data_dict: Dict[str, pd.DataFrame],
        positions: Dict[str, dict],
        market_df: Optional[pd.DataFrame] = None,
        account_equity: Optional[pd.Series] = None,
        as_of_date: Optional[Union[str, pd.Timestamp]] = None
    ) -> dict:
        """
        Check risk controls for entire portfolio.

        Args:
            data_dict: Dictionary mapping symbol -> OHLCV DataFrame
            positions: Dictionary mapping symbol -> position info dict
            market_df: Market index DataFrame for circuit breaker check
            account_equity: Account equity Series for circuit breaker check
            as_of_date: Reference date; uses latest if None

        Returns:
            Dictionary with keys:
            - circuit_breaker: dict - result from check_circuit_breaker()
            - position_risks: dict - mapping symbol -> check_position_risk() result
            - portfolio_actions: list - portfolio-level recommended actions
            - summary: dict - aggregated statistics
        """
        # Check circuit breaker
        circuit_breaker = {'triggered': False, 'reason': 'not_checked'}

        try:
            circuit_breaker = check_circuit_breaker(
                market_df=market_df,
                account_equity=account_equity,
                as_of_date=as_of_date,
                market_drop_threshold=self.market_drop_threshold,
                account_drawdown_threshold=self.account_drawdown_threshold,
                lookback_days=self.circuit_breaker_lookback
            )
        except Exception as e:
            logger.warning(f"Circuit breaker check skipped or failed: {e}")

        # Check individual positions
        position_risks = {}

        for symbol, position in positions.items():
            if symbol not in data_dict:
                logger.warning(f"{symbol}: No data available for risk check")
                continue

            try:
                risk_status = self.check_position_risk(
                    symbol=symbol,
                    df=data_dict[symbol],
                    position=position,
                    as_of_date=as_of_date
                )
                position_risks[symbol] = risk_status
            except Exception as e:
                logger.error(f"{symbol}: Position risk check failed: {e}")

        # Generate portfolio-level actions
        portfolio_actions = []

        if circuit_breaker.get('triggered', False):
            portfolio_actions.extend(circuit_breaker.get('recommendations', []))

        # Count stops triggered
        atr_stops = sum(1 for r in position_risks.values()
                       if r.get('atr_stop', {}).get('triggered', False))
        time_stops = sum(1 for r in position_risks.values()
                        if r.get('time_stop', {}).get('triggered', False))
        low_liquidity = sum(1 for r in position_risks.values()
                           if not r.get('liquidity', {}).get('sufficient', True))

        # Summary statistics
        summary = {
            'total_positions': len(positions),
            'positions_checked': len(position_risks),
            'atr_stops_triggered': atr_stops,
            'time_stops_triggered': time_stops,
            'low_liquidity_warnings': low_liquidity,
            'circuit_breaker_active': circuit_breaker.get('triggered', False)
        }

        if atr_stops > 0:
            logger.warning(f"Portfolio: {atr_stops} ATR stops triggered")
        if time_stops > 0:
            logger.info(f"Portfolio: {time_stops} time stops triggered")
        if circuit_breaker.get('triggered', False):
            logger.warning(f"Portfolio: Circuit breaker activated - {circuit_breaker['reason']}")

        return {
            'circuit_breaker': circuit_breaker,
            'position_risks': position_risks,
            'portfolio_actions': portfolio_actions,
            'summary': summary
        }
