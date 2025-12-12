"""
Portfolio Management Module for ETF Trend Following System

This module handles position tracking, T+1 constraints, trade order generation,
and portfolio state management. It provides core functionality for maintaining
holdings, generating rebalancing orders, and tracking equity curves.

Key Features:
- Position state tracking with entry price, shares, P&L, and stop loss levels
- T+1 constraint handling (cannot sell on the day of purchase)
- Trade order generation with configurable execution logic
- Portfolio snapshots for state persistence and recovery
- Equity curve tracking for performance analysis
- Transaction cost modeling (optional)

Author: Claude
Date: 2025-12-11
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import defaultdict


@dataclass
class Position:
    """
    Represents a single position in the portfolio.

    Attributes
    ----------
    symbol : str
        Security symbol/ticker
    entry_date : str
        Entry date in 'YYYY-MM-DD' format
    entry_price : float
        Entry price per share
    shares : int
        Number of shares held (must be positive multiples of 100 for A-shares)
    cost : float
        Total cost basis (entry_price * shares + commissions)
    highest_price : float, default 0.0
        Highest price seen during holding period (for trailing stop)
    stop_line : float, default 0.0
        Current stop loss price level
    """
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    cost: float
    highest_price: float = 0.0
    stop_line: float = 0.0

    def __post_init__(self):
        """Validate position data after initialization."""
        if self.shares <= 0:
            raise ValueError(f"shares must be positive, got {self.shares}")
        if self.entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {self.entry_price}")
        if self.cost <= 0:
            raise ValueError(f"cost must be positive, got {self.cost}")

        # Initialize highest_price if not set
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price

    def update(self, current_price: float, current_date: str) -> None:
        """
        Update position with current market price.

        Parameters
        ----------
        current_price : float
            Current market price
        current_date : str
            Current date in 'YYYY-MM-DD' format
        """
        if current_price <= 0:
            raise ValueError(f"current_price must be positive, got {current_price}")

        # Update highest price during holding period
        if current_price > self.highest_price:
            self.highest_price = current_price

    def can_sell(self, check_date: str) -> bool:
        """
        Check if position can be sold on the given date (T+1 constraint).

        In Chinese stock market, stocks bought on day T cannot be sold until day T+1.

        Parameters
        ----------
        check_date : str
            Date to check in 'YYYY-MM-DD' format

        Returns
        -------
        bool
            True if position can be sold on check_date, False otherwise
        """
        entry_dt = datetime.strptime(self.entry_date, '%Y-%m-%d')
        check_dt = datetime.strptime(check_date, '%Y-%m-%d')

        # Can sell if at least 1 trading day has passed
        return check_dt > entry_dt

    @property
    def current_price(self) -> float:
        """Get the latest price (for convenience, stored externally)."""
        return getattr(self, '_current_price', self.entry_price)

    @current_price.setter
    def current_price(self, price: float):
        """Set current price for P&L calculation."""
        self._current_price = price

    @property
    def market_value(self) -> float:
        """Calculate current market value of position."""
        return self.current_price * self.shares

    @property
    def pnl(self) -> float:
        """Calculate profit/loss in absolute terms."""
        return self.market_value - self.cost

    @property
    def pnl_pct(self) -> float:
        """Calculate profit/loss as percentage of cost."""
        return (self.market_value - self.cost) / self.cost if self.cost > 0 else 0.0

    @property
    def days_held(self) -> int:
        """Calculate number of days position has been held."""
        entry_dt = datetime.strptime(self.entry_date, '%Y-%m-%d')
        current_dt = datetime.now()
        return (current_dt - entry_dt).days

    def to_dict(self) -> dict:
        """
        Convert position to dictionary for serialization.

        Returns
        -------
        dict
            Dictionary representation of position
        """
        base_dict = asdict(self)
        # Add computed properties
        base_dict.update({
            'current_price': self.current_price,
            'market_value': self.market_value,
            'pnl': round(self.pnl, 2),
            'pnl_pct': round(self.pnl_pct * 100, 2),  # As percentage
            'days_held': self.days_held
        })
        return base_dict


@dataclass
class TradeOrder:
    """
    Represents a trade order to be executed.

    Attributes
    ----------
    action : str
        Trade action: 'buy' or 'sell'
    symbol : str
        Security symbol/ticker
    shares : int
        Number of shares to trade
    price : float
        Target execution price
    reason : str
        Reason for the trade (e.g., 'signal_buy', 'stop_loss', 'rank_out')
    timestamp : str, optional
        ISO format timestamp when order was created
    """
    action: str
    symbol: str
    shares: int
    price: float
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Validate order data."""
        if self.action not in ('buy', 'sell'):
            raise ValueError(f"action must be 'buy' or 'sell', got '{self.action}'")
        if self.shares <= 0:
            raise ValueError(f"shares must be positive, got {self.shares}")
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")

    @property
    def value(self) -> float:
        """Calculate order value (shares * price)."""
        return self.shares * self.price

    def to_dict(self) -> dict:
        """
        Convert order to dictionary for serialization.

        Returns
        -------
        dict
            Dictionary representation of order
        """
        order_dict = asdict(self)
        order_dict['value'] = round(self.value, 2)
        return order_dict


