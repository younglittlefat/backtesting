#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号生成器核心模块

包含 SignalGenerator 类，负责生成交易信号。
"""

import warnings
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd

from .config import COST_MODELS, DEFAULT_LOOKBACK_DAYS
from .detectors import MacdSignalDetector, SmaSignalDetector, KamaSignalDetector


class SignalGenerator:
    """交易信号生成器"""

    def __init__(self,
                 strategy_class,
                 strategy_params: Dict = None,
                 cash: float = 100000,
                 cost_model: str = 'cn_etf',
                 data_dir: str = 'data/csv/daily',
                 lookback_days: int = 250,
                 use_dual_price: bool = True,
                 max_position_pct: float = 0.05,
                 min_buy_signals: int = 1,
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None):
        """
        初始化信号生成器

        Args:
            strategy_class: 策略类
            strategy_params: 策略参数字典
            cash: 可用资金
            cost_model: 费用模型
            data_dir: 数据目录
            lookback_days: 回看天数（用于计算指标）
            use_dual_price: 是否使用双价格模式
            max_position_pct: 单仓位上限（默认0.05，即5%）
            min_buy_signals: 最小买入信号数（默认1）
            start_date: 起始日期（可选，格式: YYYY-MM-DD）
            end_date: 截止日期（可选，格式: YYYY-MM-DD）
        """
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.cash = cash
        self.cost_model = cost_model
        self.data_dir = data_dir
        self.lookback_days = lookback_days
        self.use_dual_price = use_dual_price
        self.max_position_pct = max_position_pct
        self.min_buy_signals = min_buy_signals

        # 获取费用配置
        if cost_model not in COST_MODELS:
            raise ValueError(f"未知的费用模型: {cost_model}。可用选项: {list(COST_MODELS.keys())}")

        cost_config = COST_MODELS[cost_model]
        self.commission = cost_config['commission']
        self.spread = cost_config.get('spread', 0.0)

        # 计算日期范围
        self.end_date, self.start_date = self._calculate_date_range(
            start_date, end_date, lookback_days
        )

        # 追踪最新价格日期
        self.latest_price_date = None
        self.lookback_start_date = None

        # 初始化信号检测器
        self._init_detectors()

    def _calculate_date_range(self, start_date: Optional[str], end_date: Optional[str],
                               lookback_days: int) -> Tuple[str, str]:
        """计算日期范围"""
        # 处理 end_date
        if end_date:
            if len(end_date) == 8 and end_date.isdigit():
                end_date_str = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            else:
                end_date_str = end_date
        else:
            end_date_str = datetime.now().strftime('%Y-%m-%d')

        # 处理 start_date
        if start_date:
            if len(start_date) == 8 and start_date.isdigit():
                start_date_str = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            else:
                start_date_str = start_date
        elif lookback_days > 0:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=lookback_days * 2)
            start_date_str = start_dt.strftime('%Y-%m-%d')
        else:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=500)
            start_date_str = start_dt.strftime('%Y-%m-%d')

        return end_date_str, start_date_str

    def _init_detectors(self):
        """初始化信号检测器"""
        self.macd_detector = MacdSignalDetector(self.strategy_params)
        self.sma_detector = SmaSignalDetector(self.strategy_params)
        self.kama_detector = KamaSignalDetector(self.strategy_params)

    def load_instrument_data(self, ts_code: str) -> Optional[pd.DataFrame]:
        """
        加载标的数据

        Args:
            ts_code: 标的代码

        Returns:
            OHLCV DataFrame 或 None
        """
        # 延迟导入，避免循环依赖
        from utils.data_loader import load_chinese_ohlcv_data

        try:
            # 构造数据文件路径 - 尝试多个可能的位置
            data_dir = Path(self.data_dir)
            possible_paths = [
                data_dir / f"{ts_code}.csv",
                data_dir / "etf" / f"{ts_code}.csv",
                data_dir / "fund" / f"{ts_code}.csv",
                data_dir / "stock" / f"{ts_code}.csv",
            ]

            data_file = None
            for path in possible_paths:
                if path.exists():
                    data_file = path
                    break

            if data_file is None:
                warnings.warn(f"{ts_code}: 数据文件不存在")
                return None

            # 使用utils.data_loader加载数据
            df = load_chinese_ohlcv_data(
                data_file,
                start_date=self.start_date,
                end_date=self.end_date,
                verbose=False
            )

            if df is None or len(df) < 30:
                return None

            # 追踪最新价格日期
            if self.latest_price_date is None and len(df) > 0:
                if hasattr(df.index, 'date'):
                    self.latest_price_date = str(df.index[-1].date())
                else:
                    self.latest_price_date = str(df.index[-1])

            # 只保留最近的lookback_days天数据
            df = df.tail(self.lookback_days)

            # 追踪lookback窗口的起始日期
            if self.lookback_start_date is None and len(df) > 0:
                if hasattr(df.index, 'date'):
                    self.lookback_start_date = str(df.index[0].date())
                else:
                    self.lookback_start_date = str(df.index[0])

            return df

        except Exception as e:
            warnings.warn(f"{ts_code}: 加载数据失败 - {e}")
            return None

    def get_signal(self, ts_code: str) -> Dict:
        """
        获取标的信号（根据use_dual_price自动选择方法）

        Args:
            ts_code: 标的代码

        Returns:
            信号字典
        """
        if self.use_dual_price:
            return self.get_current_signal_dual_price(ts_code)
        else:
            return self.get_current_signal(ts_code)

    def get_current_signal(self, ts_code: str) -> Dict:
        """
        获取标的当前的交易信号（单价格模式）

        Args:
            ts_code: 标的代码

        Returns:
            信号字典
        """
        # 延迟导入
        from backtesting import Backtest

        result = {
            'ts_code': ts_code,
            'signal': 'ERROR',
            'price': 0,
            'sma_short': 0,
            'sma_long': 0,
            'signal_strength': 0,
            'message': ''
        }

        # 加载数据
        df = self.load_instrument_data(ts_code)
        if df is None:
            result['message'] = '数据不足或加载失败'
            return result

        try:
            # 运行回测以获取策略状态
            bt = Backtest(
                df,
                self.strategy_class,
                cash=self.cash,
                commission=self.commission,
                exclusive_orders=True
            )

            if self.strategy_params:
                stats = bt.run(**self.strategy_params)
            else:
                stats = bt.run()

            strategy = stats._strategy
            current_price = df['Close'].iloc[-1]
            result['price'] = current_price

            # 检测策略类型并调用相应的检测器
            result = self._detect_signal_by_strategy_type(strategy, result, df)

        except Exception as e:
            result['message'] = f'策略运行失败: {e}'
            import traceback
            warnings.warn(f"详细错误信息:\n{traceback.format_exc()}")

        return result

    def get_current_signal_dual_price(self, ts_code: str) -> Dict:
        """
        获取标的当前的交易信号（双价格模式）

        使用复权价格计算信号，同时返回原始价格用于交易

        Args:
            ts_code: 标的代码

        Returns:
            信号字典
        """
        # 延迟导入
        from backtesting import Backtest
        from utils.data_loader import load_dual_price_data

        result = {
            'ts_code': ts_code,
            'signal': 'ERROR',
            'adj_price': 0,
            'real_price': 0,
            'price': 0,
            'adj_factor': 1.0,
            'sma_short': 0,
            'sma_long': 0,
            'signal_strength': 0,
            'message': ''
        }

        try:
            csv_path = self._get_csv_path(ts_code)
            if not csv_path.exists():
                result['message'] = f'数据文件不存在: {csv_path}'
                return result

            adj_df, real_df, price_mapping = load_dual_price_data(
                csv_path,
                verbose=False,
                start_date=self.start_date,
                end_date=self.end_date
            )

            # 追踪日期
            self._update_date_tracking(adj_df)

            # 检查数据是否充足
            min_data_points = self._get_min_data_points()
            if len(adj_df) < min_data_points:
                result['message'] = '数据点不足，无法计算指标'
                return result

            # 使用复权价格运行回测
            bt = Backtest(
                adj_df,
                self.strategy_class,
                cash=self.cash,
                commission=self.commission,
                exclusive_orders=True
            )

            if self.strategy_params:
                stats = bt.run(**self.strategy_params)
            else:
                stats = bt.run()

            strategy = stats._strategy

            # 设置价格信息
            result['adj_price'] = price_mapping['latest_adj_price']
            result['real_price'] = price_mapping['latest_real_price']
            result['price'] = price_mapping['latest_real_price']
            result['adj_factor'] = price_mapping['adj_factor']

            # 检测信号
            result = self._detect_signal_by_strategy_type(strategy, result, adj_df)

        except Exception as e:
            result['message'] = f'双价格策略运行失败: {e}'

        return result

    def _detect_signal_by_strategy_type(self, strategy, result: Dict, df: pd.DataFrame) -> Dict:
        """
        根据策略类型检测信号

        Args:
            strategy: 策略实例
            result: 结果字典
            df: 价格数据

        Returns:
            更新后的结果字典
        """
        if hasattr(strategy, 'macd_line') and hasattr(strategy, 'signal_line'):
            return self.macd_detector.detect_signal(strategy, result)
        elif hasattr(strategy, 'sma1') and hasattr(strategy, 'sma2'):
            return self.sma_detector.detect_signal(strategy, result)
        elif hasattr(strategy, 'kama'):
            return self.kama_detector.detect_signal(strategy, result, df)
        else:
            result['message'] = f'不支持的策略类型: {self.strategy_class.__name__}'
            return result

    def _get_csv_path(self, ts_code: str) -> Path:
        """根据股票代码构造CSV文件路径"""
        csv_path = Path(self.data_dir) / 'etf' / f'{ts_code}.csv'
        if csv_path.exists():
            return csv_path

        for subdir in ['fund', 'stock', '']:
            csv_path = Path(self.data_dir) / subdir / f'{ts_code}.csv'
            if csv_path.exists():
                return csv_path

        return Path(self.data_dir) / 'etf' / f'{ts_code}.csv'

    def _get_min_data_points(self) -> int:
        """获取最小数据点数"""
        min_data_points = 50
        if hasattr(self.strategy_class, 'slow_period'):
            min_data_points = self.strategy_params.get('slow_period', 26) + 10
        elif 'n2' in self.strategy_params:
            min_data_points = max(
                self.strategy_params.get('n1', 10),
                self.strategy_params.get('n2', 20)
            ) + 10
        return min_data_points

    def _update_date_tracking(self, df: pd.DataFrame):
        """更新日期追踪"""
        if self.latest_price_date is None and len(df) > 0:
            if hasattr(df.index, 'date'):
                self.latest_price_date = str(df.index[-1].date())
            else:
                self.latest_price_date = str(df.index[-1])

        if self.lookback_start_date is None and len(df) > 0:
            if hasattr(df.index, 'date'):
                self.lookback_start_date = str(df.index[0].date())
            else:
                self.lookback_start_date = str(df.index[0])

    def generate_signals_for_pool(self,
                                  stock_list_file: str,
                                  target_positions: int = 10) -> Tuple[pd.DataFrame, Dict]:
        """
        为股票池生成交易信号

        Args:
            stock_list_file: 股票列表CSV文件
            target_positions: 目标持仓数量

        Returns:
            (signals_df, allocation_dict)
        """
        stock_df = pd.read_csv(stock_list_file)
        if 'ts_code' not in stock_df.columns:
            raise ValueError(f"股票列表文件缺少 'ts_code' 列: {stock_list_file}")

        ts_codes = stock_df['ts_code'].tolist()

        print(f"开始分析 {len(ts_codes)} 只标的...")
        print("=" * 80)

        signals = []
        for i, ts_code in enumerate(ts_codes, 1):
            print(f"[{i}/{len(ts_codes)}] 分析 {ts_code}...", end=' ')
            signal = self.get_signal(ts_code)
            signals.append(signal)
            print(f"{signal['signal']}")

        signals_df = pd.DataFrame(signals)
        allocation = self._calculate_allocation(signals_df, target_positions)

        return signals_df, allocation

    def _calculate_allocation(self,
                             signals_df: pd.DataFrame,
                             target_positions: int) -> Dict:
        """
        计算资金分配方案

        Args:
            signals_df: 信号DataFrame
            target_positions: 目标持仓数量

        Returns:
            资金分配字典
        """
        buy_signals = signals_df[signals_df['signal'] == 'BUY'].copy()

        if len(buy_signals) == 0:
            return {
                'total_cash': self.cash,
                'positions': [],
                'message': '当前没有买入信号'
            }

        if len(buy_signals) < self.min_buy_signals:
            return {
                'total_cash': self.cash,
                'allocated_cash': 0,
                'remaining_cash': self.cash,
                'n_positions': 0,
                'positions': [],
                'message': f'买入信号数量不足（{len(buy_signals)} < {self.min_buy_signals}），本次不执行买入'
            }

        buy_signals['abs_strength'] = buy_signals['signal_strength'].abs()
        buy_signals = buy_signals.sort_values('abs_strength', ascending=False)
        buy_signals = buy_signals.head(target_positions)

        n_positions = len(buy_signals)
        max_cash_per_position = self.cash * self.max_position_pct
        cash_per_position = min(self.cash / n_positions, max_cash_per_position)

        positions = []
        for _, row in buy_signals.iterrows():
            price = row['price']
            effective_cash = cash_per_position * (1 - self.commission - self.spread)
            shares = int(effective_cash / price / 100) * 100

            if shares > 0:
                cost = shares * price * (1 + self.commission + self.spread)
                positions.append({
                    'ts_code': row['ts_code'],
                    'price': price,
                    'shares': shares,
                    'cost': cost,
                    'weight': cost / self.cash * 100,
                    'signal_strength': row['signal_strength'],
                    'message': row['message']
                })

        total_cost = sum(p['cost'] for p in positions)
        remaining_cash = self.cash - total_cost

        return {
            'total_cash': self.cash,
            'allocated_cash': total_cost,
            'remaining_cash': remaining_cash,
            'n_positions': len(positions),
            'positions': positions
        }
