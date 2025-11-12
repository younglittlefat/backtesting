#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实盘交易信号生成器

每天收盘后运行，分析股票池中的所有标的，生成买入/卖出信号。
适用于双均线策略等技术指标策略。

作者: Claude Code
日期: 2025-11-07
"""

import os
import sys
import warnings
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# 禁用进度条输出（在导入backtesting之前设置）
os.environ['BACKTESTING_DISABLE_PROGRESS'] = 'true'

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting import Backtest
from backtesting.lib import crossover
from utils.data_loader import load_chinese_ohlcv_data, load_dual_price_data
from utils.strategy_params_manager import StrategyParamsManager
from portfolio_manager import Portfolio, PortfolioTrader, TradeLogger, Trade

# 过滤掉关于未平仓交易的UserWarning
warnings.filterwarnings('ignore', message='.*Some trades remain open.*')
warnings.filterwarnings('ignore', category=UserWarning, module='backtesting')


# 费用模型配置
COST_MODELS = {
    'default': {'commission': 0.0, 'spread': 0.0},
    'cn_etf': {'commission': 0.0001, 'spread': 0.0001},
    'cn_stock': {'commission': 0.0003, 'spread': 0.001},
    'us_stock': {'commission': 0.001, 'spread': 0.0005},
}


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
        # 优先使用自定义日期，如果没有则使用lookback_days计算
        # 日期格式支持 YYYYMMDD
        if end_date:
            # 转换 YYYYMMDD 格式到 YYYY-MM-DD
            if len(end_date) == 8 and end_date.isdigit():
                self.end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            else:
                self.end_date = end_date
        else:
            self.end_date = datetime.now().strftime('%Y-%m-%d')

        if start_date:
            # 转换 YYYYMMDD 格式到 YYYY-MM-DD
            if len(start_date) == 8 and start_date.isdigit():
                self.start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            else:
                self.start_date = start_date
        elif lookback_days > 0:
            # 使用end_date计算start_date
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=lookback_days * 2)  # 预留更多天数以防节假日
            self.start_date = start_dt.strftime('%Y-%m-%d')
        else:
            # 默认使用250个交易日（约1年）
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=500)
            self.start_date = start_dt.strftime('%Y-%m-%d')

        # 追踪最新价格日期
        self.latest_price_date = None
        self.lookback_start_date = None

    def load_instrument_data(self, ts_code: str) -> Optional[pd.DataFrame]:
        """
        加载标的数据

        Args:
            ts_code: 标的代码

        Returns:
            OHLCV DataFrame 或 None
        """
        try:
            # 构造数据文件路径 - 尝试多个可能的位置
            data_dir = Path(self.data_dir)
            possible_paths = [
                data_dir / f"{ts_code}.csv",  # 直接在data_dir下
                data_dir / "etf" / f"{ts_code}.csv",  # data_dir/etf子目录
                data_dir / "fund" / f"{ts_code}.csv",  # data_dir/fund子目录
                data_dir / "stock" / f"{ts_code}.csv",  # data_dir/stock子目录
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
            df = load_chinese_ohlcv_data(data_file, verbose=False)

            if df is None or len(df) < 30:
                return None

            # 追踪最新价格日期（来自完整数据）
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

    def get_current_signal(self, ts_code: str) -> Dict:
        """
        获取标的当前的交易信号

        Args:
            ts_code: 标的代码

        Returns:
            信号字典，包含：
            - signal: 'BUY', 'SELL', 'HOLD', 'ERROR'
            - price: 当前价格
            - sma_short: 短期均线值
            - sma_long: 长期均线值
            - signal_strength: 信号强度（均线差值百分比）
            - message: 说明信息
        """
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

            # 设置策略参数
            if self.strategy_params:
                stats = bt.run(**self.strategy_params)
            else:
                stats = bt.run()

            # 获取策略实例
            strategy = stats._strategy
            current_price = df['Close'].iloc[-1]
            result['price'] = current_price

            # 检测策略类型并获取相应的指标
            if hasattr(strategy, 'macd_line') and hasattr(strategy, 'signal_line'):
                # MACD策略
                macd_line = strategy.macd_line[-1]
                signal_line = strategy.signal_line[-1]
                macd_line_prev = strategy.macd_line[-2] if len(strategy.macd_line) > 1 else macd_line
                signal_line_prev = strategy.signal_line[-2] if len(strategy.signal_line) > 1 else signal_line

                result['sma_short'] = macd_line  # 兼容性：用macd_line代替
                result['sma_long'] = signal_line  # 兼容性：用signal_line代替

                # 计算信号强度
                signal_strength = macd_line - signal_line  # MACD柱状图值
                result['signal_strength'] = signal_strength

                # 判断信号
                # 金叉：MACD线从下方穿过信号线
                if macd_line_prev <= signal_line_prev and macd_line > signal_line:
                    result['signal'] = 'BUY'
                    fast = getattr(strategy, 'fast_period', 12)
                    slow = getattr(strategy, 'slow_period', 26)
                    sig = getattr(strategy, 'signal_period', 9)
                    result['message'] = f'MACD金叉买入信号！MACD({fast},{slow},{sig})线上穿信号线'
                # 死叉：MACD线从上方穿过信号线
                elif macd_line_prev >= signal_line_prev and macd_line < signal_line:
                    result['signal'] = 'SELL'
                    fast = getattr(strategy, 'fast_period', 12)
                    slow = getattr(strategy, 'slow_period', 26)
                    sig = getattr(strategy, 'signal_period', 9)
                    result['message'] = f'MACD死叉卖出信号！MACD({fast},{slow},{sig})线下穿信号线'
                # 持有状态
                elif macd_line > signal_line:
                    result['signal'] = 'HOLD_LONG'
                    result['message'] = f'持有多头。MACD线在信号线上方（柱状图: {signal_strength:.4f}）'
                else:
                    result['signal'] = 'HOLD_SHORT'
                    result['message'] = f'持有空头。MACD线在信号线下方（柱状图: {signal_strength:.4f}）'

            elif hasattr(strategy, 'sma1') and hasattr(strategy, 'sma2'):
                # SMA策略
                sma_short = strategy.sma1[-1]
                sma_long = strategy.sma2[-1]

                # 获取前一天的指标值（用于检测交叉）
                sma_short_prev = strategy.sma1[-2] if len(strategy.sma1) > 1 else sma_short
                sma_long_prev = strategy.sma2[-2] if len(strategy.sma2) > 1 else sma_long

                result['sma_short'] = sma_short
                result['sma_long'] = sma_long

                # 计算信号强度（均线差值的百分比）
                signal_strength = ((sma_short - sma_long) / sma_long) * 100
                result['signal_strength'] = signal_strength

                # 判断信号
                # 金叉：短期均线从下方穿过长期均线
                if sma_short_prev <= sma_long_prev and sma_short > sma_long:
                    result['signal'] = 'BUY'
                    result['message'] = f'金叉买入信号！短期均线({strategy.n1}日)上穿长期均线({strategy.n2}日)'
                # 死叉：短期均线从上方穿过长期均线
                elif sma_short_prev >= sma_long_prev and sma_short < sma_long:
                    result['signal'] = 'SELL'
                    result['message'] = f'死叉卖出信号！短期均线({strategy.n1}日)下穿长期均线({strategy.n2}日)'
                # 持有状态
                elif sma_short > sma_long:
                    result['signal'] = 'HOLD_LONG'
                    result['message'] = f'持有多头。短期均线在长期均线上方（{signal_strength:.2f}%）'
                else:
                    result['signal'] = 'HOLD_SHORT'
                    result['message'] = f'持有空头。短期均线在长期均线下方（{signal_strength:.2f}%）'
            else:
                # 未知策略类型
                result['message'] = f'不支持的策略类型: {self.strategy_class.__name__}'

        except Exception as e:
            result['message'] = f'策略运行失败: {e}'
            import traceback
            warnings.warn(f"详细错误信息:\n{traceback.format_exc()}")

        return result

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

    def get_current_signal_dual_price(self, ts_code: str) -> Dict:
        """
        获取标的当前的交易信号（双价格模式）

        使用复权价格计算信号，同时返回原始价格用于交易

        Args:
            ts_code: 标的代码

        Returns:
            信号字典，包含：
            - signal: 'BUY', 'SELL', 'HOLD', 'ERROR'
            - adj_price: 复权价格（用于信号计算）
            - real_price: 原始价格（用于实际交易）
            - price: 兼容性价格（为原始price, 等于real_price）
            - adj_factor: 复权因子
            - sma_short: 短期均线值
            - sma_long: 长期均线值
            - signal_strength: 信号强度（均线差值百分比）
            - message: 说明信息
        """
        result = {
            'ts_code': ts_code,
            'signal': 'ERROR',
            'adj_price': 0,      # 复权价格（用于信号）
            'real_price': 0,     # 原始价格（用于交易）
            'price': 0,          # 兼容性价格（等于real_price）
            'adj_factor': 1.0,   # 复权因子
            'sma_short': 0,
            'sma_long': 0,
            'signal_strength': 0,
            'message': ''
        }

        try:
            # 加载双价格数据
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

            # 追踪最新价格日期和lookback开始日期（来自adj_df）
            if self.latest_price_date is None and len(adj_df) > 0:
                if hasattr(adj_df.index, 'date'):
                    self.latest_price_date = str(adj_df.index[-1].date())
                else:
                    self.latest_price_date = str(adj_df.index[-1])

            if self.lookback_start_date is None and len(adj_df) > 0:
                if hasattr(adj_df.index, 'date'):
                    self.lookback_start_date = str(adj_df.index[0].date())
                else:
                    self.lookback_start_date = str(adj_df.index[0])

            # 检查数据是否充足（根据策略类型判断）
            min_data_points = 50  # 默认最小数据点
            if hasattr(self.strategy_class, 'slow_period'):
                # MACD策略
                min_data_points = self.strategy_params.get('slow_period', 26) + 10
            elif 'n2' in self.strategy_params:
                # SMA策略
                min_data_points = max(self.strategy_params.get('n1', 10),
                                    self.strategy_params.get('n2', 20)) + 10

            if len(adj_df) < min_data_points:
                result['message'] = '数据点不足，无法计算指标'
                return result

            # 使用复权价格运行回测以获取策略状态（信号计算）
            bt = Backtest(
                adj_df,
                self.strategy_class,
                cash=self.cash,
                commission=self.commission,
                exclusive_orders=True
            )

            # 设置策略参数
            if self.strategy_params:
                stats = bt.run(**self.strategy_params)
            else:
                stats = bt.run()

            # 获取策略实例
            strategy = stats._strategy

            # 设置价格信息
            result['adj_price'] = price_mapping['latest_adj_price']     # 复权价格
            result['real_price'] = price_mapping['latest_real_price']   # 原始价格
            result['price'] = price_mapping['latest_real_price']        # 兼容性（等于原始价格）
            result['adj_factor'] = price_mapping['adj_factor']

            # 检测策略类型并获取相应的指标
            if hasattr(strategy, 'macd_line') and hasattr(strategy, 'signal_line'):
                # MACD策略
                macd_line = strategy.macd_line[-1]
                signal_line = strategy.signal_line[-1]
                macd_line_prev = strategy.macd_line[-2] if len(strategy.macd_line) > 1 else macd_line
                signal_line_prev = strategy.signal_line[-2] if len(strategy.signal_line) > 1 else signal_line

                result['sma_short'] = macd_line  # 兼容性：用macd_line代替
                result['sma_long'] = signal_line  # 兼容性：用signal_line代替

                # 计算信号强度
                signal_strength = macd_line - signal_line  # MACD柱状图值
                result['signal_strength'] = signal_strength

                # 判断信号
                # 金叉：MACD线从下方穿过信号线
                if macd_line_prev <= signal_line_prev and macd_line > signal_line:
                    result['signal'] = 'BUY'
                    fast = getattr(strategy, 'fast_period', 12)
                    slow = getattr(strategy, 'slow_period', 26)
                    sig = getattr(strategy, 'signal_period', 9)
                    result['message'] = f'MACD金叉买入信号！MACD({fast},{slow},{sig})线上穿信号线'
                # 死叉：MACD线从上方穿过信号线
                elif macd_line_prev >= signal_line_prev and macd_line < signal_line:
                    result['signal'] = 'SELL'
                    fast = getattr(strategy, 'fast_period', 12)
                    slow = getattr(strategy, 'slow_period', 26)
                    sig = getattr(strategy, 'signal_period', 9)
                    result['message'] = f'MACD死叉卖出信号！MACD({fast},{slow},{sig})线下穿信号线'
                # 持有状态
                elif macd_line > signal_line:
                    result['signal'] = 'HOLD_LONG'
                    result['message'] = f'持有多头。MACD线在信号线上方（柱状图: {signal_strength:.4f}）'
                else:
                    result['signal'] = 'HOLD_SHORT'
                    result['message'] = f'持有空头。MACD线在信号线下方（柱状图: {signal_strength:.4f}）'

            elif hasattr(strategy, 'sma1') and hasattr(strategy, 'sma2'):
                # SMA策略
                sma_short = strategy.sma1[-1]
                sma_long = strategy.sma2[-1]

                # 获取前一天的指标值（用于检测交叉）
                sma_short_prev = strategy.sma1[-2] if len(strategy.sma1) > 1 else sma_short
                sma_long_prev = strategy.sma2[-2] if len(strategy.sma2) > 1 else sma_long

                result['sma_short'] = sma_short
                result['sma_long'] = sma_long

                # 计算信号强度（均线差值的百分比）
                signal_strength = ((sma_short - sma_long) / sma_long) * 100
                result['signal_strength'] = signal_strength

                # 判断信号（基于复权价格的均线）
                # 金叉：短期均线从下方穿过长期均线
                if sma_short_prev <= sma_long_prev and sma_short > sma_long:
                    result['signal'] = 'BUY'
                    result['message'] = f'金叉买入信号！短期均线({strategy.n1}日)上穿长期均线({strategy.n2}日)'
                # 死叉：短期均线从上方穿过长期均线
                elif sma_short_prev >= sma_long_prev and sma_short < sma_long:
                    result['signal'] = 'SELL'
                    result['message'] = f'死叉卖出信号！短期均线({strategy.n1}日)下穿长期均线({strategy.n2}日)'
                # 持有状态
                elif sma_short > sma_long:
                    result['signal'] = 'HOLD_LONG'
                    result['message'] = f'持有多头。短期均线在长期均线上方（{signal_strength:.2f}%）'
                else:
                    result['signal'] = 'HOLD_SHORT'
                    result['message'] = f'持有空头。短期均线在长期均线下方（{signal_strength:.2f}%）'
            else:
                # 未知策略类型
                result['message'] = f'不支持的策略类型: {self.strategy_class.__name__}'

        except Exception as e:
            result['message'] = f'双价格策略运行失败: {e}'

        return result

    def _get_csv_path(self, ts_code: str) -> Path:
        """根据股票代码构造CSV文件路径"""
        # 推测ETF数据路径
        csv_path = Path(self.data_dir) / 'etf' / f'{ts_code}.csv'
        if csv_path.exists():
            return csv_path

        # 其他可能的路径
        for subdir in ['fund', 'stock', '']:
            csv_path = Path(self.data_dir) / subdir / f'{ts_code}.csv'
            if csv_path.exists():
                return csv_path

        # 默认返回ETF路径（让调用者处理文件不存在的情况）
        return Path(self.data_dir) / 'etf' / f'{ts_code}.csv'

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
            - signals_df: 所有信号的DataFrame
            - allocation_dict: 资金分配建议
        """
        # 读取股票列表
        stock_df = pd.read_csv(stock_list_file)
        if 'ts_code' not in stock_df.columns:
            raise ValueError(f"股票列表文件缺少 'ts_code' 列: {stock_list_file}")

        ts_codes = stock_df['ts_code'].tolist()

        print(f"开始分析 {len(ts_codes)} 只标的...")
        print("=" * 80)

        # 生成信号
        signals = []
        for i, ts_code in enumerate(ts_codes, 1):
            print(f"[{i}/{len(ts_codes)}] 分析 {ts_code}...", end=' ')
            signal = self.get_signal(ts_code)
            signals.append(signal)
            print(f"{signal['signal']}")

        # 转换为DataFrame
        signals_df = pd.DataFrame(signals)

        # 生成资金分配建议
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
        # 筛选买入信号
        buy_signals = signals_df[signals_df['signal'] == 'BUY'].copy()

        if len(buy_signals) == 0:
            return {
                'total_cash': self.cash,
                'positions': [],
                'message': '当前没有买入信号'
            }

        # 检查最小买入信号数
        if len(buy_signals) < self.min_buy_signals:
            return {
                'total_cash': self.cash,
                'allocated_cash': 0,
                'remaining_cash': self.cash,
                'n_positions': 0,
                'positions': [],
                'message': f'买入信号数量不足（{len(buy_signals)} < {self.min_buy_signals}），本次不执行买入'
            }

        # 按信号强度排序（取绝对值，因为可能是负数）
        buy_signals['abs_strength'] = buy_signals['signal_strength'].abs()
        buy_signals = buy_signals.sort_values('abs_strength', ascending=False)

        # 限制持仓数量
        buy_signals = buy_signals.head(target_positions)

        # 计算每个标的的分配资金（带单仓位上限）
        n_positions = len(buy_signals)
        max_cash_per_position = self.cash * self.max_position_pct  # 单仓位上限金额
        cash_per_position = min(self.cash / n_positions, max_cash_per_position)

        # 计算每个标的的建议买入量
        positions = []
        for _, row in buy_signals.iterrows():
            price = row['price']
            # 考虑手续费后的实际可用资金
            effective_cash = cash_per_position * (1 - self.commission - self.spread)
            # 计算可买入股数（向下取整到100股的倍数，A股最小交易单位）
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


