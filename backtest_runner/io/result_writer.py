"""结果写入模块"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ..models import InstrumentInfo
from ..utils.display_utils import resolve_display_name
from ..utils.data_utils import _duration_to_days, _safe_stat


class ResultWriter:
    """回测结果写入器"""

    def __init__(self, output_dir: str):
        """
        初始化结果写入器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir

    def save_results(
        self,
        stats: pd.Series,
        instrument: InstrumentInfo,
        strategy_name: str,
        optimized: bool = False,
        cash: float = 10000,
        verbose: bool = False,
    ) -> None:
        """
        保存回测结果和交易记录

        Args:
            stats: 回测统计结果
            instrument: 标的信息
            strategy_name: 策略名称
            optimized: 是否经过优化
            cash: 初始资金
            verbose: 是否输出详细信息
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_root = Path(self.output_dir) / instrument.category
        stats_dir = output_root / 'stats'
        stats_dir.mkdir(parents=True, exist_ok=True)

        stats_file = stats_dir / f"{instrument.code}_{strategy_name}_{timestamp}.csv"

        summary_data = self._build_summary_data(
            stats=stats,
            instrument=instrument,
            strategy_name=strategy_name,
            optimized=optimized,
            cash=cash
        )

        summary_df = pd.DataFrame([summary_data])
        summary_df.to_csv(stats_file, index=False, encoding='utf-8-sig')
        if verbose:
            print(f"保存统计数据: {stats_file}")

        # 保存交易记录
        if len(stats._trades) > 0:
            trades_file = stats_dir / f"{instrument.code}_{strategy_name}_{timestamp}_trades.csv"
            stats._trades.to_csv(trades_file, encoding='utf-8-sig')
            if verbose:
                print(f"保存交易记录: {trades_file}")

    def _build_summary_data(
        self,
        stats: pd.Series,
        instrument: InstrumentInfo,
        strategy_name: str,
        optimized: bool,
        cash: float
    ) -> dict:
        """
        构建汇总数据

        Args:
            stats: 回测统计结果
            instrument: 标的信息
            strategy_name: 策略名称
            optimized: 是否经过优化
            cash: 初始资金

        Returns:
            汇总数据字典
        """
        summary_data = {
            '标的代码': instrument.code,
            '标的名称': resolve_display_name(instrument),
            '标的类型': instrument.category,
            '货币': instrument.currency,
            '策略': strategy_name,
            '是否优化': '是' if optimized else '否',
            '开始日期': str(stats['Start'])[:10],  # 只显示日期部分
            '结束日期': str(stats['End'])[:10],    # 只显示日期部分
            '持续天数': _duration_to_days(stats.get('Duration')),
            '初始资金': round(cash, 3),
            '最终资金': round(stats['Equity Final [$]'], 3),
            '收益率(%)': round(_safe_stat(stats, 'Return [%]'), 3),
            '年化收益率(%)': round(_safe_stat(stats, 'Return (Ann.) [%]'), 3),
            '买入持有收益率(%)': round(_safe_stat(stats, 'Buy & Hold Return [%]', default=0.0), 3),
            '夏普比率': round(stats['Sharpe Ratio'], 3) if not pd.isna(stats['Sharpe Ratio']) else None,
            '索提诺比率': round(stats['Sortino Ratio'], 3) if not pd.isna(stats['Sortino Ratio']) else None,
            '卡玛比率': round(stats['Calmar Ratio'], 3) if not pd.isna(stats['Calmar Ratio']) else None,
            '最大回撤(%)': round(_safe_stat(stats, 'Max. Drawdown [%]', default=0.0), 3),
            '平均回撤(%)': round(_safe_stat(stats, 'Avg. Drawdown [%]', default=0.0), 3),
            '最大回撤持续天数': _duration_to_days(stats.get('Max. Drawdown Duration')),
            '交易次数': stats['# Trades'],
            '胜率(%)': round(_safe_stat(stats, 'Win Rate [%]', default=0.0), 3),
            '最佳交易(%)': round(_safe_stat(stats, 'Best Trade [%]', default=0.0), 3),
            '最差交易(%)': round(_safe_stat(stats, 'Worst Trade [%]', default=0.0), 3),
            '平均交易(%)': round(_safe_stat(stats, 'Avg. Trade [%]', default=0.0), 3),
            '盈亏比': round(_safe_stat(stats, 'Profit Factor', default=0.0), 3),
            '期望值(%)': round(_safe_stat(stats, 'Expectancy [%]', default=0.0), 3),
            'SQN': round(_safe_stat(stats, 'SQN', default=0.0), 3),
            '手续费': round(stats.get('Commissions [$]', 0), 3),
        }

        # 如果是优化模式，添加优化参数
        if optimized and hasattr(stats._strategy, 'n1'):
            summary_data['短期均线(n1)'] = stats._strategy.n1
            if hasattr(stats._strategy, 'n2'):
                summary_data['长期均线(n2)'] = stats._strategy.n2

        return summary_data


# 向后兼容的函数接口
def save_results(
    stats: pd.Series,
    instrument: InstrumentInfo,
    strategy_name: str,
    output_dir: str,
    optimized: bool = False,
    cash: float = 10000,
    verbose: bool = False,
) -> None:
    """
    保存回测结果和交易记录（向后兼容接口）

    Args:
        stats: 回测统计结果
        instrument: 标的信息
        strategy_name: 策略名称
        output_dir: 输出目录
        optimized: 是否经过优化
        cash: 初始资金
        verbose: 是否输出详细信息
    """
    writer = ResultWriter(output_dir)
    writer.save_results(
        stats=stats,
        instrument=instrument,
        strategy_name=strategy_name,
        optimized=optimized,
        cash=cash,
        verbose=verbose
    )
