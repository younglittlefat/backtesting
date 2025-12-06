#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MySQL数据导出至CSV - CLI入口

模块化重构版本，保持向后兼容
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict

# 将项目根目录加入路径，确保可以导入公共模块
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.mysql_manager import MySQLManager  # noqa: E402

from .config import create_argument_parser, validate_arguments
from .core import MySQLToCSVExporter, BenchmarkExporter
from .io import MetadataGenerator
from .models import FilterThresholds
from .utils import configure_logging, parse_data_types, validate_date


def main() -> int:
    """
    CLI入口函数

    Returns:
        int: 退出码，0表示成功，1表示失败
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    # 验证参数
    try:
        validate_arguments(args)
    except ValueError as exc:
        print(f"参数错误: {exc}")
        return 1

    # 配置日志
    configure_logging(args.log_level)
    logger = logging.getLogger("export_mysql_to_csv")

    # 验证日期
    try:
        start_date = validate_date(args.start_date, "start_date")
        end_date = validate_date(args.end_date, "end_date")
        if start_date > end_date:
            raise ValueError("start_date不能晚于end_date")
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    # 解析数据类型
    try:
        data_types = parse_data_types(args.data_type)
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    ts_code = args.ts_code.strip() if args.ts_code else None

    # 创建数据库管理器
    db_manager = MySQLManager(
        host=args.db_host,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        port=args.db_port,
    )

    # 创建导出器
    exporter = MySQLToCSVExporter(
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        logger=logger,
        db_manager=db_manager,
    )

    # 创建过滤阈值
    thresholds = FilterThresholds(
        min_history_days=args.min_history_days,
        min_annual_vol=args.min_annual_vol,
        min_avg_turnover_yuan=args.min_avg_turnover_yuan,
    )

    # 验证单标的代码
    if ts_code:
        basic_info = exporter.db_manager.get_instrument_basic(ts_code=ts_code)
        if not basic_info:
            logger.error("未在数据库中找到标的代码: %s", ts_code)
            return 1
        instrument_type = basic_info[0]["data_type"]
        if instrument_type not in data_types:
            logger.error(
                "标的代码%s的数据类型为%s，与指定的数据类型不匹配",
                ts_code,
                instrument_type,
            )
            return 1
        data_types = [instrument_type]

    # 确保目录存在
    exporter._ensure_directories(
        need_basic=args.export_basic,
        daily_types=data_types if args.export_daily else [],
    )

    basic_stats: Dict[str, int] = {}
    daily_stats: Dict[str, Dict[str, object]] = {}

    # 导出基础信息
    if args.export_basic:
        logger.info("开始导出基础信息...")
        basic_stats = exporter.export_basic_info(
            data_types,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            thresholds=thresholds,
        )

    # 导出日线数据
    if args.export_daily:
        logger.info("开始导出日线数据...")
        daily_stats = exporter.export_daily_data(
            data_types=data_types,
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
            thresholds=thresholds,
        )

    # 导出基准指数数据
    benchmark_stats: Dict[str, int] = {}
    if args.include_benchmark:
        logger.info("开始导出基准指数数据...")
        benchmark_exporter = BenchmarkExporter(
            output_dir=args.output_dir,
            db_manager=db_manager,
            logger=logger,
        )

        try:
            # 加载基准配置
            benchmarks = benchmark_exporter.load_benchmark_config(args.benchmark_config)
            logger.info("加载基准指数配置: %d 个基准", len(benchmarks))

            # 导出基准数据
            benchmark_stats = benchmark_exporter.export_benchmark_data(
                benchmarks=benchmarks,
                start_date=start_date,
                end_date=end_date,
            )

            # 打印统计
            total_records = sum(benchmark_stats.values())
            logger.info(
                "基准指数导出完成: %d 个基准, 共 %d 条记录",
                len([v for v in benchmark_stats.values() if v > 0]),
                total_records,
            )
        except FileNotFoundError as exc:
            logger.error("基准配置文件不存在: %s", exc)
            return 1
        except ValueError as exc:
            logger.error("基准配置文件格式错误: %s", exc)
            return 1

    # 生成元数据
    if args.export_metadata:
        logger.info("生成导出元数据...")
        metadata_gen = MetadataGenerator(
            output_dir=Path(args.output_dir).expanduser(),
            db_manager=db_manager,
        )

        # 构建过滤配置
        filter_config = None
        if args.export_daily:
            filter_config = {
                "filters": {
                    "min_history_days": thresholds.min_history_days,
                    "min_annual_vol": thresholds.min_annual_vol,
                    "min_avg_turnover_yuan": thresholds.min_avg_turnover_yuan,
                    "applied_to_types": ["etf", "fund"],
                    "boundary_inclusive_as_fail": True,
                },
                "filter_statistics": {
                    dtype: stats.get("filter_statistics", {})
                    for dtype, stats in daily_stats.items()
                },
            }

        metadata = metadata_gen.generate_metadata(
            start_date=start_date,
            end_date=end_date,
            data_types=data_types,
            export_basic=args.export_basic,
            export_daily=args.export_daily,
            basic_stats=basic_stats,
            daily_stats=daily_stats,
            filter_config=filter_config,
        )
        metadata_gen.save_metadata(metadata, logger)

    logger.info("导出流程全部完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).error("用户中断执行")
        sys.exit(1)
    except Exception as exc:
        logging.getLogger(__name__).exception("导出过程出现异常: %s", exc)
        sys.exit(1)
