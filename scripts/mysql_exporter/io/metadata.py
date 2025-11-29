"""
元数据生成模块

负责生成和保存导出任务的元数据
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class MetadataGenerator:
    """
    元数据生成器

    负责生成导出任务的元数据并保存到文件
    """

    def __init__(self, output_dir: Path, db_manager) -> None:
        """
        初始化元数据生成器

        Args:
            output_dir: 输出目录
            db_manager: 数据库管理器
        """
        self.output_dir = output_dir
        self.db_manager = db_manager

    def generate_metadata(
        self,
        start_date: str,
        end_date: str,
        data_types: List[str],
        export_basic: bool,
        export_daily: bool,
        basic_stats: Dict[str, int],
        daily_stats: Dict[str, Dict[str, object]],
        filter_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, object]:
        """
        生成导出任务的元数据字典

        Args:
            start_date: 导出范围的开始日期
            end_date: 导出范围的结束日期
            data_types: 实际处理的数据类型列表
            export_basic: 是否导出基础信息
            export_daily: 是否导出日线数据
            basic_stats: 按类型统计的基础信息条数
            daily_stats: 按类型统计的日线数据结果
            filter_config: 过滤配置

        Returns:
            Dict[str, object]: 元数据内容
        """
        statistics: Dict[str, Dict[str, object]] = {}
        for dtype in data_types:
            daily_info = daily_stats.get(
                dtype, {"instrument_count": 0, "daily_records": 0, "date_range": []}
            )
            statistics[dtype] = {
                "instrument_count": daily_info.get("instrument_count", 0),
                "daily_records": daily_info.get("daily_records", 0),
                "date_range": daily_info.get("date_range", []),
            }
            if export_basic:
                statistics[dtype]["basic_records"] = basic_stats.get(dtype, 0)

        metadata: Dict[str, object] = {
            "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": start_date,
            "end_date": end_date,
            "data_types": data_types,
            "export_basic": export_basic,
            "export_daily": export_daily,
            "statistics": statistics,
            "output_dir": str(self.output_dir.resolve()),
            "database": {
                "host": getattr(self.db_manager, "host", "unknown"),
                "database": getattr(self.db_manager, "database", "unknown"),
                "port": getattr(self.db_manager, "port", None),
                "user": getattr(self.db_manager, "user", None),
            },
            "disk_free_gb": round(self._query_disk_free_gb(), 2),
        }

        # 附加过滤配置与统计
        if filter_config:
            metadata["filters"] = filter_config.get("filters", {})
            metadata["filter_statistics"] = filter_config.get("filter_statistics", {})

        return metadata

    def save_metadata(self, metadata: Dict[str, object], logger=None) -> Path:
        """
        将元数据写入JSON文件

        Args:
            metadata: 已生成的元数据内容
            logger: 可选，日志记录器

        Returns:
            Path: 元数据文件路径
        """
        metadata_path = self.output_dir / "export_metadata.json"
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=4)
        if logger:
            logger.info("元数据已写入: %s", metadata_path)
        return metadata_path

    def _query_disk_free_gb(self) -> float:
        """
        查询输出目录所在磁盘的剩余空间

        Returns:
            float: 可用空间（GB）
        """
        target = self.output_dir
        if not target.exists():
            target = target.parent if target.parent.exists() else Path(".")
        usage = shutil.disk_usage(target)
        return usage.free / (1024 ** 3)
