"""命令行参数解析"""

import argparse


def create_argument_parser() -> argparse.ArgumentParser:
    """
    创建命令行参数解析器

    Returns:
        配置好的ArgumentParser对象
    """
    parser = argparse.ArgumentParser(
        description="MySQL数据导出至CSV脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导出所有类型的基础信息和日线数据
  python export_mysql_to_csv.py --start_date 20200101 --end_date 20231231 \\
    --export_basic --export_daily --export_metadata

  # 导出指定ETF的数据
  python export_mysql_to_csv.py --start_date 20200101 --end_date 20231231 \\
    --data_type etf --ts_code 510300.SH --export_daily

  # 自定义过滤阈值
  python export_mysql_to_csv.py --start_date 20200101 --end_date 20231231 \\
    --min_history_days 252 --min_annual_vol 0.05 --export_daily
        """,
    )

    # === 必需参数 ===
    _add_required_arguments(parser)

    # === 数据类型参数 ===
    _add_data_type_arguments(parser)

    # === 导出选项 ===
    _add_export_arguments(parser)

    # === 过滤参数 ===
    _add_filter_arguments(parser)

    # === 数据库参数 ===
    _add_database_arguments(parser)

    # === 其他参数 ===
    _add_misc_arguments(parser)

    return parser


def _add_required_arguments(parser: argparse.ArgumentParser) -> None:
    """添加必需参数"""
    parser.add_argument(
        "--start_date",
        required=True,
        help="开始日期(YYYYMMDD)",
    )
    parser.add_argument(
        "--end_date",
        required=True,
        help="结束日期(YYYYMMDD)",
    )


def _add_data_type_arguments(parser: argparse.ArgumentParser) -> None:
    """添加数据类型参数"""
    parser.add_argument(
        "--data_type",
        default="all",
        help="数据类型(etf/index/fund/all或逗号分隔组合)",
    )
    parser.add_argument(
        "--ts_code",
        default=None,
        help="可选，指定单个标的代码",
    )


def _add_export_arguments(parser: argparse.ArgumentParser) -> None:
    """添加导出选项参数"""
    parser.add_argument(
        "--output_dir",
        default="data/csv",
        help="导出结果保存的目录",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=10000,
        help="数据库查询批次大小",
    )
    parser.add_argument(
        "--export_basic",
        action="store_true",
        help="是否导出基础信息",
    )
    parser.add_argument(
        "--export_daily",
        action="store_true",
        help="是否导出日线数据",
    )
    parser.add_argument(
        "--export_metadata",
        action="store_true",
        help="是否导出元数据文件",
    )


def _add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """添加过滤相关参数"""
    filter_group = parser.add_argument_group('过滤参数（仅适用于 etf、fund）')

    filter_group.add_argument(
        "--min_history_days",
        type=int,
        default=180,
        help="最小历史样本交易日数N（严格大于N才通过，默认: 180）",
    )
    filter_group.add_argument(
        "--min_annual_vol",
        type=float,
        default=0.02,
        help="区间年化波动率阈值x（严格大于x才通过，默认: 0.02）",
    )
    filter_group.add_argument(
        "--min_avg_turnover_yuan",
        type=float,
        default=5000.0,
        help="区间日均成交额阈值y，单位元（严格大于y才通过，默认: 5000）",
    )


def _add_database_arguments(parser: argparse.ArgumentParser) -> None:
    """添加数据库连接参数"""
    db_group = parser.add_argument_group('数据库连接参数')

    db_group.add_argument(
        "--db_host",
        default="localhost",
        help="MySQL主机地址，默认localhost",
    )
    db_group.add_argument(
        "--db_port",
        type=int,
        default=3306,
        help="MySQL端口，默认3306",
    )
    db_group.add_argument(
        "--db_user",
        default="root",
        help="MySQL用户名，默认root",
    )
    db_group.add_argument(
        "--db_password",
        default="qlib_data",
        help="MySQL密码，默认qlib",
    )
    db_group.add_argument(
        "--db_name",
        default="qlib_data",
        help="MySQL数据库名称，默认qlib_data",
    )


def _add_misc_arguments(parser: argparse.ArgumentParser) -> None:
    """添加其他参数"""
    parser.add_argument(
        "--log_level",
        default="INFO",
        help="日志级别，默认INFO",
    )


def validate_arguments(args: argparse.Namespace) -> None:
    """
    验证命令行参数

    Args:
        args: 解析后的参数命名空间

    Raises:
        ValueError: 当参数验证失败时抛出
    """
    if not args.export_basic and not args.export_daily and not args.export_metadata:
        raise ValueError(
            "至少需要指定一个导出选项，如--export_basic或--export_daily或--export_metadata"
        )
