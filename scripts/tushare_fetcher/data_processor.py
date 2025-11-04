"""
数据处理器

提供数据批量收集和插入的辅助功能
"""

import logging
from typing import List, Dict, Optional, Tuple


class DataProcessor:
    """数据处理器，负责数据批量收集和插入"""

    def __init__(self, db_manager, batch_size: int = 10000, logger: Optional[logging.Logger] = None):
        """
        初始化数据处理器

        Args:
            db_manager: 数据库管理器实例
            batch_size: 批处理大小
            logger: 日志记录器
        """
        self.db_manager = db_manager
        self.batch_size = batch_size
        self.logger = logger or logging.getLogger(__name__)
        self.data_buffer = []
        self.success_count = 0

    def add_data(self, data: Dict):
        """
        添加数据到缓冲区

        Args:
            data: 待添加的数据字典
        """
        self.data_buffer.append(data)

        # 达到批处理大小时自动刷新
        if len(self.data_buffer) >= self.batch_size:
            self.flush()

    def flush(self, insert_method: str = 'instrument_daily') -> int:
        """
        刷新缓冲区，将数据批量插入数据库

        Args:
            insert_method: 插入方法类型 ('instrument_daily', 'fund_share', 'fund_dividend')

        Returns:
            int: 成功插入的数据条数
        """
        if not self.data_buffer:
            return 0

        try:
            if insert_method == 'instrument_daily':
                batch_success = self.db_manager.batch_insert_instrument_daily(
                    self.data_buffer, batch_size=self.batch_size
                )
            elif insert_method == 'fund_share':
                batch_success = self.db_manager.batch_insert_fund_share_data(
                    self.data_buffer, batch_size=self.batch_size
                )
            elif insert_method == 'fund_dividend':
                batch_success = self.db_manager.insert_fund_dividend_data(self.data_buffer)
            else:
                self.logger.error(f"未知的插入方法: {insert_method}")
                batch_success = 0

            self.success_count += batch_success
            buffer_size = len(self.data_buffer)
            self.data_buffer = []  # 清空缓冲区

            self.logger.debug(f"批量插入完成: 缓冲区{buffer_size}条 -> 成功{batch_success}条")
            return batch_success

        except Exception as e:
            self.logger.error(f"批量插入失败: {e}")
            self.data_buffer = []
            return 0

    def get_success_count(self) -> int:
        """获取累计成功插入的数据条数"""
        return self.success_count

    def get_buffer_size(self) -> int:
        """获取当前缓冲区大小"""
        return len(self.data_buffer)

    def calculate_date_chunks(self, trading_dates: List[str], max_records: int = 2000) -> List[Tuple[str, str]]:
        """
        计算日期分割块

        Args:
            trading_dates: 交易日期列表
            max_records: 单次最大记录数

        Returns:
            List[Tuple[str, str]]: 日期分割块列表 [(start1, end1), (start2, end2), ...]
        """
        if not trading_dates:
            return []

        chunks = []
        total_days = len(trading_dates)

        if total_days <= max_records:
            # 日期范围内的交易日数量 <= max_records，一次获取
            chunks.append((trading_dates[0], trading_dates[-1]))
        else:
            # 需要分割，每个块包含最多max_records个交易日
            for i in range(0, total_days, max_records):
                chunk_start_date = trading_dates[i]
                chunk_end_index = min(i + max_records - 1, total_days - 1)
                chunk_end_date = trading_dates[chunk_end_index]
                chunks.append((chunk_start_date, chunk_end_date))

        self.logger.info(f"数据分割: 总交易日{total_days}天，分{len(chunks)}个块")
        return chunks
