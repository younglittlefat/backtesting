"""
v3 真实调仓回测脚本

功能:
1. 支持季度/半年/年度三种调仓周期
2. 模拟真实调仓交易（计入成本）
3. 新标的等待KAMA信号建仓
4. 重叠标的保持持仓不动

使用方法:
    python run_backtests_v3.py [--period quarterly|semi-annual|annual]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# 添加项目根目录到path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from portfolio_simulator import PortfolioSimulator, CostConfig, KAMAIndicator
from rotation_scheduler import RotationScheduler


class DataLoader:
    """ETF数据加载器"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, pd.DataFrame] = {}

    def load_etf(self, symbol: str) -> Optional[pd.DataFrame]:
        """加载单个ETF数据"""
        if symbol in self._cache:
            return self._cache[symbol]

        csv_path = self.data_dir / f"{symbol}.csv"
        if not csv_path.exists():
            return None

        try:
            df = pd.read_csv(csv_path)
            df['trade_date'] = df['trade_date'].astype(str)
            df = df.sort_values('trade_date').reset_index(drop=True)
            self._cache[symbol] = df
            return df
        except Exception as e:
            print(f"加载 {symbol} 失败: {e}")
            return None

    def get_price(self, symbol: str, date: str, price_type: str = 'adj_close') -> Optional[float]:
        """获取指定日期的价格"""
        df = self.load_etf(symbol)
        if df is None:
            return None

        row = df[df['trade_date'] == date]
        if row.empty:
            return None

        return row[price_type].iloc[0]

    def get_prices_for_date(
        self,
        symbols: List[str],
        date: str,
        price_type: str = 'adj_close'
    ) -> Dict[str, float]:
        """获取指定日期所有标的的价格"""
        prices = {}
        for symbol in symbols:
            price = self.get_price(symbol, date, price_type)
            if price is not None:
                prices[symbol] = price
        return prices

    def get_trading_calendar(self, start_date: str, end_date: str, etf_list: List[str] = None) -> List[str]:
        """从数据中提取交易日历

        Args:
            start_date: 开始日期 (YYYYMMDD格式)
            end_date: 结束日期 (YYYYMMDD格式)
            etf_list: ETF列表，如果提供则从这些ETF中提取日期，否则从样本文件中提取
        """
        all_dates = set()

        # 如果提供了ETF列表，从这些ETF中提取日期
        if etf_list:
            csv_files = [self.data_dir / f"{symbol}.csv" for symbol in etf_list]
        else:
            # 否则从样本文件中提取
            csv_files = list(self.data_dir.glob('*.csv'))[:20]

        for csv_file in csv_files:
            if not csv_file.exists():
                continue
            try:
                df = pd.read_csv(csv_file, usecols=['trade_date'])
                df['trade_date'] = df['trade_date'].astype(str)
                dates = df[
                    (df['trade_date'] >= start_date) &
                    (df['trade_date'] <= end_date)
                ]['trade_date']
                all_dates.update(dates.tolist())
            except Exception:
                continue

        return sorted(list(all_dates))

    def get_kama_for_date(
        self,
        symbols: List[str],
        date: str,
        kama_params: Dict
    ) -> Dict[str, float]:
        """计算指定日期所有标的的KAMA值"""
        kama_calc = KAMAIndicator(
            period=kama_params.get('period', 20),
            fast=kama_params.get('fast', 2),
            slow=kama_params.get('slow', 30)
        )

        kama_values = {}
        for symbol in symbols:
            df = self.load_etf(symbol)
            if df is None:
                continue

            # 获取截至date的数据
            df_sub = df[df['trade_date'] <= date].copy()
            if len(df_sub) < kama_params.get('period', 20) + 10:
                continue

            close = df_sub['adj_close']
            kama = kama_calc.calculate(close)

            if not kama.empty and not pd.isna(kama.iloc[-1]):
                kama_values[symbol] = kama.iloc[-1]

        return kama_values

    def get_prev_close(self, symbols: List[str], date: str) -> Dict[str, float]:
        """获取指定日期前一日的收盘价"""
        prev_closes = {}
        for symbol in symbols:
            df = self.load_etf(symbol)
            if df is None:
                continue

            df_before = df[df['trade_date'] < date]
            if df_before.empty:
                continue

            prev_closes[symbol] = df_before['adj_close'].iloc[-1]

        return prev_closes


