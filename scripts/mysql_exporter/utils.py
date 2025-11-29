"""
工具函数模块

提供各种辅助函数
"""

import logging
from datetime import datetime
from typing import List


def validate_date(date_str: str, label: str) -> str:
    """
    校验日期格式并返回原始字符串

    Args:
        date_str: 待校验的日期字符串
        label: 字段含义标签，用于错误提示

    Returns:
        str: 原始日期字符串

    Raises:
        ValueError: 当日期格式不是YYYYMMDD时抛出
    """
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{label}格式错误，应为YYYYMMDD: {date_str}") from exc
    return date_str


def parse_data_types(data_type: str) -> List[str]:
    """
    将用户输入的类型字符串解析为标准列表

    Args:
        data_type: 用户输入的类型参数，可为'all'或逗号分隔的多个类型

    Returns:
        List[str]: 解析后的类型列表

    Raises:
        ValueError: 当出现未支持的类型时抛出
    """
    valid_types = {"etf", "index", "fund"}
    if not data_type:
        raise ValueError("数据类型参数不能为空")

    if data_type.lower() == "all":
        return ["etf", "index", "fund"]

    result = []
    for item in data_type.split(","):
        dtype = item.strip().lower()
        if not dtype:
            continue
        if dtype not in valid_types:
            raise ValueError(f"不支持的数据类型: {dtype}")
        if dtype not in result:
            result.append(dtype)

    if not result:
        raise ValueError("至少需要指定一个有效的数据类型")

    return result


def configure_logging(log_level: str) -> None:
    """
    配置全局日志

    Args:
        log_level: 日志级别字符串
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
