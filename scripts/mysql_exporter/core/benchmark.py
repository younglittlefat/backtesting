"""
基准指数数据导出模块

负责从MySQL导出基准指数数据（如沪深300、中证全指），用于计算超额收益。
输出文件使用IDX前缀以区分普通ETF数据。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..models import DAILY_COLUMN_LAYOUT, PRICE_COLUMNS
from ..processing.transform import DailyDataTransformer


class BenchmarkExporter:
    """
    基准指数数据导出器

    从MySQL导出基准指数日线数据，输出到ETF目录下，文件名使用IDX前缀。
    """

    def __init__(
        self,
        output_dir: str,
        db_manager,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        初始化基准指数导出器

        Args:
            output_dir: CSV输出根目录
            db_manager: MySQL管理器实例
            logger: 可选，外部传入的日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.db_manager = db_manager
        self.output_dir = Path(output_dir).expanduser()
        self._transformer = DailyDataTransformer()

    def load_benchmark_config(self, config_path: str) -> List[Dict]:
        """
        加载基准指数配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            List[Dict]: 基准指数配置列表

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"基准指数配置文件不存在: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        benchmarks = config.get('benchmarks', [])
        if not benchmarks:
            raise ValueError(f"配置文件中未找到benchmarks配置: {config_path}")

        return benchmarks

    def export_benchmark_data(
        self,
        benchmarks: List[Dict],
        start_date: str,
        end_date: str,
    ) -> Dict[str, int]:
        """
        导出基准指数日线数据

        Args:
            benchmarks: 基准指数配置列表
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            Dict[str, int]: 每个基准指数导出的记录数
        """
        stats: Dict[str, int] = {}

        # 确保ETF目录存在（基准指数输出到ETF目录）
        etf_dir = self.output_dir / "daily" / "etf"
        etf_dir.mkdir(parents=True, exist_ok=True)

        for benchmark in benchmarks:
            ts_code = benchmark.get('ts_code')
            name = benchmark.get('name', ts_code)
            data_type = benchmark.get('type', 'index')
            output_prefix = benchmark.get('output_prefix', 'IDX')

            if not ts_code:
                self.logger.warning("跳过无效的基准配置（缺少ts_code）: %s", benchmark)
                continue

            self.logger.info("导出基准指数: %s (%s)", name, ts_code)

            try:
                # 从数据库查询日线数据
                records = self._query_benchmark_daily(
                    ts_code=ts_code,
                    data_type=data_type,
                    start_date=start_date,
                    end_date=end_date,
                )

                if not records:
                    self.logger.warning(
                        "未找到基准指数数据: %s (%s), 日期范围: %s - %s",
                        name, ts_code, start_date, end_date
                    )
                    stats[ts_code] = 0
                    continue

                # 转换为DataFrame
                df = pd.DataFrame(records)

                # 转换字段格式（使用与ETF相同的转换逻辑）
                transformed = self._transform_benchmark_data(df, ts_code, name)

                if transformed.empty:
                    self.logger.warning("转换后数据为空: %s", ts_code)
                    stats[ts_code] = 0
                    continue

                # 生成输出文件名（使用IDX前缀）
                # 例如: 000300.SH -> IDX000300.SH.csv
                code_without_suffix = ts_code.split('.')[0]
                suffix = ts_code.split('.')[-1] if '.' in ts_code else 'SH'
                output_filename = f"{output_prefix}{code_without_suffix}.{suffix}.csv"
                output_path = etf_dir / output_filename

                # 保存CSV
                transformed.to_csv(
                    output_path,
                    index=False,
                    encoding='utf-8',
                    na_rep='',
                )

                stats[ts_code] = len(transformed)
                self.logger.info(
                    "基准指数导出完成: %s -> %s (记录数=%d)",
                    ts_code, output_path, len(transformed)
                )

            except Exception as exc:
                self.logger.error("导出基准指数失败 %s: %s", ts_code, exc)
                stats[ts_code] = 0

        return stats

    def _query_benchmark_daily(
        self,
        ts_code: str,
        data_type: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict]:
        """
        查询基准指数日线数据

        Args:
            ts_code: 指数代码
            data_type: 数据类型（index/etf/fund）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[Dict]: 日线数据记录列表
        """
        return self.db_manager.get_instrument_daily(
            data_type=data_type,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

    def _transform_benchmark_data(
        self,
        df: pd.DataFrame,
        ts_code: str,
        name: str,
    ) -> pd.DataFrame:
        """
        转换基准指数数据格式

        将数据库字段转换为与ETF日线数据兼容的格式，便于etf_selector直接使用。

        Args:
            df: 原始数据DataFrame
            ts_code: 指数代码
            name: 指数名称

        Returns:
            pd.DataFrame: 转换后的DataFrame
        """
        if df.empty:
            return df

        # 创建输出DataFrame
        result = pd.DataFrame()

        # 基础字段映射（数据库字段 -> 输出字段）
        field_mapping = {
            'trade_date': 'trade_date',
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'close_price': 'close',
            'pre_close': 'pre_close',
            'pct_change': 'pct_chg',
            'change_amount': 'change',
            'volume': 'volume',
            'amount': 'amount',
        }

        # 映射字段
        for src_col, dst_col in field_mapping.items():
            if src_col in df.columns:
                result[dst_col] = df[src_col]

        # 添加instrument_name字段
        result['instrument_name'] = name

        # 指数没有复权因子，设置为1.0
        result['adj_factor'] = 1.0

        # 计算复权价格（指数本身就是点位，不需要复权，adj_* = 原始价格）
        for price_col in ['open', 'high', 'low', 'close']:
            adj_col = f'adj_{price_col}'
            if price_col in result.columns:
                result[adj_col] = result[price_col]

        # 按照ETF日线数据的字段顺序排列
        output_columns = [
            'trade_date', 'instrument_name',
            'open', 'high', 'low', 'close',
            'pre_close', 'change', 'pct_chg',
            'volume', 'amount',
            'adj_factor', 'adj_open', 'adj_high', 'adj_low', 'adj_close',
        ]

        # 只保留存在的列
        available_columns = [col for col in output_columns if col in result.columns]
        result = result[available_columns]

        # 按日期排序
        result = result.sort_values('trade_date')

        return result
