"""
组合优化模块

实现第三级筛选：相关性分析和低相关性组合构建
核心功能：
1. 计算ETF收益率相关系数矩阵
2. 基于相关性构建分散化组合
3. 考虑行业分散和权重平衡
4. 提供组合风险度量
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from .data_loader import ETFDataLoader
from .config import IndustryKeywords


class PortfolioOptimizer:
    """组合优化器

    基于相关性分析构建低相关性、分散化的ETF组合

    Example:
        >>> optimizer = PortfolioOptimizer()
        >>> final_portfolio = optimizer.optimize_portfolio(
        ...     etf_candidates,
        ...     max_correlation=0.7,
        ...     target_size=20
        >>> )
        >>> print(f"优化后组合: {len(final_portfolio)} 只ETF")
    """

    def __init__(
        self,
        data_loader: Optional[ETFDataLoader] = None,
        data_dir: str = 'data/csv'
    ):
        """初始化组合优化器

        Args:
            data_loader: 数据加载器，默认None自动创建
            data_dir: 数据目录，仅在data_loader为None时使用
        """
        self.data_loader = data_loader if data_loader is not None else ETFDataLoader(data_dir)
        self.industry_classifier = IndustryKeywords()

        # 缓存收益率数据
        self._returns_cache = {}

    def calculate_returns_matrix(
        self,
        etf_codes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_periods: int = 100
    ) -> pd.DataFrame:
        """计算ETF收益率矩阵

        Args:
            etf_codes: ETF代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            min_periods: 最小数据期数，少于此值的ETF将被跳过

        Returns:
            收益率矩阵DataFrame，index为日期，columns为ETF代码
        """
        returns_dict = {}

        for ts_code in etf_codes:
            try:
                # 加载ETF日线数据
                data = self.data_loader.load_etf_daily(
                    ts_code, start_date=start_date, end_date=end_date, use_adj=True
                )

                if len(data) < min_periods:
                    continue

                # 计算日收益率
                returns = data['adj_close'].pct_change().dropna()

                if len(returns) < min_periods:
                    continue

                returns_dict[ts_code] = returns

            except (FileNotFoundError, ValueError, KeyError) as e:
                warnings.warn(f"加载 {ts_code} 收益率数据失败: {e}")
                continue

        if not returns_dict:
            return pd.DataFrame()

        # 构建收益率矩阵，对齐日期
        returns_df = pd.DataFrame(returns_dict)

        # 删除全为NaN的日期
        returns_df = returns_df.dropna(how='all')

        return returns_df

    def calculate_correlation_matrix(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """计算相关系数矩阵

        Args:
            returns_df: 收益率矩阵

        Returns:
            相关系数矩阵DataFrame
        """
        if returns_df.empty:
            return pd.DataFrame()

        # 计算Pearson相关系数
        correlation_matrix = returns_df.corr()

        # 将对角线设为0（避免自相关影响）
        np.fill_diagonal(correlation_matrix.values, 0)

        return correlation_matrix

    def optimize_portfolio(
        self,
        etf_candidates: List[Dict],
        max_correlation: float = 0.7,
        target_size: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        balance_industries: bool = True,
        verbose: bool = True
    ) -> List[Dict]:
        """组合优化：构建低相关性、分散化组合

        Args:
            etf_candidates: ETF候选列表，每个元素包含ts_code, name, industry等信息
            max_correlation: 最大相关系数阈值
            target_size: 目标组合大小
            start_date: 收益率计算开始日期
            end_date: 收益率计算结束日期
            balance_industries: 是否平衡行业分布
            verbose: 是否打印详细信息

        Returns:
            优化后的ETF组合列表，按原排序保持
        """
        if len(etf_candidates) == 0:
            return []

        if verbose:
            print("🔧 第三级优化：相关性分析和组合构建")
            print(f"  📊 候选ETF数量: {len(etf_candidates)}")
            print(f"  🎯 目标组合大小: {target_size}")
            print(f"  📈 相关性阈值: < {max_correlation}")

        # 提取ETF代码
        etf_codes = [etf['ts_code'] for etf in etf_candidates]

        # 计算收益率矩阵
        if verbose:
            print(f"  📊 计算收益率矩阵...")

        returns_df = self.calculate_returns_matrix(
            etf_codes, start_date=start_date, end_date=end_date
        )

        if returns_df.empty:
            if verbose:
                print("  ❌ 无法获取足够的收益率数据")
            return etf_candidates[:target_size]  # 降级到直接截取

        # 计算相关系数矩阵
        correlation_matrix = self.calculate_correlation_matrix(returns_df)

        if correlation_matrix.empty:
            return etf_candidates[:target_size]

        if verbose:
            print(f"  ✅ 相关性矩阵计算完成 ({correlation_matrix.shape[0]}x{correlation_matrix.shape[1]})")

        # 贪心算法选择低相关性组合
        selected_portfolio = self._greedy_selection(
            etf_candidates, correlation_matrix, max_correlation, target_size
        )

        if verbose:
            print(f"  🎯 贪心选择完成: {len(selected_portfolio)} 只ETF")

        # 行业平衡优化（如果启用）
        if balance_industries and len(selected_portfolio) > target_size:
            selected_portfolio = self._balance_industries(selected_portfolio, target_size)
            if verbose:
                print(f"  ⚖️ 行业平衡完成: {len(selected_portfolio)} 只ETF")

        # 更新排名信息
        for i, etf in enumerate(selected_portfolio):
            etf['final_rank'] = i + 1

        if verbose:
            print(f"  ✅ 组合优化完成！最终选出 {len(selected_portfolio)} 只ETF")

            # 打印行业分布
            industry_count = {}
            for etf in selected_portfolio:
                industry = etf.get('industry', '其他')
                industry_count[industry] = industry_count.get(industry, 0) + 1

            print(f"  📊 行业分布: {dict(industry_count)}")

            # 打印平均相关性
            if len(selected_portfolio) > 1:
                portfolio_codes = [etf['ts_code'] for etf in selected_portfolio]
                portfolio_corr = correlation_matrix.loc[portfolio_codes, portfolio_codes]
                avg_corr = portfolio_corr.values[portfolio_corr.values != 0].mean()
                print(f"  📈 平均相关性: {avg_corr:.3f}")

        return selected_portfolio

    def _greedy_selection(
        self,
        etf_candidates: List[Dict],
        correlation_matrix: pd.DataFrame,
        max_correlation: float,
        target_size: int
    ) -> List[Dict]:
        """贪心算法选择低相关性ETF组合

        算法逻辑：
        1. 选择收益回撤比最高的ETF作为起点
        2. 依次选择与已选ETF相关性最低的候选ETF
        3. 如果相关性超过阈值，跳过该ETF
        4. 重复直到达到目标数量

        Args:
            etf_candidates: ETF候选列表（已按收益回撤比排序）
            correlation_matrix: 相关系数矩阵
            max_correlation: 最大相关系数阈值
            target_size: 目标组合大小

        Returns:
            选中的ETF列表
        """
        selected = []

        # 第一步：选择排名第一的ETF作为起点
        if etf_candidates[0]['ts_code'] in correlation_matrix.index:
            selected.append(etf_candidates[0])

        # 第二步：贪心选择剩余ETF
        for etf in etf_candidates[1:]:
            if len(selected) >= target_size:
                break

            ts_code = etf['ts_code']

            # 检查该ETF是否在相关性矩阵中
            if ts_code not in correlation_matrix.index:
                continue

            # 计算与已选ETF的平均相关性
            selected_codes = [s['ts_code'] for s in selected]

            try:
                correlations = correlation_matrix.loc[ts_code, selected_codes]
                if isinstance(correlations, pd.Series):
                    avg_correlation = correlations.abs().mean()
                else:
                    # 单个值的情况
                    avg_correlation = abs(correlations)

                # 如果平均相关性低于阈值，加入组合
                if avg_correlation < max_correlation:
                    selected.append(etf)

            except (KeyError, IndexError):
                # 如果出现索引错误，跳过该ETF
                continue

        return selected

    def _balance_industries(
        self,
        etf_list: List[Dict],
        target_size: int
    ) -> List[Dict]:
        """行业平衡优化

        在保持收益回撤比排序的基础上，适当平衡行业分布

        Args:
            etf_list: ETF列表
            target_size: 目标组合大小

        Returns:
            平衡后的ETF列表
        """
        if len(etf_list) <= target_size:
            return etf_list

        # 统计行业分布
        industry_etfs = {}
        for etf in etf_list:
            industry = etf.get('industry', '其他')
            if industry not in industry_etfs:
                industry_etfs[industry] = []
            industry_etfs[industry].append(etf)

        # 计算行业权重目标（均匀分布）
        num_industries = len(industry_etfs)
        target_per_industry = target_size // num_industries
        remainder = target_size % num_industries

        balanced_portfolio = []

        # 为每个行业分配ETF
        industry_names = sorted(industry_etfs.keys())
        for i, industry in enumerate(industry_names):
            # 该行业的目标数量
            industry_target = target_per_industry + (1 if i < remainder else 0)
            industry_target = min(industry_target, len(industry_etfs[industry]))

            # 选择该行业中排名最高的ETF
            balanced_portfolio.extend(industry_etfs[industry][:industry_target])

        # 按原始排序重新排列
        original_order = {etf['ts_code']: i for i, etf in enumerate(etf_list)}
        balanced_portfolio.sort(key=lambda x: original_order.get(x['ts_code'], float('inf')))

        return balanced_portfolio[:target_size]

    def analyze_portfolio_risk(
        self,
        portfolio: List[Dict],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """分析组合风险特征

        Args:
            portfolio: ETF组合列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            风险分析结果字典
        """
        if len(portfolio) == 0:
            return {}

        # 获取组合收益率矩阵
        portfolio_codes = [etf['ts_code'] for etf in portfolio]
        returns_df = self.calculate_returns_matrix(
            portfolio_codes, start_date=start_date, end_date=end_date
        )

        if returns_df.empty:
            return {'error': '无法获取组合收益率数据'}

        # 计算风险指标
        correlation_matrix = self.calculate_correlation_matrix(returns_df)

        # 平均相关性（去除对角线）
        correlation_values = correlation_matrix.values
        correlation_values = correlation_values[correlation_values != 0]  # 去除对角线0值
        avg_correlation = np.mean(np.abs(correlation_values)) if len(correlation_values) > 0 else 0

        # 组合日收益率（等权重）
        portfolio_returns = returns_df.mean(axis=1)

        # 年化波动率
        portfolio_volatility = portfolio_returns.std() * np.sqrt(252)

        # 最大相关性
        max_correlation = np.max(np.abs(correlation_values)) if len(correlation_values) > 0 else 0

        # 行业分布
        industry_distribution = {}
        for etf in portfolio:
            industry = etf.get('industry', '其他')
            industry_distribution[industry] = industry_distribution.get(industry, 0) + 1

        return {
            'portfolio_size': len(portfolio),
            'avg_correlation': avg_correlation,
            'max_correlation': max_correlation,
            'portfolio_volatility': portfolio_volatility,
            'industry_distribution': industry_distribution,
            'diversification_ratio': len(industry_distribution) / len(portfolio),
        }

    def export_portfolio_analysis(
        self,
        portfolio: List[Dict],
        output_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> None:
        """导出组合分析报告

        Args:
            portfolio: ETF组合列表
            output_path: 输出文件路径
            start_date: 分析开始日期
            end_date: 分析结束日期
        """
        # 组合基本信息
        portfolio_df = pd.DataFrame(portfolio)

        # 风险分析
        risk_analysis = self.analyze_portfolio_risk(
            portfolio, start_date=start_date, end_date=end_date
        )

        # 确保输出目录存在
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 导出组合详情
        timestamp = datetime.now().strftime('%Y%m%d')
        if not output_path.stem.endswith(timestamp[:8]):
            stem = output_path.stem + f'_{timestamp}'
            output_path = output_path.with_stem(stem)

        # 导出CSV
        portfolio_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        # 导出分析报告
        analysis_path = output_path.with_suffix('.analysis.txt')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write(f"ETF组合风险分析报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"分析期间: {start_date or '全部'} 至 {end_date or '全部'}\n")
            f.write(f"{'='*50}\n\n")

            f.write(f"组合规模: {risk_analysis.get('portfolio_size', 0)} 只ETF\n")
            f.write(f"平均相关性: {risk_analysis.get('avg_correlation', 0):.3f}\n")
            f.write(f"最大相关性: {risk_analysis.get('max_correlation', 0):.3f}\n")
            f.write(f"组合波动率: {risk_analysis.get('portfolio_volatility', 0):.2%}\n")
            f.write(f"行业分散度: {risk_analysis.get('diversification_ratio', 0):.2f}\n\n")

            f.write("行业分布:\n")
            industry_dist = risk_analysis.get('industry_distribution', {})
            for industry, count in sorted(industry_dist.items()):
                f.write(f"  {industry}: {count} 只\n")

        print(f"✅ 组合分析已导出:")
        print(f"  📄 组合详情: {output_path}")
        print(f"  📊 风险分析: {analysis_path}")