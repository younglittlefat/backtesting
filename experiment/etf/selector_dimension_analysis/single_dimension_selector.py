"""
单维度ETF筛选器

基于etf_selector系统，实现按单一维度排序的ETF筛选功能，
用于验证各个评分维度对策略收益的单独贡献效果。
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from etf_selector.selector import TrendETFSelector
from etf_selector.config import FilterConfig
from etf_selector.data_loader import ETFDataLoader
from etf_selector.indicators import calculate_adx, calculate_momentum, calculate_volatility
from etf_selector.unbiased_indicators import (
    calculate_trend_consistency,
    calculate_price_efficiency,
    calculate_liquidity_score
)


class SingleDimensionSelector:
    """单维度ETF筛选器"""

    # 支持的维度列表
    SUPPORTED_DIMENSIONS = [
        'adx_mean',           # ADX趋势强度
        'trend_consistency',  # 趋势一致性
        'price_efficiency',   # 价格发现效率
        'liquidity_score',    # 流动性评分
        'momentum_3m',        # 3个月动量
        'momentum_12m',       # 12个月动量
        'comprehensive'       # 综合评分（作为基准）
    ]

    def __init__(self, config: Optional[FilterConfig] = None):
        """
        初始化单维度筛选器

        Args:
            config: 筛选配置，默认None使用实验配置
        """
        self.config = config or self._create_experiment_config()
        self.data_loader = ETFDataLoader(self.config.data_dir)
        self.selector = TrendETFSelector(self.config, data_loader=self.data_loader)

    def _create_experiment_config(self) -> FilterConfig:
        """创建实验专用配置"""
        config = FilterConfig()

        # 第一级筛选：放宽条件确保有足够候选
        config.min_turnover = 50_000  # 5万元 (50K yuan)
        config.min_listing_days = 180  # 6个月

        # 第二级筛选：基础过滤，不做百分位筛选
        config.min_volatility = 0.15
        config.max_volatility = 0.80
        config.adx_percentile = 0  # 不做ADX百分位筛选，只要>20即可
        config.momentum_min_positive = True  # 要求动量为正
        config.enable_ma_backtest_filter = False  # 不使用收益回撤比筛选

        # 跳过第二级的百分位筛选，直接排序取前N
        config.skip_stage2_percentile_filtering = True
        config.skip_stage2_range_filtering = False  # 仍然应用范围过滤

        # 第三级：跳过相关性优化，直接取前20
        config.target_portfolio_size = 20
        config.max_correlation = 1.0  # 不做相关性筛选

        # 数据路径
        config.data_dir = 'data/chinese_etf'

        return config

    def select_by_dimension(
        self,
        dimension: str,
        target_size: int = 20
    ) -> pd.DataFrame:
        """
        按指定维度进行ETF筛选

        Args:
            dimension: 筛选维度，必须在SUPPORTED_DIMENSIONS中
            target_size: 目标池子大小

        Returns:
            筛选结果DataFrame，包含ETF信息和维度值

        Raises:
            ValueError: 当维度不支持时
        """
        if dimension not in self.SUPPORTED_DIMENSIONS:
            raise ValueError(f"不支持的维度: {dimension}. 支持的维度: {self.SUPPORTED_DIMENSIONS}")

        print(f"\\n=== 开始{dimension}维度筛选 ===")

        # 如果是综合评分，使用标准筛选流程
        if dimension == 'comprehensive':
            return self._select_comprehensive(target_size)

        # 单维度筛选流程
        return self._select_single_dimension(dimension, target_size)

    def _select_comprehensive(self, target_size: int) -> pd.DataFrame:
        """使用综合评分进行筛选（基准组）"""
        print("使用标准综合评分筛选...")

        # 恢复标准配置
        standard_config = FilterConfig()
        standard_config.min_turnover = 50_000  # 5万元 (与单维度保持一致)
        standard_config.min_listing_days = 180
        standard_config.min_volatility = 0.15
        standard_config.max_volatility = 0.80
        standard_config.adx_percentile = 70  # 恢复百分位筛选
        standard_config.momentum_min_positive = True
        standard_config.target_portfolio_size = target_size
        standard_config.data_dir = 'data/chinese_etf'

        standard_selector = TrendETFSelector(standard_config, data_loader=self.data_loader)
        results_list = standard_selector.run_pipeline()

        # 将List转换为DataFrame，并添加维度标识
        results = pd.DataFrame(results_list)
        results['dimension'] = 'comprehensive'
        if 'final_score' in results.columns:
            results['dimension_value'] = results['final_score']
        else:
            results['dimension_value'] = np.nan

        print(f"综合评分筛选完成，共{len(results)}只ETF")
        return results

    def _select_single_dimension(self, dimension: str, target_size: int) -> pd.DataFrame:
        """按单一维度进行筛选"""
        print(f"开始{dimension}维度单独筛选...")

        # 第一级：基础筛选（流动性 + 上市时间）
        print("第一级：基础筛选...")
        etf_list = self.data_loader.load_basic_info()
        print(f"初始ETF数量: {len(etf_list)}")

        # 应用基础筛选 - 返回ETF代码列表
        filtered_codes = self.selector._stage1_basic_filter()
        print(f"第一级筛选后: {len(filtered_codes)}只ETF")

        if len(filtered_codes) == 0:
            raise RuntimeError("第一级筛选后没有ETF通过，请检查筛选条件")

        # 转换为ETF信息字典列表
        basic_info_df = self.data_loader.load_basic_info()
        filtered_etf = []
        for code in filtered_codes:
            etf_row = basic_info_df[basic_info_df['ts_code'] == code]
            if len(etf_row) > 0:
                filtered_etf.append(etf_row.iloc[0].to_dict())

        print(f"转换后的ETF信息数量: {len(filtered_etf)}")

        # 第二级：计算指标并排序
        print("第二级：计算指标并按维度排序...")
        metrics_df = self._calculate_dimension_metrics(filtered_etf, dimension)

        # 应用基础范围过滤（波动率、动量等）
        if not self.config.skip_stage2_range_filtering:
            before_count = len(metrics_df)
            metrics_df = self._apply_range_filtering(metrics_df)
            print(f"范围过滤: {before_count} -> {len(metrics_df)}只ETF")

        if len(metrics_df) == 0:
            raise RuntimeError("范围过滤后没有ETF通过，请检查筛选条件")

        # 按指定维度排序（降序，值越大越好）
        dimension_col = self._get_dimension_column(dimension)
        if dimension_col not in metrics_df.columns:
            raise RuntimeError(f"维度列{dimension_col}不存在，可用列: {list(metrics_df.columns)}")

        # 移除无效值并排序
        valid_mask = ~pd.isna(metrics_df[dimension_col])
        metrics_df = metrics_df[valid_mask].copy()
        metrics_df = metrics_df.sort_values(dimension_col, ascending=False)

        print(f"按{dimension_col}排序，有效数据{len(metrics_df)}只")

        # 取前N个
        final_results = metrics_df.head(target_size).copy()

        # 添加维度信息
        final_results['dimension'] = dimension
        final_results['dimension_value'] = final_results[dimension_col]
        final_results['rank'] = range(1, len(final_results) + 1)

        print(f"{dimension}维度筛选完成，最终{len(final_results)}只ETF")
        print(f"维度值范围: {final_results[dimension_col].min():.4f} - {final_results[dimension_col].max():.4f}")

        return final_results

    def _get_dimension_column(self, dimension: str) -> str:
        """获取维度对应的数据列名"""
        dimension_mapping = {
            'adx_mean': 'adx_mean',
            'trend_consistency': 'trend_consistency',
            'price_efficiency': 'price_efficiency',
            'liquidity_score': 'liquidity_score',
            'momentum_3m': 'momentum_3m',
            'momentum_12m': 'momentum_12m'
        }
        return dimension_mapping[dimension]

    def _calculate_dimension_metrics(self, etf_list: List[Dict], dimension: str) -> pd.DataFrame:
        """计算指定维度的指标"""
        results = []

        print(f"计算{dimension}维度指标...")
        for i, etf_info in enumerate(etf_list):
            if (i + 1) % 50 == 0:
                print(f"  处理进度: {i+1}/{len(etf_list)}")

            ts_code = etf_info['ts_code']

            try:
                # 加载ETF数据
                data = self.data_loader.load_etf_daily(ts_code, use_adj=True)
                if data is None or len(data) < 252:  # 需要至少1年数据
                    continue

                # 计算基础指标
                metrics = {
                    'ts_code': ts_code,
                    'name': etf_info['name'],
                    'industry': etf_info.get('industry', '其他')
                }

                # 根据需要的维度计算指标
                if dimension == 'adx_mean':
                    adx_values = calculate_adx(data['adj_high'], data['adj_low'], data['adj_close'], period=self.config.adx_period)
                    if len(adx_values) > 0:
                        metrics['adx_mean'] = float(pd.Series(adx_values).tail(self.config.adx_lookback_days).mean())

                elif dimension == 'trend_consistency':
                    metrics['trend_consistency'] = calculate_trend_consistency(
                        data['adj_close'], window=self.config.trend_consistency_window
                    )

                elif dimension == 'price_efficiency':
                    metrics['price_efficiency'] = calculate_price_efficiency(
                        data['adj_close'], data['volume'], window=self.config.price_efficiency_window
                    )

                elif dimension == 'liquidity_score':
                    metrics['liquidity_score'] = calculate_liquidity_score(
                        data['volume'], data['adj_close'], window=self.config.liquidity_score_window
                    )

                elif dimension in ['momentum_3m', 'momentum_12m']:
                    mom = calculate_momentum(data['adj_close'], self.config.momentum_periods)
                    if mom is not None:
                        metrics['momentum_3m'] = mom.get('63d', 0)
                        metrics['momentum_12m'] = mom.get('252d', 0)

                # 无论什么维度，都计算波动率（用于范围过滤）
                returns = data['adj_close'].pct_change().dropna()
                volatility = calculate_volatility(returns, self.config.volatility_lookback_days)
                if volatility is not None:
                    metrics['volatility'] = volatility

                # 计算ADX（用于基础过滤，即使不是主要维度）
                if dimension != 'adx_mean':
                    adx_values = calculate_adx(data['adj_high'], data['adj_low'], data['adj_close'], period=self.config.adx_period)
                    if len(adx_values) > 0:
                        metrics['adx_mean'] = float(pd.Series(adx_values).tail(self.config.adx_lookback_days).mean())

                # 计算动量（用于基础过滤）
                if dimension not in ['momentum_3m', 'momentum_12m']:
                    mom = calculate_momentum(data['adj_close'], self.config.momentum_periods)
                    if mom is not None:
                        metrics['momentum_3m'] = mom.get('63d', 0)
                        metrics['momentum_12m'] = mom.get('252d', 0)

                results.append(metrics)

            except Exception as e:
                print(f"  计算{ts_code}指标失败: {e}")
                continue

        df = pd.DataFrame(results)
        print(f"成功计算{len(df)}只ETF的{dimension}指标")

        return df

    def _apply_range_filtering(self, df: pd.DataFrame) -> pd.DataFrame:
        """应用范围过滤（波动率、动量、ADX基础过滤）"""
        initial_count = len(df)

        # 波动率过滤
        if 'volatility' in df.columns:
            before = len(df)
            df = df[
                (df['volatility'] >= self.config.min_volatility) &
                (df['volatility'] <= self.config.max_volatility)
            ].copy()
            print(f"  波动率过滤: {before} -> {len(df)}")

        # ADX基础过滤（>20）
        if 'adx_mean' in df.columns:
            before = len(df)
            df = df[df['adx_mean'] > 20].copy()
            print(f"  ADX基础过滤(>20): {before} -> {len(df)}")

        # 动量正值过滤
        if self.config.momentum_min_positive and 'momentum_3m' in df.columns:
            before = len(df)
            df = df[df['momentum_3m'] > 0].copy()
            print(f"  3M动量正值过滤: {before} -> {len(df)}")

        print(f"范围过滤总计: {initial_count} -> {len(df)}")
        return df

    def batch_select_all_dimensions(self, target_size: int = 20) -> Dict[str, pd.DataFrame]:
        """批量执行所有维度的筛选"""
        results = {}

        print("\\n=== 开始批量维度筛选 ===")
        print(f"目标池子大小: {target_size}")
        print(f"筛选维度: {self.SUPPORTED_DIMENSIONS}")

        for dimension in self.SUPPORTED_DIMENSIONS:
            try:
                print(f"\\n--- 执行{dimension}维度筛选 ---")
                result = self.select_by_dimension(dimension, target_size)
                results[dimension] = result
                print(f"✅ {dimension}筛选成功: {len(result)}只ETF")

                # 显示前5只ETF
                if len(result) > 0:
                    print("前5只ETF:")
                    display_cols = ['ts_code', 'name', 'dimension_value']
                    for col in display_cols:
                        if col in result.columns:
                            for i in range(min(5, len(result))):
                                row = result.iloc[i]
                                if i == 0:
                                    print(f"  {col}: {row[col]}")
                                else:
                                    print(f"  {' ' * len(col)}: {row[col]}")

            except Exception as e:
                print(f"❌ {dimension}筛选失败: {e}")
                results[dimension] = pd.DataFrame()  # 空结果
                continue

        success_count = sum(1 for df in results.values() if len(df) > 0)
        print(f"\\n=== 批量筛选完成 ===")
        print(f"成功: {success_count}/{len(self.SUPPORTED_DIMENSIONS)}个维度")

        return results

    def save_results(
        self,
        results: Dict[str, pd.DataFrame],
        output_dir: str = "results/stock_lists"
    ) -> Dict[str, str]:
        """保存筛选结果到CSV文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = {}

        for dimension, df in results.items():
            if len(df) == 0:
                print(f"⚠️ {dimension}维度结果为空，跳过保存")
                continue

            # 准备保存的列
            save_columns = ['ts_code', 'name', 'industry', 'dimension_value', 'rank']
            # 只保留存在的列
            available_columns = [col for col in save_columns if col in df.columns]
            save_df = df[available_columns].copy()

            # 文件名
            filename = f"dimension_{dimension}_etf_pool.csv"
            filepath = output_dir / filename

            # 保存文件
            save_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            saved_files[dimension] = str(filepath)
            print(f"✅ {dimension}维度结果已保存: {filepath}")

        print(f"\\n共保存{len(saved_files)}个文件")
        return saved_files


def main():
    """测试单维度筛选器"""
    print("=== ETF单维度筛选器测试 ===")

    try:
        # 初始化筛选器
        selector = SingleDimensionSelector()

        # 测试单个维度
        print("\\n--- 测试ADX维度筛选 ---")
        adx_results = selector.select_by_dimension('adx_mean', target_size=10)
        print(f"ADX维度筛选结果: {len(adx_results)}只ETF")
        if len(adx_results) > 0:
            print(adx_results[['ts_code', 'name', 'adx_mean']].head())

        # 测试批量筛选（小规模）
        print("\\n--- 测试批量维度筛选 ---")
        all_results = selector.batch_select_all_dimensions(target_size=5)

        # 保存结果
        output_dir = Path(__file__).parent / "results" / "stock_lists"
        saved_files = selector.save_results(all_results, str(output_dir))

        print(f"\\n=== 测试完成 ===")
        print(f"保存的文件: {list(saved_files.values())}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()