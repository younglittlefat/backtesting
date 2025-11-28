#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号生成器配置模块

包含费用模型配置和默认参数。
"""

# 费用模型配置
COST_MODELS = {
    'default': {'commission': 0.0, 'spread': 0.0},
    'cn_etf': {'commission': 0.0001, 'spread': 0.0001},
    'cn_stock': {'commission': 0.0003, 'spread': 0.001},
    'us_stock': {'commission': 0.001, 'spread': 0.0005},
}

# 默认参数
DEFAULT_CASH = 100000
DEFAULT_LOOKBACK_DAYS = 250
DEFAULT_TARGET_POSITIONS = 10
DEFAULT_MAX_POSITION_PCT = 0.05
DEFAULT_MIN_BUY_SIGNALS = 1
DEFAULT_COST_MODEL = 'cn_etf'
DEFAULT_DATA_DIR = 'data/csv/daily'
