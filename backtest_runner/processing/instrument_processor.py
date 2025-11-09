"""标的处理模块"""

from typing import Dict, List

from ..models import InstrumentInfo
from ..utils.display_utils import resolve_display_name


def enrich_instruments_with_names(instruments: List[InstrumentInfo]) -> List[InstrumentInfo]:
    """
    从数据库获取标的中文名称，丰富InstrumentInfo对象。

    Args:
        instruments: 标的信息列表

    Returns:
        更新后的标的信息列表，包含中文名称
    """
    if not instruments:
        return instruments

    # 创建数据库连接
    try:
        from common.mysql_manager import MySQLManager
        db_manager = MySQLManager()
    except Exception as exc:
        print(f"警告: 无法连接数据库获取中文名称: {exc}")
        return instruments

    # 按类别分组以优化查询
    by_category: Dict[str, List[InstrumentInfo]] = {}
    for instrument in instruments:
        if instrument.category not in by_category:
            by_category[instrument.category] = []
        by_category[instrument.category].append(instrument)

    # 获取基础信息
    name_mapping: Dict[str, str] = {}  # ts_code -> name
    for category, cat_instruments in by_category.items():
        codes = [inst.code for inst in cat_instruments]
        try:
            # 批量查询该类别的基础信息
            basic_infos = db_manager.get_instrument_basic(data_type=category)
            if basic_infos:
                for info in basic_infos:
                    ts_code = info.get('ts_code', '').strip()
                    name = info.get('name', '').strip()
                    if ts_code and name and ts_code in codes:
                        name_mapping[ts_code] = name
        except Exception as exc:
            print(f"警告: 获取{category}类别基础信息失败: {exc}")
            continue

    # 更新InstrumentInfo对象
    updated_instruments = []
    for instrument in instruments:
        display_name = name_mapping.get(instrument.code, None)
        updated_instrument = instrument.with_display_name(display_name)
        updated_instruments.append(updated_instrument)

    # 统计获取情况
    found_count = sum(1 for inst in updated_instruments if inst.display_name)
    print(f"数据库中文名称映射: {found_count}/{len(instruments)} 个标的")

    return updated_instruments