class V3BacktestRunner:
    """v3回测执行器"""

    def __init__(
        self,
        rotation_period: str,
        data_dir: str,
        schedule_path: str,
        output_dir: str,
        start_date: str = '20240101',
        end_date: str = '20251130',
        initial_cash: float = 1_000_000,
        kama_params: Optional[Dict] = None
    ):
        self.rotation_period = rotation_period
        self.data_dir = data_dir
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.kama_params = kama_params or {'period': 20, 'fast': 2, 'slow': 30}

        # 初始化组件
        self.scheduler = RotationScheduler(schedule_path, rotation_period)
        self.data_loader = DataLoader(data_dir)
        self.simulator = PortfolioSimulator(
            initial_cash=initial_cash,
            cost_config=CostConfig(),
            kama_params=self.kama_params
        )

    def run(self) -> Dict:
        """执行回测"""
        print(f"\n{'='*60}")
        print(f"v3 真实调仓回测 - {self.rotation_period.upper()}")
        print(f"{'='*60}")

        # 获取所有涉及的ETF
        all_etfs = self.scheduler.get_all_etfs()
        print(f"涉及ETF: {len(all_etfs)} 只")

        # 获取交易日历（从实际ETF中提取）
        trading_calendar = self.data_loader.get_trading_calendar(
            self.start_date, self.end_date, all_etfs
        )
        print(f"交易日历: {len(trading_calendar)} 天 ({trading_calendar[0]} ~ {trading_calendar[-1]})")

        # 获取调仓周期信息
        periods = self.scheduler.get_period_info()
        print(f"调仓周期数: {len(periods)}")

        # 构建调仓日期 -> 池子的映射
        rotation_map = {}
        for p in periods:
            start = p['start'].replace('-', '')
            # 找到该日期或之后的第一个交易日
            for td in trading_calendar:
                if td >= start:
                    rotation_map[td] = p['etfs']
                    break

        print(f"调仓日期: {sorted(rotation_map.keys())}")

        # 初始化：将第一个周期的ETF加入等待信号列表
        first_rotation_date = min(rotation_map.keys())
        first_pool = rotation_map[first_rotation_date]
        self.simulator.current_pool = first_pool
        self.simulator.waiting_for_signal = set(first_pool)

        rotation_records = []
        processed_rotations = {first_rotation_date}

        # 逐日回测
        for i, date in enumerate(trading_calendar):
            # 检查是否为调仓日（非首日）
            if date in rotation_map and date not in processed_rotations:
                new_pool = rotation_map[date]
                prices = self.data_loader.get_prices_for_date(
                    list(set(self.simulator.current_pool + new_pool)),
                    date,
                    'adj_open'  # 调仓用开盘价
                )

                result = self.simulator.rotate(new_pool, date, prices)
                rotation_records.append(result)
                processed_rotations.add(date)

                print(f"\n[{date}] 调仓: 卖出{len(result['sold'])}只, "
                      f"新增观察{len(result['added_to_watchlist'])}只, "
                      f"保持{len(result['kept'])}只")

            # 获取当日数据
            current_pool = self.simulator.current_pool
            close_prices = self.data_loader.get_prices_for_date(current_pool, date, 'adj_close')
            kama_values = self.data_loader.get_kama_for_date(current_pool, date, self.kama_params)
            prev_closes = self.data_loader.get_prev_close(current_pool, date)

            # 添加前日收盘价到prices字典
            for symbol, prev_close in prev_closes.items():
                close_prices[f'{symbol}_prev_close'] = prev_close

            # 处理策略信号
            day_trades = self.simulator.process_signals(date, close_prices, kama_values)

            # 记录净值
            self.simulator.record_nav(date, close_prices)

            # 进度显示
            if (i + 1) % 50 == 0:
                nav = self.simulator.nav_history[-1]['nav'] if self.simulator.nav_history else self.initial_cash
                print(f"  进度: {i+1}/{len(trading_calendar)}, 净值: {nav:.2f}")

        # 生成结果
        summary = self.simulator.get_summary()
        summary['rotation_period'] = self.rotation_period
        summary['rotation_count'] = len(rotation_records)

        # 保存结果
        self._save_results(summary, rotation_records)

        return summary

    def _save_results(self, summary: Dict, rotation_records: List[Dict]):
        """保存回测结果"""
        period_name = self.rotation_period.replace('-', '_')

        # 保存汇总
        summary_path = self.output_dir / f'v3_{period_name}_overall.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n已保存: {summary_path}")

        # 保存净值序列
        nav_df = self.simulator.get_nav_df()
        nav_path = self.output_dir / f'v3_{period_name}_nav.csv'
        nav_df.to_csv(nav_path, index=False)
        print(f"已保存: {nav_path}")

        # 保存交易记录
        trades_df = self.simulator.get_trades_df()
        trades_path = self.output_dir / f'v3_{period_name}_trades.csv'
        trades_df.to_csv(trades_path, index=False)
        print(f"已保存: {trades_path}")

        # 保存调仓记录
        rotation_path = self.output_dir / f'v3_{period_name}_rotations.json'
        with open(rotation_path, 'w', encoding='utf-8') as f:
            json.dump(rotation_records, f, indent=2, ensure_ascii=False)
        print(f"已保存: {rotation_path}")


