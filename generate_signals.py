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

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting import Backtest
from backtesting.lib import crossover
from utils.data_loader import load_chinese_ohlcv_data


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
                 lookback_days: int = 250):
        """
        初始化信号生成器

        Args:
            strategy_class: 策略类
            strategy_params: 策略参数字典
            cash: 可用资金
            cost_model: 费用模型
            data_dir: 数据目录
            lookback_days: 回看天数（用于计算指标）
        """
        self.strategy_class = strategy_class
        self.strategy_params = strategy_params or {}
        self.cash = cash
        self.cost_model = cost_model
        self.data_dir = data_dir
        self.lookback_days = lookback_days

        # 获取费用配置
        if cost_model not in COST_MODELS:
            raise ValueError(f"未知的费用模型: {cost_model}。可用选项: {list(COST_MODELS.keys())}")

        cost_config = COST_MODELS[cost_model]
        self.commission = cost_config['commission']
        self.spread = cost_config.get('spread', 0.0)

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

            # 只保留最近的lookback_days天数据
            df = df.tail(self.lookback_days)

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

            # 获取最新的指标值
            sma_short = strategy.sma1[-1]
            sma_long = strategy.sma2[-1]
            current_price = df['Close'].iloc[-1]

            # 获取前一天的指标值（用于检测交叉）
            sma_short_prev = strategy.sma1[-2] if len(strategy.sma1) > 1 else sma_short
            sma_long_prev = strategy.sma2[-2] if len(strategy.sma2) > 1 else sma_long

            result['price'] = current_price
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

        except Exception as e:
            result['message'] = f'策略运行失败: {e}'

        return result

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
            signal = self.get_current_signal(ts_code)
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

        # 按信号强度排序（取绝对值，因为可能是负数）
        buy_signals['abs_strength'] = buy_signals['signal_strength'].abs()
        buy_signals = buy_signals.sort_values('abs_strength', ascending=False)

        # 限制持仓数量
        buy_signals = buy_signals.head(target_positions)

        # 计算每个标的的分配资金（等权重）
        n_positions = len(buy_signals)
        cash_per_position = self.cash / n_positions

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
            lines.append(f"    当前价格: ¥{row['price']:.2f}")
            lines.append(f"    短期均线: {row['sma_short']:.2f}")
            lines.append(f"    长期均线: {row['sma_long']:.2f}")
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
            lines.append(f"    当前价格: ¥{row['price']:.2f}")
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
            lines.append(f"      买入价格: ¥{pos['price']:.2f}")
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='生成实盘交易信号',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--stock-list', required=True,
                       help='股票列表CSV文件路径')
    parser.add_argument('--strategy', default='sma_cross',
                       help='策略名称（默认: sma_cross）')
    parser.add_argument('--cash', type=float, default=100000,
                       help='可用资金（默认: 100000）')
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

    args = parser.parse_args()

    # 检查股票列表文件
    if not os.path.exists(args.stock_list):
        print(f"错误: 股票列表文件不存在: {args.stock_list}")
        sys.exit(1)

    # 加载策略
    try:
        if args.strategy == 'sma_cross':
            from strategies.sma_cross import SmaCross
            strategy_class = SmaCross
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
        lookback_days=args.lookback_days
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
