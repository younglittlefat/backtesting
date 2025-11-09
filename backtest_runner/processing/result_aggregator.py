"""结果聚合模块"""

from typing import Dict, List

from ..models import InstrumentInfo
from ..utils.data_utils import _safe_stat


def build_aggregate_payload(results: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    构建聚合统计数据的占位结构，便于未来汇总分析。
    当前仅包含基础收益指标，可按需扩展。

    Args:
        results: 回测结果列表

    Returns:
        聚合数据列表
    """
    payload: List[Dict[str, object]] = []
    for item in results:
        instrument: InstrumentInfo = item['instrument']  # type: ignore[index]
        stats = item['stats']  # type: ignore[index]
        payload.append(
            {
                'code': instrument.code,
                'category': instrument.category,
                'strategy': item['strategy'],  # type: ignore[index]
                'return_pct': _safe_stat(stats, 'Return [%]'),
                'annual_return_pct': _safe_stat(stats, 'Return (Ann.) [%]'),
                'sharpe': stats['Sharpe Ratio'],
                'max_drawdown_pct': _safe_stat(stats, 'Max. Drawdown [%]', default=0.0),
            }
        )
    return payload