def print_signal_report(signals_df: pd.DataFrame,
                       allocation: Dict,
                       output_file: Optional[str] = None):
    """
    打印信号报告

    Args:
        signals_df: 信号DataFrame
        allocation: 资金分配字典
        output_file: 输出文件路径（可选）
    """
    lines = []

    # 标题
    lines.append("=" * 80)
    lines.append(f"交易信号报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")

    # 统计摘要
    lines.append("📊 信号统计")
    lines.append("-" * 80)
    signal_counts = signals_df['signal'].value_counts()
    for signal, count in signal_counts.items():
        lines.append(f"  {signal}: {count} 只")
    lines.append("")

    # 买入信号详情
    buy_signals = signals_df[signals_df['signal'] == 'BUY']
    if len(buy_signals) > 0:
        lines.append("🔔 买入信号（金叉）")
        lines.append("-" * 80)
        for _, row in buy_signals.iterrows():
            lines.append(f"  {row['ts_code']}")
            lines.append(f"    当前价格: ¥{row['price']:.3f}")
            lines.append(f"    短期均线: {row['sma_short']:.3f}")
            lines.append(f"    长期均线: {row['sma_long']:.3f}")
            lines.append(f"    信号强度: {row['signal_strength']:.2f}%")
            lines.append(f"    说明: {row['message']}")
            lines.append("")

    # 卖出信号详情
    sell_signals = signals_df[signals_df['signal'] == 'SELL']
    if len(sell_signals) > 0:
        lines.append("📉 卖出信号（死叉）")
        lines.append("-" * 80)
        for _, row in sell_signals.iterrows():
            lines.append(f"  {row['ts_code']}")
            lines.append(f"    当前价格: ¥{row['price']:.3f}")
            lines.append(f"    说明: {row['message']}")
            lines.append("")

    # 资金分配建议
    lines.append("💰 资金分配建议")
    lines.append("-" * 80)
    lines.append(f"  总资金: ¥{allocation['total_cash']:,.2f}")

    if len(allocation['positions']) > 0:
        lines.append(f"  分配资金: ¥{allocation['allocated_cash']:,.2f}")
        lines.append(f"  剩余资金: ¥{allocation['remaining_cash']:,.2f}")
        lines.append(f"  建议持仓数: {allocation['n_positions']}")
        lines.append("")
        lines.append("  具体买入建议:")
        lines.append("")

        for i, pos in enumerate(allocation['positions'], 1):
            lines.append(f"  [{i}] {pos['ts_code']}")
            lines.append(f"      买入价格: ¥{pos['price']:.3f}")
            lines.append(f"      买入数量: {pos['shares']} 股")
            lines.append(f"      预计成本: ¥{pos['cost']:,.2f}")
            lines.append(f"      仓位占比: {pos['weight']:.2f}%")
            lines.append(f"      信号强度: {pos['signal_strength']:.2f}%")
            lines.append("")
    else:
        lines.append(f"  {allocation.get('message', '无买入建议')}")
        lines.append("")

    # 持仓状态
    hold_long = signals_df[signals_df['signal'] == 'HOLD_LONG']
    if len(hold_long) > 0:
        lines.append("✅ 持有多头（继续持有）")
        lines.append("-" * 80)
        for _, row in hold_long.iterrows():
            lines.append(f"  {row['ts_code']}: {row['message']}")
        lines.append("")

    # 打印到控制台
    report = "\n".join(lines)
    print(report)

    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {output_file}")


