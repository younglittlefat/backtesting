"""
组合模拟器 - v3真实调仓模拟的核心模块

功能:
1. 管理多标的持仓状态
2. 执行调仓操作（卖出旧标的、买入新标的）
3. 处理策略信号（KAMA交叉）
4. 计算交易成本和净值

设计原则:
- 模块化: 持仓、交易、指标计算分离
- 可追溯: 所有交易记录详细日志
- 可配置: 成本参数、调仓周期可配置
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime


class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Position:
    """单标的持仓"""
    symbol: str
    shares: float = 0.0           # 持仓股数
    cost_basis: float = 0.0       # 成本价
    entry_date: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return self.shares <= 0


@dataclass
class Trade:
    """交易记录"""
    date: str
    symbol: str
    side: str                     # "buy" or "sell"
    shares: float
    price: float
    amount: float                 # 成交金额
    commission: float             # 佣金
    slippage_cost: float          # 滑点成本
    total_cost: float             # 总成本
    trade_type: str               # "rotation" or "signal"
    note: str = ""


@dataclass
class CostConfig:
    """交易成本配置"""
    commission_rate: float = 0.00025    # 佣金费率 0.025%
    slippage_rate: float = 0.001        # 滑点 0.1%
    stamp_tax_rate: float = 0.0         # 印花税（ETF免征）

    def calc_buy_cost(self, amount: float) -> Tuple[float, float, float]:
        """计算买入成本，返回(佣金, 滑点成本, 总成本)"""
        commission = amount * self.commission_rate
        slippage = amount * self.slippage_rate
        return commission, slippage, commission + slippage

    def calc_sell_cost(self, amount: float) -> Tuple[float, float, float]:
        """计算卖出成本，返回(佣金, 滑点成本, 总成本)"""
        commission = amount * self.commission_rate
        slippage = amount * self.slippage_rate
        stamp_tax = amount * self.stamp_tax_rate
        return commission, slippage + stamp_tax, commission + slippage + stamp_tax


class KAMAIndicator:
    """KAMA指标计算器"""

    def __init__(self, period: int = 20, fast: int = 2, slow: int = 30):
        self.period = period
        self.fast = fast
        self.slow = slow
        self.fast_sc = 2.0 / (fast + 1)
        self.slow_sc = 2.0 / (slow + 1)

    def calculate(self, close: pd.Series) -> pd.Series:
        """计算KAMA序列"""
        if len(close) < self.period:
            return pd.Series([np.nan] * len(close), index=close.index)

        # 效率比率 ER
        change = abs(close - close.shift(self.period))
        volatility = abs(close - close.shift(1)).rolling(self.period).sum()
        er = change / volatility.replace(0, np.nan)

        # 平滑常数 SC
        sc = (er * (self.fast_sc - self.slow_sc) + self.slow_sc) ** 2

        # 计算KAMA
        kama = pd.Series(index=close.index, dtype=float)
        kama.iloc[:self.period] = np.nan
        kama.iloc[self.period - 1] = close.iloc[:self.period].mean()

        for i in range(self.period, len(close)):
            prev_kama = kama.iloc[i - 1]
            if pd.isna(prev_kama):
                prev_kama = close.iloc[i]
            kama.iloc[i] = prev_kama + sc.iloc[i] * (close.iloc[i] - prev_kama)

        return kama


class PortfolioSimulator:
    """
    真实调仓组合模拟器

    核心职责:
    1. 管理现金和持仓
    2. 执行调仓操作
    3. 处理策略信号
    4. 计算净值序列
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000,
        cost_config: Optional[CostConfig] = None,
        kama_params: Optional[Dict] = None
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.cost_config = cost_config or CostConfig()

        # KAMA参数
        kama_params = kama_params or {}
        self.kama = KAMAIndicator(
            period=kama_params.get('period', 20),
            fast=kama_params.get('fast', 2),
            slow=kama_params.get('slow', 30)
        )

        # 持仓状态
        self.positions: Dict[str, Position] = {}

        # 每个标的的KAMA状态 (用于信号判断)
        self.kama_values: Dict[str, float] = {}
        self.prev_kama_values: Dict[str, float] = {}

        # 交易和净值记录
        self.trades: List[Trade] = []
        self.nav_history: List[Dict] = []

        # 当前允许交易的标的池
        self.current_pool: List[str] = []

        # 等待买入信号的标的（调仓时新增的）
        self.waiting_for_signal: set = set()

    def get_position_value(self, prices: Dict[str, float]) -> float:
        """计算持仓市值"""
        total = 0.0
        for symbol, pos in self.positions.items():
            if not pos.is_empty and symbol in prices:
                total += pos.shares * prices[symbol]
        return total

    def get_nav(self, prices: Dict[str, float]) -> float:
        """计算净值"""
        return self.cash + self.get_position_value(prices)

    def rotate(
        self,
        new_pool: List[str],
        date: str,
        prices: Dict[str, float],
        suspended: List[str] = None
    ) -> Dict:
        """
        执行调仓操作

        参数:
            new_pool: 新的ETF池
            date: 调仓日期
            prices: 开盘价字典
            suspended: 停牌标的列表

        返回:
            调仓结果摘要
        """
        suspended = suspended or []
        old_pool = set(self.current_pool)
        new_pool_set = set(new_pool)

        # 计算需要操作的标的
        to_sell = old_pool - new_pool_set  # 需卖出
        to_buy = new_pool_set - old_pool   # 需买入
        to_keep = old_pool & new_pool_set  # 保持不动

        # 过滤停牌标的
        to_sell = [s for s in to_sell if s not in suspended]
        to_buy = [s for s in to_buy if s not in suspended]

        rotation_trades = []
        sell_proceeds = 0.0
        sell_cost = 0.0

        # 1. 卖出旧标的
        for symbol in to_sell:
            if symbol in self.positions and not self.positions[symbol].is_empty:
                pos = self.positions[symbol]
                if symbol not in prices:
                    continue

                # 卖出价 = 开盘价 × (1 - 滑点)
                sell_price = prices[symbol] * (1 - self.cost_config.slippage_rate)
                amount = pos.shares * sell_price
                commission, slippage, total_cost = self.cost_config.calc_sell_cost(amount)

                trade = Trade(
                    date=date,
                    symbol=symbol,
                    side="sell",
                    shares=pos.shares,
                    price=sell_price,
                    amount=amount,
                    commission=commission,
                    slippage_cost=slippage,
                    total_cost=total_cost,
                    trade_type="rotation",
                    note="调仓卖出"
                )
                self.trades.append(trade)
                rotation_trades.append(trade)

                sell_proceeds += amount
                sell_cost += total_cost

                # 清空持仓
                self.positions[symbol] = Position(symbol=symbol)

                # 清除KAMA状态
                if symbol in self.kama_values:
                    del self.kama_values[symbol]
                if symbol in self.prev_kama_values:
                    del self.prev_kama_values[symbol]

        # 更新现金
        self.cash += sell_proceeds - sell_cost

        # 2. 新标的加入等待信号列表（不立即买入）
        self.waiting_for_signal.update(to_buy)

        # 更新当前池子
        self.current_pool = list(new_pool)

        return {
            'date': date,
            'sold': list(to_sell),
            'added_to_watchlist': list(to_buy),
            'kept': list(to_keep),
            'sell_proceeds': sell_proceeds,
            'sell_cost': sell_cost,
            'trades_count': len(rotation_trades)
        }

    def process_signals(
        self,
        date: str,
        prices: Dict[str, float],
        kama_values: Dict[str, float],
        suspended: List[str] = None
    ) -> List[Trade]:
        """
        处理KAMA策略信号

        参数:
            date: 日期
            prices: 当日收盘价
            kama_values: 当日KAMA值
            suspended: 停牌标的

        返回:
            当日产生的交易列表
        """
        suspended = suspended or []
        day_trades = []

        for symbol in self.current_pool:
            if symbol in suspended or symbol not in prices or symbol not in kama_values:
                continue

            close = prices[symbol]
            kama_val = kama_values[symbol]
            prev_kama = self.prev_kama_values.get(symbol, kama_val)

            # 判断金叉（价格上穿KAMA）
            is_golden_cross = (close > kama_val) and (prices.get(f'{symbol}_prev_close', close) <= prev_kama)

            # 判断死叉（价格下穿KAMA）
            is_death_cross = (close < kama_val) and (prices.get(f'{symbol}_prev_close', close) >= prev_kama)

            # 处理等待信号的新标的
            if symbol in self.waiting_for_signal:
                if is_golden_cross:
                    # 买入信号 - 分配资金
                    trade = self._execute_buy(symbol, date, close)
                    if trade:
                        day_trades.append(trade)
                        self.waiting_for_signal.discard(symbol)

            # 处理已持仓标的
            elif symbol in self.positions and not self.positions[symbol].is_empty:
                if is_death_cross:
                    # 卖出信号
                    trade = self._execute_sell(symbol, date, close, "signal")
                    if trade:
                        day_trades.append(trade)
                        self.waiting_for_signal.add(symbol)  # 卖出后等待下次信号

            # 更新KAMA状态
            self.prev_kama_values[symbol] = self.kama_values.get(symbol, kama_val)
            self.kama_values[symbol] = kama_val

        return day_trades

    def _execute_buy(self, symbol: str, date: str, price: float) -> Optional[Trade]:
        """执行买入操作"""
        # 计算可用于该标的的资金（等权分配给所有等待信号的标的）
        waiting_count = len(self.waiting_for_signal)
        if waiting_count == 0:
            return None

        # 每个标的分配的资金 = 可用现金 / 等待数量
        allocation = self.cash / waiting_count

        # 买入价 = 收盘价 × (1 + 滑点)
        buy_price = price * (1 + self.cost_config.slippage_rate)

        # 计算可买股数（考虑成本）
        effective_amount = allocation / (1 + self.cost_config.commission_rate + self.cost_config.slippage_rate)
        shares = effective_amount / buy_price

        if shares <= 0:
            return None

        amount = shares * buy_price
        commission, slippage, total_cost = self.cost_config.calc_buy_cost(amount)

        trade = Trade(
            date=date,
            symbol=symbol,
            side="buy",
            shares=shares,
            price=buy_price,
            amount=amount,
            commission=commission,
            slippage_cost=slippage,
            total_cost=total_cost,
            trade_type="signal",
            note="KAMA金叉买入"
        )

        # 更新持仓
        self.positions[symbol] = Position(
            symbol=symbol,
            shares=shares,
            cost_basis=buy_price,
            entry_date=date
        )

        # 扣除现金
        self.cash -= (amount + total_cost)

        self.trades.append(trade)
        return trade

    def _execute_sell(self, symbol: str, date: str, price: float, trade_type: str) -> Optional[Trade]:
        """执行卖出操作"""
        if symbol not in self.positions or self.positions[symbol].is_empty:
            return None

        pos = self.positions[symbol]

        # 卖出价 = 收盘价 × (1 - 滑点)
        sell_price = price * (1 - self.cost_config.slippage_rate)
        amount = pos.shares * sell_price
        commission, slippage, total_cost = self.cost_config.calc_sell_cost(amount)

        trade = Trade(
            date=date,
            symbol=symbol,
            side="sell",
            shares=pos.shares,
            price=sell_price,
            amount=amount,
            commission=commission,
            slippage_cost=slippage,
            total_cost=total_cost,
            trade_type=trade_type,
            note="KAMA死叉卖出" if trade_type == "signal" else "调仓卖出"
        )

        # 更新现金
        self.cash += amount - total_cost

        # 清空持仓
        self.positions[symbol] = Position(symbol=symbol)

        self.trades.append(trade)
        return trade

    def record_nav(self, date: str, prices: Dict[str, float]):
        """记录每日净值"""
        nav = self.get_nav(prices)
        position_value = self.get_position_value(prices)

        self.nav_history.append({
            'date': date,
            'nav': nav,
            'cash': self.cash,
            'position_value': position_value,
            'return_pct': (nav / self.initial_cash - 1) * 100
        })

    def get_trades_df(self) -> pd.DataFrame:
        """获取交易记录DataFrame"""
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame([
            {
                'date': t.date,
                'symbol': t.symbol,
                'side': t.side,
                'shares': t.shares,
                'price': t.price,
                'amount': t.amount,
                'commission': t.commission,
                'slippage_cost': t.slippage_cost,
                'total_cost': t.total_cost,
                'trade_type': t.trade_type,
                'note': t.note
            }
            for t in self.trades
        ])

    def get_nav_df(self) -> pd.DataFrame:
        """获取净值序列DataFrame"""
        if not self.nav_history:
            return pd.DataFrame()
        return pd.DataFrame(self.nav_history)

    def get_summary(self) -> Dict:
        """获取模拟结果摘要"""
        nav_df = self.get_nav_df()
        trades_df = self.get_trades_df()

        if nav_df.empty:
            return {}

        final_nav = nav_df['nav'].iloc[-1]
        total_return = (final_nav / self.initial_cash - 1) * 100

        # 计算年化收益（假设一年252个交易日）
        trading_days = len(nav_df)
        annualized_return = total_return * (252 / trading_days) if trading_days > 0 else 0

        # 计算最大回撤
        nav_series = nav_df['nav']
        rolling_max = nav_series.expanding().max()
        drawdown = (nav_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()

        # 计算夏普比率
        daily_returns = nav_series.pct_change().dropna()
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        else:
            sharpe = 0

        # 统计交易
        rotation_trades = trades_df[trades_df['trade_type'] == 'rotation'] if not trades_df.empty else pd.DataFrame()
        signal_trades = trades_df[trades_df['trade_type'] == 'signal'] if not trades_df.empty else pd.DataFrame()

        total_rotation_cost = rotation_trades['total_cost'].sum() if not rotation_trades.empty else 0
        total_signal_cost = signal_trades['total_cost'].sum() if not signal_trades.empty else 0

        return {
            'initial_cash': self.initial_cash,
            'final_nav': final_nav,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'total_trades': len(trades_df),
            'rotation_trades': len(rotation_trades),
            'signal_trades': len(signal_trades),
            'total_rotation_cost': total_rotation_cost,
            'total_signal_cost': total_signal_cost,
            'total_cost': total_rotation_cost + total_signal_cost,
            'trading_days': trading_days
        }
