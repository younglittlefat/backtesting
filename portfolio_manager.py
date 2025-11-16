#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
持仓管理模块

管理交易持仓状态、执行增量交易决策、记录交易历史。
支持端到端的持续交易工作流。

作者: Claude Code
日期: 2025-11-07
"""

import json
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from utils.data_loader import load_chinese_ohlcv_data


@dataclass
class Position:
    """持仓信息"""
    ts_code: str           # 股票代码
    shares: int            # 持有股数
    entry_price: float     # 买入均价
    entry_date: str        # 建仓日期
    cost: float            # 持仓成本（含手续费）

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        """从字典创建"""
        return cls(**data)


@dataclass
class Trade:
    """交易记录"""
    ts_code: str           # 股票代码
    action: str            # 'BUY' 或 'SELL'
    shares: int            # 股数
    price: float           # 成交价格
    amount: float          # 交易金额（买入为负，卖出为正）
    commission: float      # 手续费
    date: str              # 交易日期
    reason: str            # 交易原因

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Trade':
        """从字典创建"""
        return cls(**data)


class Portfolio:
    """投资组合管理器"""

    def __init__(self,
                 cash: float = 0.0,
                 positions: Optional[List[Position]] = None,
                 portfolio_file: Optional[str] = None):
        """
        初始化投资组合

        Args:
            cash: 初始现金
            positions: 初始持仓列表
            portfolio_file: 持仓文件路径
        """
        self.cash = cash
        self.positions = positions or []
        self.portfolio_file = portfolio_file
        self.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_position(self, ts_code: str) -> Optional[Position]:
        """
        获取指定标的的持仓

        Args:
            ts_code: 股票代码

        Returns:
            Position对象或None
        """
        for pos in self.positions:
            if pos.ts_code == ts_code:
                return pos
        return None

    def has_position(self, ts_code: str) -> bool:
        """
        检查是否持有某标的

        Args:
            ts_code: 股票代码

        Returns:
            是否持有
        """
        return self.get_position(ts_code) is not None

    def add_position(self, position: Position):
        """
        添加持仓

        Args:
            position: 持仓对象
        """
        # 检查是否已存在
        existing = self.get_position(position.ts_code)
        if existing:
            # 合并持仓（加权平均成本）
            total_shares = existing.shares + position.shares
            total_cost = existing.cost + position.cost
            existing.shares = total_shares
            existing.cost = total_cost
            existing.entry_price = total_cost / total_shares if total_shares > 0 else 0
            existing.entry_date = position.entry_date  # 更新为最新日期
        else:
            self.positions.append(position)

    def remove_position(self, ts_code: str) -> Optional[Position]:
        """
        移除持仓

        Args:
            ts_code: 股票代码

        Returns:
            被移除的持仓对象
        """
        for i, pos in enumerate(self.positions):
            if pos.ts_code == ts_code:
                return self.positions.pop(i)
        return None

    def get_total_market_value(self, current_prices: Dict[str, float]) -> float:
        """
        计算持仓市值

        Args:
            current_prices: 当前价格字典 {ts_code: price}

        Returns:
            总市值
        """
        total_value = 0.0
        for pos in self.positions:
            price = current_prices.get(pos.ts_code, pos.entry_price)
            total_value += pos.shares * price
        return total_value

    def get_total_cost(self) -> float:
        """
        计算持仓总成本

        Returns:
            总成本
        """
        return sum(pos.cost for pos in self.positions)

    def get_total_pnl(self, current_prices: Dict[str, float]) -> float:
        """
        计算持仓盈亏

        Args:
            current_prices: 当前价格字典 {ts_code: price}

        Returns:
            总盈亏
        """
        market_value = self.get_total_market_value(current_prices)
        total_cost = self.get_total_cost()
        return market_value - total_cost

    def get_position_count(self) -> int:
        """
        获取持仓数量

        Returns:
            持仓数量
        """
        return len(self.positions)

    def to_dict(self) -> Dict:
        """
        转换为字典（用于JSON序列化）

        Returns:
            字典格式的持仓数据
        """
        return {
            'cash': self.cash,
            'positions': [pos.to_dict() for pos in self.positions],
            'last_update': self.last_update
        }

    @classmethod
    def from_dict(cls, data: Dict, portfolio_file: Optional[str] = None) -> 'Portfolio':
        """
        从字典创建Portfolio对象

        Args:
            data: 字典数据
            portfolio_file: 持仓文件路径

        Returns:
            Portfolio对象
        """
        positions = [Position.from_dict(p) for p in data.get('positions', [])]
        portfolio = cls(
            cash=data.get('cash', 0.0),
            positions=positions,
            portfolio_file=portfolio_file
        )
        portfolio.last_update = data.get('last_update', portfolio.last_update)
        return portfolio

    def save(self, filepath: Optional[str] = None):
        """
        保存持仓到文件

        Args:
            filepath: 文件路径（如果为None，使用self.portfolio_file）
        """
        filepath = filepath or self.portfolio_file
        if not filepath:
            raise ValueError("必须指定保存路径")

        # 更新时间戳
        self.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 确保目录存在
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # 保存JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> 'Portfolio':
        """
        从文件加载持仓

        Args:
            filepath: 文件路径

        Returns:
            Portfolio对象
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"持仓文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return cls.from_dict(data, portfolio_file=filepath)

    @classmethod
    def initialize(cls, initial_cash: float, filepath: str) -> 'Portfolio':
        """
        初始化新的投资组合

        Args:
            initial_cash: 初始资金
            filepath: 保存路径

        Returns:
            Portfolio对象
        """
        portfolio = cls(cash=initial_cash, portfolio_file=filepath)
        portfolio.save()
        return portfolio