def print_portfolio_status(portfolio: Portfolio,
                          current_prices: Dict[str, float],
                          max_positions: int):
    """
    打印持仓状态报告

    Args:
        portfolio: 投资组合对象
        current_prices: 当前价格字典
        max_positions: 最大持仓数
    """
    lines = []

    lines.append("=" * 80)
    lines.append("当前持仓状态")
    lines.append("=" * 80)
    lines.append("")

    # 资金信息
    market_value = portfolio.get_total_market_value(current_prices)
    total_cost = portfolio.get_total_cost()
    total_pnl = portfolio.get_total_pnl(current_prices)
    total_assets = portfolio.cash + market_value
    pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    lines.append("💰 资金信息")
    lines.append("-" * 80)
    lines.append(f"  可用现金: ¥{portfolio.cash:,.2f}")
    lines.append(f"  持仓市值: ¥{market_value:,.2f}")
    lines.append(f"  总资产:   ¥{total_assets:,.2f}")
    pnl_sign = '+' if total_pnl >= 0 else ''
    lines.append(f"  持仓盈亏: {pnl_sign}¥{total_pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)")
    lines.append("")

    # 持仓明细
    lines.append(f"📊 持仓明细 ({len(portfolio.positions)}/{max_positions})")
    lines.append("-" * 80)

    if portfolio.positions:
        for pos in portfolio.positions:
            current_price = current_prices.get(pos.ts_code, pos.entry_price)
            current_value = pos.shares * current_price
            pnl = current_value - pos.cost
            pnl_pct = (pnl / pos.cost * 100) if pos.cost > 0 else 0
            pnl_sign = '+' if pnl >= 0 else ''

            lines.append(f"  {pos.ts_code}")
            lines.append(f"    持仓数量: {pos.shares} 股")
            lines.append(f"    买入价格: ¥{pos.entry_price:.3f} ({pos.entry_date})")
            lines.append(f"    当前价格: ¥{current_price:.3f}")
            lines.append(f"    持仓成本: ¥{pos.cost:,.2f}")
            lines.append(f"    当前市值: ¥{current_value:,.2f}")
            lines.append(f"    盈亏:     {pnl_sign}¥{pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)")
            lines.append("")
    else:
        lines.append("  (无持仓)")
        lines.append("")

    lines.append(f"最后更新: {portfolio.last_update}")
    lines.append("=" * 80)

    print("\n".join(lines))


