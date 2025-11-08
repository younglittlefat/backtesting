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
from .indicators import calculate_rolling_adx_mean, calculate_volatility, calculate_momentum
from .backtest_engine import calculate_backtest_metrics


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
        verbose: bool = True
    ) -> List[Dict]:
        """执行完整筛选流程

        Args:
            start_date: 回测开始日期 (YYYY-MM-DD)，默认None使用全部数据
            end_date: 回测结束日期 (YYYY-MM-DD)，默认None使用全部数据
            target_size: 目标筛选数量，默认None使用config中的配置
            verbose: 是否打印详细信息

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
                max_correlation=0.7,
                target_size=target_size,
                start_date=start_date,
                end_date=end_date,
                enable_deduplication=True,  # 启用智能去重
                dedup_min_ratio=0.8,        # 最小保留比例80%
                verbose=verbose
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

        for i, ts_code in enumerate(etf_codes):
            if verbose and (i + 1) % 100 == 0:
                print(f"  🏃 进度: {i + 1}/{len(etf_codes)}")

            try:
                # 加载数据
                data = self.data_loader.load_etf_daily(
                    ts_code, start_date=start_date, end_date=end_date, use_adj=True
                )

                # 数据长度检查（需要足够的数据计算指标）
                min_data_length = max(
                    self.config.ma_long + 10,  # 双均线需要的最小长度
                    self.config.adx_period + self.config.adx_lookback_days // 4,  # ADX需要的最小长度
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

                # 应用筛选条件
                # 波动率范围检查
                if volatility < self.config.min_volatility or volatility > self.config.max_volatility:
                    continue

                # 动量检查（3个月动量必须为正）
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
            sort_columns = ['adx_mean', 'momentum_12m', 'momentum_3m']
            df = df.sort_values(
                by=sort_columns, ascending=[False, False, False], na_position='last'
            ).reset_index(drop=True)

        # 添加排名信息
        df['stage2_rank'] = range(1, len(df) + 1)

        if verbose:
            print(f"  🏆 第二级筛选完成，共 {len(df)} 只标的通过")
            if len(df) > 0:
                print(f"  📊 ADX均值范围: {df['adx_mean'].min():.1f} ~ {df['adx_mean'].max():.1f}")
                print(f"  📊 波动率范围: {df['volatility'].min():.1%} ~ {df['volatility'].max():.1%}")
                if use_ma_filter:
                    print(
                        f"  📊 收益回撤比范围: "
                        f"{df['return_dd_ratio'].min():.2f} ~ {df['return_dd_ratio'].max():.2f}"
                    )
                else:
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
