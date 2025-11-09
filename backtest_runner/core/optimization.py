"""参数优化相关逻辑"""

import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..models import InstrumentInfo
from ..utils.display_utils import resolve_display_name


def find_robust_params(
    all_results: List[Dict[str, object]],
    verbose: bool = False
) -> tuple:
    """
    寻找全局稳健参数

    采用综合评分法，而非单纯选择单个标的的最优参数
    评分标准：
    1. 中位数夏普比率（30%）- 抗极端值
    2. 平均夏普比率（20%）- 整体表现
    3. 胜率（30%）- 正收益标的比例
    4. 稳定性（20%）- 夏普标准差倒数

    Args:
        all_results: 所有回测结果列表
        verbose: 是否输出详细信息

    Returns:
        (best_params, best_metrics, best_result, params_analysis)
    """
    # 筛选有优化参数的结果
    optimized_results = [
        result for result in all_results
        if 'optimized_params' in result and result['optimized_params'] is not None
    ]

    if not optimized_results:
        return None, None, None, None

    # 检测参数名称（使用第一个结果的参数作为参考）
    first_params = optimized_results[0]['optimized_params']  # type: ignore[index]
    param_names = tuple(sorted(first_params.keys()))  # type: ignore[union-attr]

    # 按参数分组
    params_groups = defaultdict(list)
    for result in optimized_results:
        params = result['optimized_params']  # type: ignore[assignment]
        # 创建参数元组作为key（按参数名排序后保证一致性）
        params_key = tuple(params[name] for name in param_names)  # type: ignore[index]
        params_groups[params_key].append(result)

    # 计算每组参数的综合评分
    best_score = -float('inf')
    best_params_key = None
    best_result = None
    params_analysis = []

    for params_key, group_results in params_groups.items():
        # 提取夏普比率值
        sharpe_values = []
        return_values = []
        for r in group_results:
            stats = r['stats']  # type: ignore[assignment]
            sharpe = stats['Sharpe Ratio']
            return_pct = stats['Return [%]']

            if not pd.isna(sharpe):
                sharpe_values.append(float(sharpe))
            if not pd.isna(return_pct):
                return_values.append(float(return_pct))

        if not sharpe_values:
            continue

        # 1. 中位数夏普
        median_sharpe = float(np.median(sharpe_values))

        # 2. 平均夏普
        avg_sharpe = float(np.mean(sharpe_values))

        # 3. 胜率（夏普>0 或 收益>0 的比例）
        sharpe_win_rate = sum(s > 0 for s in sharpe_values) / len(sharpe_values)
        return_win_rate = sum(r > 0 for r in return_values) / len(return_values) if return_values else 0
        win_rate = max(sharpe_win_rate, return_win_rate)

        # 4. 稳定性（标准差越小越好）
        sharpe_std = float(np.std(sharpe_values))
        stability_score = 1.0 / (sharpe_std + 0.01) if sharpe_std > 0 else 10.0

        # 综合评分
        score = (
            0.30 * median_sharpe +
            0.20 * avg_sharpe +
            0.30 * win_rate +
            0.20 * min(stability_score, 5.0)  # 限制稳定性得分上限避免极端值
        )

        # 记录分析结果（包含所有参数）
        analysis_entry = {
            'params': params_key,
            'median_sharpe': median_sharpe,
            'avg_sharpe': avg_sharpe,
            'win_rate': win_rate,
            'sharpe_std': sharpe_std,
            'stability_score': stability_score,
            'score': score,
            'num_instruments': len(group_results)
        }
        # 添加具体参数名称和值到analysis_entry
        for i, name in enumerate(param_names):
            analysis_entry[name] = params_key[i]

        params_analysis.append(analysis_entry)

        if score > best_score:
            best_score = score
            best_params_key = params_key
            best_metrics = analysis_entry
            # 找到该参数组中表现最好的一个标的作为代表
            best_result = max(group_results, key=lambda x: x['stats']['Sharpe Ratio'] if not pd.isna(x['stats']['Sharpe Ratio']) else -float('inf'))  # type: ignore[assignment, index]

    # 按综合评分排序
    params_analysis.sort(key=lambda x: x['score'], reverse=True)

    if verbose and params_analysis:
        from ..utils.display_utils import print_optimization_info
        print_optimization_info(params_analysis, verbose=verbose)

    if best_params_key is None:
        return None, None, None, params_analysis

    # 构建参数字典
    best_params = {name: best_params_key[i] for i, name in enumerate(param_names)}
    return best_params, best_metrics, best_result, params_analysis