class TradeLogger:
    """交易日志记录器"""

    def __init__(self, history_dir: str = 'positions/history'):
        """
        初始化交易日志记录器

        Args:
            history_dir: 历史记录目录
        """
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def log_trades(self, trades: List[Trade], date: Optional[str] = None, portfolio_name: Optional[str] = None):
        """
        记录交易

        Args:
            trades: 交易列表
            date: 日期字符串（YYYYMMDD），如果为None则使用当天
            portfolio_name: 可选，持仓配置名称（用于区分不同策略/组合）
        """
        if not trades:
            return

        date = date or datetime.now().strftime('%Y%m%d')
        # 文件名中加入持仓配置名（若提供）
        if portfolio_name:
            safe_name = portfolio_name.replace('/', '_')
            filename = f"trades_{safe_name}_{date}.json"
        else:
            filename = f"trades_{date}.json"
        filepath = self.history_dir / filename

        # 转换为字典列表
        trades_data = [trade.to_dict() for trade in trades]

        # 保存
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'date': date,
                'trades': trades_data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }, f, ensure_ascii=False, indent=2)

    def get_trades(self, date: str, portfolio_name: Optional[str] = None) -> List[Trade]:
        """
        获取指定日期的交易记录

        Args:
            date: 日期字符串（YYYYMMDD）
            portfolio_name: 可选，持仓配置名称

        Returns:
            交易列表
        """
        # 优先匹配带 portfolio_name 的文件
        candidates: List[Path] = []
        if portfolio_name:
            candidates.append(self.history_dir / f"trades_{portfolio_name}_{date}.json")
        # 兼容旧命名（无 portfolio_name）
        candidates.append(self.history_dir / f"trades_{date}.json")

        filepath: Optional[Path] = None
        for p in candidates:
            if p.exists():
                filepath = p
                break
        if filepath is None:
            # 回退到通配查找（取第一个匹配）
            matches = list(self.history_dir.glob(f"trades_*_{date}.json"))
            if matches:
                filepath = matches[0]
            else:
                return []

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return [Trade.from_dict(t) for t in data.get('trades', [])]