def main():
    parser = argparse.ArgumentParser(description='v3 真实调仓回测')
    parser.add_argument(
        '--period',
        choices=['quarterly', 'semi-annual', 'annual', 'all'],
        default='all',
        help='调仓周期 (默认: all, 运行所有周期)'
    )
    parser.add_argument(
        '--start-date',
        default='20240101',
        help='开始日期 (默认: 20240101)'
    )
    parser.add_argument(
        '--end-date',
        default='20251130',
        help='结束日期 (默认: 20251130)'
    )
    parser.add_argument(
        '--initial-cash',
        type=float,
        default=1_000_000,
        help='初始资金 (默认: 1000000)'
    )

    args = parser.parse_args()

    # 路径配置
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_dir = PROJECT_ROOT / 'data' / 'chinese_etf' / 'daily' / 'etf'
    schedule_path = project_root / 'pool_rotation_schedule.json'
    output_dir = project_root / 'results' / 'comparison_v3'

    # 确定要运行的周期
    if args.period == 'all':
        periods = ['quarterly', 'semi-annual', 'annual']
    else:
        periods = [args.period]

    results = {}

    for period in periods:
        runner = V3BacktestRunner(
            rotation_period=period,
            data_dir=str(data_dir),
            schedule_path=str(schedule_path),
            output_dir=str(output_dir),
            start_date=args.start_date,
            end_date=args.end_date,
            initial_cash=args.initial_cash
        )

        summary = runner.run()
        results[period] = summary

        print(f"\n{'='*40}")
        print(f"{period.upper()} 回测结果:")
        print(f"  总收益率: {summary['total_return']:.2f}%")
        print(f"  年化收益: {summary['annualized_return']:.2f}%")
        print(f"  夏普比率: {summary['sharpe']:.4f}")
        print(f"  最大回撤: {summary['max_drawdown']:.2f}%")
        print(f"  总交易次数: {summary['total_trades']}")
        print(f"  调仓交易: {summary['rotation_trades']}")
        print(f"  信号交易: {summary['signal_trades']}")
        print(f"  总成本: {summary['total_cost']:.2f}")

    # 保存对比汇总
    comparison_path = output_dir / 'v3_comparison_summary.json'
    with open(comparison_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n已保存对比汇总: {comparison_path}")


if __name__ == '__main__':
    main()