class Portfolio:
    """
    Portfolio manager for ETF trend following strategy.

    Manages positions, cash, trade execution, and portfolio analytics.
    Handles T+1 constraints and transaction costs.

    Parameters
    ----------
    initial_cash : float, default 1_000_000
        Initial cash balance in portfolio
    commission_rate : float, default 0.0003
        Commission rate (0.03% for ETFs in China)
    stamp_duty_rate : float, default 0.0
        Stamp duty rate (0% for ETFs, 0.1% for stocks)
    min_commission : float, default 5.0
        Minimum commission per trade (5 RMB)
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000,
        commission_rate: float = 0.0003,
        stamp_duty_rate: float = 0.0,
        min_commission: float = 5.0
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeOrder] = []
        self.equity_curve: List[dict] = []

        # Transaction cost parameters
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.min_commission = min_commission

        # Track last update date
        self.last_update_date: Optional[str] = None

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a given symbol.

        Parameters
        ----------
        symbol : str
            Security symbol

        Returns
        -------
        Position or None
            Position object if exists, None otherwise
        """
        return self.positions.get(symbol)

    def add_position(
        self,
        symbol: str,
        shares: int,
        price: float,
        date: str,
        include_costs: bool = True
    ) -> None:
        """
        Add a new position to the portfolio.

        Parameters
        ----------
        symbol : str
            Security symbol
        shares : int
            Number of shares to buy
        price : float
            Entry price per share
        date : str
            Entry date in 'YYYY-MM-DD' format
        include_costs : bool, default True
            Whether to include transaction costs in cost basis

        Raises
        ------
        ValueError
            If position already exists or insufficient cash
        """
        if symbol in self.positions:
            raise ValueError(f"Position for {symbol} already exists")

        # Calculate transaction costs
        gross_value = shares * price
        commission = max(gross_value * self.commission_rate, self.min_commission) if include_costs else 0.0
        total_cost = gross_value + commission

        # Check available cash
        if total_cost > self.cash:
            raise ValueError(
                f"Insufficient cash to open position. "
                f"Required: {total_cost:.2f}, Available: {self.cash:.2f}"
            )

        # Create position
        position = Position(
            symbol=symbol,
            entry_date=date,
            entry_price=price,
            shares=shares,
            cost=total_cost,
            highest_price=price
        )

        # Update portfolio state
        self.positions[symbol] = position
        self.cash -= total_cost

        # Update position's current price
        position.current_price = price

    def close_position(
        self,
        symbol: str,
        price: float,
        date: str,
        reason: str,
        include_costs: bool = True
    ) -> TradeOrder:
        """
        Close an existing position.

        Parameters
        ----------
        symbol : str
            Security symbol
        price : float
            Exit price per share
        date : str
            Exit date in 'YYYY-MM-DD' format
        reason : str
            Reason for closing (e.g., 'stop_loss', 'signal_sell')
        include_costs : bool, default True
            Whether to deduct transaction costs from proceeds

        Returns
        -------
        TradeOrder
            The sell order that was created

        Raises
        ------
        ValueError
            If position doesn't exist or cannot be sold due to T+1
        """
        position = self.positions.get(symbol)
        if position is None:
            raise ValueError(f"No position found for {symbol}")

        # Check T+1 constraint
        if not position.can_sell(date):
            raise ValueError(
                f"Cannot sell {symbol} on {date} due to T+1 constraint. "
                f"Position opened on {position.entry_date}"
            )

        # Calculate proceeds
        gross_proceeds = position.shares * price
        commission = max(gross_proceeds * self.commission_rate, self.min_commission) if include_costs else 0.0
        stamp_duty = gross_proceeds * self.stamp_duty_rate if include_costs else 0.0
        net_proceeds = gross_proceeds - commission - stamp_duty

        # Create sell order
        order = TradeOrder(
            action='sell',
            symbol=symbol,
            shares=position.shares,
            price=price,
            reason=reason
        )

        # Update portfolio state
        self.cash += net_proceeds
        del self.positions[symbol]

        return order

    def update_positions(
        self,
        prices: Dict[str, float],
        date: str
    ) -> None:
        """
        Update all positions with current market prices.

        Parameters
        ----------
        prices : dict
            Dictionary mapping symbols to current prices
        date : str
            Current date in 'YYYY-MM-DD' format
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                price = prices[symbol]
                position.update(price, date)
                position.current_price = price

        self.last_update_date = date

    def get_total_equity(self) -> float:
        """
        Calculate total portfolio equity (cash + positions market value).

        Returns
        -------
        float
            Total equity value
        """
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + positions_value

    def get_holdings_summary(self) -> pd.DataFrame:
        """
        Get summary DataFrame of all current holdings.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: symbol, shares, entry_date, entry_price,
            current_price, market_value, cost, pnl, pnl_pct, days_held, stop_line
        """
        if not self.positions:
            return pd.DataFrame()

        holdings_data = []
        for symbol, pos in self.positions.items():
            holdings_data.append({
                'symbol': symbol,
                'shares': pos.shares,
                'entry_date': pos.entry_date,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'market_value': pos.market_value,
                'cost': pos.cost,
                'pnl': pos.pnl,
                'pnl_pct': pos.pnl_pct * 100,  # As percentage
                'days_held': pos.days_held,
                'highest_price': pos.highest_price,
                'stop_line': pos.stop_line
            })

        df = pd.DataFrame(holdings_data)
        # Sort by market value descending
        df = df.sort_values('market_value', ascending=False).reset_index(drop=True)
        return df

    def generate_orders(
        self,
        target_positions: Dict[str, dict],
        current_date: str,
        current_prices: Dict[str, float],
        sell_reasons: Optional[Dict[str, str]] = None
    ) -> List[TradeOrder]:
        """
        Generate trade orders to rebalance to target positions.

        Considers T+1 constraints: positions bought today cannot be sold.

        Parameters
        ----------
        target_positions : dict
            Dictionary mapping symbol to target specs:
            {'symbol': {'shares': int, 'price': float}}
        current_date : str
            Current date in 'YYYY-MM-DD' format
        current_prices : dict
            Dictionary mapping symbols to current market prices
        sell_reasons : dict, optional
            Dictionary mapping symbols to sell reasons for positions to close

        Returns
        -------
        list of TradeOrder
            List of orders to execute (sells first, then buys)
        """
        orders = []
        sell_reasons = sell_reasons or {}

        # Phase 1: Generate sell orders for positions to close
        symbols_to_sell = set(self.positions.keys()) - set(target_positions.keys())

        for symbol in symbols_to_sell:
            position = self.positions[symbol]

            # Check T+1 constraint
            if not position.can_sell(current_date):
                # Skip this sell, will retry next day
                continue

            price = current_prices.get(symbol, position.current_price)
            reason = sell_reasons.get(symbol, 'rebalance')

            order = TradeOrder(
                action='sell',
                symbol=symbol,
                shares=position.shares,
                price=price,
                reason=reason
            )
            orders.append(order)

        # Phase 2: Generate orders for position adjustments
        for symbol, target_spec in target_positions.items():
            target_shares = target_spec['shares']
            target_price = target_spec.get('price', current_prices.get(symbol, 0))

            if target_price <= 0:
                continue  # Skip if no valid price

            current_position = self.positions.get(symbol)

            if current_position is None:
                # New position to open
                if target_shares > 0:
                    order = TradeOrder(
                        action='buy',
                        symbol=symbol,
                        shares=target_shares,
                        price=target_price,
                        reason='signal_buy'
                    )
                    orders.append(order)
            else:
                # Adjust existing position
                current_shares = current_position.shares
                shares_diff = target_shares - current_shares

                if shares_diff > 0:
                    # Increase position
                    order = TradeOrder(
                        action='buy',
                        symbol=symbol,
                        shares=shares_diff,
                        price=target_price,
                        reason='rebalance_add'
                    )
                    orders.append(order)
                elif shares_diff < 0:
                    # Decrease position (check T+1)
                    if current_position.can_sell(current_date):
                        order = TradeOrder(
                            action='sell',
                            symbol=symbol,
                            shares=abs(shares_diff),
                            price=target_price,
                            reason=sell_reasons.get(symbol, 'rebalance_reduce')
                        )
                        orders.append(order)
                # If shares_diff == 0, no action needed

        # Sort orders: sells first, then buys
        orders.sort(key=lambda x: 0 if x.action == 'sell' else 1)

        return orders

    def apply_orders(
        self,
        orders: List[TradeOrder],
        execution_date: str,
        execution_prices: Optional[Dict[str, float]] = None,
        include_costs: bool = True
    ) -> Dict[str, str]:
        """
        Execute trade orders and update portfolio state.

        Parameters
        ----------
        orders : list of TradeOrder
            Orders to execute
        execution_date : str
            Date of execution in 'YYYY-MM-DD' format
        execution_prices : dict, optional
            Actual execution prices (if different from order prices)
        include_costs : bool, default True
            Whether to apply transaction costs

        Returns
        -------
        dict
            Dictionary mapping order index to execution status ('executed' or error message)
        """
        execution_prices = execution_prices or {}
        results = {}

        for i, order in enumerate(orders):
            try:
                price = execution_prices.get(order.symbol, order.price)

                if order.action == 'buy':
                    # Check if position already exists
                    if order.symbol in self.positions:
                        # Add to existing position (average up/down)
                        existing_pos = self.positions[order.symbol]

                        # Calculate new cost basis
                        gross_value = order.shares * price
                        commission = max(gross_value * self.commission_rate, self.min_commission) if include_costs else 0.0
                        additional_cost = gross_value + commission

                        if additional_cost > self.cash:
                            results[i] = f"Insufficient cash: need {additional_cost:.2f}, have {self.cash:.2f}"
                            continue

                        # Update position
                        new_shares = existing_pos.shares + order.shares
                        new_cost = existing_pos.cost + additional_cost
                        new_avg_price = (existing_pos.entry_price * existing_pos.shares + price * order.shares) / new_shares

                        existing_pos.shares = new_shares
                        existing_pos.cost = new_cost
                        existing_pos.entry_price = new_avg_price
                        existing_pos.current_price = price

                        self.cash -= additional_cost
                    else:
                        # Open new position
                        self.add_position(
                            symbol=order.symbol,
                            shares=order.shares,
                            price=price,
                            date=execution_date,
                            include_costs=include_costs
                        )

                    results[i] = 'executed'

                elif order.action == 'sell':
                    # Check if position exists
                    if order.symbol not in self.positions:
                        results[i] = f"No position to sell for {order.symbol}"
                        continue

                    position = self.positions[order.symbol]

                    # Check T+1 constraint
                    if not position.can_sell(execution_date):
                        results[i] = f"T+1 constraint: cannot sell {order.symbol} on {execution_date}"
                        continue

                    # Partial or full close
                    shares_to_sell = min(order.shares, position.shares)

                    if shares_to_sell == position.shares:
                        # Full close
                        self.close_position(
                            symbol=order.symbol,
                            price=price,
                            date=execution_date,
                            reason=order.reason,
                            include_costs=include_costs
                        )
                    else:
                        # Partial close
                        gross_proceeds = shares_to_sell * price
                        commission = max(gross_proceeds * self.commission_rate, self.min_commission) if include_costs else 0.0
                        stamp_duty = gross_proceeds * self.stamp_duty_rate if include_costs else 0.0
                        net_proceeds = gross_proceeds - commission - stamp_duty

                        # Reduce position proportionally
                        cost_per_share = position.cost / position.shares
                        position.shares -= shares_to_sell
                        position.cost -= cost_per_share * shares_to_sell

                        self.cash += net_proceeds

                    results[i] = 'executed'

                # Record in trade history
                self.trade_history.append(order)

            except Exception as e:
                results[i] = f"Error: {str(e)}"

        return results

    def record_equity(self, date: str, prices: Dict[str, float]) -> None:
        """
        Record a snapshot of portfolio equity for the equity curve.

        Parameters
        ----------
        date : str
            Date of snapshot in 'YYYY-MM-DD' format
        prices : dict
            Current market prices for all positions
        """
        # Update positions with current prices
        self.update_positions(prices, date)

        # Calculate metrics
        total_equity = self.get_total_equity()
        positions_value = sum(pos.market_value for pos in self.positions.values())

        snapshot = {
            'date': date,
            'equity': round(total_equity, 2),
            'cash': round(self.cash, 2),
            'positions_value': round(positions_value, 2),
            'num_positions': len(self.positions),
            'leverage': round(positions_value / total_equity, 4) if total_equity > 0 else 0.0
        }

        self.equity_curve.append(snapshot)

    def save_snapshot(self, path: str, date: str) -> None:
        """
        Save portfolio state to JSON file.

        Parameters
        ----------
        path : str
            File path to save snapshot
        date : str
            Date of snapshot (for metadata)
        """
        snapshot = {
            'metadata': {
                'snapshot_date': date,
                'created_at': datetime.now().isoformat(),
                'initial_cash': self.initial_cash
            },
            'portfolio': {
                'cash': round(self.cash, 2),
                'total_equity': round(self.get_total_equity(), 2),
                'last_update_date': self.last_update_date
            },
            'positions': {
                symbol: pos.to_dict()
                for symbol, pos in self.positions.items()
            },
            'cost_params': {
                'commission_rate': self.commission_rate,
                'stamp_duty_rate': self.stamp_duty_rate,
                'min_commission': self.min_commission
            }
        }

        # Create directory if needed
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

    def load_snapshot(self, path: str) -> None:
        """
        Load portfolio state from JSON file.

        Parameters
        ----------
        path : str
            File path to load snapshot from

        Raises
        ------
        FileNotFoundError
            If snapshot file doesn't exist
        ValueError
            If snapshot format is invalid
        """
        with open(path, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)

        # Validate snapshot structure
        required_keys = ['metadata', 'portfolio', 'positions']
        if not all(key in snapshot for key in required_keys):
            raise ValueError(f"Invalid snapshot format. Required keys: {required_keys}")

        # Restore portfolio state
        self.cash = snapshot['portfolio']['cash']
        self.last_update_date = snapshot['portfolio'].get('last_update_date')
        self.initial_cash = snapshot['metadata']['initial_cash']

        # Restore cost parameters if present
        if 'cost_params' in snapshot:
            params = snapshot['cost_params']
            self.commission_rate = params.get('commission_rate', self.commission_rate)
            self.stamp_duty_rate = params.get('stamp_duty_rate', self.stamp_duty_rate)
            self.min_commission = params.get('min_commission', self.min_commission)

        # Restore positions
        self.positions = {}
        for symbol, pos_data in snapshot['positions'].items():
            # Remove computed fields that are not in Position dataclass
            pos_dict = {
                k: v for k, v in pos_data.items()
                if k in ['symbol', 'entry_date', 'entry_price', 'shares', 'cost', 'highest_price', 'stop_line']
            }
            position = Position(**pos_dict)

            # Restore current price if available
            if 'current_price' in pos_data:
                position.current_price = pos_data['current_price']

            self.positions[symbol] = position

    def get_equity_history(self) -> pd.DataFrame:
        """
        Get equity curve as DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: date, equity, cash, positions_value, num_positions, leverage
        """
        if not self.equity_curve:
            return pd.DataFrame()

        df = pd.DataFrame(self.equity_curve)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        return df

    def get_trade_history(self) -> pd.DataFrame:
        """
        Get trade history as DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: timestamp, action, symbol, shares, price, value, reason
        """
        if not self.trade_history:
            return pd.DataFrame()

        trades_data = [order.to_dict() for order in self.trade_history]
        df = pd.DataFrame(trades_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df

    def get_performance_stats(self) -> dict:
        """
        Calculate basic performance statistics.

        Returns
        -------
        dict
            Dictionary with performance metrics:
            - total_return: Total return percentage
            - total_equity: Current total equity
            - cash: Current cash balance
            - invested: Current invested amount
            - num_positions: Number of open positions
            - num_trades: Total number of trades executed
        """
        total_equity = self.get_total_equity()
        total_return = (total_equity - self.initial_cash) / self.initial_cash * 100
        positions_value = sum(pos.market_value for pos in self.positions.values())

        return {
            'total_return_pct': round(total_return, 2),
            'total_equity': round(total_equity, 2),
            'initial_cash': round(self.initial_cash, 2),
            'current_cash': round(self.cash, 2),
            'invested_value': round(positions_value, 2),
            'num_positions': len(self.positions),
            'num_trades': len(self.trade_history)
        }

    def __repr__(self) -> str:
        """String representation of portfolio."""
        equity = self.get_total_equity()
        return (
            f"Portfolio(equity={equity:.2f}, cash={self.cash:.2f}, "
            f"positions={len(self.positions)}, trades={len(self.trade_history)})"
        )
