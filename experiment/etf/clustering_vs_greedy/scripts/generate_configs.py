#!/usr/bin/env python3
"""
生成聚类 vs 贪心对比实验的配置文件

为每个 (评分维度, 筛选周期, 选择算法) 组合生成一个JSON配置文件
"""
import json
from pathlib import Path
from typing import Dict, Any

# 实验根目录
EXPERIMENT_DIR = Path(__file__).parent.parent
CONFIGS_DIR = EXPERIMENT_DIR / "configs"

# 评分维度配置
SCORING_DIMENSIONS = {
    "adx_score": {
        "description": "ADX趋势强度",
        "weights": {
            "trend": {"weight": 1.0, "sub_weights": {"adx_score": 1.0, "trend_consistency": 0, "trend_quality": 0}},
            "return": {"weight": 0, "sub_weights": {"momentum_3m": 0, "momentum_12m": 0, "excess_return_20d": 0, "excess_return_60d": 0}},
            "liquidity": {"weight": 0, "sub_weights": {"liquidity_score": 0, "price_efficiency": 0, "volume_trend": 0}},
            "risk_adjusted": {"weight": 0, "sub_weights": {"idr": 0}},
        }
    },
    "liquidity_score": {
        "description": "流动性评分",
        "weights": {
            "trend": {"weight": 0, "sub_weights": {"adx_score": 0, "trend_consistency": 0, "trend_quality": 0}},
            "return": {"weight": 0, "sub_weights": {"momentum_3m": 0, "momentum_12m": 0, "excess_return_20d": 0, "excess_return_60d": 0}},
            "liquidity": {"weight": 1.0, "sub_weights": {"liquidity_score": 1.0, "price_efficiency": 0, "volume_trend": 0}},
            "risk_adjusted": {"weight": 0, "sub_weights": {"idr": 0}},
        }
    },
    "price_efficiency": {
        "description": "价格效率",
        "weights": {
            "trend": {"weight": 0, "sub_weights": {"adx_score": 0, "trend_consistency": 0, "trend_quality": 0}},
            "return": {"weight": 0, "sub_weights": {"momentum_3m": 0, "momentum_12m": 0, "excess_return_20d": 0, "excess_return_60d": 0}},
            "liquidity": {"weight": 1.0, "sub_weights": {"liquidity_score": 0, "price_efficiency": 1.0, "volume_trend": 0}},
            "risk_adjusted": {"weight": 0, "sub_weights": {"idr": 0}},
        }
    },
    "trend_consistency": {
        "description": "趋势一致性",
        "weights": {
            "trend": {"weight": 1.0, "sub_weights": {"adx_score": 0, "trend_consistency": 1.0, "trend_quality": 0}},
            "return": {"weight": 0, "sub_weights": {"momentum_3m": 0, "momentum_12m": 0, "excess_return_20d": 0, "excess_return_60d": 0}},
            "liquidity": {"weight": 0, "sub_weights": {"liquidity_score": 0, "price_efficiency": 0, "volume_trend": 0}},
            "risk_adjusted": {"weight": 0, "sub_weights": {"idr": 0}},
        }
    },
    "momentum_12m": {
        "description": "12个月动量",
        "weights": {
            "trend": {"weight": 0, "sub_weights": {"adx_score": 0, "trend_consistency": 0, "trend_quality": 0}},
            "return": {"weight": 1.0, "sub_weights": {"momentum_3m": 0, "momentum_12m": 1.0, "excess_return_20d": 0, "excess_return_60d": 0}},
            "liquidity": {"weight": 0, "sub_weights": {"liquidity_score": 0, "price_efficiency": 0, "volume_trend": 0}},
            "risk_adjusted": {"weight": 0, "sub_weights": {"idr": 0}},
        }
    },
    "trend_quality": {
        "description": "趋势质量",
        "weights": {
            "trend": {"weight": 1.0, "sub_weights": {"adx_score": 0, "trend_consistency": 0, "trend_quality": 1.0}},
            "return": {"weight": 0, "sub_weights": {"momentum_3m": 0, "momentum_12m": 0, "excess_return_20d": 0, "excess_return_60d": 0}},
            "liquidity": {"weight": 0, "sub_weights": {"liquidity_score": 0, "price_efficiency": 0, "volume_trend": 0}},
            "risk_adjusted": {"weight": 0, "sub_weights": {"idr": 0}},
        }
    },
}

# 筛选周期配置
TIME_PERIODS = {
    "2019_2021": {
        "start_date": "20190102",
        "end_date": "20211231",
        "description": "熊市前筛选期"
    },
    "2022_2023": {
        "start_date": "20220102",
        "end_date": "20231231",
        "description": "牛市前筛选期"
    },
}

