#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MySQL数据导出至CSV脚本

用于根据需求文档，将MySQL数据库中的ETF、指数、基金数据导出为CSV文件。

模块化重构版本 - 仅保留CLI入口调用
原有功能已拆分至 mysql_exporter 包
"""

import sys

from mysql_exporter.cli import main


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        import logging
        logging.getLogger(__name__).error("用户中断执行")
        sys.exit(1)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("导出过程出现异常: %s", exc)
        sys.exit(1)
