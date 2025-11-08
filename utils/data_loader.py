"""
数据加载模块

从理杏仁网站下载的CSV文件加载数据并转换为backtesting.py需要的OHLCV格式
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class InstrumentInfo:
    """描述单个标的文件及其元数据."""

    code: str
    path: Path
    category: str = "unknown"
    display_name: Optional[str] = None
    currency: str = "CNY"

    def with_display_name(self, name: Optional[str]) -> "InstrumentInfo":
        return InstrumentInfo(
            code=self.code,
            path=self.path,
            category=self.category,
            display_name=name,
            currency=self.currency,
        )


@dataclass(frozen=True)
class LowVolatilityConfig:
    """低波动标的过滤参数."""

    threshold: float = 0.02
    lookback: int = 60
    min_samples: int = 20
    annualization_factor: int = 252
    blacklist: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.threshold < 0:
            raise ValueError("低波动阈值必须为非负数")
        if self.lookback <= 0:
            raise ValueError("波动率回看窗口必须为正数")
        if self.min_samples <= 0:
            raise ValueError("最小样本数量必须为正数")
        if self.annualization_factor <= 0:
            raise ValueError("年化因子必须为正数")


def compute_annualized_volatility(
    prices: pd.Series,
    *,
    lookback: int,
    min_samples: int,
    annualization_factor: int,
) -> Optional[float]:
    """
    根据收盘价计算指定窗口的年化波动率。

    返回 None 代表有效样本不足。
    """
    if prices.empty:
        return None

    returns = prices.pct_change().dropna()
    if returns.empty:
        return None

    window = returns if lookback <= 0 else returns.iloc[-lookback:]
    required = min_samples if lookback <= 0 else min(min_samples, lookback)
    if len(window) < max(2, required):
        return None

    volatility = window.std()
    if pd.isna(volatility):
        return None

    return float(volatility * (annualization_factor ** 0.5))


def is_low_volatility(
    instrument: InstrumentInfo,
    data: pd.DataFrame,
    config: LowVolatilityConfig,
) -> tuple[bool, Optional[float], str]:
    """
    判断标的是否为低波动资产。

    Returns:
        tuple: (是否低波动, 年化波动率, 过滤原因)
    """
    close_col = 'Close'
    if close_col not in data.columns:
        return True, None, f"缺少收盘价列 '{close_col}'，无法计算波动率"

    volatility = compute_annualized_volatility(
        data[close_col],
        lookback=config.lookback,
        min_samples=config.min_samples,
        annualization_factor=config.annualization_factor,
    )

    if instrument.code in config.blacklist:
        reason = "命中低波动黑名单"
        return True, volatility, reason

    if volatility is None:
        reason = (
            f"有效收益样本不足，需至少 {config.min_samples} 条"
        )
        return True, None, reason

    if volatility < config.threshold:
        formatted_threshold = f"{config.threshold:.4%}"
        reason = f"年化波动率 {volatility:.4%} 低于阈值 {formatted_threshold}"
        return True, volatility, reason

    return False, volatility, ""


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


def load_lixinger_data(
    csv_path: str,
    stock_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    verbose: bool = True,
) -> pd.DataFrame:
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
    if verbose:
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
            if verbose:
                print(f"应用开始日期过滤: {start_date}")

        if end_date:
            end_dt = pd.to_datetime(end_date)
            result_df = result_df[result_df.index <= end_dt]
            if verbose:
                print(f"应用结束日期过滤: {end_date}")

        filtered_count = original_len - len(result_df)
        if filtered_count > 0 and verbose:
            print(f"过滤掉 {filtered_count} 行数据")

    # 验证数据
    if len(result_df) == 0:
        raise ValueError("处理后数据为空（可能是日期过滤范围不正确）")

    if verbose:
        print(f"处理后数据行数: {len(result_df)}")
        print(f"日期范围: {result_df.index[0]} 至 {result_df.index[-1]}")
        print(f"价格范围: ${result_df['Close'].min():.2f} - ${result_df['Close'].max():.2f}")
        print()

    return result_df

def _infer_category(base_path: Path, csv_path: Path) -> str:
    """根据文件相对路径推断标的分类."""
    try:
        rel_parts = csv_path.relative_to(base_path).parts
    except ValueError:
        # relative_to 失败时，尝试从 csv_path 的父目录名推断
        parent_name = csv_path.parent.name.lower()
        if parent_name and parent_name not in {'data', 'csv', 'daily', 'intraday'}:
            return parent_name
        return "unknown"

    # 情况1: 相对路径有多个部分且包含 daily/intraday
    # 例如: daily/etf/510300.SH.csv -> 'etf'
    # 例如: csv/daily/etf/510300.SH.csv -> 'etf'
    if len(rel_parts) >= 2:
        for i, part in enumerate(rel_parts[:-1]):  # 排除文件名本身
            if part.lower() in {'daily', 'intraday'}:
                # 下一部分是类别
                if i + 1 < len(rel_parts) - 1:
                    return rel_parts[i + 1].lower()

    # 情况2: 相对路径只有一个文件名，从完整路径提取类别
    # 例如: base_path=data/csv/daily/etf, csv_path=.../etf/159231.SZ.csv -> 'etf'
    if len(rel_parts) == 1:
        # 从完整路径的父目录提取类别
        parent_name = csv_path.parent.name.lower()
        if parent_name and parent_name not in {'data', 'csv', 'daily', 'intraday'}:
            return parent_name

    # 情况3: 其他情况，尝试从第一个部分提取
    if len(rel_parts) >= 1:
        first_part = rel_parts[0].lower()
        # 如果第一部分不是文件名（即包含子目录），使用它
        if first_part != csv_path.name.lower():
            parent = Path(first_part).stem.lower()
            return parent if parent else "unknown"

    return "unknown"


def list_available_instruments(
    data_dir: str,
    categories: Optional[Iterable[str]] = None,
) -> Dict[str, InstrumentInfo]:
    """
    列出数据目录下可用的标的文件，支持递归扫描子目录。

    Args:
        data_dir: 数据根目录路径
        categories: 需要过滤的标的类别（如 etf/fund）。None 表示不过滤。

    Returns:
        dict: {代码: InstrumentInfo}
    """
    base_path = Path(data_dir)
    if not base_path.exists():
        return {}

    category_filter: Optional[set[str]]
    if categories is not None:
        category_filter = {cat.lower() for cat in categories}
    else:
        category_filter = None

    instruments: Dict[str, InstrumentInfo] = {}
    for csv_path in base_path.rglob("*.csv"):
        if not csv_path.is_file():
            continue

        code = csv_path.stem
        category = _infer_category(base_path, csv_path)
        if category_filter and category not in category_filter:
            continue

        info = InstrumentInfo(code=code, path=csv_path, category=category)
        if code not in instruments:
            instruments[code] = info
        else:
            # 保留最先发现的文件，避免覆盖；未来可扩展冲突处理
            continue

    return instruments


def list_available_stocks(data_dir: str = 'data/american_stocks') -> dict:
    """
    向后兼容的包装函数。

    Args:
        data_dir: 数据目录路径

    Returns:
        dict: {股票名称: 文件路径}
    """
    instruments = list_available_instruments(data_dir)
    return {code: str(info.path) for code, info in instruments.items()}


def _create_ohlcv_dataframe(
    df: pd.DataFrame,
    date_col: str,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    volume_col: str,
) -> pd.DataFrame:
    """根据列映射构造标准 OHLCV DataFrame."""
    result_df = pd.DataFrame()
    result_df['Date'] = pd.to_datetime(df[date_col], format='%Y%m%d', errors='coerce')
    result_df['Open'] = pd.to_numeric(df[open_col], errors='coerce')
    result_df['High'] = pd.to_numeric(df[high_col], errors='coerce')
    result_df['Low'] = pd.to_numeric(df[low_col], errors='coerce')
    result_df['Close'] = pd.to_numeric(df[close_col], errors='coerce')
    result_df['Volume'] = pd.to_numeric(df[volume_col], errors='coerce').fillna(0)

    result_df = result_df.dropna(subset=['Date', 'Open', 'High', 'Low', 'Close'])
    result_df = result_df.sort_values('Date')
    result_df.set_index('Date', inplace=True)
    return result_df


def load_chinese_ohlcv_data(
    csv_path: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    加载中国市场标准 OHLCV CSV 数据。

    Args:
        csv_path: CSV 文件路径
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）

    Returns:
        pd.DataFrame: 标准化的 OHLCV 数据
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {csv_path}")

    df = pd.read_csv(csv_path)
    if verbose:
        print(f"加载数据文件: {csv_path}")
        print(f"原始数据行数: {len(df)}")

    # 统一列名大小写
    df_lower = df.rename(columns={orig: orig.lower() for orig in df.columns})
    available_cols = set(df_lower.columns)

    # 检查是否有复权价格列
    has_adj_prices = all(col in available_cols for col in ['adj_open', 'adj_high', 'adj_low', 'adj_close'])

    if has_adj_prices:
        # 使用复权价格
        required_cols = {'trade_date', 'adj_open', 'adj_high', 'adj_low', 'adj_close', 'volume'}
        if not required_cols.issubset(available_cols):
            raise ValueError(f"CSV文件缺少必要的列: {required_cols}. 可用列: {list(df.columns)}")

        if verbose:
            print("使用复权价格进行回测")

        ohlcv_df = _create_ohlcv_dataframe(
            df=df_lower,
            date_col='trade_date',
            open_col='adj_open',
            high_col='adj_high',
            low_col='adj_low',
            close_col='adj_close',
            volume_col='volume',
        )
    else:
        # 使用原始价格
        required_cols = {'trade_date', 'open', 'high', 'low', 'close', 'volume'}
        if not required_cols.issubset(available_cols):
            raise ValueError(f"CSV文件缺少必要的列: {required_cols}. 可用列: {list(df.columns)}")

        if verbose:
            print("使用原始价格进行回测（未找到复权价格列）")

        ohlcv_df = _create_ohlcv_dataframe(
            df=df_lower,
            date_col='trade_date',
            open_col='open',
            high_col='high',
            low_col='low',
            close_col='close',
            volume_col='volume',
        )

    if start_date or end_date:
        original_len = len(ohlcv_df)
        if start_date:
            ohlcv_df = ohlcv_df[ohlcv_df.index >= pd.to_datetime(start_date)]
        if end_date:
            ohlcv_df = ohlcv_df[ohlcv_df.index <= pd.to_datetime(end_date)]
        filtered = original_len - len(ohlcv_df)
        if filtered > 0 and verbose:
            print(f"过滤掉 {filtered} 行数据")

    if len(ohlcv_df) == 0:
        raise ValueError("处理后数据为空（可能是日期过滤范围不正确）")

    if verbose:
        print(f"处理后数据行数: {len(ohlcv_df)}")
        print(f"日期范围: {ohlcv_df.index[0]} 至 {ohlcv_df.index[-1]}")
        price_min = ohlcv_df['Close'].min()
        price_max = ohlcv_df['Close'].max()
        print(f"价格范围: {price_min:.4f} - {price_max:.4f}")
        print()

    return ohlcv_df



def load_instrument_data(
    instrument: InstrumentInfo,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    根据标的信息加载并标准化数据。
    当前默认解析中国市场数据，未来可根据 instrument.category 扩展。
    """
    csv_path = instrument.path

    if instrument.category in {'etf', 'fund', 'index'} or 'chinese_stocks' in str(csv_path):
        data = load_chinese_ohlcv_data(
            csv_path,
            start_date=start_date,
            end_date=end_date,
            verbose=verbose,
        )
    else:
        data = load_lixinger_data(
            str(csv_path),
            stock_name=instrument.code,
            start_date=start_date,
            end_date=end_date,
            verbose=verbose,
        )

    return data



