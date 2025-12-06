#!/bin/bash
################################################################################
# Mega Test结果收集脚本
#
# 功能：
# - 从各个回测实验目录中提取global_summary CSV
# - 解析实验配置（启用的选项和参数）
# - 生成汇总CSV文件
#
# 用法：
#   ./collect_mega_test_results.sh <实验根目录> <输出CSV路径>
#
# 作者: Claude Code
# 日期: 2025-11-22
################################################################################

# ============================================================================
# 参数检查
# ============================================================================

if [ $# -ne 2 ]; then
    echo "用法: $0 <实验根目录> <输出CSV路径>"
    exit 1
fi

EXPERIMENT_DIR="$1"
OUTPUT_CSV="$2"

if [ ! -d "$EXPERIMENT_DIR" ]; then
    echo "错误: 实验目录不存在: $EXPERIMENT_DIR"
    exit 1
fi

# ============================================================================
# 颜色定义
# ============================================================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# 调用Python脚本进行结果收集
# ============================================================================

echo -e "${CYAN}▶ 开始收集实验结果...${NC}"

python3 << 'PYTHON_SCRIPT'
import os
import sys
import glob
import re
import csv
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

# 从环境变量读取参数
EXPERIMENT_DIR = os.environ.get('EXPERIMENT_DIR')
OUTPUT_CSV = os.environ.get('OUTPUT_CSV')
METADATA_FILE = os.environ.get('EXPERIMENT_METADATA_FILE')

# ============================================================================
# 尝试从元数据文件读取实验类型
# ============================================================================

def detect_experiment_type():
    """
    检测实验类型，优先从元数据文件读取，其次使用启发式方法

    返回: 'mega_test_greedy', 'mega_test_full', 或 'unknown'
    """
    # 方法1: 从元数据文件读取
    if METADATA_FILE and os.path.exists(METADATA_FILE):
        try:
            import json
            with open(METADATA_FILE, 'r') as f:
                meta = json.load(f)
                exp_type = meta.get('experiment_type', 'unknown')
                print(f"从元数据文件识别实验类型: {exp_type}")
                return exp_type
        except Exception as e:
            print(f"读取元数据文件失败: {e}")

    # 方法2: 启发式检测（基于父目录名）
    parent_dir = os.path.dirname(EXPERIMENT_DIR)
    dir_name = os.path.basename(parent_dir)

    if 'greedy' in dir_name.lower():
        print(f"从目录名启发式识别: mega_test_greedy")
        return 'mega_test_greedy'
    elif 'full' in dir_name.lower():
        print(f"从目录名启发式识别: mega_test_full")
        return 'mega_test_full'

    print(f"无法识别实验类型，使用通用模式")
    return 'unknown'

EXPERIMENT_TYPE = detect_experiment_type()

# ============================================================================
# 核心超参定义（与主脚本保持一致）
# 包含 MACD 和 KAMA 策略的所有选项
# ============================================================================

CORE_OPTIONS = [
    # MACD 专用选项
    'enable-hysteresis',
    'enable-zero-axis',
    'confirm-bars-sell',
    'min-hold-bars',
    # KAMA 专用选项
    'enable-efficiency-filter',
    'enable-slope-confirmation',
    # 通用过滤器选项
    'enable-slope-filter',
    'enable-adx-filter',
    'enable-volume-filter',
    'enable-confirm-filter',
    # 通用止损选项
    'enable-loss-protection',
    'enable-trailing-stop',
    'enable-atr-stop'
]

# 非store_true参数及其默认值
NON_BOOLEAN_PARAMS = {
    # 通用过滤器参数
    'adx-period': 14,
    'adx-threshold': 25.0,
    'volume-period': 20,
    'volume-ratio': 1.2,
    'slope-lookback': 5,
    'confirm-bars': 2,  # enable-confirm-filter的附属参数
    # 通用止损参数
    'max-consecutive-losses': 3,
    'pause-bars': 10,
    'trailing-stop-pct': 0.05,
    'atr-period': 14,
    'atr-multiplier': 2.5,
    # MACD 专用参数
    'hysteresis-mode': 'std',
    'hysteresis-k': 0.5,
    'hysteresis-window': 20,
    'zero-axis-mode': 'symmetric',
    # KAMA 专用参数
    'min-efficiency-ratio': 0.3,
    'min-slope-periods': 3,
    # 注意：confirm-bars-sell和min-hold-bars是独立开关，值在组合中时固定
}

# ============================================================================
# 解析实验目录名称，提取配置
# ============================================================================

def parse_experiment_name(exp_name: str) -> Dict[str, any]:
    """
    从实验目录名称解析出配置

    支持两种格式:
    1. "1_macd_enable-hysteresis_enable-loss-protection"
    2. "exp_macd_enable-hysteresis_enable-loss-protection"

    => {
        'exp_num': 1 或 None,
        'enable-hysteresis': True,
        'enable-loss-protection': True,
        'confirm-bars-sell': 2 或 False (检测到confirm-bars-sell时为2)
        'min-hold-bars': 3 或 False (检测到min-hold-bars时为3)
        ...
    }
    """
    config = {}

    # 提取实验编号（如果有）
    match = re.match(r'^(\d+)_macd', exp_name)
    if match:
        config['exp_num'] = int(match.group(1))
    else:
        # 尝试从exp_前缀提取
        if exp_name.startswith('exp_'):
            config['exp_num'] = None  # 旧格式，无编号
        else:
            config['exp_num'] = None

    # 检查每个核心选项是否启用
    for opt in CORE_OPTIONS:
        if opt == 'confirm-bars-sell':
            # 检测confirm-bars-sell，返回值2或False
            if 'confirm-bars-sell' in exp_name or 'confirm_bars_sell' in exp_name:
                config[opt] = 2
            else:
                config[opt] = False
        elif opt == 'min-hold-bars':
            # 检测min-hold-bars，返回值3或False
            if 'min-hold-bars' in exp_name or 'min_hold_bars' in exp_name:
                config[opt] = 3
            else:
                config[opt] = False
        else:
            # 其他选项返回True/False
            config[opt] = opt in exp_name

    # 检查baseline
    if 'baseline' in exp_name or exp_name.endswith('_base'):
        config['is_baseline'] = True
    else:
        config['is_baseline'] = False

    return config

# ============================================================================
# 从global_summary CSV中提取指标
# ============================================================================

def extract_metrics_from_summary(summary_path: str) -> Optional[Dict[str, float]]:
    """
    从global_summary CSV中提取关键指标

    返回:
    {
        'return_mean': 平均收益率,
        'return_median': 中位数收益率,
        'sharpe_mean': 平均夏普比率,
        'sharpe_median': 中位数夏普比率,
        'max_dd_mean': 平均最大回撤,
        'max_dd_median': 中位数最大回撤
    }
    """
    try:
        df = pd.read_csv(summary_path, encoding='utf-8-sig')

        # 支持中文和英文列名
        col_mapping = {
            'return_mean': ['年化收益率-均值(%)', 'Return [%] Mean'],
            'return_median': ['年化收益率-中位数(%)', 'Return [%] Median'],
            'sharpe_mean': ['夏普-均值', 'Sharpe Ratio Mean'],
            'sharpe_median': ['夏普-中位数', 'Sharpe Ratio Median'],
            'max_dd_mean': ['最大回撤-均值(%)', 'Max. Drawdown [%] Mean'],
            'max_dd_median': ['最大回撤-中位数(%)', 'Max. Drawdown [%] Median'],
            # 新增指标
            'win_rate_mean': ['胜率-均值(%)', 'Win Rate [%] Mean'],
            'win_rate_median': ['胜率-中位数(%)', 'Win Rate [%] Median'],
            'pl_ratio_mean': ['盈亏比-均值', 'Profit/Loss Ratio Mean'],
            'pl_ratio_median': ['盈亏比-中位数', 'Profit/Loss Ratio Median'],
            'trades_mean': ['交易次数-均值', '# Trades Mean'],
            'trades_median': ['交易次数-中位数', '# Trades Median'],
        }

        # 如果是汇总格式（单行），直接读取
        if len(df) == 1:
            metrics = {}
            for key, possible_names in col_mapping.items():
                found = False
                for col_name in possible_names:
                    if col_name in df.columns:
                        metrics[key] = df[col_name].iloc[0]
                        found = True
                        break
                if not found:
                    print(f"警告: {summary_path} 未找到列: {possible_names}")
                    metrics[key] = None

            # 提取标的数量
            if '标的数量' in df.columns:
                metrics['num_stocks'] = df['标的数量'].iloc[0]
            else:
                metrics['num_stocks'] = None

            return metrics

        # 如果是详细格式（多行），需要计算统计值
        # 检查必需的列是否存在
        required_cols_variants = [
            ['Return [%]', 'Sharpe Ratio', 'Max. Drawdown [%]'],
            ['年化收益率(%)', '夏普比率', '最大回撤(%)']
        ]

        cols_found = None
        for variant in required_cols_variants:
            if all(col in df.columns for col in variant):
                cols_found = variant
                break

        if not cols_found:
            print(f"警告: {summary_path} 列格式不匹配")
            print(f"可用列: {df.columns.tolist()}")
            return None

        # 提取指标
        metrics = {
            'return_mean': df[cols_found[0]].mean(),
            'return_median': df[cols_found[0]].median(),
            'sharpe_mean': df[cols_found[1]].mean(),
            'sharpe_median': df[cols_found[1]].median(),
            'max_dd_mean': df[cols_found[2]].mean(),
            'max_dd_median': df[cols_found[2]].median(),
            'num_stocks': len(df)
        }

        # 提取新增指标（详细格式）
        for col in ['胜率(%)', 'Win Rate [%]']:
            if col in df.columns:
                metrics['win_rate_mean'] = float(df[col].mean())
                metrics['win_rate_median'] = float(df[col].median())
                break
        for col in ['盈亏比', 'Profit/Loss Ratio']:
            if col in df.columns:
                metrics['pl_ratio_mean'] = float(df[col].dropna().mean()) if df[col].dropna().size else None
                metrics['pl_ratio_median'] = float(df[col].dropna().median()) if df[col].dropna().size else None
                break
        for col in ['交易次数', '# Trades']:
            if col in df.columns:
                metrics['trades_mean'] = float(df[col].mean())
                metrics['trades_median'] = float(df[col].median())
                break

        return metrics

    except Exception as e:
        print(f"错误: 无法读取 {summary_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# 查找global_summary文件
# ============================================================================

def find_global_summary(exp_dir: str) -> Optional[str]:
    """
    在实验目录中查找global_summary CSV文件

    路径格式: <exp_dir>/summary/global_summary_*.csv
    """
    pattern = os.path.join(exp_dir, 'summary', 'global_summary_*.csv')
    matches = glob.glob(pattern)

    if not matches:
        return None

    # 如果有多个，取最新的
    if len(matches) > 1:
        matches.sort(key=os.path.getmtime, reverse=True)

    return matches[0]

# ============================================================================
# 主收集函数
# ============================================================================

def collect_results():
    """
    遍历所有实验目录，收集结果并生成CSV
    """
    print(f"实验根目录: {EXPERIMENT_DIR}")
    print(f"输出CSV: {OUTPUT_CSV}")

    # 查找所有实验子目录
    # 根据实验类型使用不同的匹配规则
    exp_dirs = []

    if EXPERIMENT_TYPE == 'mega_test_greedy':
        # 贪心筛选格式: baseline, single_xxx, k2_xxx
        print(f"使用贪心筛选目录匹配规则")
        for item in os.listdir(EXPERIMENT_DIR):
            item_path = os.path.join(EXPERIMENT_DIR, item)
            if os.path.isdir(item_path):
                if (item == 'baseline' or
                    re.match(r'^single_', item) or
                    re.match(r'^k\d+_', item)):
                    exp_dirs.append((item, item_path))

    elif EXPERIMENT_TYPE == 'mega_test_full':
        # 完整因子设计格式: 数字_macd_xxx 或 exp_macd_xxx
        print(f"使用完整测试目录匹配规则")
        for item in os.listdir(EXPERIMENT_DIR):
            item_path = os.path.join(EXPERIMENT_DIR, item)
            if os.path.isdir(item_path):
                if (re.match(r'^\d+_macd', item) or
                    re.match(r'^exp_macd', item) or
                    'macd' in item.lower()):
                    exp_dirs.append((item, item_path))

    else:
        # 通用模式: 尝试匹配所有可能的格式
        print(f"使用通用目录匹配规则")
        for item in os.listdir(EXPERIMENT_DIR):
            item_path = os.path.join(EXPERIMENT_DIR, item)
            if os.path.isdir(item_path):
                # 匹配所有已知格式
                if (re.match(r'^\d+_macd', item) or
                    re.match(r'^exp_macd', item) or
                    'macd' in item.lower() or
                    item == 'baseline' or
                    re.match(r'^single_', item) or
                    re.match(r'^k\d+_', item)):
                    exp_dirs.append((item, item_path))

    # 尝试按实验编号排序，如果没有编号则按名称排序
    def sort_key(x):
        match = re.match(r'^(\d+)_', x[0])
        if match:
            return (0, int(match.group(1)), x[0])  # 有编号的排在前面
        else:
            return (1, 0, x[0])  # 无编号的按名称排序

    exp_dirs.sort(key=sort_key)

    print(f"找到 {len(exp_dirs)} 个实验目录")

    # 收集所有结果
    results = []

    for exp_name, exp_path in exp_dirs:
        print(f"  处理: {exp_name}...")

        # 解析配置
        config = parse_experiment_name(exp_name)

        # 查找global_summary文件
        summary_path = find_global_summary(exp_path)

        if not summary_path:
            print(f"    警告: 未找到global_summary文件")
            continue

        # 提取指标
        metrics = extract_metrics_from_summary(summary_path)

        if not metrics:
            print(f"    警告: 无法提取指标")
            continue

        # 合并配置和指标
        row = {**config, **metrics}
        row['exp_name'] = exp_name
        row['summary_path'] = summary_path

        results.append(row)
        print(f"    ✓ 成功提取指标")

    # 生成CSV
    if not results:
        print("错误: 没有成功收集到任何结果")
        return False

    # 构建CSV表头
    csv_columns = ['exp_num', 'exp_name']

    # 添加核心选项列
    for opt in CORE_OPTIONS:
        csv_columns.append(opt)

    # 添加非布尔参数列（根据启用的选项决定是否显示值）
    for param in NON_BOOLEAN_PARAMS.keys():
        csv_columns.append(param)

    # 添加指标列
    csv_columns.extend([
        'return_mean',
        'return_median',
        'sharpe_mean',
        'sharpe_median',
        'max_dd_mean',
        'max_dd_median',
        # 新增指标
        'win_rate_mean',
        'win_rate_median',
        'pl_ratio_mean',
        'pl_ratio_median',
        'trades_mean',
        'trades_median',
        'num_stocks',
        'summary_path'
    ])

    # 按夏普中位数降序排序结果
    results.sort(key=lambda x: x.get('sharpe_median', -float('inf')), reverse=True)
    print(f"\n按夏普中位数降序排序")

    # 写入CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction='ignore')
        writer.writeheader()

        for row in results:
            # 填充非布尔参数的值
            for param, default_value in NON_BOOLEAN_PARAMS.items():
                # 判断该参数是否应该生效
                if param.startswith('adx-') and not row.get('enable-adx-filter', False):
                    row[param] = ''
                elif param.startswith('volume-') and not row.get('enable-volume-filter', False):
                    row[param] = ''
                elif param == 'slope-lookback' and not row.get('enable-slope-filter', False):
                    row[param] = ''
                elif param == 'confirm-bars' and not row.get('enable-confirm-filter', False):
                    row[param] = ''
                elif param in ['max-consecutive-losses', 'pause-bars'] and not row.get('enable-loss-protection', False):
                    row[param] = ''
                elif param == 'trailing-stop-pct' and not row.get('enable-trailing-stop', False):
                    row[param] = ''
                elif param.startswith('atr-') and not row.get('enable-atr-stop', False):
                    row[param] = ''
                elif param.startswith('hysteresis-') and not row.get('enable-hysteresis', False):
                    row[param] = ''
                elif param == 'zero-axis-mode' and not row.get('enable-zero-axis', False):
                    row[param] = ''
                elif param == 'min-efficiency-ratio' and not row.get('enable-efficiency-filter', False):
                    row[param] = ''
                elif param == 'min-slope-periods' and not row.get('enable-slope-confirmation', False):
                    row[param] = ''
                else:
                    # 对于生效的参数，显示默认值
                    if param in ['adx-period', 'adx-threshold'] and row.get('enable-adx-filter', False):
                        row[param] = default_value
                    elif param in ['volume-period', 'volume-ratio'] and row.get('enable-volume-filter', False):
                        row[param] = default_value
                    elif param == 'slope-lookback' and row.get('enable-slope-filter', False):
                        row[param] = default_value
                    elif param == 'confirm-bars' and row.get('enable-confirm-filter', False):
                        row[param] = default_value
                    elif param in ['max-consecutive-losses', 'pause-bars'] and row.get('enable-loss-protection', False):
                        row[param] = default_value
                    elif param == 'trailing-stop-pct' and row.get('enable-trailing-stop', False):
                        row[param] = default_value
                    elif param in ['atr-period', 'atr-multiplier'] and row.get('enable-atr-stop', False):
                        row[param] = default_value
                    elif param.startswith('hysteresis-') and row.get('enable-hysteresis', False):
                        row[param] = default_value
                    elif param == 'zero-axis-mode' and row.get('enable-zero-axis', False):
                        row[param] = default_value
                    elif param == 'min-efficiency-ratio' and row.get('enable-efficiency-filter', False):
                        row[param] = default_value
                    elif param == 'min-slope-periods' and row.get('enable-slope-confirmation', False):
                        row[param] = default_value
                    else:
                        row[param] = ''

            # 将布尔值转换为TRUE/FALSE，特殊值保持原样
            for opt in CORE_OPTIONS:
                val = row.get(opt, False)
                if opt == 'confirm-bars-sell':
                    # confirm-bars-sell: 2或空
                    row[opt] = 2 if val == 2 else ''
                elif opt == 'min-hold-bars':
                    # min-hold-bars: 3或空
                    row[opt] = 3 if val == 3 else ''
                else:
                    # 其他布尔选项: TRUE/FALSE
                    row[opt] = 'TRUE' if val else 'FALSE'

            writer.writerow(row)

    print(f"\n✓ 成功生成结果CSV: {OUTPUT_CSV}")
    print(f"  总计 {len(results)} 个实验结果")

    return True

# ============================================================================
# 执行
# ============================================================================

if __name__ == '__main__':
    success = collect_results()
    sys.exit(0 if success else 1)

PYTHON_SCRIPT

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ 结果收集完成${NC}"
else
    echo -e "${YELLOW}⚠ 结果收集失败${NC}"
fi

exit $exit_code
