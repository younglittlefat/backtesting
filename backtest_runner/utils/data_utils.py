"""
数据转换与验证工具函数
"""

import math
from typing import List, Optional

import numpy as np
import pandas as pd


def _duration_to_days(value) -> int:
    """
    安全地将持续时长转换为天数，兼容 float/Timedelta/timedelta64。

    Args:
        value: 持续时长值（可以是多种类型）

    Returns:
        转换后的天数（整数）
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0

    if isinstance(value, pd.Timedelta):
        return int(value.days)

    if isinstance(value, np.timedelta64):
        return int(pd.to_timedelta(value).days)

    if hasattr(value, "days"):
        try:
            return int(value.days)
        except (TypeError, ValueError):
            pass

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_stat(stats: pd.Series, key: str, default: float = 0.0) -> float:
    """
    从 stats 中安全获取数值，遇到 NaN/缺失时返回默认值。

    Args:
        stats: 统计数据 Series
        key: 要获取的键
        default: 默认值

    Returns:
        获取到的数值或默认值
    """
    value = stats.get(key, default)
    if value is None:
        return default
    if isinstance(value, (float, int, np.floating, np.integer)):
        if math.isnan(float(value)):
            return default
        return float(value)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return 0.0 if math.isnan(numeric) else numeric


def parse_multi_values(raw: Optional[str]) -> List[str]:
    """
    解析逗号分隔的参数，返回去重且保持顺序的列表。

    Args:
        raw: 原始字符串（逗号分隔）

    Returns:
        解析后的字符串列表
    """
    if raw is None:
        return []
    raw = raw.strip()
    if not raw or raw.lower() == 'all':
        return []

    seen = set()
    values: List[str] = []
    for part in raw.split(','):
        token = part.strip()
        if not token:
            continue
        if token not in seen:
            seen.add(token)
            values.append(token)
    return values


def parse_blacklist(raw: Optional[str]) -> List[str]:
    """
    解析低波动黑名单配置。

    Args:
        raw: 原始配置字符串

    Returns:
        黑名单代码列表
    """
    if raw is None:
        return []

    normalized = raw.strip()
    if not normalized:
        return []

    if normalized.lower() in {'none', 'null', 'off', 'disable', 'disabled'}:
        return []

    seen = set()
    values: List[str] = []
    for part in normalized.split(','):
        token = part.strip()
        if not token:
            continue
        if token not in seen:
            seen.add(token)
            values.append(token)
    return values
