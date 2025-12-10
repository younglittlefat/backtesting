"""2022-2023评分池子的牛市回测配置"""
import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = Path("/mnt/d/git/backtesting")  # 直接指定项目根目录

# 回测时间范围（2024年牛市）
START_DATE = "2024-01-01"
END_DATE = "2025-11-30"

# 数据目录
DATA_DIR = PROJECT_ROOT / "data" / "chinese_etf" / "daily"

# 结果输出目录
RESULTS_DIR = BASE_DIR / "results" / "bull_market_2024"

# 策略配置
STRATEGY = "kama_cross"
STRATEGY_PARAMS = {}  # 使用KAMA默认参数

# 自动发现所有池子CSV文件
def get_pool_files():
    """获取所有池子文件"""
    pools = {}
    for f in BASE_DIR.glob("single_*_pool_2022_2023.csv"):
        # 从文件名提取维度名称
        name = f.stem.replace("single_", "").replace("_pool_2022_2023", "")
        pools[name] = f
    return pools
