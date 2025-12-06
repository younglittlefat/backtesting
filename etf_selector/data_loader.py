"""
ETF数据加载和预处理模块

负责从CSV文件加载ETF基本信息和日线数据，并进行数据清洗和验证
"""
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd


class ETFDataLoader:
    """ETF数据加载器"""

    def __init__(self, data_dir: str = 'data/csv'):
        """初始化数据加载器

        Args:
            data_dir: CSV数据根目录
        """
        self.data_dir = Path(data_dir)
        self.basic_info_path = self.data_dir / 'basic_info' / 'etf_basic_info.csv'
        self.daily_data_dir = self.data_dir / 'daily' / 'etf'

        # 验证路径存在
        if not self.basic_info_path.exists():
            raise FileNotFoundError(f"基本信息文件不存在: {self.basic_info_path}")
        if not self.daily_data_dir.exists():
            raise FileNotFoundError(f"日线数据目录不存在: {self.daily_data_dir}")

    def load_basic_info(self, fund_type: Optional[str] = '股票型') -> pd.DataFrame:
        """加载ETF基本信息

        Args:
            fund_type: 基金类型筛选，默认'股票型'。传入None则不筛选

        Returns:
            ETF基本信息DataFrame，包含以下字段：
            - ts_code: 标的代码
            - symbol: 简称
            - name: 名称
            - fullname: 全称
            - market: 市场
            - tracking_index: 跟踪指数
            - management: 管理人
            - fund_type: 基金类型
            - list_date: 上市日期（datetime）
            - found_date: 成立日期（datetime）
            - status: 状态
        """
        df = pd.read_csv(self.basic_info_path, encoding='utf-8-sig')

        # 日期格式转换
        if 'list_date' in df.columns:
            df['list_date'] = pd.to_datetime(df['list_date'], format='%Y%m%d', errors='coerce')
        if 'found_date' in df.columns:
            df['found_date'] = pd.to_datetime(df['found_date'], format='%Y%m%d', errors='coerce')

        # 筛选基金类型
        if fund_type is not None and 'fund_type' in df.columns:
            df = df[df['fund_type'] == fund_type].copy()

        # 删除status为'D'（退市）的标的
        if 'status' in df.columns:
            df = df[df['status'] != 'D'].copy()

        return df

    def load_etf_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_adj: bool = True,
    ) -> pd.DataFrame:
        """加载ETF日线数据

        Args:
            ts_code: 标的代码（如 159915.SZ）或基准指数代码（如 IDX000300.SH）
            start_date: 开始日期 (YYYY-MM-DD)，默认None表示全部数据
            end_date: 结束日期 (YYYY-MM-DD)，默认None表示全部数据
            use_adj: 是否使用复权数据，默认True

        Returns:
            日线数据DataFrame，索引为日期（datetime），包含以下字段：
            - open, high, low, close: 原始价格
            - volume: 成交量
            - amount: 成交额
            - adj_open, adj_high, adj_low, adj_close: 复权价格（use_adj=True时）

        Raises:
            FileNotFoundError: 数据文件不存在
            ValueError: 数据不足或格式错误

        Note:
            支持IDX前缀的基准指数文件，例如:
            - ts_code='IDX000300.SH' -> 加载 IDX000300.SH.csv (沪深300指数)
            - 对于基准指数，adj_close = close（指数无复权概念）
        """
        # 构建文件路径
        file_path = self.daily_data_dir / f"{ts_code}.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"日线数据文件不存在: {file_path}")

        # 加载数据
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        # 日期格式转换
        if 'trade_date' not in df.columns:
            raise ValueError(f"{ts_code}: 缺少 trade_date 字段")

        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')

        # 删除日期为NaT的行
        df = df.dropna(subset=['trade_date'])

        # 设置索引
        df = df.set_index('trade_date').sort_index()

        # 日期范围筛选
        if start_date is not None:
            start = pd.to_datetime(start_date)
            df = df[df.index >= start]
        if end_date is not None:
            end = pd.to_datetime(end_date)
            df = df[df.index <= end]

        # 数据清洗
        # 1. 删除成交额为0的异常日（停牌或数据错误）
        if 'amount' in df.columns:
            df = df[df['amount'] > 0]

        # 2. 删除价格<=0的异常数据
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns:
                df = df[df[col] > 0]

        # 3. 如果使用复权数据，检查复权字段
        if use_adj:
            adj_cols = ['adj_open', 'adj_high', 'adj_low', 'adj_close']
            missing_cols = [col for col in adj_cols if col not in df.columns]
            if missing_cols:
                warnings.warn(
                    f"{ts_code}: 缺少复权字段 {missing_cols}，将使用原始价格"
                )
                # 如果缺少复权数据，使用原始价格
                for adj_col, orig_col in zip(adj_cols, price_cols):
                    if adj_col not in df.columns and orig_col in df.columns:
                        df[adj_col] = df[orig_col]
            else:
                # 删除复权价格<=0的异常数据
                for col in adj_cols:
                    df = df[df[col] > 0]

        # 4. 删除包含NaN的行（仅针对关键字段）
        critical_cols = ['close', 'volume', 'amount']
        if use_adj:
            critical_cols.append('adj_close')
        df = df.dropna(subset=[col for col in critical_cols if col in df.columns])

        # 数据验证
        if len(df) == 0:
            raise ValueError(f"{ts_code}: 筛选后数据为空")

        if len(df) < 30:
            warnings.warn(f"{ts_code}: 数据量不足30天，仅{len(df)}天")

        return df

    def get_etf_listing_info(
        self, ts_code: str, basic_info_df: Optional[pd.DataFrame] = None
    ) -> Tuple[Optional[datetime], int]:
        """获取ETF上市信息

        Args:
            ts_code: 标的代码
            basic_info_df: 基本信息DataFrame，如果为None则重新加载

        Returns:
            (上市日期, 上市天数)
        """
        if basic_info_df is None:
            basic_info_df = self.load_basic_info(fund_type=None)

        row = basic_info_df[basic_info_df['ts_code'] == ts_code]
        if len(row) == 0:
            return None, 0

        list_date = row['list_date'].iloc[0]
        if pd.isna(list_date):
            return None, 0

        days_since_listing = (datetime.now() - list_date).days
        return list_date, days_since_listing

    def calculate_avg_turnover(
        self, ts_code: str, lookback_days: int = 30
    ) -> Optional[float]:
        """计算日均成交额

        Args:
            ts_code: 标的代码
            lookback_days: 回看天数

        Returns:
            日均成交额（元），如果数据不足则返回None
        """
        try:
            data = self.load_etf_daily(ts_code)
        except (FileNotFoundError, ValueError):
            return None

        if len(data) < lookback_days:
            # 数据不足，使用全部数据
            avg_turnover = data['amount'].mean()
        else:
            # 使用最近N天数据
            avg_turnover = data['amount'].tail(lookback_days).mean()

        return float(avg_turnover)