def save_best_params(
    all_results: List[Dict[str, object]],
    save_params_file: str,
    strategy_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    verbose: bool = False
) -> None:
    """
    保存表现最佳的全局稳健参数

    使用综合评分法找出在所有标的上表现最稳健的参数，
    而非单纯选择某个标的的历史最优参数。

    Args:
        all_results: 所有回测结果列表
        save_params_file: 参数配置文件路径
        strategy_name: 策略名称
        start_date: 回测开始日期
        end_date: 回测结束日期
        verbose: 是否输出详细信息
    """
    try:
        from utils.strategy_params_manager import StrategyParamsManager

        # 使用全局稳健参数查找方法
        best_params, best_metrics, best_result, params_analysis = find_robust_params(
            all_results, verbose=verbose
        )

        if best_params is None or best_result is None:
            if verbose:
                print("\n⚠️ 未找到有效的优化参数，跳过参数保存")
            return

        # 获取代表标的信息
        instrument = best_result['instrument']  # type: ignore[assignment]
        stats = best_result['stats']  # type: ignore[assignment]

        params_manager = StrategyParamsManager(save_params_file)

        # 构建性能统计（使用该参数在代表标的上的表现）
        performance_stats = {
            'sharpe_ratio': float(stats['Sharpe Ratio']) if stats['Sharpe Ratio'] is not None else None,
            'annual_return': float(stats['Return (Ann.) [%]']) if stats['Return (Ann.) [%]'] is not None else None,
            'max_drawdown': float(stats['Max. Drawdown [%]']) if stats['Max. Drawdown [%]'] is not None else None,
            'return_pct': float(stats['Return [%]']) if stats['Return [%]'] is not None else None,
            # 新增：全局稳健性指标
            'median_sharpe': best_metrics['median_sharpe'],
            'avg_sharpe': best_metrics['avg_sharpe'],
            'win_rate': best_metrics['win_rate'],
            'sharpe_std': best_metrics['sharpe_std'],
            'robustness_score': best_metrics['score']
        }

        # 构建优化期间信息
        optimization_period = None
        if start_date and end_date:
            optimization_period = f"{start_date} 至 {end_date}"
        elif start_date:
            optimization_period = f"{start_date} 至今"
        elif end_date:
            optimization_period = f"开始 至 {end_date}"

        # 构建股票池信息
        num_instruments = len([r for r in all_results if 'optimized_params' in r])
        if num_instruments > 1:
            stock_pool = f"全局稳健优化 (共{num_instruments}只标的)"
        else:
            stock_pool = f"{resolve_display_name(instrument)}"

        # 构建详细说明
        # 动态构建参数说明字符串
        param_names = sorted(best_params.keys())
        params_str = ", ".join(f"{name}={best_params[name]}" for name in param_names)

        notes = (
            f"全局稳健参数优化 (综合评分={best_metrics['score']:.4f})\n"
            f"参数: {params_str}\n"
            f"中位数夏普={best_metrics['median_sharpe']:.4f}, "
            f"平均夏普={best_metrics['avg_sharpe']:.4f}, "
            f"胜率={best_metrics['win_rate']*100:.1f}%, "
            f"稳定性(标准差)={best_metrics['sharpe_std']:.4f}"
        )

        # 保存优化结果
        params_manager.save_optimization_results(
            strategy_name=strategy_name,
            optimized_params=best_params,
            performance_stats=performance_stats,
            optimization_period=optimization_period,
            stock_pool=stock_pool,
            notes=notes
        )

        # 输出摘要信息
        if verbose:
            print(f"\n✓ 全局稳健参数已保存到 {save_params_file}")
            print(f"  参数: {params_str}")
            print(f"  中位数夏普: {best_metrics['median_sharpe']:.4f}")
            print(f"  平均夏普: {best_metrics['avg_sharpe']:.4f}")
            print(f"  胜率: {best_metrics['win_rate']*100:.1f}%")
            print(f"  稳定性: 标准差={best_metrics['sharpe_std']:.4f}")
            print(f"  综合评分: {best_metrics['score']:.4f}")
            print(f"  该参数在{int(best_metrics['win_rate']*num_instruments)}/{num_instruments}个标的上盈利")
        else:
            print(f"\n✓ 全局稳健参数已保存到 {save_params_file}")
            print(f"  参数: {params_str}")
            print(f"  胜率: {best_metrics['win_rate']*100:.1f}% ({int(best_metrics['win_rate']*num_instruments)}/{num_instruments}个标的盈利)")
            print(f"  平均夏普: {best_metrics['avg_sharpe']:.4f}, 中位数夏普: {best_metrics['median_sharpe']:.4f}")

    except Exception as e:
        print(f"\n⚠️ 保存优化参数失败: {e}")
        if verbose:
            import traceback
            print(traceback.format_exc())