class PortfolioTrader:
    """持仓交易决策引擎"""

    def __init__(self,
                 portfolio: Portfolio,
                 commission: float = 0.0001,
                 spread: float = 0.0001,
                 max_positions: int = 10,
                 max_position_pct: float = 0.05,
                 min_buy_signals: int = 1,
                 trade_date: Optional[str] = None,
                 *,
                 min_hold_bars: int = 0,
                 data_dir: Optional[str] = None):
        """
        初始化交易引擎

        Args:
            portfolio: 投资组合对象
            commission: 佣金率
            spread: 滑点率
            max_positions: 最大持仓数
            max_position_pct: 单仓位上限（默认0.05，即5%）
            min_buy_signals: 最小买入信号数（默认1）
            trade_date: 交易日期（YYYY-MM-DD）。不指定则使用当前日期
        """
        self.portfolio = portfolio
        self.commission = commission
        self.spread = spread
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.min_buy_signals = min_buy_signals
        # 如果传入交易日则全流程使用该日期（与 --end-date 对齐）
        self.trade_date = trade_date
        # Anti-Whipsaw: 最短持有期与数据目录
        self.min_hold_bars = int(min_hold_bars or 0)
        self.data_dir = data_dir or 'data/csv/daily'

    def _resolve_csv_path(self, ts_code: str) -> Path:
        """根据数据目录推测CSV位置"""
        base = Path(self.data_dir)
        candidates = [
            base / 'etf' / f'{ts_code}.csv',
            base / 'fund' / f'{ts_code}.csv',
            base / 'stock' / f'{ts_code}.csv',
            base / f'{ts_code}.csv',
        ]
        for p in candidates:
            if p.exists():
                return p
        return candidates[0]

    def _count_bars_since(self, ts_code: str, start_date: str, end_date: Optional[str] = None) -> Optional[int]:
        """
        计算从 start_date 到 end_date（含）之间的交易bar数量。
        返回 None 代表无法计算（数据缺失等）。
        """
        try:
            csv_path = self._resolve_csv_path(ts_code)
            df = load_chinese_ohlcv_data(
                csv_path,
                start_date=start_date,
                end_date=end_date or self.trade_date,
                verbose=False
            )
            if df is None or len(df) == 0:
                return None
            # 包含起止两端
            return int(len(df))
        except Exception:
            return None

    def generate_trade_plan(self,
                           signals: Dict[str, Dict]) -> Tuple[List[Trade], List[Trade]]:
        """
        根据信号生成交易计划

        Args:
            signals: 信号字典 {ts_code: {'signal': 'BUY/SELL/HOLD', 'price': ..., ...}}

        Returns:
            (sell_trades, buy_trades) 卖出和买入交易列表
        """
        sell_trades = []
        buy_trades = []

        # 统一使用指定交易日（若未指定则为“今天”）
        today = self.trade_date or datetime.now().strftime('%Y-%m-%d')

        # 第一步：处理卖出（优先）
        for position in self.portfolio.positions:
            ts_code = position.ts_code
            signal_data = signals.get(ts_code)

            if signal_data and signal_data['signal'] == 'SELL':
                # Anti-Whipsaw: 最短持有期保护
                if self.min_hold_bars > 0 and position.entry_date:
                    bars = self._count_bars_since(ts_code, position.entry_date, today)
                    if bars is not None and bars < self.min_hold_bars:
                        # 忽略该卖出（保护期内）
                        print(f"[过滤] 最短持有期: {ts_code} 已持有{bars}<{self.min_hold_bars} 根，忽略本次卖出")
                        continue

                # 生成卖出交易
                price = signal_data['price']
                shares = position.shares

                # 计算收入（扣除手续费）
                gross_amount = shares * price
                commission_fee = gross_amount * self.commission
                net_amount = gross_amount - commission_fee

                trade = Trade(
                    ts_code=ts_code,
                    action='SELL',
                    shares=shares,
                    price=price,
                    amount=net_amount,
                    commission=commission_fee,
                    date=today,
                    reason=signal_data.get('message', '死叉卖出信号')
                )
                sell_trades.append(trade)

        # 第二步：计算可用资金
        # 当前现金 + 卖出后的收入
        available_cash = self.portfolio.cash
        for trade in sell_trades:
            available_cash += trade.amount

        # 第三步：计算可用持仓槽位
        current_positions = self.portfolio.get_position_count()
        positions_to_remove = len(sell_trades)
        available_slots = self.max_positions - (current_positions - positions_to_remove)

        if available_slots <= 0:
            return sell_trades, buy_trades

        # 第四步：筛选买入候选（不在当前持仓中的BUY信号）
        buy_candidates = []
        for ts_code, signal_data in signals.items():
            if signal_data['signal'] == 'BUY' and not self.portfolio.has_position(ts_code):
                buy_candidates.append({
                    'ts_code': ts_code,
                    'price': signal_data['price'],
                    'signal_strength': signal_data.get('signal_strength', 0),
                    'message': signal_data.get('message', '金叉买入信号')
                })

        # 检查最小买入信号数
        if len(buy_candidates) < self.min_buy_signals:
            print(f"\n⚠️  买入信号数量（{len(buy_candidates)}）少于最小要求（{self.min_buy_signals}），本次不执行买入")
            print(f"   等待更多买入信号出现...")
            return sell_trades, []  # 返回空的买入交易列表

        # 按信号强度排序，取前N个
        buy_candidates = sorted(
            buy_candidates,
            key=lambda x: abs(x['signal_strength']),
            reverse=True
        )[:available_slots]

        # 第五步：分配资金，生成买入交易（带单仓位上限）
        if buy_candidates and available_cash > 0:
            # 计算总资产（现金 + 持仓成本）
            total_capital = self.portfolio.cash + self.portfolio.get_total_cost()
            max_cash_per_position = total_capital * self.max_position_pct  # 单仓位上限金额
            cash_per_position = min(available_cash / len(buy_candidates), max_cash_per_position)

            for candidate in buy_candidates:
                price = candidate['price']

                # 考虑手续费和滑点后的有效资金
                effective_cash = cash_per_position * (1 - self.commission - self.spread)

                # 计算股数（向下取整到100股倍数）
                shares = int(effective_cash / price / 100) * 100

                if shares > 0:
                    # 计算实际成本（含手续费和滑点）
                    gross_cost = shares * price
                    commission_fee = gross_cost * self.commission
                    slippage_cost = gross_cost * self.spread
                    total_cost = gross_cost + commission_fee + slippage_cost

                    trade = Trade(
                        ts_code=candidate['ts_code'],
                        action='BUY',
                        shares=shares,
                        price=price,
                        amount=-total_cost,  # 买入为负
                        commission=commission_fee,
                        date=today,
                        reason=candidate['message']
                    )
                    buy_trades.append(trade)

        return sell_trades, buy_trades

    def execute_trades(self,
                      sell_trades: List[Trade],
                      buy_trades: List[Trade],
                      dry_run: bool = False) -> bool:
        """
        执行交易计划

        Args:
            sell_trades: 卖出交易列表
            buy_trades: 买入交易列表
            dry_run: 是否为模拟运行（不实际修改持仓）

        Returns:
            是否成功执行
        """
        if dry_run:
            return True

        # 统一使用指定交易日（若未指定则为“今天”）
        today = self.trade_date or datetime.now().strftime('%Y-%m-%d')

        # 执行卖出
        for trade in sell_trades:
            position = self.portfolio.remove_position(trade.ts_code)
            if position:
                self.portfolio.cash += trade.amount

        # 执行买入
        for trade in buy_trades:
            # 检查现金是否足够
            if self.portfolio.cash < abs(trade.amount):
                warnings.warn(f"现金不足，无法买入 {trade.ts_code}")
                continue

            # 扣除现金
            self.portfolio.cash += trade.amount  # amount是负数

            # 添加持仓
            position = Position(
                ts_code=trade.ts_code,
                shares=trade.shares,
                entry_price=trade.price,
                entry_date=today,
                cost=abs(trade.amount)
            )
            self.portfolio.add_position(position)

        # 更新时间戳
        self.portfolio.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return True
