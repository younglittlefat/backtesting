#!/usr/bin/env python3
"""
批量回测管理器

封装回测脚本调用，解析结果，提取关键性能指标。
"""
import subprocess
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
import logging


class BacktestManager:
    """批量回测管理器"""

    def __init__(self, project_root: str = "/mnt/d/git/backtesting"):
        """
        初始化回测管理器

        Args:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root)
        self.run_backtest_sh = self.project_root / "run_backtest.sh"
        self.logger = logging.getLogger(__name__)

        if not self.run_backtest_sh.exists():
            raise FileNotFoundError(f"回测脚本不存在: {self.run_backtest_sh}")

    def run_backtest(
        self,
        stock_list_csv: str,
        strategy: str = "macd_cross_enhanced",
        enable_loss_protection: bool = True,
        max_consecutive_losses: int = 3,
        pause_bars: int = 10,
        optimize: bool = True,
        data_dir: str = "data/chinese_etf/daily"
    ) -> Dict:
        """
        执行单次回测

        Args:
            stock_list_csv: 标的池CSV文件路径
            strategy: 策略名称
            enable_loss_protection: 是否启用连续止损保护
            max_consecutive_losses: 连续亏损阈值
            pause_bars: 暂停K线数
            optimize: 是否优化参数
            data_dir: 数据目录

        Returns:
            回测结果字典，包含关键性能指标
        """
        # 构建命令
        cmd = [
            str(self.run_backtest_sh),
            "--stock-list", stock_list_csv,
            "-t", strategy,
            "--data-dir", data_dir
        ]

        # 添加止损保护参数
        if enable_loss_protection:
            cmd.extend([
                "--enable-loss-protection",
                "--max-consecutive-losses", str(max_consecutive_losses),
                "--pause-bars", str(pause_bars)
            ])

        # 添加优化标志
        if optimize:
            cmd.append("-o")

        self.logger.info(f"执行回测命令: {' '.join(cmd)}")

        try:
            # 执行回测
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.project_root)
            )

            # 解析输出
            self.logger.info(f"回测完成，输出:\n{result.stdout}")

            # 查找最新的结果文件
            # 回测结果保存在 results/summary/ 目录下
            results_dir = self.project_root / "results" / "summary"
            result_files = list(results_dir.glob("backtest_summary_*.csv"))

            if not result_files:
                raise FileNotFoundError("未找到回测结果文件")

            # 选择最新的结果文件
            latest_result = max(result_files, key=lambda p: p.stat().st_mtime)
            self.logger.info(f"读取回测结果: {latest_result}")

            # 解析结果
            metrics = self._parse_backtest_results(latest_result)
            return metrics

        except subprocess.CalledProcessError as e:
            self.logger.error(f"回测失败: {e.stderr}")
            raise RuntimeError(f"回测失败: {e.stderr}")

    def _parse_backtest_results(self, result_csv: Path) -> Dict:
        """
        解析回测结果CSV

        Args:
            result_csv: 结果CSV文件路径

        Returns:
            性能指标字典
        """
        df = pd.read_csv(result_csv)

        # 支持中英文列名
        column_mapping = {
            '收益率(%)': 'Return [%]',
            '夏普比率': 'Sharpe Ratio',
            '最大回撤(%)': 'Max. Drawdown [%]',
            'Sharpe Ratio': 'Sharpe Ratio',
            'Return [%]': 'Return [%]',
            'Max. Drawdown [%]': 'Max. Drawdown [%]'
        }

        # 统一列名
        df = df.rename(columns=column_mapping)

        # 提取平均指标（所有标的的平均表现）
        metrics = {
            'sharpe_ratio': df['Sharpe Ratio'].mean() if 'Sharpe Ratio' in df.columns else 0.0,
            'annual_return': df['Return [%]'].mean() / 100 if 'Return [%]' in df.columns else 0.0,
            'max_drawdown': df['Max. Drawdown [%]'].mean() / 100 if 'Max. Drawdown [%]' in df.columns else 0.0,
            'win_rate': df['Win Rate [%]'].mean() / 100 if 'Win Rate [%]' in df.columns else 0.0,
            'profit_factor': df['Profit Factor'].mean() if 'Profit Factor' in df.columns else 0.0,
            'num_trades': df['# Trades'].sum() if '# Trades' in df.columns else 0,
            'num_stocks': len(df)
        }

        # 计算中位数和最差情况
        metrics['sharpe_ratio_median'] = df['Sharpe Ratio'].median() if 'Sharpe Ratio' in df.columns else 0.0
        metrics['annual_return_median'] = df['Return [%]'].median() / 100 if 'Return [%]' in df.columns else 0.0
        metrics['max_drawdown_worst'] = df['Max. Drawdown [%]'].min() / 100 if 'Max. Drawdown [%]' in df.columns else 0.0

        self.logger.info(f"解析结果: 夏普比率={metrics['sharpe_ratio']:.2f}, "
                        f"年化收益={metrics['annual_return']:.2%}, "
                        f"最大回撤={metrics['max_drawdown']:.2%}")

        return metrics


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    manager = BacktestManager()

    # 需要实际的股票列表文件进行测试
    # result = manager.run_backtest(
    #     stock_list_csv="results/trend_etf_pool.csv",
    #     enable_loss_protection=True,
    #     optimize=True
    # )
    # print(result)

    print("BacktestManager 类已创建，可以开始使用")
