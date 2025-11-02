"""
数据加载模块

从理杏仁网站下载的CSV文件加载数据并转换为backtesting.py需要的OHLCV格式
"""

import os
import re
import pandas as pd
from pathlib import Path
from typing import Optional


def clean_excel_format(value):
    """
    清理Excel公式格式（去除=前缀）

    Args:
        value: 原始值，可能包含"="前缀

    Returns:
        清理后的浮点数
    """
    if pd.isna(value):
        return None

    if isinstance(value, str):
        # 去除"="前缀
        value = value.strip().replace('=', '')
        # 尝试转换为浮点数
        try:
            return float(value)
        except ValueError:
            return None

    return float(value)


def load_lixinger_data(csv_path: str,
                       stock_name: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
    """
    加载理杏仁CSV数据并转换为OHLCV格式

    Args:
        csv_path: CSV文件路径
        stock_name: 股票名称（可选，用于日志输出）
        start_date: 开始日期，格式：YYYY-MM-DD（可选）
        end_date: 结束日期，格式：YYYY-MM-DD（可选）

    Returns:
        pd.DataFrame: 包含Open, High, Low, Close, Volume列的DataFrame，
                      索引为日期时间

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 数据格式不正确
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"数据文件不存在: {csv_path}")

    # 读取CSV，处理BOM和编码
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except Exception as e:
        raise ValueError(f"读取CSV文件失败: {e}")

    # 检查必要的列是否存在
    required_cols = ['日期', '股价(美元)']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV文件缺少必要的列: {missing_cols}. 可用列: {list(df.columns)}")

    # 清理数据
    print(f"加载数据文件: {csv_path}")
    print(f"原始数据行数: {len(df)}")

    # 提取并清理日期和股价
    result_df = pd.DataFrame()
    result_df['Date'] = pd.to_datetime(df['日期'], errors='coerce')

    # 清理股价数据（去除"="前缀）
    result_df['Close'] = df['股价(美元)'].apply(clean_excel_format)

    # 由于只有收盘价，设置 Open = High = Low = Close
    result_df['Open'] = result_df['Close']
    result_df['High'] = result_df['Close']
    result_df['Low'] = result_df['Close']

    # Volume设为0（原始数据无成交量）
    result_df['Volume'] = 0

    # 删除包含NaN的行
    result_df = result_df.dropna()

    # 按日期排序（从旧到新）
    result_df = result_df.sort_values('Date')

    # 设置日期为索引
    result_df.set_index('Date', inplace=True)

    # 应用日期过滤
    if start_date or end_date:
        original_len = len(result_df)

        if start_date:
            start_dt = pd.to_datetime(start_date)
            result_df = result_df[result_df.index >= start_dt]
            print(f"应用开始日期过滤: {start_date}")

        if end_date:
            end_dt = pd.to_datetime(end_date)
            result_df = result_df[result_df.index <= end_dt]
            print(f"应用结束日期过滤: {end_date}")

        filtered_count = original_len - len(result_df)
        if filtered_count > 0:
            print(f"过滤掉 {filtered_count} 行数据")

    # 验证数据
    if len(result_df) == 0:
        raise ValueError("处理后数据为空（可能是日期过滤范围不正确）")

    print(f"处理后数据行数: {len(result_df)}")
    print(f"日期范围: {result_df.index[0]} 至 {result_df.index[-1]}")
    print(f"价格范围: ${result_df['Close'].min():.2f} - ${result_df['Close'].max():.2f}")
    print()

    return result_df


def get_stock_name(csv_path: str) -> str:
    """
    从文件名提取股票名称

    Args:
        csv_path: CSV文件路径

    Returns:
        股票名称（tesla 或 nvidia）
    """
    filename = os.path.basename(csv_path)

    if '特斯拉' in filename or 'tesla' in filename.lower():
        return 'tesla'
    elif '英伟达' in filename or 'nvidia' in filename.lower():
        return 'nvidia'
    else:
        # 提取文件名中的第一个词作为股票名
        name = filename.split('_')[0]
        return name


def list_available_stocks(data_dir: str = 'data/american_stocks') -> dict:
    """
    列出可用的股票数据文件

    Args:
        data_dir: 数据目录路径

    Returns:
        dict: {股票名称: 文件路径}
    """
    if not os.path.exists(data_dir):
        return {}

    stocks = {}
    for filename in os.listdir(data_dir):
        if filename.endswith('.csv'):
            filepath = os.path.join(data_dir, filename)
            stock_name = get_stock_name(filepath)
            stocks[stock_name] = filepath

    return stocks


def validate_ohlc_data(df: pd.DataFrame) -> bool:
    """
    验证OHLCV数据格式

    Args:
        df: 待验证的DataFrame

    Returns:
        bool: 是否有效
    """
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    # 检查列
    if not all(col in df.columns for col in required_columns):
        return False

    # 检查索引是否为日期时间
    if not isinstance(df.index, pd.DatetimeIndex):
        return False

    # 检查是否有数据
    if len(df) == 0:
        return False

    # 检查是否有NaN值
    if df[required_columns].isna().any().any():
        return False

    return True


if __name__ == '__main__':
    """测试数据加载功能"""
    import sys

    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data' / 'american_stocks'

    print("=" * 60)
    print("测试数据加载模块")
    print("=" * 60)
    print()

    # 列出可用股票
    stocks = list_available_stocks(str(data_dir))
    print(f"发现 {len(stocks)} 个股票数据文件:")
    for name, path in stocks.items():
        print(f"  - {name}: {os.path.basename(path)}")
    print()

    # 测试加载每个股票
    for stock_name, csv_path in stocks.items():
        print(f"\n{'=' * 60}")
        print(f"加载股票: {stock_name}")
        print('=' * 60)

        try:
            df = load_lixinger_data(csv_path, stock_name)

            # 验证数据
            if validate_ohlc_data(df):
                print("✓ 数据验证通过")
            else:
                print("✗ 数据验证失败")

            # 显示前几行
            print("\n前5行数据:")
            print(df.head())

            # 显示统计信息
            print("\n数据统计:")
            print(df['Close'].describe())

        except Exception as e:
            print(f"✗ 加载失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