def load_dual_price_data(
    csv_path: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    verbose: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    加载双价格数据：同时返回复权价格（用于信号）和原始价格（用于交易）。

    Args:
        csv_path: CSV 文件路径
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        verbose: 是否显示详细信息

    Returns:
        tuple: (复权价格DataFrame, 原始价格DataFrame, 价格映射字典)
            - 复权价格DataFrame: 用于信号计算的OHLCV数据
            - 原始价格DataFrame: 用于实际交易的OHLCV数据
            - 价格映射字典: {
                'adj_factor': 复权因子,
                'latest_adj_price': 最新复权价格,
                'latest_real_price': 最新原始价格
              }
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {csv_path}")

    df = pd.read_csv(csv_path)
    if verbose:
        print(f"加载双价格数据: {csv_path}")
        print(f"原始数据行数: {len(df)}")

    # 统一列名大小写
    df_lower = df.rename(columns={orig: orig.lower() for orig in df.columns})
    available_cols = set(df_lower.columns)

    # 检查是否有复权价格列和原始价格列
    has_adj_prices = all(col in available_cols for col in ['adj_open', 'adj_high', 'adj_low', 'adj_close'])
    has_real_prices = all(col in available_cols for col in ['open', 'high', 'low', 'close'])
    has_adj_factor = 'adj_factor' in available_cols

    if not (has_adj_prices and has_real_prices):
        # 如果没有双价格数据，回退到单价格模式
        if has_adj_prices:
            if verbose:
                print("只有复权价格，使用复权价格作为双价格")
            adj_df = _create_ohlcv_dataframe(
                df=df_lower,
                date_col='trade_date',
                open_col='adj_open',
                high_col='adj_high',
                low_col='adj_low',
                close_col='adj_close',
                volume_col='volume',
            )
            real_df = adj_df.copy()  # 复权价格作为原始价格
            price_mapping = {
                'adj_factor': 1.0,
                'latest_adj_price': adj_df['Close'].iloc[-1] if len(adj_df) > 0 else 0.0,
                'latest_real_price': adj_df['Close'].iloc[-1] if len(adj_df) > 0 else 0.0,
            }
        elif has_real_prices:
            if verbose:
                print("只有原始价格，使用原始价格作为双价格")
            real_df = _create_ohlcv_dataframe(
                df=df_lower,
                date_col='trade_date',
                open_col='open',
                high_col='high',
                low_col='low',
                close_col='close',
                volume_col='volume',
            )
            adj_df = real_df.copy()  # 原始价格作为复权价格
            price_mapping = {
                'adj_factor': 1.0,
                'latest_adj_price': real_df['Close'].iloc[-1] if len(real_df) > 0 else 0.0,
                'latest_real_price': real_df['Close'].iloc[-1] if len(real_df) > 0 else 0.0,
            }
        else:
            raise ValueError(f"CSV文件缺少价格数据列。可用列: {list(df.columns)}")
    else:
        # 有完整的双价格数据
        if verbose:
            print("使用双价格模式：复权价格用于信号，原始价格用于交易")

        # 创建复权价格DataFrame
        adj_df = _create_ohlcv_dataframe(
            df=df_lower,
            date_col='trade_date',
            open_col='adj_open',
            high_col='adj_high',
            low_col='adj_low',
            close_col='adj_close',
            volume_col='volume',
        )

        # 创建原始价格DataFrame
        real_df = _create_ohlcv_dataframe(
            df=df_lower,
            date_col='trade_date',
            open_col='open',
            high_col='high',
            low_col='low',
            close_col='close',
            volume_col='volume',
        )

        # 构建价格映射
        latest_adj_factor = df_lower['adj_factor'].iloc[-1] if has_adj_factor and len(df_lower) > 0 else 1.0
        latest_adj_price = adj_df['Close'].iloc[-1] if len(adj_df) > 0 else 0.0
        latest_real_price = real_df['Close'].iloc[-1] if len(real_df) > 0 else 0.0

        price_mapping = {
            'adj_factor': latest_adj_factor,
            'latest_adj_price': latest_adj_price,
            'latest_real_price': latest_real_price,
        }

    # 应用日期过滤（对两个DataFrame）
    if start_date or end_date:
        original_len = len(adj_df)
        if start_date:
            start_dt = pd.to_datetime(start_date)
            adj_df = adj_df[adj_df.index >= start_dt]
            real_df = real_df[real_df.index >= start_dt]
        if end_date:
            end_dt = pd.to_datetime(end_date)
            adj_df = adj_df[adj_df.index <= end_dt]
            real_df = real_df[real_df.index <= end_dt]
        filtered = original_len - len(adj_df)
        if filtered > 0 and verbose:
            print(f"过滤掉 {filtered} 行数据")

    if len(adj_df) == 0 or len(real_df) == 0:
        raise ValueError("处理后数据为空（可能是日期过滤范围不正确）")

    if verbose:
        print(f"处理后数据行数: {len(adj_df)}")
        print(f"日期范围: {adj_df.index[0]} 至 {adj_df.index[-1]}")
        print(f"复权价格范围: {adj_df['Close'].min():.4f} - {adj_df['Close'].max():.4f}")
        print(f"原始价格范围: {real_df['Close'].min():.4f} - {real_df['Close'].max():.4f}")
        print(f"最新复权因子: {price_mapping['adj_factor']:.6f}")
        print()

    return adj_df, real_df, price_mapping


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
    """简单的命令行测试，用于验证加载逻辑。"""
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data' / 'chinese_stocks'

    print("=" * 60)
    print("测试中国市场数据加载模块")
    print("=" * 60)

    instruments = list_available_instruments(str(data_dir))
    print(f"发现 {len(instruments)} 个标的文件")
    for code, info in list(instruments.items())[:5]:
        print(f"  - {code} ({info.category}) -> {info.path.name}")
    if len(instruments) > 5:
        print("  ...")

    for code in list(instruments.keys())[:3]:
        info = instruments[code]
        print(f"\n{'=' * 60}")
        print(f"加载标的: {code} ({info.category})")
        print('=' * 60)

        try:
            df = load_instrument_data(info)
            if validate_ohlc_data(df):
                print("✓ 数据验证通过")
            else:
                print("✗ 数据验证失败")
            print(df.head())
        except Exception as exc:
            print(f"✗ 加载失败: {exc}")
