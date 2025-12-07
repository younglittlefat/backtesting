# -*- coding: utf-8 -*-
"""
贪心搜索实验框架 - 公共模块

提供超参组合贪心搜索的可复用组件：
- metrics_extractor: 从回测结果提取指标
- candidate_filter: 阶段筛选逻辑
- combo_generator: 组合生成器
"""

from .metrics_extractor import (
    extract_metrics_from_summary,
    extract_metrics_from_csv,
    STANDARD_COL_MAPPING,
)

from .candidate_filter import (
    filter_stage1_candidates,
    filter_stage_k_candidates,
    load_candidates,
    save_candidates,
)

from .combo_generator import (
    generate_k_combinations,
    check_all_subs_passed,
)

__version__ = '1.0.0'
__all__ = [
    'extract_metrics_from_summary',
    'extract_metrics_from_csv',
    'STANDARD_COL_MAPPING',
    'filter_stage1_candidates',
    'filter_stage_k_candidates',
    'load_candidates',
    'save_candidates',
    'generate_k_combinations',
    'check_all_subs_passed',
]
