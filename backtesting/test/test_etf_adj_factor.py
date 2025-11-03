"""
ETF复权因子功能测试

测试159300.SZ（沪深300ETF）在2024年的复权因子数据
该ETF在2024年6月24日进行了分红
"""

import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from common.mysql_manager import MySQLManager
import pandas as pd


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_etf_adj_factor():
    """测试ETF复权因子功能"""
    logger = logging.getLogger(__name__)

    # 测试参数
    ts_code = '159300.SZ'
    start_date = '20240101'
    end_date = '20241231'
    dividend_date = '20240624'  # 分红日

    logger.info("=" * 80)
    logger.info(f"开始测试ETF复权因子功能")
    logger.info(f"测试标的: {ts_code}")
    logger.info(f"日期范围: {start_date} - {end_date}")
    logger.info(f"预期分红日: {dividend_date}")
    logger.info("=" * 80)

    # 初始化数据库管理器
    db_manager = MySQLManager()

    # 1. 查询数据
    logger.info("\n【步骤1】查询ETF日线数据")
    data = db_manager.get_instrument_daily(
        data_type='etf',
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date
    )

    if not data:
        logger.error(f"未找到{ts_code}的数据，请先运行数据获取脚本")
        return False

    logger.info(f"查询到{len(data)}条记录")

    # 转换为DataFrame方便分析
    df = pd.DataFrame(data)

    # 2. 检查adj_factor字段
    logger.info("\n【步骤2】检查adj_factor字段")
    if 'adj_factor' not in df.columns:
        logger.error("数据表中没有adj_factor字段，请检查表结构")
        return False

    # 统计adj_factor数据
    adj_factor_count = df['adj_factor'].notna().sum()
    logger.info(f"adj_factor字段存在: ✓")
    logger.info(f"有效adj_factor数据: {adj_factor_count}/{len(df)} ({adj_factor_count/len(df)*100:.1f}%)")

    if adj_factor_count == 0:
        logger.error("所有记录的adj_factor都为空，请检查数据获取逻辑")
        return False

    # 3. 检查分红日前后的adj_factor变化
    logger.info(f"\n【步骤3】检查分红日({dividend_date})前后的adj_factor变化")

    # 筛选分红日前后10天的数据
    df_sorted = df.sort_values('trade_date')
    dividend_idx = df_sorted[df_sorted['trade_date'] == dividend_date].index

    if len(dividend_idx) == 0:
        logger.warning(f"未找到分红日{dividend_date}的数据，可能该日期为非交易日")
        # 查找最接近的交易日
        df_sorted['trade_date_int'] = df_sorted['trade_date'].astype(int)
        closest_idx = (df_sorted['trade_date_int'] - int(dividend_date)).abs().idxmin()
        closest_date = df_sorted.loc[closest_idx, 'trade_date']
        logger.info(f"使用最接近的交易日: {closest_date}")
        dividend_idx = [closest_idx]

    dividend_idx = dividend_idx[0]
    start_idx = max(0, df_sorted.index.get_loc(dividend_idx) - 10)
    end_idx = min(len(df_sorted), df_sorted.index.get_loc(dividend_idx) + 11)

    df_around_dividend = df_sorted.iloc[start_idx:end_idx]

    logger.info(f"\n分红日前后的adj_factor变化:")
    logger.info("-" * 80)
    logger.info(f"{'日期':<12} {'收盘价':<10} {'复权因子':<12} {'后复权价':<12} {'变化率':<10}")
    logger.info("-" * 80)

    prev_adj_close = None
    dividend_trade_date = df_sorted.loc[dividend_idx, 'trade_date'] if isinstance(dividend_idx, (int, pd.Index)) else None

    for _, row in df_around_dividend.iterrows():
        trade_date = row['trade_date']
        close_price = row.get('close_price', 0)
        adj_factor = row.get('adj_factor')

        if adj_factor is not None and close_price is not None:
            adj_close = float(close_price) * float(adj_factor)
            change = ((adj_close - prev_adj_close) / prev_adj_close * 100) if prev_adj_close else 0

            marker = " <== 分红日" if trade_date == dividend_date or trade_date == dividend_trade_date else ""
            logger.info(f"{trade_date:<12} {close_price:<10.4f} {adj_factor:<12.6f} {adj_close:<12.4f} {change:>9.2f}%{marker}")

            prev_adj_close = adj_close
        else:
            logger.info(f"{trade_date:<12} {close_price:<10} {'N/A':<12} {'N/A':<12} {'N/A':<10}")

    # 4. 检查最新交易日的adj_factor
    logger.info(f"\n【步骤4】检查最新交易日的adj_factor")
    latest_data = df_sorted.iloc[-1]
    latest_adj_factor = latest_data.get('adj_factor')

    logger.info(f"最新交易日: {latest_data['trade_date']}")
    logger.info(f"最新adj_factor: {latest_adj_factor}")

    if latest_adj_factor and abs(float(latest_adj_factor) - 1.0) < 0.001:
        logger.info("最新adj_factor接近1.0: ✓")
    else:
        logger.warning(f"最新adj_factor不接近1.0，实际值为{latest_adj_factor}")

    # 5. 计算前复权和后复权价格示例
    logger.info(f"\n【步骤5】复权价格计算示例（最近5个交易日）")
    logger.info("-" * 100)
    logger.info(f"{'日期':<12} {'原始收盘':<10} {'复权因子':<12} {'后复权价':<12} {'前复权价':<12}")
    logger.info("-" * 100)

    latest_adj_factor_val = float(latest_adj_factor) if latest_adj_factor else 1.0

    for _, row in df_sorted.tail(5).iterrows():
        trade_date = row['trade_date']
        close_price = row.get('close_price', 0)
        adj_factor = row.get('adj_factor')

        if adj_factor is not None and close_price is not None:
            adj_close_back = float(close_price) * float(adj_factor)  # 后复权
            adj_close_forward = float(close_price) / latest_adj_factor_val  # 前复权

            logger.info(f"{trade_date:<12} {close_price:<10.4f} {adj_factor:<12.6f} "
                       f"{adj_close_back:<12.4f} {adj_close_forward:<12.4f}")

    logger.info("\n" + "=" * 80)
    logger.info("测试完成！")
    logger.info("=" * 80)

    return True


if __name__ == '__main__':
    setup_logging()
    success = test_etf_adj_factor()
    sys.exit(0 if success else 1)