def print_trade_plan(sell_trades: List[Trade],
                    buy_trades: List[Trade],
                    portfolio: Portfolio):
    """
    打印交易计划

    Args:
        sell_trades: 卖出交易列表
        buy_trades: 买入交易列表
        portfolio: 当前持仓
    """
    lines = []

    lines.append("")
    lines.append("=" * 80)
    lines.append("交易建议")
    lines.append("=" * 80)
    lines.append("")

    # 卖出操作
    if sell_trades:
        lines.append(f"📉 卖出操作 ({len(sell_trades)})")
        lines.append("-" * 80)
        for i, trade in enumerate(sell_trades, 1):
            lines.append(f"  [{i}] {trade.ts_code}")
            lines.append(f"      操作: 卖出")
            lines.append(f"      价格: ¥{trade.price:.3f}")
            lines.append(f"      数量: {trade.shares} 股")
            lines.append(f"      预计收入: ¥{trade.amount:,.2f}")
            lines.append(f"      原因: {trade.reason}")
            lines.append("")

    # 买入操作
    if buy_trades:
        lines.append(f"📈 买入操作 ({len(buy_trades)})")
        lines.append("-" * 80)
        for i, trade in enumerate(buy_trades, 1):
            lines.append(f"  [{i}] {trade.ts_code}")
            lines.append(f"      操作: 买入")
            lines.append(f"      价格: ¥{trade.price:.3f}")
            lines.append(f"      数量: {trade.shares} 股")
            lines.append(f"      预计成本: ¥{abs(trade.amount):,.2f}")
            lines.append(f"      原因: {trade.reason}")
            lines.append("")

    if not sell_trades and not buy_trades:
        lines.append("✅ 无需交易")
        lines.append("-" * 80)
        lines.append("  当前持仓无需调整，继续持有即可。")
        lines.append("")

    # 交易后预期状态
    lines.append("📊 交易后预期状态")
    lines.append("-" * 80)

    # 计算预期现金
    expected_cash = portfolio.cash
    for trade in sell_trades:
        expected_cash += trade.amount
    for trade in buy_trades:
        expected_cash += trade.amount  # amount是负数

    # 计算预期持仓数
    expected_positions = portfolio.get_position_count() - len(sell_trades) + len(buy_trades)

    lines.append(f"  预期现金: ¥{expected_cash:,.2f}")
    lines.append(f"  预期持仓数: {expected_positions}")
    lines.append("")

    lines.append("=" * 80)

    print("\n".join(lines))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='生成实盘交易信号',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 工作模式
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--init', type=float, metavar='CASH',
                           help='初始化持仓文件（指定初始资金）')
    mode_group.add_argument('--status', action='store_true',
                           help='查看持仓状态')
    mode_group.add_argument('--analyze', action='store_true',
                           help='分析模式（生成交易建议但不执行）')
    mode_group.add_argument('--execute', action='store_true',
                           help='执行模式（执行交易并更新持仓）')

    # 基本参数
    parser.add_argument('--stock-list',
                       help='股票列表CSV文件路径')
    parser.add_argument('--portfolio-file',
                       help='持仓文件路径（JSON格式）')
    parser.add_argument('--strategy', default='sma_cross',
                       help='策略名称（默认: sma_cross）')
    parser.add_argument('--cash', type=float, default=100000,
                       help='可用资金（默认: 100000，仅无状态模式）')
    parser.add_argument('--positions', type=int, default=10,
                       help='目标持仓数量（默认: 10）')
    parser.add_argument('--cost-model', default='cn_etf',
                       help='费用模型（默认: cn_etf）')
    parser.add_argument('--data-dir', default='data/csv/daily',
                       help='数据目录（默认: data/csv/daily）')
    parser.add_argument('--lookback-days', type=int, default=250,
                       help='回看天数（默认: 250）')
    parser.add_argument('--output', help='输出报告文件路径（可选）')
    parser.add_argument('--csv', help='输出CSV文件路径（可选）')

    # 策略参数
    parser.add_argument('--n1', type=int, help='短期均线周期')
    parser.add_argument('--n2', type=int, help='长期均线周期')
    parser.add_argument('--load-params', type=str, help='从配置文件加载策略参数')

    # 仓位管理参数（方案A）
    parser.add_argument('--max-position-pct', type=float, default=0.05,
                       help='单仓位上限，占总资金的百分比（默认: 0.05，即5%%）')
    parser.add_argument('--min-buy-signals', type=int, default=1,
                       help='最小买入信号数，少于此数不执行买入（默认: 1，有信号就买入）')

    # 日期范围参数
    parser.add_argument('--start-date', type=str,
                       help='起始日期（格式: YYYYMMDD），优先级高于--lookback-days')
    parser.add_argument('--end-date', type=str,
                       help='截止日期（格式: YYYYMMDD），默认为当前日期')

    # 价格模式
    parser.add_argument('--disable-dual-price', action='store_true',
                       help='禁用双价格模式（回退到旧的单价格模式，不推荐）')

    # 执行确认
    parser.add_argument('--yes', '-y', action='store_true',
                       help='自动确认执行，跳过交互式确认（用于非交互式环境或脚本自动化）')

    args = parser.parse_args()

    # ========== 模式1：初始化持仓 ==========
    if args.init is not None:
        if not args.portfolio_file:
            print("错误: 初始化模式必须指定 --portfolio-file")
            sys.exit(1)

        if args.init <= 0:
            print("错误: 初始资金必须大于0")
            sys.exit(1)

        portfolio = Portfolio.initialize(args.init, args.portfolio_file)
        print("=" * 80)
        print("✓ 持仓状态已初始化")
        print("=" * 80)
        print(f"  初始资金: ¥{args.init:,.2f}")
        print(f"  持仓文件: {args.portfolio_file}")
        print("=" * 80)
        return

    # ========== 模式2：查看持仓状态 ==========
    if args.status:
        if not args.portfolio_file:
            print("错误: 状态查看模式必须指定 --portfolio-file")
            sys.exit(1)

        try:
            portfolio = Portfolio.load(args.portfolio_file)
        except FileNotFoundError:
            print(f"错误: 持仓文件不存在: {args.portfolio_file}")
            print("请先使用 --init 初始化持仓文件")
            sys.exit(1)

        # 获取当前价格
        cost_config = COST_MODELS.get(args.cost_model, COST_MODELS['cn_etf'])
        generator = SignalGenerator(
            strategy_class=None,  # 不需要策略
            cash=0,
            cost_model=args.cost_model,
            data_dir=args.data_dir,
            lookback_days=args.lookback_days,
            start_date=args.start_date if hasattr(args, 'start_date') else None,
            end_date=args.end_date if hasattr(args, 'end_date') else None
        )

        current_prices = {}
        for pos in portfolio.positions:
            df = generator.load_instrument_data(pos.ts_code)
            if df is not None:
                current_prices[pos.ts_code] = df['Close'].iloc[-1]
            else:
                current_prices[pos.ts_code] = pos.entry_price

        print_portfolio_status(portfolio, current_prices, args.positions)
        return

    # ========== 模式3 & 4：分析和执行模式 ==========
    if args.analyze or args.execute:
        if not args.portfolio_file:
            print("错误: 分析/执行模式必须指定 --portfolio-file")
            sys.exit(1)

        if not args.stock_list:
            print("错误: 分析/执行模式必须指定 --stock-list")
            sys.exit(1)

        # 加载持仓
        try:
            portfolio = Portfolio.load(args.portfolio_file)
        except FileNotFoundError:
            print(f"错误: 持仓文件不存在: {args.portfolio_file}")
            print("请先使用 --init 初始化持仓文件")
            sys.exit(1)

        # 加载策略
        try:
            if args.strategy == 'sma_cross':
                from strategies.sma_cross import SmaCross
                strategy_class = SmaCross
            elif args.strategy == 'sma_cross_enhanced':
                from strategies.sma_cross_enhanced import SmaCrossEnhanced
                strategy_class = SmaCrossEnhanced
            elif args.strategy == 'macd_cross':
                from strategies.macd_cross import MacdCross
                strategy_class = MacdCross
            else:
                print(f"错误: 未知策略 '{args.strategy}'")
                sys.exit(1)
        except ImportError as e:
            print(f"错误: 无法加载策略 '{args.strategy}': {e}")
            sys.exit(1)

        # 准备策略参数
        strategy_params = {}

        # 优先从配置文件加载参数
        if args.load_params:
            try:
                params_manager = StrategyParamsManager(args.load_params)
                loaded_params = params_manager.get_strategy_params(args.strategy)
                strategy_params.update(loaded_params)
                print(f"✓ 从配置文件加载参数: {loaded_params}")

                # 新增：加载运行时配置（过滤器、止损保护等）
                runtime_config = params_manager.get_runtime_config(args.strategy)
                if runtime_config:
                    print(f"✓ 从配置文件加载运行时配置")
                    # 合并过滤器配置
                    if 'filters' in runtime_config:
                        strategy_params.update(runtime_config['filters'])
                        filters_info = ', '.join([
                            f"{k.replace('enable_', '')}={'ON' if v else 'OFF'}"
                            for k, v in runtime_config['filters'].items()
                            if k.startswith('enable_')
                        ])
                        print(f"  过滤器: {filters_info}")

                    # 合并止损保护配置
                    if 'loss_protection' in runtime_config:
                        strategy_params.update(runtime_config['loss_protection'])
                        if runtime_config['loss_protection'].get('enable_loss_protection'):
                            print(f"  止损保护: ON (连续亏损={runtime_config['loss_protection'].get('max_consecutive_losses')}, 暂停={runtime_config['loss_protection'].get('pause_bars')})")
                        else:
                            print(f"  止损保护: OFF")
                else:
                    print("  ⚠️ 配置文件中没有运行时配置，使用默认值")

            except Exception as e:
                print(f"⚠️ 加载配置文件失败: {e}")
                print("使用命令行参数或默认参数")

        # 命令行参数会覆盖配置文件参数（如果同时指定）
        if args.n1:
            strategy_params['n1'] = args.n1
            print(f"使用命令行指定的 n1: {args.n1}")
        if args.n2:
            strategy_params['n2'] = args.n2
            print(f"使用命令行指定的 n2: {args.n2}")

        # 如果没有任何参数，使用策略的默认参数
        if not strategy_params:
            print("使用策略默认参数")

        # 获取费用配置
        cost_config = COST_MODELS.get(args.cost_model, COST_MODELS['cn_etf'])

        # 创建信号生成器
        generator = SignalGenerator(
            strategy_class=strategy_class,
            strategy_params=strategy_params,
            cash=portfolio.cash,
            cost_model=args.cost_model,
            data_dir=args.data_dir,
            lookback_days=args.lookback_days,
            use_dual_price=not args.disable_dual_price,
            max_position_pct=args.max_position_pct,
            min_buy_signals=args.min_buy_signals,
            start_date=args.start_date if hasattr(args, 'start_date') else None,
            end_date=args.end_date if hasattr(args, 'end_date') else None
        )

        # 读取股票列表
        stock_df = pd.read_csv(args.stock_list)
        if 'ts_code' not in stock_df.columns:
            print(f"错误: 股票列表文件缺少 'ts_code' 列: {args.stock_list}")
            sys.exit(1)

        ts_codes = stock_df['ts_code'].tolist()

        # 生成所有标的的信号
        print(f"开始分析 {len(ts_codes)} 只标的...")
        print("=" * 80)

        signals = {}
        current_prices = {}

        for i, ts_code in enumerate(ts_codes, 1):
            print(f"[{i}/{len(ts_codes)}] 分析 {ts_code}...", end=' ')
            signal = generator.get_signal(ts_code)
            signals[ts_code] = signal
            current_prices[ts_code] = signal['price']
            print(f"{signal['signal']}")

        print("")

        # 显示数据日期信息
        print("=" * 80)
        print("📊 数据信息")
        print("=" * 80)
        if generator.latest_price_date:
            print(f"最新价格日期:  {generator.latest_price_date}")
        if generator.lookback_start_date:
            print(f"Lookback起始:  {generator.lookback_start_date}")
        print(f"Lookback周期:   {args.lookback_days} 天")
        print("=" * 80)
        print("")

        # 显示当前持仓状态
        print_portfolio_status(portfolio, current_prices, args.positions)

        # 创建交易引擎
        trader = PortfolioTrader(
            portfolio=portfolio,
            commission=cost_config['commission'],
            spread=cost_config.get('spread', 0.0),
            max_positions=args.positions,
            max_position_pct=args.max_position_pct,
            min_buy_signals=args.min_buy_signals
        )

        # 生成交易计划
        sell_trades, buy_trades = trader.generate_trade_plan(signals)

        # 显示交易计划
        print_trade_plan(sell_trades, buy_trades, portfolio)

        # 执行模式
        if args.execute:
            if not sell_trades and not buy_trades:
                print("无需执行任何交易。")
                return

            # 确认执行
            print("")
            print("⚠️  即将执行交易操作，请确认：")
            print(f"  - 卖出 {len(sell_trades)} 只标的")
            print(f"  - 买入 {len(buy_trades)} 只标的")
            print("")

            # 检查是否跳过确认
            if not args.yes:
                try:
                    confirm = input("是否确认执行？(yes/no): ").strip().lower()
                    if confirm != 'yes':
                        print("已取消执行。")
                        return
                except EOFError:
                    print("")
                    print("❌ 错误: 无法读取用户输入（非交互式环境）")
                    print("提示: 请使用 --yes 参数自动确认，或在交互式终端中运行")
                    return
            else:
                print("使用 --yes 参数，自动确认执行...")
                print("")

            # 执行交易
            print("")
            print("开始执行交易...")
            trader.execute_trades(sell_trades, buy_trades, dry_run=False)

            for trade in sell_trades:
                print(f"✓ 卖出: {trade.ts_code} {trade.shares}股 @¥{trade.price:.3f} 收入¥{trade.amount:,.2f}")

            for trade in buy_trades:
                print(f"✓ 买入: {trade.ts_code} {trade.shares}股 @¥{trade.price:.3f} 成本¥{abs(trade.amount):,.2f}")

            # 保存持仓
            portfolio.save()
            print(f"\n✓ 持仓已更新: {args.portfolio_file}")

            # 记录交易历史
            if sell_trades or buy_trades:
                history_dir = Path(args.portfolio_file).parent / 'history'
                logger = TradeLogger(str(history_dir))
                all_trades = sell_trades + buy_trades
                logger.log_trades(all_trades)
                today = datetime.now().strftime('%Y%m%d')
                print(f"✓ 交易记录已保存: {history_dir}/trades_{today}.json")

        return

    # ========== 无状态模式（原有逻辑）==========
    if not args.stock_list:
        print("错误: 必须指定 --stock-list")
        sys.exit(1)

    # 检查股票列表文件
    if not os.path.exists(args.stock_list):
        print(f"错误: 股票列表文件不存在: {args.stock_list}")
        sys.exit(1)

    # 加载策略
    try:
        if args.strategy == 'sma_cross':
            from strategies.sma_cross import SmaCross
            strategy_class = SmaCross
        elif args.strategy == 'sma_cross_enhanced':
            from strategies.sma_cross_enhanced import SmaCrossEnhanced
            strategy_class = SmaCrossEnhanced
        elif args.strategy == 'macd_cross':
            from strategies.macd_cross import MacdCross
            strategy_class = MacdCross
        else:
            print(f"错误: 未知策略 '{args.strategy}'")
            sys.exit(1)
    except ImportError as e:
        print(f"错误: 无法加载策略 '{args.strategy}': {e}")
        sys.exit(1)

    # 准备策略参数
    strategy_params = {}
    if args.n1:
        strategy_params['n1'] = args.n1
    if args.n2:
        strategy_params['n2'] = args.n2

    # 创建信号生成器
    generator = SignalGenerator(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        cash=args.cash,
        cost_model=args.cost_model,
        data_dir=args.data_dir,
        lookback_days=args.lookback_days,
        use_dual_price=not args.disable_dual_price,
        max_position_pct=args.max_position_pct,
        min_buy_signals=args.min_buy_signals,
        start_date=args.start_date if hasattr(args, 'start_date') else None,
        end_date=args.end_date if hasattr(args, 'end_date') else None
    )

    # 生成信号
    signals_df, allocation = generator.generate_signals_for_pool(
        stock_list_file=args.stock_list,
        target_positions=args.positions
    )

    # 打印报告
    print("\n")
    print_signal_report(signals_df, allocation, args.output)

    # 保存CSV
    if args.csv:
        signals_df.to_csv(args.csv, index=False, encoding='utf-8-sig')
        print(f"信号数据已保存到: {args.csv}")


if __name__ == '__main__':
    main()

