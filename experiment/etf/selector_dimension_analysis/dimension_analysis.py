#!/usr/bin/env python3
"""
ETF筛选器单维度效果验证主实验脚本

执行7个维度的独立筛选和KAMA策略回测，分析各维度的单独贡献效果。
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from single_dimension_selector import SingleDimensionSelector


class DimensionAnalysisExperiment:
    """单维度效果验证实验主类"""

    def __init__(self, output_dir: str = None):
        """
        初始化实验

        Args:
            output_dir: 输出目录，默认使用当前目录下的results
        """
        self.experiment_dir = Path(__file__).parent
        self.output_dir = Path(output_dir or self.experiment_dir / "results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 设置日志
        self._setup_logging()

        # 切换到项目根目录（数据路径相对于项目根）
        os.chdir(project_root)
        self.logger.info(f"Working directory: {os.getcwd()}")

        # 初始化筛选器配置
        from etf_selector.config import FilterConfig
        config = FilterConfig()
        config.data_dir = 'data/chinese_etf'  # 确保使用正确的数据路径

        # 初始化筛选器
        self.selector = SingleDimensionSelector(config)

        # 实验配置
        self.target_size = 20
        self.strategy_type = 'kama_cross'
        self.data_dir = 'data/chinese_etf/daily'

        # 实验时间戳
        self.experiment_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.logger.info("=== ETF单维度效果验证实验初始化 ===")
        self.logger.info(f"实验目录: {self.experiment_dir}")
        self.logger.info(f"输出目录: {self.output_dir}")
        self.logger.info(f"目标池子大小: {self.target_size}")

    def _setup_logging(self):
        """设置日志"""
        log_file = self.output_dir / "experiment.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def run_experiment(self) -> Dict[str, Any]:
        """
        运行完整实验流程

        Returns:
            实验结果字典
        """
        self.logger.info("\\n=== 开始完整实验流程 ===")

        try:
            # 第一步：执行筛选
            selection_results = self.run_selection_phase()

            # 第二步：执行回测
            backtest_results = self.run_backtest_phase(selection_results)

            # 第三步：分析结果
            analysis_results = self.run_analysis_phase(backtest_results)

            # 第四步：生成报告
            report_path = self.generate_final_report(analysis_results)

            # 汇总实验结果
            experiment_results = {
                'selection_results': selection_results,
                'backtest_results': backtest_results,
                'analysis_results': analysis_results,
                'report_path': report_path,
                'experiment_time': self.experiment_time,
                'success': True
            }

            self.logger.info("\\n=== 实验完成 ===")
            self.logger.info(f"实验报告: {report_path}")

            return experiment_results

        except Exception as e:
            self.logger.error(f"实验失败: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'experiment_time': self.experiment_time
            }

    def run_selection_phase(self) -> Dict[str, pd.DataFrame]:
        """
        运行筛选阶段：为每个维度生成ETF池

        Returns:
            各维度的筛选结果
        """
        self.logger.info("\\n--- 第一阶段：维度筛选 ---")

        # 执行批量筛选
        selection_results = self.selector.batch_select_all_dimensions(
            target_size=self.target_size
        )

        # 保存筛选结果
        stock_lists_dir = self.output_dir / "stock_lists"
        saved_files = self.selector.save_results(selection_results, str(stock_lists_dir))

        self.logger.info(f"筛选阶段完成，共生成{len(saved_files)}个ETF池")

        # 记录筛选统计
        selection_stats = {}
        for dimension, df in selection_results.items():
            if len(df) > 0:
                selection_stats[dimension] = {
                    'count': len(df),
                    'min_value': df['dimension_value'].min(),
                    'max_value': df['dimension_value'].max(),
                    'mean_value': df['dimension_value'].mean()
                }
            else:
                selection_stats[dimension] = {'count': 0}

        # 保存筛选统计
        stats_file = self.output_dir / "selection_stats.csv"
        pd.DataFrame(selection_stats).T.to_csv(stats_file)
        self.logger.info(f"筛选统计已保存: {stats_file}")

        return selection_results

    def run_backtest_phase(self, selection_results: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        运行回测阶段：对每个ETF池执行KAMA策略回测

        Args:
            selection_results: 筛选结果

        Returns:
            各维度的回测结果
        """
        self.logger.info("\\n--- 第二阶段：策略回测 ---")

        backtest_results = {}
        backtest_dir = self.output_dir / "backtest_results"
        backtest_dir.mkdir(exist_ok=True)

        for dimension, df in selection_results.items():
            if len(df) == 0:
                self.logger.warning(f"⚠️ {dimension}维度筛选结果为空，跳过回测")
                backtest_results[dimension] = {'success': False, 'error': 'Empty selection'}
                continue

            try:
                self.logger.info(f"执行{dimension}维度回测...")

                # 准备ETF列表文件
                etf_list_file = self.output_dir / "stock_lists" / f"dimension_{dimension}_etf_pool.csv"

                # 执行回测
                result = self._run_single_backtest(dimension, str(etf_list_file))
                backtest_results[dimension] = result

                if result['success']:
                    self.logger.info(f"✅ {dimension}回测成功")
                else:
                    self.logger.error(f"❌ {dimension}回测失败: {result.get('error', 'Unknown error')}")

            except Exception as e:
                self.logger.error(f"❌ {dimension}回测异常: {e}")
                backtest_results[dimension] = {'success': False, 'error': str(e)}

        success_count = sum(1 for r in backtest_results.values() if r.get('success', False))
        self.logger.info(f"回测阶段完成: {success_count}/{len(backtest_results)}个维度成功")

        return backtest_results

    def _run_single_backtest(self, dimension: str, etf_list_file: str) -> Dict[str, Any]:
        """
        执行单个维度的回测

        Args:
            dimension: 维度名称
            etf_list_file: ETF列表文件路径

        Returns:
            回测结果
        """
        try:
            # 构建回测命令
            cmd = [
                '/home/zijunliu/miniforge3/condabin/conda', 'run', '-n', 'backtesting',
                'python', str(project_root / "backtest_runner.py"),
                '--stock-list', etf_list_file,
                '--strategy', self.strategy_type,
                '--data-dir', self.data_dir,
                '--output', str(self.output_dir / "backtest_results" / f"dimension_{dimension}"),
                '--save-trades',  # 保存交易记录
                '--save-returns'  # 保存收益序列
            ]

            self.logger.info(f"回测命令: {' '.join(cmd)}")

            # 执行回测
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=3600  # 1小时超时
            )

            if result.returncode == 0:
                # 解析回测结果
                return self._parse_backtest_result(dimension)
            else:
                return {
                    'success': False,
                    'error': f"回测命令失败 (exit code {result.returncode})",
                    'stderr': result.stderr,
                    'stdout': result.stdout
                }

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': '回测超时'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _parse_backtest_result(self, dimension: str) -> Dict[str, Any]:
        """
        解析回测结果文件

        Args:
            dimension: 维度名称

        Returns:
            解析后的回测结果
        """
        try:
            # 寻找结果文件
            result_dir = self.output_dir / "backtest_results" / f"dimension_{dimension}"
            result_files = list(result_dir.glob("*_summary.csv"))

            if not result_files:
                return {'success': False, 'error': '未找到回测结果文件'}

            # 读取最新的结果文件
            result_file = max(result_files, key=lambda x: x.stat().st_mtime)
            df = pd.read_csv(result_file)

            if len(df) == 0:
                return {'success': False, 'error': '回测结果为空'}

            # 提取关键指标
            summary = df.iloc[0]  # 取第一行作为汇总结果

            metrics = {
                'total_return': summary.get('Return [%]', 0),
                'sharpe_ratio': summary.get('Sharpe Ratio', 0),
                'max_drawdown': summary.get('Max. Drawdown [%]', 0),
                'win_rate': summary.get('Win Rate [%]', 0),
                'trades_count': summary.get('# Trades', 0),
                'avg_return': summary.get('Avg. Trade [%]', 0),
                'std_return': summary.get('Std. Trade [%]', 0)
            }

            # 计算Calmar比率
            if metrics['max_drawdown'] != 0:
                metrics['calmar_ratio'] = abs(metrics['total_return'] / metrics['max_drawdown'])
            else:
                metrics['calmar_ratio'] = 0

            return {
                'success': True,
                'metrics': metrics,
                'result_file': str(result_file),
                'dimension': dimension
            }

        except Exception as e:
            return {'success': False, 'error': f'解析结果失败: {str(e)}'}

    def run_analysis_phase(self, backtest_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        运行分析阶段：汇总和对比各维度的表现

        Args:
            backtest_results: 回测结果

        Returns:
            分析结果DataFrame
        """
        self.logger.info("\\n--- 第三阶段：结果分析 ---")

        # 提取成功的回测结果
        analysis_data = []
        for dimension, result in backtest_results.items():
            if result.get('success', False):
                metrics = result['metrics']
                row = {
                    'dimension': dimension,
                    'total_return': metrics['total_return'],
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'max_drawdown': metrics['max_drawdown'],
                    'calmar_ratio': metrics['calmar_ratio'],
                    'win_rate': metrics['win_rate'],
                    'trades_count': metrics['trades_count'],
                    'avg_return': metrics['avg_return'],
                    'std_return': metrics['std_return']
                }
                analysis_data.append(row)
            else:
                # 失败的情况也记录，用NaN填充
                row = {
                    'dimension': dimension,
                    'error': result.get('error', 'Unknown error')
                }
                for metric in ['total_return', 'sharpe_ratio', 'max_drawdown', 'calmar_ratio',
                              'win_rate', 'trades_count', 'avg_return', 'std_return']:
                    row[metric] = np.nan
                analysis_data.append(row)

        # 创建分析DataFrame
        analysis_df = pd.DataFrame(analysis_data)

        # 按夏普比率排序（降序）
        analysis_df = analysis_df.sort_values('sharpe_ratio', ascending=False, na_position='last')
        analysis_df['sharpe_rank'] = range(1, len(analysis_df) + 1)

        # 按总收益排序
        analysis_df_return_sorted = analysis_df.sort_values('total_return', ascending=False, na_position='last')
        analysis_df['return_rank'] = analysis_df_return_sorted.index.map(
            lambda x: analysis_df_return_sorted.index.get_loc(x) + 1
        )

        # 保存分析结果
        analysis_file = self.output_dir / "analysis" / f"dimension_comparison_{self.experiment_time}.csv"
        analysis_file.parent.mkdir(exist_ok=True)
        analysis_df.to_csv(analysis_file, index=False, encoding='utf-8-sig')

        self.logger.info(f"分析结果已保存: {analysis_file}")

        # 打印简要结果
        self.logger.info("\\n=== 维度表现排名 ===")
        self.logger.info("按夏普比率排序:")
        for _, row in analysis_df.iterrows():
            if not pd.isna(row['sharpe_ratio']):
                self.logger.info(f"{row['sharpe_rank']:2d}. {row['dimension']:20s} - "
                               f"夏普:{row['sharpe_ratio']:6.3f}, "
                               f"收益:{row['total_return']:7.2f}%, "
                               f"回撤:{row['max_drawdown']:6.2f}%")

        return analysis_df

    def generate_final_report(self, analysis_df: pd.DataFrame) -> str:
        """
        生成最终实验报告

        Args:
            analysis_df: 分析结果DataFrame

        Returns:
            报告文件路径
        """
        self.logger.info("\\n--- 第四阶段：生成报告 ---")

        report_file = self.output_dir / f"DIMENSION_ANALYSIS_REPORT_{self.experiment_time}.md"

        # 生成报告内容
        report_content = self._generate_report_content(analysis_df)

        # 写入文件
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        self.logger.info(f"实验报告已生成: {report_file}")
        return str(report_file)

    def _generate_report_content(self, analysis_df: pd.DataFrame) -> str:
        """生成报告内容"""
        # 获取最佳维度
        best_sharpe = analysis_df.iloc[0] if len(analysis_df) > 0 else None
        best_return = analysis_df.loc[analysis_df['return_rank'] == 1].iloc[0] if len(analysis_df) > 0 else None

        # 分组统计
        main_indicators = ['adx_mean', 'trend_consistency', 'price_efficiency', 'liquidity_score']
        secondary_indicators = ['momentum_3m', 'momentum_12m']

        # 过滤有效数据
        valid_df = analysis_df[~pd.isna(analysis_df['sharpe_ratio'])]

        report = f"""# ETF筛选器单维度效果验证实验报告

**实验时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**实验版本**: {self.experiment_time}

## 1. 实验概述

### 1.1 实验目标
验证ETF筛选系统中各个评分维度对KAMA自适应策略收益的单独贡献效果，识别关键维度并为权重优化提供依据。

### 1.2 实验设计
- **测试维度**: {len(SingleDimensionSelector.SUPPORTED_DIMENSIONS)}个 ({', '.join(SingleDimensionSelector.SUPPORTED_DIMENSIONS)})
- **池子规模**: {self.target_size}只ETF
- **回测策略**: KAMA自适应均线策略
- **时间窗口**: 2023-11-01 至 2025-11-12
- **成功率**: {len(valid_df)}/{len(analysis_df)} ({len(valid_df)/len(analysis_df)*100:.1f}%)

## 2. 实验结果

### 2.1 维度表现排名

#### 按夏普比率排序
| 排名 | 维度 | 夏普比率 | 总收益(%) | 最大回撤(%) | Calmar比率 | 胜率(%) |
|------|------|---------|-----------|-------------|------------|---------|
"""

        # 添加排名表格
        for _, row in valid_df.iterrows():
            report += f"| {row['sharpe_rank']:2d} | {row['dimension']:20s} | {row['sharpe_ratio']:8.3f} | {row['total_return']:9.2f} | {row['max_drawdown']:11.2f} | {row['calmar_ratio']:10.3f} | {row['win_rate']:7.2f} |\n"

        # 添加关键发现
        if best_sharpe is not None:
            report += f"""

### 2.2 关键发现

**🏆 夏普比率最优维度**: {best_sharpe['dimension']}
- 夏普比率: {best_sharpe['sharpe_ratio']:.3f}
- 总收益: {best_sharpe['total_return']:.2f}%
- 最大回撤: {best_sharpe['max_drawdown']:.2f}%
- 胜率: {best_sharpe['win_rate']:.2f}%

"""

        if best_return is not None and best_return['dimension'] != best_sharpe['dimension']:
            report += f"""**📈 总收益最优维度**: {best_return['dimension']}
- 总收益: {best_return['total_return']:.2f}%
- 夏普比率: {best_return['sharpe_ratio']:.3f}
- 最大回撤: {best_return['max_drawdown']:.2f}%

"""

        # 分组分析
        main_df = valid_df[valid_df['dimension'].isin(main_indicators)]
        secondary_df = valid_df[valid_df['dimension'].isin(secondary_indicators)]

        if len(main_df) > 0:
            report += f"""### 2.3 主要指标分析（无偏技术指标）

- **平均夏普比率**: {main_df['sharpe_ratio'].mean():.3f}
- **平均总收益**: {main_df['total_return'].mean():.2f}%
- **平均回撤**: {main_df['max_drawdown'].mean():.2f}%
- **最佳表现**: {main_df.loc[main_df['sharpe_ratio'].idxmax(), 'dimension']} (夏普比率 {main_df['sharpe_ratio'].max():.3f})

"""

        if len(secondary_df) > 0:
            report += f"""### 2.4 次要指标分析（动量指标）

- **平均夏普比率**: {secondary_df['sharpe_ratio'].mean():.3f}
- **平均总收益**: {secondary_df['total_return'].mean():.2f}%
- **平均回撤**: {secondary_df['max_drawdown'].mean():.2f}%
- **最佳表现**: {secondary_df.loc[secondary_df['sharpe_ratio'].idxmax(), 'dimension']} (夏普比率 {secondary_df['sharpe_ratio'].max():.3f})

"""

        # 验证假设
        report += f"""## 3. 假设验证

### 3.1 核心假设检验

"""

        # H1: ADX表现最好
        adx_row = valid_df[valid_df['dimension'] == 'adx_mean']
        if len(adx_row) > 0:
            adx_rank = adx_row.iloc[0]['sharpe_rank']
            h1_result = "✅ 成立" if adx_rank <= 2 else "❌ 不成立"
            report += f"**H1 - ADX趋势强度表现最优**: {h1_result} (夏普比率排名第{adx_rank}位)\n\n"

        # H2: 动量表现良好但有偏差风险
        if len(secondary_df) > 0:
            momentum_avg_rank = secondary_df['sharpe_rank'].mean()
            h2_result = "✅ 成立" if momentum_avg_rank <= 3 else "⚠️ 部分成立"
            report += f"**H2 - 动量指标表现良好**: {h2_result} (平均排名第{momentum_avg_rank:.1f}位)\n\n"

        # H3: 无偏指标稳健性更强
        if len(main_df) > 0 and len(secondary_df) > 0:
            main_std = main_df['sharpe_ratio'].std()
            secondary_std = secondary_df['sharpe_ratio'].std()
            h3_result = "✅ 成立" if main_std < secondary_std else "❌ 不成立"
            report += f"**H3 - 无偏指标更稳健**: {h3_result} (主要指标标准差 {main_std:.3f} vs 次要指标 {secondary_std:.3f})\n\n"

        # 实际建议
        report += """## 4. 实用建议

### 4.1 权重优化建议

"""

        if len(valid_df) >= 3:
            top3_dimensions = valid_df.head(3)['dimension'].tolist()
            report += f"**推荐重点关注维度**:\n"
            for i, dim in enumerate(top3_dimensions, 1):
                report += f"{i}. {dim}\n"
            report += "\n"

        # 结论
        if best_sharpe is not None:
            report += f"""### 4.2 配置建议

基于实验结果，建议：

1. **提升{best_sharpe['dimension']}权重** - 作为表现最优的维度
2. **保持技术指标主导地位** - 无偏指标整体表现稳健
3. **适度降低低表现维度权重** - 优化整体配置效率

### 4.3 后续优化方向

1. 基于本实验结果调整权重配置
2. 考虑组合效应的进一步实验
3. 验证结果在不同市场环境下的稳定性

"""

        # 技术附录
        report += f"""## 5. 技术附录

### 5.1 实验配置
- 项目根目录: {project_root}
- 数据目录: {self.data_dir}
- 输出目录: {self.output_dir}
- 策略类型: {self.strategy_type}

### 5.2 文件清单
- 筛选结果: `stock_lists/dimension_*_etf_pool.csv`
- 回测结果: `backtest_results/dimension_*/`
- 分析数据: `analysis/dimension_comparison_{self.experiment_time}.csv`

---

**实验完成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**报告生成**: ETF筛选器单维度效果验证实验系统
"""

        return report


def main():
    """主函数"""
    print("=== ETF筛选器单维度效果验证实验 ===")

    try:
        # 创建实验实例
        experiment = DimensionAnalysisExperiment()

        # 运行完整实验
        results = experiment.run_experiment()

        if results['success']:
            print(f"\\n🎉 实验成功完成！")
            print(f"📊 实验报告: {results['report_path']}")
            print(f"📁 输出目录: {experiment.output_dir}")

            # 显示简要结果
            if 'analysis_results' in results:
                analysis_df = results['analysis_results']
                valid_df = analysis_df[~pd.isna(analysis_df['sharpe_ratio'])]
                if len(valid_df) > 0:
                    best_dim = valid_df.iloc[0]
                    print(f"\\n🏆 最优维度: {best_dim['dimension']}")
                    print(f"   夏普比率: {best_dim['sharpe_ratio']:.3f}")
                    print(f"   总收益: {best_dim['total_return']:.2f}%")
        else:
            print(f"\\n❌ 实验失败: {results.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ 实验异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()