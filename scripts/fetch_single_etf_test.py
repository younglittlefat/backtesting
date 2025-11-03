"""
单个ETF数据获取测试脚本

仅获取指定ETF的日线和复权数据
"""

import sys
import os
import logging
import time

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

import tushare as ts
import pandas as pd
from common.mysql_manager import MySQLManager


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def fetch_single_etf_with_adj(ts_code, start_date, end_date, token):
    """获取单个ETF的日线和复权数据"""
    logger = logging.getLogger(__name__)

    logger.info(f"开始获取{ts_code}的数据: {start_date} - {end_date}")

    # 初始化Tushare
    ts.set_token(token)
    pro = ts.pro_api()

    # 获取日线数据
    logger.info("获取日线数据...")
    df_daily = pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    logger.info(f"获取到{len(df_daily)}条日线数据")

    # 获取复权因子
    logger.info("获取复权因子...")
    df_adj = pro.fund_adj(ts_code=ts_code, start_date=start_date, end_date=end_date)
    logger.info(f"获取到{len(df_adj)}条复权因子数据")

    # 合并数据
    if not df_daily.empty and not df_adj.empty:
        df = pd.merge(df_daily, df_adj[['trade_date', 'adj_factor']],
                     on='trade_date', how='left')
        logger.info(f"成功合并数据，共{len(df)}条记录")
    else:
        df = df_daily
        logger.warning("复权因子为空，使用原始日线数据")

    # 显示部分数据
    logger.info("\n数据样例（前5条）:")
    logger.info(df.head().to_string())

    # 存入数据库
    logger.info("\n开始存入数据库...")
    db_manager = MySQLManager()

    all_data = []
    for _, row in df.iterrows():
        data = {
            'data_type': 'etf',
            'ts_code': row['ts_code'],
            'trade_date': row['trade_date'],
            'open_price': row.get('open'),
            'high_price': row.get('high'),
            'low_price': row.get('low'),
            'close_price': row.get('close'),
            'pre_close': row.get('pre_close'),
            'adj_factor': row.get('adj_factor'),
            'change_amount': row.get('change'),
            'pct_change': row.get('pct_chg'),
            'volume': row.get('vol'),
            'amount': row.get('amount')
        }
        # 清理NaN值
        data = {k: (None if pd.isna(v) else v) for k, v in data.items()}
        all_data.append(data)

    success_count = db_manager.batch_insert_instrument_daily(all_data)
    logger.info(f"成功插入{success_count}条记录")

    return success_count


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    # 测试参数
    ts_code = '159300.SZ'
    start_date = '20240101'
    end_date = '20241231'
    token = '18e20abc9ab15f381594da84aac654a11890ecf119a35e2ed70283f0'

    logger.info("=" * 80)
    logger.info("单个ETF数据获取测试")
    logger.info(f"标的代码: {ts_code}")
    logger.info(f"日期范围: {start_date} - {end_date}")
    logger.info("=" * 80)

    try:
        count = fetch_single_etf_with_adj(ts_code, start_date, end_date, token)

        logger.info("\n" + "=" * 80)
        logger.info(f"数据获取完成，共{count}条记录")
        logger.info("=" * 80)

        return 0
    except Exception as e:
        logger.error(f"数据获取失败: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
