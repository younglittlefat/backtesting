"""
核心筛选器

实现三级漏斗ETF筛选系统：
1. 第一级：初级筛选（流动性、上市时间）
2. 第二级：核心筛选（ADX、双均线回测、波动率、动量）
3. 第三级：组合优化（相关性分析）
"""
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import FilterConfig, IndustryKeywords
from .data_loader import ETFDataLoader
from .indicators import (
    calculate_rolling_adx_mean,
    calculate_volatility,
    calculate_momentum,
    calculate_excess_return,
    calculate_trend_r2,
    calculate_volume_trend,
    calculate_idr,
)
from .backtest_engine import calculate_backtest_metrics
from .unbiased_indicators import calculate_all_unbiased_indicators
from .scoring import (
    UnbiasedScorer,
    ScoringWeights,
    calculate_etf_scores,
    LegacyUnbiasedScorer,
    LegacyScoringWeights,
    calculate_legacy_etf_scores
)


class TrendETFSelector:
    """趋势ETF筛选器

    使用三级漏斗模型系统化筛选适合趋势跟踪策略的ETF标的池。

    三级筛选流程：
    1. 初级筛选：流动性（日均成交额）+ 上市时间
    2. 核心筛选：ADX趋势强度 + 双均线回测 + 波动率 + 动量
    3. 组合优化：相关性分析 + 行业分散

    Example:
        >>> selector = TrendETFSelector()
        >>> selected_etfs = selector.run_pipeline(
        ...     start_date='2023-01-01',
        ...     end_date='2024-12-31'
        >>> )
        >>> print(f"筛选出 {len(selected_etfs)} 只ETF")
    """

    def __init__(
        self,
        config: Optional[FilterConfig] = None,
        data_loader: Optional[ETFDataLoader] = None,
        data_dir: str = 'data/csv'
    ):
        """初始化筛选器

        Args:
            config: 筛选参数配置，默认None使用默认配置
            data_loader: 数据加载器，默认None自动创建
            data_dir: 数据目录，仅在data_loader为None时使用
        """
        self.config = config if config is not None else FilterConfig()
        self.data_loader = data_loader if data_loader is not None else ETFDataLoader(data_dir)
        self.industry_classifier = IndustryKeywords()

        # 筛选结果存储
        self.stage_results = {}
        self.metrics_cache = {}

    def run_pipeline(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        target_size: Optional[int] = None,
        verbose: bool = True,
        diversify_v2: bool = False,
        score_diff_threshold: float = 0.05
    ) -> List[Dict]:
        """执行完整筛选流程

        Args:
            start_date: 回测开始日期 (YYYY-MM-DD)，默认None使用全部数据
            end_date: 回测结束日期 (YYYY-MM-DD)，默认None使用全部数据
            target_size: 目标筛选数量，默认None使用config中的配置
            verbose: 是否打印详细信息
            diversify_v2: 是否启用V2分散逻辑（P0: max pairwise相关性, P1: Score优先去重）
            score_diff_threshold: V2去重时Score差异阈值（仅diversify_v2生效）

        Returns:
            筛选结果列表，每个元素包含：
            - ts_code: ETF代码
            - name: ETF名称
            - industry: 行业分类
            - stage1_rank, stage2_rank, final_rank: 各阶段排名
            - adx_mean, return_dd_ratio, volatility, momentum_3m: 关键指标
        """
        if target_size is None:
            target_size = self.config.target_portfolio_size

        if verbose:
            print(f"🎯 ETF趋势筛选器启动")
            print(f"📅 数据期间: {start_date or '全部'} 至 {end_date or '全部'}")
            print(f"🎲 目标数量: {target_size} 只")
            print("=" * 60)

        # 第一级：初级筛选
        stage1_etfs = self._stage1_basic_filter(verbose=verbose)
        self.stage_results['stage1'] = stage1_etfs

        if len(stage1_etfs) == 0:
            if verbose:
                print("❌ 第一级筛选后无剩余标的")
            return []

        # 第二级：核心筛选
        stage2_etfs = self._stage2_trend_filter(
            stage1_etfs, start_date=start_date, end_date=end_date, verbose=verbose
        )
        self.stage_results['stage2'] = stage2_etfs

        if len(stage2_etfs) == 0:
            if verbose:
                print("❌ 第二级筛选后无剩余标的")
            return []

        # 第三级：组合优化（包括去重和相关性分析）
        try:
            from .portfolio import PortfolioOptimizer
            optimizer = PortfolioOptimizer(data_loader=self.data_loader)

            # 总是执行第三级筛选，包括去重和分散化
            final_etfs = optimizer.optimize_portfolio(
                stage2_etfs,
                max_correlation=self.config.max_correlation,
                target_size=target_size,
                start_date=start_date,
                end_date=end_date,
                enable_deduplication=self.config.enable_deduplication,
                dedup_min_ratio=self.config.dedup_min_ratio,
                verbose=verbose,
                diversify_v2=diversify_v2,
                score_diff_threshold=score_diff_threshold,
                dedup_thresholds=self.config.dedup_thresholds
            )
        except ImportError:
            if verbose:
                print("  ⚠️ 组合优化模块不可用，直接使用前N个结果")
            final_etfs = stage2_etfs[:target_size]

        self.stage_results['final'] = final_etfs

        if verbose:
            print(f"✅ 筛选完成！最终选出 {len(final_etfs)} 只ETF")
            print("=" * 60)

        return final_etfs

    def _stage1_basic_filter(self, verbose: bool = True) -> List[str]:
        """第一级：初级筛选（流动性 + 上市时间）

        Args:
            verbose: 是否打印详细信息

        Returns:
            通过初级筛选的ETF代码列表
        """
        if verbose:
            print("🔍 第一级筛选：流动性 + 上市时间")

        # 加载基本信息（只加载股票型ETF）
        basic_info = self.data_loader.load_basic_info(fund_type='股票型')
        initial_count = len(basic_info)

        if verbose:
            print(f"  📊 初始股票型ETF数量: {initial_count}")

        passed_etfs = []
        liquidity_failed = 0
        listing_failed = 0
        data_failed = 0

        for _, row in basic_info.iterrows():
            ts_code = row['ts_code']

            try:
                # 1. 上市时间筛选
                list_date, days_since_listing = self.data_loader.get_etf_listing_info(
                    ts_code, basic_info
                )

                if days_since_listing < self.config.min_listing_days:
                    listing_failed += 1
                    continue

                # 2. 流动性筛选
                avg_turnover = self.data_loader.calculate_avg_turnover(
                    ts_code, lookback_days=self.config.turnover_lookback_days
                )

                if avg_turnover is None or avg_turnover < self.config.min_turnover:
                    liquidity_failed += 1
                    continue

                passed_etfs.append(ts_code)

            except (FileNotFoundError, ValueError):
                data_failed += 1
                continue

        if verbose:
            print(f"  ❌ 上市时间不足(<{self.config.min_listing_days}天): {listing_failed}")
            print(f"  ❌ 流动性不足(<{self.config.min_turnover/1e8:.1f}亿): {liquidity_failed}")
            print(f"  ❌ 数据缺失或异常: {data_failed}")
            print(f"  ✅ 通过第一级筛选: {len(passed_etfs)}")
            print(f"  📉 筛选率: {len(passed_etfs)/initial_count:.1%}")

        return passed_etfs

    def _stage2_trend_filter(
        self,
        etf_codes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        verbose: bool = True
    ) -> List[Dict]:
        """第二级：核心筛选（趋势性量化指标）

        Args:
            etf_codes: 通过第一级筛选的ETF代码列表
            start_date: 回测开始日期
            end_date: 回测结束日期
            verbose: 是否打印详细信息

        Returns:
            按收益回撤比排序的ETF信息列表，每个元素包含：
            - ts_code, name, industry
            - adx_mean, return_dd_ratio, volatility, momentum_3m, momentum_12m
        """
        use_ma_filter = self.config.enable_ma_backtest_filter

        if verbose:
            print("🧮 第二级筛选：趋势性量化分析")
            print(f"  📊 待分析ETF数量: {len(etf_codes)}")

        metrics_list = []
        basic_info = self.data_loader.load_basic_info(fund_type=None)  # 加载全部以获取名称
        benchmark_close = None

        if self.config.enable_unbiased_scoring and self.config.benchmark_ts_code:
            try:
                benchmark_data = self.data_loader.load_etf_daily(
                    self.config.benchmark_ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    use_adj=True
                )
                if 'adj_close' in benchmark_data.columns:
                    benchmark_close = benchmark_data['adj_close']
                elif 'close' in benchmark_data.columns:
                    benchmark_close = benchmark_data['close']
            except Exception as e:
                if verbose:
                    warnings.warn(f"加载基准 {self.config.benchmark_ts_code} 数据失败，超额收益将跳过: {e}")
                benchmark_close = None

        def combine_trend_quality(values: List[float]) -> float:
            valid_values = [v for v in values if not (pd.isna(v) or np.isnan(v))]
            if len(valid_values) == 0:
                return np.nan
            return float(np.mean(valid_values))

        for i, ts_code in enumerate(etf_codes):
            if verbose and (i + 1) % 100 == 0:
                print(f"  🏃 进度: {i + 1}/{len(etf_codes)}")

            try:
                # 加载数据
                data = self.data_loader.load_etf_daily(
                    ts_code, start_date=start_date, end_date=end_date, use_adj=True
                )
                price_series = data['adj_close']

                # 数据长度检查（需要足够的数据计算指标）
                min_data_length = max(
                    self.config.ma_long + 10,  # 双均线需要的最小长度
                    self.config.adx_period + self.config.adx_lookback_days // 4,  # ADX需要的最小长度
                    self.config.trend_quality_window + 5,
                    self.config.excess_return_long_window + 5,
                    self.config.volume_long_window + 5,
                    100  # 至少100天
                )

                if len(data) < min_data_length:
                    continue

                # 1. ADX趋势强度
                adx_mean = calculate_rolling_adx_mean(
                    data['adj_high'], data['adj_low'], data['adj_close'],
                    adx_period=self.config.adx_period,
                    window=min(self.config.adx_lookback_days, len(data))
                )

                if np.isnan(adx_mean):
                    continue

                if use_ma_filter:
                    # 2. 双均线回测
                    backtest_metrics = calculate_backtest_metrics(
                        data, short=self.config.ma_short, long=self.config.ma_long, use_adj=True
                    )

                    annual_return = backtest_metrics['annual_return']
                    max_drawdown = backtest_metrics['max_drawdown']
                    return_dd_ratio = backtest_metrics['return_dd_ratio']
                else:
                    annual_return = np.nan
                    max_drawdown = np.nan
                    return_dd_ratio = np.nan

                # 3. 波动率
                returns = data['adj_close'].pct_change().dropna()
                volatility = calculate_volatility(
                    returns, window=min(self.config.volatility_lookback_days, len(returns))
                )

                if np.isnan(volatility):
                    continue

                # 4. 动量
                momentum_periods = self.config.momentum_periods or [63, 252]
                momentum = calculate_momentum(data['adj_close'], periods=momentum_periods)
                momentum_3m = momentum.get('63d', np.nan)
                momentum_12m = momentum.get('252d', np.nan)

                # 5. 新增：无偏指标计算
                unbiased_indicators = {}
                if self.config.enable_unbiased_scoring:
                    try:
                        unbiased_indicators = calculate_all_unbiased_indicators(
                            close=data['adj_close'],
                            volume=data['volume'],
                            trend_window=self.config.trend_consistency_window,
                            efficiency_window=self.config.price_efficiency_window,
                            liquidity_window=self.config.liquidity_score_window
                        )
                    except Exception as e:
                        if verbose:
                            warnings.warn(f"计算 {ts_code} 无偏指标时出错: {e}")
                        unbiased_indicators = {
                            'trend_consistency': np.nan,
                            'price_efficiency': np.nan,
                            'liquidity_score': np.nan
                        }

                # 6. 相对强弱与趋势质量
                excess_return_20d = calculate_excess_return(
                    price_series,
                    benchmark_close,
                    period=self.config.excess_return_short_window
                )
                excess_return_60d = calculate_excess_return(
                    price_series,
                    benchmark_close,
                    period=self.config.excess_return_long_window
                )
                trend_quality_r2 = calculate_trend_r2(
                    price_series,
                    window=self.config.trend_quality_window
                )
                volume_trend = calculate_volume_trend(
                    data['volume'],
                    short_window=self.config.volume_short_window,
                    long_window=self.config.volume_long_window
                )
                trend_quality = combine_trend_quality([
                    trend_quality_r2,
                    unbiased_indicators.get('trend_consistency', np.nan),
                    unbiased_indicators.get('price_efficiency', np.nan)
                ])

                # 7. IDR（风险调整后超额收益）
                idr = calculate_idr(
                    price_series,
                    benchmark_close,
                    period=self.config.excess_return_long_window
                )

                # 应用筛选条件
                # 波动率范围检查（可选）
                if not self.config.skip_stage2_range_filtering:
                    if volatility < self.config.min_volatility or volatility > self.config.max_volatility:
                        continue

                # 动量检查（3个月动量必须为正）（可选）
                if not self.config.skip_stage2_range_filtering:
                    if np.isnan(momentum_3m) or momentum_3m <= 0:
                        continue

                # 获取ETF名称和行业分类
                etf_info = basic_info[basic_info['ts_code'] == ts_code]
                name = etf_info['name'].iloc[0] if len(etf_info) > 0 else ts_code
                industry = self.industry_classifier.classify(name)

                # 存储指标
                metrics_list.append({
                    'ts_code': ts_code,
                    'name': name,
                    'industry': industry,
                    'adx_mean': adx_mean,
                    'annual_return': annual_return,
                    'max_drawdown': max_drawdown,
                    'return_dd_ratio': return_dd_ratio,
                    'volatility': volatility,
                    'momentum_3m': momentum_3m,
                    'momentum_12m': momentum_12m,
                    # 新增无偏指标
                    'trend_consistency': unbiased_indicators.get('trend_consistency', np.nan),
                    'price_efficiency': unbiased_indicators.get('price_efficiency', np.nan),
                    'liquidity_score': unbiased_indicators.get('liquidity_score', np.nan),
                    # 新增优化后的评分输入
                    'excess_return_20d': excess_return_20d,
                    'excess_return_60d': excess_return_60d,
                    'trend_quality': trend_quality,
                    'trend_quality_r2': trend_quality_r2,
                    'volume_trend': volume_trend,
                    'idr': idr,
                })

            except Exception as e:
                if verbose and isinstance(e, (FileNotFoundError, ValueError)):
                    # 这些是预期的错误，不需要打印堆栈
                    pass
                else:
                    warnings.warn(f"处理 {ts_code} 时出错: {e}")
                continue

        if verbose:
            print(f"  ✅ 计算完成，获得 {len(metrics_list)} 只有效标的")

        if len(metrics_list) == 0:
            return []

        # 转为DataFrame便于排序和筛选
        df = pd.DataFrame(metrics_list)

        # 如果启用了跳过二级百分位筛选选项，直接跳到排序步骤
        if self.config.skip_stage2_percentile_filtering:
            if verbose:
                print("  ⚠️ 已跳过第二级百分位筛选（ADX、收益回撤比），将直接按评分排序")
        else:
            # ADX筛选：保留前adx_percentile%的标的
            adx_threshold = np.percentile(df['adx_mean'], self.config.adx_percentile)
            df = df[df['adx_mean'] >= adx_threshold]

            if verbose:
                print(f"  🎯 ADX筛选(>{adx_threshold:.1f}): 保留 {len(df)} 只")

            # 收益回撤比筛选：保留前ret_dd_percentile%的标的（可选）
            if len(df) > 0 and use_ma_filter:
                ret_dd_threshold = np.percentile(df['return_dd_ratio'], self.config.ret_dd_percentile)
                df = df[df['return_dd_ratio'] >= ret_dd_threshold]

                if verbose:
                    print(f"  📈 收益回撤比筛选(>{ret_dd_threshold:.2f}): 保留 {len(df)} 只")
            elif len(df) > 0 and not use_ma_filter and verbose:
                print("  ⚠️ 已禁用双均线回测过滤，跳过收益回撤比筛选")

        # 按收益回撤比降序排序
        if use_ma_filter:
            df = df.sort_values('return_dd_ratio', ascending=False).reset_index(drop=True)
        else:
            # 使用无偏评分系统排序
            if self.config.enable_unbiased_scoring:
                if self.config.use_optimized_score:
                    # 创建评分器（优化版）
                    scoring_weights = ScoringWeights(
                        core_trend_weight=self.config.core_trend_weight,
                        trend_quality_weight=self.config.trend_quality_weight,
                        strength_weight=self.config.strength_weight,
                        volume_weight=self.config.volume_weight,
                        idr_weight=self.config.idr_weight,
                        excess_return_20d_weight=self.config.excess_return_20d_weight,
                        excess_return_60d_weight=self.config.excess_return_60d_weight
                    )
                    scorer = UnbiasedScorer(scoring_weights)

                    df = calculate_etf_scores(
                        df,
                        scorer=scorer,
                        normalize_method='percentile'
                    )

                    if verbose:
                        weights_parts = [
                            f"超额收益{self.config.core_trend_weight:.0%}",
                            f"趋势质量{self.config.trend_quality_weight:.0%}",
                            f"ADX{self.config.strength_weight:.0%}",
                            f"资金动能{self.config.volume_weight:.0%}"
                        ]
                        if self.config.idr_weight > 0:
                            weights_parts.append(f"IDR{self.config.idr_weight:.0%}")
                        print(
                            "  🎯 启用无偏评分系统（优化版）：" +
                            " + ".join(weights_parts)
                        )
                else:
                    # 创建评分器（旧版）
                    scoring_weights = LegacyScoringWeights(
                        primary_weight=self.config.primary_weight,
                        secondary_weight=self.config.secondary_weight,
                        adx_weight=self.config.adx_score_weight,
                        trend_consistency_weight=self.config.trend_consistency_weight,
                        price_efficiency_weight=self.config.price_efficiency_weight,
                        liquidity_weight=self.config.liquidity_score_weight,
                        momentum_3m_weight=self.config.momentum_3m_score_weight,
                        momentum_12m_weight=self.config.momentum_12m_score_weight
                    )
                    scorer = LegacyUnbiasedScorer(scoring_weights)

                    df = calculate_legacy_etf_scores(
                        df,
                        scorer=scorer,
                        normalize_method='percentile'
                    )

                    if verbose:
                        print(
                            "  🎯 启用无偏评分系统（旧版）：主要"
                            f"{self.config.primary_weight:.0%} + 动量{self.config.secondary_weight:.0%} "
                            f"(ADX/TC/效率/流动性: "
                            f"{self.config.adx_score_weight:.0%}/"
                            f"{self.config.trend_consistency_weight:.0%}/"
                            f"{self.config.price_efficiency_weight:.0%}/"
                            f"{self.config.liquidity_score_weight:.0%}; "
                            f"3M/12M动量: "
                            f"{self.config.momentum_3m_score_weight:.0%}/"
                            f"{self.config.momentum_12m_score_weight:.0%})"
                        )
            else:
                # 回退到原有的动量排序（仅当禁用无偏评分时）
                sort_columns = ['adx_mean', 'momentum_12m', 'momentum_3m']
                df = df.sort_values(
                    by=sort_columns, ascending=[False, False, False], na_position='last'
                ).reset_index(drop=True)

                if verbose:
                    print("  ⚠️ 使用传统排序方式（存在选择性偏差风险）")

        # 添加排名信息
        df['stage2_rank'] = range(1, len(df) + 1)

        if verbose:
            print(f"  🏆 第二级筛选完成，共 {len(df)} 只标的通过")
            if len(df) > 0:
                print(f"  📊 ADX均值范围: {df['adx_mean'].min():.1f} ~ {df['adx_mean'].max():.1f}")
                print(f"  📊 波动率范围: {df['volatility'].min():.1%} ~ {df['volatility'].max():.1%}")

                # 显示无偏指标统计
                if self.config.enable_unbiased_scoring and 'final_score' in df.columns:
                    if self.config.use_optimized_score:
                        print(f"  📊 趋势一致性: {df['trend_consistency'].min():.2f} ~ {df['trend_consistency'].max():.2f}")
                        print(f"  📊 价格效率: {df['price_efficiency'].min():.2f} ~ {df['price_efficiency'].max():.2f}")
                        print(f"  📊 趋势质量(R^2融合): {df['trend_quality'].min():.2f} ~ {df['trend_quality'].max():.2f}")
                        print(f"  📊 成交量趋势(20/60): {df['volume_trend'].min():.2f} ~ {df['volume_trend'].max():.2f}")
                        print(f"  📊 超额收益20日: {df['excess_return_20d'].min():.2%} ~ {df['excess_return_20d'].max():.2%}")
                        print(f"  📊 超额收益60日: {df['excess_return_60d'].min():.2%} ~ {df['excess_return_60d'].max():.2%}")
                        if 'idr' in df.columns:
                            print(f"  📊 IDR(风险调整超额收益): {df['idr'].min():.2f} ~ {df['idr'].max():.2f}")
                        print(f"  📊 综合评分: {df['final_score'].min():.2f} ~ {df['final_score'].max():.2f}")
                        weights_str = (
                            f"超额收益{self.config.core_trend_weight:.0%}/"
                            f"质量{self.config.trend_quality_weight:.0%}/"
                            f"ADX{self.config.strength_weight:.0%}/"
                            f"资金{self.config.volume_weight:.0%}"
                        )
                        if self.config.idr_weight > 0:
                            weights_str += f"/IDR{self.config.idr_weight:.0%}"
                        print(f"  📊 评分权重: {weights_str}")
                    else:
                        print(f"  📊 趋势一致性: {df['trend_consistency'].min():.2f} ~ {df['trend_consistency'].max():.2f}")
                        print(f"  📊 价格效率: {df['price_efficiency'].min():.2f} ~ {df['price_efficiency'].max():.2f}")
                        print(f"  📊 动量3M: {df['momentum_3m'].min():.2%} ~ {df['momentum_3m'].max():.2%}")
                        print(f"  📊 动量12M: {df['momentum_12m'].min():.2%} ~ {df['momentum_12m'].max():.2%}")
                        print(f"  📊 综合评分: {df['final_score'].min():.2f} ~ {df['final_score'].max():.2f}")
                        print(
                            f"  📊 评分权重: 主要{self.config.primary_weight:.0%}"
                            f"(ADX/TC/效率/流动性:"
                            f"{self.config.adx_score_weight:.0%}/"
                            f"{self.config.trend_consistency_weight:.0%}/"
                            f"{self.config.price_efficiency_weight:.0%}/"
                            f"{self.config.liquidity_score_weight:.0%}) + "
                            f"动量{self.config.secondary_weight:.0%}"
                            f"(3M/12M:"
                            f"{self.config.momentum_3m_score_weight:.0%}/"
                            f"{self.config.momentum_12m_score_weight:.0%})"
                        )

                if use_ma_filter:
                    print(
                        f"  📊 收益回撤比范围: "
                        f"{df['return_dd_ratio'].min():.2f} ~ {df['return_dd_ratio'].max():.2f}"
                    )
                elif not self.config.enable_unbiased_scoring:
                    print("  📊 已禁用收益回撤比排名，结果按ADX+动量排序")

        return df.to_dict('records')

    def export_results(
        self,
        results: List[Dict],
        output_path: str,
        stage: str = 'final'
    ) -> None:
        """导出筛选结果到CSV文件

        Args:
            results: 筛选结果列表
            output_path: 输出文件路径
            stage: 筛选阶段标识（用于文件名）
        """
        if len(results) == 0:
            print(f"❌ 无结果可导出")
            return

        df = pd.DataFrame(results)

        # 确保输出目录存在
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 格式化浮点数列为5位小数
        float_columns = df.select_dtypes(include=['float64', 'float32']).columns
        for col in float_columns:
            df[col] = df[col].apply(lambda x: f'{x:.5f}' if pd.notna(x) else '')

        # 导出CSV（直接使用指定的路径，不添加时间戳）
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✅ 结果已导出: {output_path} ({len(df)} 只ETF)")

    def get_summary_stats(self) -> Dict:
        """获取筛选统计摘要

        Returns:
            统计信息字典
        """
        stats = {}

        for stage, results in self.stage_results.items():
            if isinstance(results, list):
                if len(results) > 0 and isinstance(results[0], dict):
                    # 第二级及以后的结果
                    df = pd.DataFrame(results)
                    stats[stage] = {
                        'count': len(df),
                        'avg_return_dd_ratio': df['return_dd_ratio'].mean() if 'return_dd_ratio' in df.columns else None,
                        'avg_adx': df['adx_mean'].mean() if 'adx_mean' in df.columns else None,
                        'avg_volatility': df['volatility'].mean() if 'volatility' in df.columns else None,
                    }
                else:
                    # 第一级结果（只有代码列表）
                    stats[stage] = {'count': len(results)}

        return stats