# 选择算法配置
SELECTION_ALGORITHMS = {
    "greedy": {
        "enable_clustering_selection": False,
        "description": "贪心算法+硬编码行业分类"
    },
    "clustering": {
        "enable_clustering_selection": True,
        "clustering_method": "ward",
        "clustering_min_score_percentile": 20.0,
        "description": "层次聚类选择"
    },
}


def create_config(dimension: str, period: str, algorithm: str) -> Dict[str, Any]:
    """创建单个配置文件"""
    dim_config = SCORING_DIMENSIONS[dimension]
    period_config = TIME_PERIODS[period]
    algo_config = SELECTION_ALGORITHMS[algorithm]

    output_filename = f"{dimension}_{period}_{algorithm}.csv"

    config = {
        "version": "3.0",
        "description": f"聚类vs贪心实验: {dim_config['description']} | {period_config['description']} | {algo_config['description']}",

        "paths": {
            "data_dir": "data/chinese_etf",
            "output_path": f"experiment/etf/clustering_vs_greedy/pools/{output_filename}"
        },

        "time_range": {
            "start_date": period_config["start_date"],
            "end_date": period_config["end_date"]
        },

        "stage1_initial_filter": {
            "min_turnover": 2000,
            "min_listing_days": 180,
            "turnover_lookback_days": 30
        },

        "stage2_core_filter": {
            "adx": {
                "period": 14,
                "lookback_days": 250,
                "percentile": 80.0
            },
            "ma_backtest": {
                "enable": False,
                "short_period": 20,
                "long_period": 50,
                "ret_dd_percentile": 70.0
            },
            "volatility": {
                "min": 0.20,
                "max": 0.60,
                "lookback_days": 252
            },
            "momentum": {
                "periods": [63, 252],
                "min_positive": True
            },
            "filter_mode": {
                "skip_percentile_filtering": True,
                "skip_range_filtering": True
            }
        },

        "scoring_system": {
            "enable_unbiased_scoring": True,
            "benchmark": {
                "ts_code": "510300.SH"
            },
            "windows": {
                "excess_return": {"short": 20, "long": 60},
                "volume": {"short": 20, "long": 60},
                "trend_quality": 60,
                "trend_consistency": 63,
                "price_efficiency": 252,
                "liquidity_score": 30
            },
            "weights": dim_config["weights"]
        },

        "stage3_diversification": {
            "target_portfolio_size": 20,
            "max_correlation": 0.7,
            "min_industries": 3,
            "deduplication": {
                "enable": True,
                "min_ratio": 0.8,
                "thresholds": [0.98, 0.95, 0.92, 0.90]
            },
            "diversify_v2": {
                "enable": False,
                "score_diff_threshold": 0.05
            },
            "clustering": {
                "_description": "聚类选择：数据驱动的行业分类，替代贪心算法",
                "enable": algo_config.get("enable_clustering_selection", False),
                "method": algo_config.get("clustering_method", "ward"),
                "min_score_percentile": algo_config.get("clustering_min_score_percentile", 20.0)
            },
            "balance_industries": True
        },

        "output_options": {
            "verbose": True,
            "with_analysis": False,
            "skip_portfolio_optimization": False
        }
    }

    return config


def generate_all_configs():
    """生成所有配置文件"""
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

    generated = []

    for dimension in SCORING_DIMENSIONS:
        for period in TIME_PERIODS:
            for algorithm in SELECTION_ALGORITHMS:
                config = create_config(dimension, period, algorithm)

                filename = f"{dimension}_{period}_{algorithm}.json"
                filepath = CONFIGS_DIR / filename

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)

                generated.append(filename)
                print(f"  Created: {filename}")

    return generated


def main():
    print("=" * 60)
    print("生成聚类 vs 贪心对比实验配置文件")
    print("=" * 60)
    print(f"\n评分维度: {len(SCORING_DIMENSIONS)} 个")
    print(f"筛选周期: {len(TIME_PERIODS)} 个")
    print(f"选择算法: {len(SELECTION_ALGORITHMS)} 个")
    print(f"总配置数: {len(SCORING_DIMENSIONS) * len(TIME_PERIODS) * len(SELECTION_ALGORITHMS)} 个")
    print()

    generated = generate_all_configs()

    print()
    print(f"完成！共生成 {len(generated)} 个配置文件")
    print(f"输出目录: {CONFIGS_DIR}")


if __name__ == "__main__":
    main()
