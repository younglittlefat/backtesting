#!/usr/bin/env python3
"""
简化的无偏权重优化器 - 仅运行ETF筛选测试

用于验证ETF筛选流程是否正常工作
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# 添加项目根目录到path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from etf_selector.config import FilterConfig
from etf_selector.selector import TrendETFSelector
from experiment.etf.macd_cross.selector_weights_grid_search.parameter_generator import UnbiasedWeightsGenerator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_etf_selector():
    """测试ETF筛选器"""
    logger.info("开始测试ETF筛选器...")

    # 获取第一个权重组合
    generator = UnbiasedWeightsGenerator()
    combinations = generator.generate_combinations()
    logger.info(f"共有 {len(combinations)} 个权重组合")

    test_weights = combinations[0]
    logger.info(f"使用权重配置: {test_weights}")

    # 创建自定义配置
    config = FilterConfig(
        enable_unbiased_scoring=True,
        primary_weight=test_weights.get('primary_weight', 1.0),
        secondary_weight=test_weights.get('secondary_weight', 0.0),
        adx_score_weight=test_weights['adx_weight'],
        trend_consistency_weight=test_weights['trend_consistency_weight'],
        price_efficiency_weight=test_weights['price_efficiency_weight'],
        liquidity_score_weight=test_weights['liquidity_weight'],
        momentum_3m_score_weight=test_weights['momentum_3m_weight'],
        momentum_12m_score_weight=test_weights['momentum_12m_weight'],
        target_portfolio_size=20,
        data_dir='data/chinese_etf',
        min_turnover=50_000_000,  # 5000万元（0.5亿）
        min_volatility=0.15,
        max_volatility=0.80,
        enable_ma_backtest_filter=False
    )

    logger.info("创建筛选器...")
    selector = TrendETFSelector(
        config=config,
        data_dir=str(project_root / "data" / "chinese_etf")
    )

    logger.info("执行筛选流程...")
    try:
        selected_etfs = selector.run_pipeline(
            start_date="2023-11-01",
            end_date="2025-11-01",
            target_size=20,
            verbose=True
        )

        logger.info(f"筛选完成，共 {len(selected_etfs)} 只ETF")

        if selected_etfs:
            # 保存结果
            output_dir = Path(__file__).parent / "results" / "unbiased"
            output_dir.mkdir(parents=True, exist_ok=True)

            df = pd.DataFrame(selected_etfs)
            output_file = output_dir / "test_etf_pool.csv"
            df.to_csv(output_file, index=False)
            logger.info(f"筛选结果已保存到: {output_file}")

            logger.info("\n筛选出的ETF:")
            for i, etf in enumerate(selected_etfs[:10], 1):
                logger.info(f"{i}. {etf.get('ts_code')} - {etf.get('name')}")

        return True

    except Exception as e:
        logger.error(f"筛选失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == '__main__':
    success = test_etf_selector()
    if success:
        logger.info("\n✓ 测试成功！ETF筛选器工作正常")
    else:
        logger.error("\n✗ 测试失败！请检查错误信息")
    sys.exit(0 if success else 1)
