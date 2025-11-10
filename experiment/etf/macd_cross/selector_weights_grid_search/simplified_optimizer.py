#!/usr/bin/env python3
"""
简化的无偏权重优化实验

策略调整：
1. 使用已有的ETF池文件（results/trend_etf_pool.csv）
2. 专注于测试MACD策略参数优化和止损保护的效果
3. 对比不同的止损参数组合的表现

这个简化版本可以快速验证实验框架是否工作正常。
"""
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

# 添加项目根目录到path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from experiment.etf.macd_cross.selector_weights_grid_search.backtest_manager import BacktestManager


class SimplifiedOptimizer:
    """简化的优化器 - 使用固定ETF池"""

    def __init__(self, project_root: str = "/mnt/d/git/backtesting"):
        """初始化优化器"""
        self.project_root = Path(project_root)
        self.experiment_dir = Path(__file__).parent
        self.results_dir = self.experiment_dir / "results" / "simplified"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # 使用已有的ETF池
        self.etf_pool_file = self.project_root / "results" / "trend_etf_pool.csv"

        if not self.etf_pool_file.exists():
            raise FileNotFoundError(f"ETF池文件不存在: {self.etf_pool_file}")

        # 初始化回测管理器
        self.backtest_manager = BacktestManager(project_root=str(self.project_root))

        # 设置日志
        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        log_dir = self.experiment_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"simplified_experiment_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"日志文件: {log_file}")

    def generate_param_combinations(self) -> List[Dict]:
        """
        生成参数组合

        测试不同的止损保护参数组合
        """
        combinations = []

        # 基线：无止损保护
        combinations.append({
            'experiment_id': 0,
            'enable_loss_protection': False,
            'max_consecutive_losses': None,
            'pause_bars': None,
            'description': '基线（无止损保护）'
        })

        # 不同的止损保护参数
        loss_thresholds = [2, 3, 4]
        pause_bars_options = [5, 10, 15]

        exp_id = 1
        for losses in loss_thresholds:
            for pause in pause_bars_options:
                combinations.append({
                    'experiment_id': exp_id,
                    'enable_loss_protection': True,
                    'max_consecutive_losses': losses,
                    'pause_bars': pause,
                    'description': f'止损保护（连续亏损={losses}, 暂停={pause}）'
                })
                exp_id += 1

        return combinations

    def run_single_experiment(self, params: Dict) -> Dict:
        """运行单个实验"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"实验 {params['experiment_id']}: {params['description']}")
        self.logger.info(f"{'='*60}")

        result = {
            'experiment_id': params['experiment_id'],
            'params': params,
            'status': 'failed',
            'error': None
        }

        try:
            # 执行回测
            self.logger.info(f"使用ETF池: {self.etf_pool_file}")
            backtest_result = self.backtest_manager.run_backtest(
                stock_list_csv=str(self.etf_pool_file),
                strategy="macd_cross_enhanced",
                enable_loss_protection=params['enable_loss_protection'],
                max_consecutive_losses=params['max_consecutive_losses'] or 3,
                pause_bars=params['pause_bars'] or 10,
                optimize=True,
                data_dir="data/chinese_etf/daily"
            )

            # 记录结果
            result['status'] = 'success'
            result.update(backtest_result)

            self.logger.info(f"✓ 实验 {params['experiment_id']} 完成")
            self.logger.info(f"  夏普比率: {result['sharpe_ratio']:.3f}")
            self.logger.info(f"  年化收益: {result['annual_return']:.2%}")
            self.logger.info(f"  最大回撤: {result['max_drawdown']:.2%}")

        except Exception as e:
            self.logger.error(f"实验 {params['experiment_id']} 失败: {str(e)}")
            result['error'] = str(e)

        return result

    def run_all_experiments(self) -> List[Dict]:
        """运行所有实验"""
        combinations = self.generate_param_combinations()
        self.logger.info(f"开始简化实验: 共 {len(combinations)} 个参数组合")

        results = []
        for params in combinations:
            start_time = time.time()
            result = self.run_single_experiment(params)
            results.append(result)
            elapsed = time.time() - start_time
            self.logger.info(f"耗时: {elapsed:.1f}秒\n")

        return results

    def save_results(self, results: List[Dict]):
        """保存结果"""
        records = []
        for r in results:
            if r['status'] != 'success':
                continue

            record = {
                'experiment_id': r['experiment_id'],
                'description': r['params']['description'],
                'enable_loss_protection': r['params']['enable_loss_protection'],
                'max_consecutive_losses': r['params']['max_consecutive_losses'],
                'pause_bars': r['params']['pause_bars'],
                'sharpe_ratio': r['sharpe_ratio'],
                'annual_return': r['annual_return'],
                'max_drawdown': r['max_drawdown'],
                'win_rate': r['win_rate'],
                'profit_factor': r['profit_factor']
            }
            records.append(record)

        df = pd.DataFrame(records)
        csv_path = self.results_dir / "experiment_results.csv"
        df.to_csv(csv_path, index=False)
        self.logger.info(f"\n实验结果已保存: {csv_path}")

        # 找出最优配置
        df_sorted = df.sort_values('sharpe_ratio', ascending=False)
        self.logger.info("\nTOP 5 配置:")
        for idx, row in df_sorted.head(5).iterrows():
            self.logger.info(f"  {row['description']}: "
                           f"夏普={row['sharpe_ratio']:.3f}, "
                           f"收益={row['annual_return']:.2%}, "
                           f"回撤={row['max_drawdown']:.2%}")

        return df


def main():
    """主函数"""
    optimizer = SimplifiedOptimizer()
    results = optimizer.run_all_experiments()
    df = optimizer.save_results(results)

    print("\n" + "="*60)
    print("简化实验完成！")
    print(f"成功实验: {len(df)} 个")
    print("="*60)


if __name__ == '__main__':
    main()
