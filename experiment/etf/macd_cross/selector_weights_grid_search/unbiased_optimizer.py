#!/usr/bin/env python3
"""
无偏权重优化器

执行方案B：无偏评分验证实验
完全去除动量指标，仅使用无偏技术指标进行ETF筛选，
配合MACD参数优化和止损保护，验证去偏差方法的效果。
"""
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yaml

# 添加项目根目录到path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from etf_selector.config import FilterConfig
from etf_selector.selector import TrendETFSelector
from experiment.etf.macd_cross.selector_weights_grid_search.backtest_manager import BacktestManager
from experiment.etf.macd_cross.selector_weights_grid_search.parameter_generator import UnbiasedWeightsGenerator


class UnbiasedOptimizer:
    """无偏权重优化器"""

    def __init__(
        self,
        project_root: str = "/mnt/d/git/backtesting",
        experiment_dir: Optional[str] = None
    ):
        """
        初始化优化器

        Args:
            project_root: 项目根目录
            experiment_dir: 实验目录，默认使用当前脚本所在目录
        """
        self.project_root = Path(project_root)

        if experiment_dir is None:
            self.experiment_dir = Path(__file__).parent
        else:
            self.experiment_dir = Path(experiment_dir)

        # 设置输出目录
        self.results_dir = self.experiment_dir / "results" / "unbiased"
        self.temp_dir = self.experiment_dir / "temp"
        self.checkpoint_file = self.results_dir / "checkpoint.json"

        # 创建目录
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.backtest_manager = BacktestManager(project_root=str(self.project_root))
        self.generator = UnbiasedWeightsGenerator()

        # 设置日志
        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        log_dir = self.experiment_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"unbiased_experiment_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"日志文件: {log_file}")

    def run_etf_selector(
        self,
        weights: Dict[str, float],
        target_size: int = 20
    ) -> Optional[str]:
        """
        运行ETF筛选器

        Args:
            weights: 权重配置字典
            target_size: 目标筛选数量

        Returns:
            标的池CSV文件路径，失败返回None
        """
        try:
            # 创建自定义配置
            # 注意：即使secondary_weight=0，momentum权重也必须和为1（虽然不会被使用）
            config = FilterConfig(
                enable_unbiased_scoring=True,
                primary_weight=weights.get('primary_weight', 1.0),
                secondary_weight=weights.get('secondary_weight', 0.0),
                adx_score_weight=weights['adx_weight'],
                trend_consistency_weight=weights['trend_consistency_weight'],
                price_efficiency_weight=weights['price_efficiency_weight'],
                liquidity_score_weight=weights['liquidity_weight'],
                momentum_3m_score_weight=0.5,  # 固定值，和为1（虽然secondary_weight=0时不使用）
                momentum_12m_score_weight=0.5,  # 固定值，和为1（虽然secondary_weight=0时不使用）
                target_portfolio_size=target_size,
                data_dir='data/chinese_etf',
                min_turnover=1_000_000,  # 100万元（0.01亿） - 降低流动性要求以获得足够标的
                min_volatility=0.10,  # 降低波动率下限
                max_volatility=1.00,  # 提高波动率上限
                adx_percentile=10,  # 只要在前90%即可 - 进一步放宽以获得足够标的（约15-20只）
                enable_ma_backtest_filter=False
            )

            # 创建筛选器
            selector = TrendETFSelector(
                config=config,
                data_dir=str(self.project_root / "data" / "chinese_etf")
            )

            # 执行筛选
            self.logger.info("开始ETF筛选...")
            selected_etfs = selector.run_pipeline(
                start_date="2023-11-01",
                end_date="2025-11-01",
                target_size=target_size,
                verbose=False
            )

            if not selected_etfs or len(selected_etfs) < 10:
                self.logger.warning(f"筛选出的ETF数量不足: {len(selected_etfs)}")
                return None

            # 保存到临时CSV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_csv = self.temp_dir / f"etf_pool_{timestamp}.csv"

            # 转换为DataFrame
            df = pd.DataFrame(selected_etfs)
            df.to_csv(temp_csv, index=False)

            self.logger.info(f"筛选完成，共 {len(selected_etfs)} 只ETF，保存到: {temp_csv}")
            return str(temp_csv)

        except Exception as e:
            self.logger.error(f"ETF筛选失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None

    def run_single_experiment(
        self,
        experiment_id: int,
        weights: Dict[str, float]
    ) -> Dict:
        """
        运行单个实验

        Args:
            experiment_id: 实验编号
            weights: 权重配置

        Returns:
            实验结果字典
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"实验 {experiment_id}: 权重配置")
        self.logger.info(f"  ADX: {weights['adx_weight']:.2f}")
        self.logger.info(f"  趋势一致性: {weights['trend_consistency_weight']:.2f}")
        self.logger.info(f"  价格效率: {weights['price_efficiency_weight']:.2f}")
        self.logger.info(f"  流动性: {weights['liquidity_weight']:.2f}")
        self.logger.info(f"{'='*60}")

        result = {
            'experiment_id': experiment_id,
            'weights': weights,
            'status': 'failed',
            'error': None
        }

        try:
            # 1. 运行ETF筛选
            stock_list_csv = self.run_etf_selector(weights)

            if stock_list_csv is None:
                result['error'] = "ETF筛选失败"
                return result

            # 2. 执行MACD增强策略回测
            self.logger.info("开始MACD增强策略回测...")
            backtest_result = self.backtest_manager.run_backtest(
                stock_list_csv=stock_list_csv,
                strategy="macd_cross",  # 使用macd_cross策略（带止损保护）
                enable_loss_protection=True,
                max_consecutive_losses=3,
                pause_bars=10,
                optimize=True,
                data_dir="data/chinese_etf/daily"
            )

            # 3. 记录结果
            result['status'] = 'success'
            result['etf_count'] = backtest_result['num_stocks']
            result['sharpe_ratio'] = backtest_result['sharpe_ratio']
            result['sharpe_ratio_median'] = backtest_result['sharpe_ratio_median']
            result['annual_return'] = backtest_result['annual_return']
            result['annual_return_median'] = backtest_result['annual_return_median']
            result['max_drawdown'] = backtest_result['max_drawdown']
            result['max_drawdown_worst'] = backtest_result['max_drawdown_worst']
            result['win_rate'] = backtest_result['win_rate']
            result['profit_factor'] = backtest_result['profit_factor']
            result['num_trades'] = backtest_result['num_trades']

            self.logger.info(f"✓ 实验 {experiment_id} 完成")
            self.logger.info(f"  夏普比率: {result['sharpe_ratio']:.3f}")
            self.logger.info(f"  年化收益: {result['annual_return']:.2%}")
            self.logger.info(f"  最大回撤: {result['max_drawdown']:.2%}")
            self.logger.info(f"  胜率: {result['win_rate']:.2%}")

        except Exception as e:
            self.logger.error(f"实验 {experiment_id} 失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            result['error'] = str(e)

        return result

    def load_checkpoint(self) -> List[Dict]:
        """加载检查点"""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
                self.logger.info(f"从检查点恢复，已完成 {len(data['results'])} 个实验")
                return data['results']
        return []

    def save_checkpoint(self, results: List[Dict]):
        """保存检查点"""
        with open(self.checkpoint_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'completed_count': len(results),
                'results': results
            }, f, indent=2)
        self.logger.info(f"检查点已保存: {len(results)} 个实验")

    def run_all_experiments(
        self,
        checkpoint_interval: int = 10
    ) -> List[Dict]:
        """
        运行所有实验

        Args:
            checkpoint_interval: 检查点保存间隔

        Returns:
            所有实验结果列表
        """
        # 生成参数组合
        combinations = self.generator.generate_combinations()
        total_count = len(combinations)

        self.logger.info(f"开始方案B实验: 共 {total_count} 个无偏权重组合")

        # 加载已完成的实验
        results = self.load_checkpoint()
        completed_ids = {r['experiment_id'] for r in results}

        # 执行实验
        for i, weights in enumerate(combinations):
            if i in completed_ids:
                self.logger.info(f"跳过已完成的实验 {i}")
                continue

            start_time = time.time()

            # 运行单个实验
            result = self.run_single_experiment(i, weights)
            results.append(result)

            elapsed = time.time() - start_time
            self.logger.info(f"实验 {i} 耗时: {elapsed:.1f}秒")

            # 定期保存检查点
            if (i + 1) % checkpoint_interval == 0:
                self.save_checkpoint(results)

            # 预估剩余时间
            remaining = total_count - len(results)
            if remaining > 0:
                avg_time = elapsed
                est_remaining = avg_time * remaining / 60
                self.logger.info(f"预计剩余时间: {est_remaining:.1f}分钟")

        # 最终保存
        self.save_checkpoint(results)

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"所有实验完成！总计: {len(results)} 个")
        self.logger.info(f"{'='*60}")

        return results

    def save_results(self, results: List[Dict]):
        """
        保存实验结果到CSV

        Args:
            results: 实验结果列表
        """
        # 转换为DataFrame
        records = []
        for r in results:
            if r['status'] != 'success':
                continue

            record = {
                'experiment_id': r['experiment_id'],
                'adx_weight': r['weights']['adx_weight'],
                'trend_consistency_weight': r['weights']['trend_consistency_weight'],
                'price_efficiency_weight': r['weights']['price_efficiency_weight'],
                'liquidity_weight': r['weights']['liquidity_weight'],
                'momentum_3m_weight': r['weights']['momentum_3m_weight'],
                'momentum_12m_weight': r['weights']['momentum_12m_weight'],
                'etf_count': r['etf_count'],
                'sharpe_ratio': r['sharpe_ratio'],
                'sharpe_ratio_median': r['sharpe_ratio_median'],
                'annual_return': r['annual_return'],
                'annual_return_median': r['annual_return_median'],
                'max_drawdown': r['max_drawdown'],
                'max_drawdown_worst': r['max_drawdown_worst'],
                'win_rate': r['win_rate'],
                'profit_factor': r['profit_factor'],
                'num_trades': r['num_trades']
            }
            records.append(record)

        df = pd.DataFrame(records)

        # 保存CSV
        csv_path = self.results_dir / "experiment_results.csv"
        df.to_csv(csv_path, index=False)
        self.logger.info(f"实验结果已保存: {csv_path}")

        # 找出最优配置（按夏普比率排序）
        df_sorted = df.sort_values('sharpe_ratio', ascending=False)
        top5 = df_sorted.head(5)

        self.logger.info("\nTOP 5 配置:")
        for idx, row in top5.iterrows():
            self.logger.info(f"  {row['experiment_id']}: 夏普={row['sharpe_ratio']:.3f}, "
                           f"收益={row['annual_return']:.2%}, "
                           f"回撤={row['max_drawdown']:.2%}")

        # 保存最优配置
        best = df_sorted.iloc[0]
        best_config = {
            'experiment_id': int(best['experiment_id']),
            'weights': {
                'adx_weight': float(best['adx_weight']),
                'trend_consistency_weight': float(best['trend_consistency_weight']),
                'price_efficiency_weight': float(best['price_efficiency_weight']),
                'liquidity_weight': float(best['liquidity_weight']),
                'momentum_3m_weight': float(best['momentum_3m_weight']),
                'momentum_12m_weight': float(best['momentum_12m_weight'])
            },
            'performance': {
                'sharpe_ratio': float(best['sharpe_ratio']),
                'annual_return': float(best['annual_return']),
                'max_drawdown': float(best['max_drawdown']),
                'win_rate': float(best['win_rate']),
                'profit_factor': float(best['profit_factor'])
            }
        }

        best_config_path = self.results_dir / "best_weights.json"
        with open(best_config_path, 'w') as f:
            json.dump(best_config, f, indent=2)
        self.logger.info(f"最优配置已保存: {best_config_path}")

        return df, best_config


def main():
    """主函数"""
    optimizer = UnbiasedOptimizer()

    # 运行所有实验
    results = optimizer.run_all_experiments(checkpoint_interval=10)

    # 保存结果
    df, best_config = optimizer.save_results(results)

    print("\n" + "="*60)
    print("方案B实验完成！")
    print(f"成功实验: {len(df)} 个")
    print(f"最优夏普比率: {best_config['performance']['sharpe_ratio']:.3f}")
    print("="*60)


if __name__ == '__main__':
    main()
