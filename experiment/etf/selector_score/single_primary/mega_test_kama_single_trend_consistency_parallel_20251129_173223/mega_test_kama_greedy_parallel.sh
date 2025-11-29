#!/bin/bash
################################################################################
# KAMA策略贪心筛选超参组合测试脚本 - 并发版本
#
# 功能：
# - 通过递归剪枝大幅减少实验次数（预计50-200个实验 vs 1024个完整因子设计）
# - 每个阶段结束后自动筛选优秀候选
# - 支持中断续传，可在任意阶段暂停分析
# - 生成详细的阶段分析报告
# - ⭐ 支持阶段内并发执行，大幅提升实验效率
#
# 算法：
# 1. 阶段0: 测试Baseline（串行）
# 2. 阶段1: 单变量筛选（并发执行，OR逻辑筛选）
# 3. 阶段k: k变量筛选（并发执行，严格递增筛选）
# 4. 终止条件：某阶段无任何组合满足严格递增条件
#
# 用法：
#   ./mega_test_kama_greedy_parallel.sh                    # 执行完整实验流程（默认并发度3）
#   ./mega_test_kama_greedy_parallel.sh -j 5               # 指定并发度为5
#   ./mega_test_kama_greedy_parallel.sh --collect-only <实验目录>  # 仅收集已有结果
#
# 作者: Claude Code
# 日期: 2025-11-29
################################################################################

# ============================================================================
# 配置区域
# ============================================================================

# 并发度配置（可通过 -j 参数覆盖）
PARALLEL_JOBS=4

# 实验类型标识（用于自动识别实验目录）
EXPERIMENT_TYPE="mega_test_greedy"

# 基础路径配置
POOL_PATH="experiment/etf/selector_score/single_primary/single_trend_consistency_pool_2019_2021.csv"
DATA_DIR="data/chinese_etf/daily"
TEMP_PARAMS_PATH="config/test/kama_single_trend_consistency_strategy_params.json"
OUTPUT_BASE_DIR="experiment/etf/selector_score/single_primary/mega_test_kama_single_trend_consistency_parallel_$(date +%Y%m%d_%H%M%S)"
START_DATE="20220102"
END_DATE="20240102"

# 候选池和报告路径
CANDIDATES_DIR="${OUTPUT_BASE_DIR}/candidates"
REPORTS_DIR="${OUTPUT_BASE_DIR}/reports"
BACKTEST_DIR="${OUTPUT_BASE_DIR}/backtests"
LOGS_DIR="${OUTPUT_BASE_DIR}/logs"

# 结果汇总CSV路径
RESULT_CSV="${OUTPUT_BASE_DIR}/mega_test_greedy_summary.csv"

# 实验命令记录CSV路径
COMMANDS_CSV="${OUTPUT_BASE_DIR}/experiment_commands.csv"

# 元数据文件路径
METADATA_FILE="${OUTPUT_BASE_DIR}/.experiment_metadata.json"

# ============================================================================
# 定义核心超参开关（KAMA专用+通用过滤/止损）
# ============================================================================
declare -a CORE_OPTIONS=(
    "enable-efficiency-filter"
    "enable-slope-confirmation"
    "enable-slope-filter"
    "enable-adx-filter"
    "enable-volume-filter"
    "enable-confirm-filter"
    "enable-loss-protection"
    "enable-trailing-stop"
    "enable-atr-stop"
)

# ============================================================================
# 固定超参（所有实验共享）
# ============================================================================
ADX_PERIOD=14
ADX_THRESHOLD=25.0
VOLUME_PERIOD=20
VOLUME_RATIO=1.2
SLOPE_LOOKBACK=5
CONFIRM_BARS=2
MAX_CONSECUTIVE_LOSSES=3
PAUSE_BARS=10
TRAILING_STOP_PCT=0.05
ATR_PERIOD=14
ATR_MULTIPLIER=2.5
MIN_EFFICIENCY_RATIO=0.3
MIN_SLOPE_PERIODS=3

# ============================================================================
# 颜色定义
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ============================================================================
# 工具函数
# ============================================================================

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
}

print_stage() {
    echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_section() {
    echo -e "\n${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# 创建实验元数据文件
create_metadata() {
    local metadata_path=$1

    cat > "$metadata_path" << EOF
{
  "experiment_type": "$EXPERIMENT_TYPE",
  "experiment_version": "1.1-parallel",
  "created_at": "$(date -Iseconds)",
  "script": "$(basename $0)",
  "description": "KAMA策略贪心筛选超参组合测试（并发版本）",
  "parallel_jobs": $PARALLEL_JOBS,
  "config": {
    "pool_path": "$POOL_PATH",
    "data_dir": "$DATA_DIR",
    "start_date": "$START_DATE",
    "end_date": "$END_DATE",
    "core_options": [
$(printf '      "%s"' "${CORE_OPTIONS[0]}")
$(for opt in "${CORE_OPTIONS[@]:1}"; do printf ',\n      "%s"' "$opt"; done)
    ]
  }
}
EOF

    print_success "创建实验元数据: $metadata_path"
}

# ============================================================================
# 实验执行函数（支持日志隔离）
# ============================================================================

# 单个实验执行函数（用于并发调用）
run_single_experiment() {
    local exp_name=$1
    local options_str=$2  # 空格分隔的选项字符串
    local log_file="${LOGS_DIR}/${exp_name}.log"

    local output_dir="${BACKTEST_DIR}/${exp_name}"

    # 构建命令行
    local cmd="./run_backtest.sh"
    cmd="$cmd --stock-list \"$POOL_PATH\""
    cmd="$cmd --strategy kama_cross"
    cmd="$cmd --optimize"
    cmd="$cmd --data-dir \"$DATA_DIR\""
    cmd="$cmd --save-params \"$TEMP_PARAMS_PATH\""
    cmd="$cmd --output-dir \"$output_dir\""
    cmd="$cmd --start-date $START_DATE"
    cmd="$cmd --end-date $END_DATE"

    # 添加选项开关
    if [ -n "$options_str" ]; then
        for opt in $options_str; do
            cmd="$cmd --${opt}"
        done
    fi

    # 添加非store_true参数
    if [[ " $options_str " =~ " enable-adx-filter " ]]; then
        cmd="$cmd --adx-period $ADX_PERIOD --adx-threshold $ADX_THRESHOLD"
    fi

    if [[ " $options_str " =~ " enable-volume-filter " ]]; then
        cmd="$cmd --volume-period $VOLUME_PERIOD --volume-ratio $VOLUME_RATIO"
    fi

    if [[ " $options_str " =~ " enable-slope-filter " ]]; then
        cmd="$cmd --slope-lookback $SLOPE_LOOKBACK"
    fi

    if [[ " $options_str " =~ " enable-loss-protection " ]]; then
        cmd="$cmd --max-consecutive-losses $MAX_CONSECUTIVE_LOSSES --pause-bars $PAUSE_BARS"
    fi

    if [[ " $options_str " =~ " enable-trailing-stop " ]]; then
        cmd="$cmd --trailing-stop-pct $TRAILING_STOP_PCT"
    fi

    if [[ " $options_str " =~ " enable-atr-stop " ]]; then
        cmd="$cmd --atr-period $ATR_PERIOD --atr-multiplier $ATR_MULTIPLIER"
    fi

    if [[ " $options_str " =~ " enable-confirm-filter " ]]; then
        cmd="$cmd --confirm-bars $CONFIRM_BARS"
    fi

    if [[ " $options_str " =~ " enable-efficiency-filter " ]]; then
        cmd="$cmd --min-efficiency-ratio $MIN_EFFICIENCY_RATIO"
    fi

    if [[ " $options_str " =~ " enable-slope-confirmation " ]]; then
        cmd="$cmd --min-slope-periods $MIN_SLOPE_PERIODS"
    fi

    # 记录命令到CSV（使用锁避免并发写入冲突）
    (
        flock -x 200
        echo "${exp_name},\"${cmd}\"" >> "$COMMANDS_CSV"
    ) 200>"${COMMANDS_CSV}.lock"

    # 执行命令并记录日志
    echo "======================================" > "$log_file"
    echo "实验: ${exp_name}" >> "$log_file"
    echo "时间: $(date)" >> "$log_file"
    echo "命令: $cmd" >> "$log_file"
    echo "======================================" >> "$log_file"

    eval $cmd >> "$log_file" 2>&1
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "✓ 实验完成 (exit code: 0)" >> "$log_file"
        echo "SUCCESS:${exp_name}"
    else
        echo "✗ 实验失败 (exit code: $exit_code)" >> "$log_file"
        echo "FAILED:${exp_name}"
    fi

    return $exit_code
}

# 导出函数和变量供并发子进程使用
export -f run_single_experiment
export POOL_PATH DATA_DIR TEMP_PARAMS_PATH START_DATE END_DATE
export ADX_PERIOD ADX_THRESHOLD VOLUME_PERIOD VOLUME_RATIO SLOPE_LOOKBACK
export CONFIRM_BARS MAX_CONSECUTIVE_LOSSES PAUSE_BARS TRAILING_STOP_PCT
export ATR_PERIOD ATR_MULTIPLIER MIN_EFFICIENCY_RATIO MIN_SLOPE_PERIODS

# ============================================================================
# 阶段0：Baseline测试（串行）
# ============================================================================

run_stage0_baseline() {
    print_stage "阶段0：Baseline测试（无任何选项的纯KAMA策略）"

    export BACKTEST_DIR LOGS_DIR COMMANDS_CSV

    local baseline_name="baseline"
    print_section "实验: ${baseline_name}"

    local result=$(run_single_experiment "$baseline_name" "")
    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        print_error "Baseline实验失败，终止流程"
        echo "查看日志: ${LOGS_DIR}/${baseline_name}.log"
        exit 1
    fi

    print_success "Baseline实验完成"

    # 提取Baseline指标
    print_section "提取Baseline性能指标"

    python3 << 'PYTHON_EXTRACT_BASELINE'
import os
import sys
import glob
import pandas as pd
import json

BACKTEST_DIR = os.environ.get('BACKTEST_DIR')
CANDIDATES_DIR = os.environ.get('CANDIDATES_DIR')

baseline_dir = os.path.join(BACKTEST_DIR, 'baseline')
summary_pattern = os.path.join(baseline_dir, 'summary', 'global_summary_*.csv')
matches = glob.glob(summary_pattern)

if not matches:
    print(f"错误: 未找到Baseline的global_summary文件")
    sys.exit(1)

summary_path = matches[0]
print(f"读取: {summary_path}")

try:
    df = pd.read_csv(summary_path, encoding='utf-8-sig')

    # 支持中英文列名
    col_mapping = {
        'sharpe_mean': ['夏普-均值', 'Sharpe Ratio Mean'],
        'sharpe_median': ['夏普-中位数', 'Sharpe Ratio Median'],
    }

    baseline_metrics = {}

    if len(df) == 1:
        # 汇总格式
        for key, possible_names in col_mapping.items():
            for col_name in possible_names:
                if col_name in df.columns:
                    baseline_metrics[key] = float(df[col_name].iloc[0])
                    break
    else:
        # 详细格式，需要计算统计值
        cols_variants = [
            ['Sharpe Ratio'],
            ['夏普比率']
        ]

        cols_found = None
        for variant in cols_variants:
            if all(col in df.columns for col in variant):
                cols_found = variant
                break

        if not cols_found:
            print(f"错误: 列格式不匹配，可用列: {df.columns.tolist()}")
            sys.exit(1)

        baseline_metrics['sharpe_mean'] = float(df[cols_found[0]].mean())
        baseline_metrics['sharpe_median'] = float(df[cols_found[0]].median())

    # 保存到JSON
    baseline_json = os.path.join(CANDIDATES_DIR, 'baseline.json')
    with open(baseline_json, 'w', encoding='utf-8') as f:
        json.dump(baseline_metrics, f, indent=2, ensure_ascii=False)

    print(f"✓ Baseline指标:")
    print(f"  - 夏普均值: {baseline_metrics['sharpe_mean']:.4f}")
    print(f"  - 夏普中位数: {baseline_metrics['sharpe_median']:.4f}")
    print(f"✓ 已保存到: {baseline_json}")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

PYTHON_EXTRACT_BASELINE

    if [ $? -ne 0 ]; then
        print_error "Baseline指标提取失败"
        exit 1
    fi

    print_success "阶段0完成"
}

# ============================================================================
# 阶段1：单变量筛选（并发执行）
# ============================================================================

run_stage1_single_var() {
    print_stage "阶段1：单变量筛选（测试${#CORE_OPTIONS[@]}个独立选项，并发度=${PARALLEL_JOBS}）"

    export BACKTEST_DIR LOGS_DIR COMMANDS_CSV

    # 生成任务列表
    local task_file="${OUTPUT_BASE_DIR}/.stage1_tasks.txt"
    > "$task_file"
    for opt in "${CORE_OPTIONS[@]}"; do
        echo "single_${opt} $opt" >> "$task_file"
    done

    local total_tasks=$(wc -l < "$task_file")
    print_section "开始并发执行 ${total_tasks} 个实验..."

    # 并发执行并收集结果
    local results_file="${OUTPUT_BASE_DIR}/.stage1_results.txt"
    > "$results_file"

    grep -v '^$' "$task_file" | xargs -P $PARALLEL_JOBS -I {} bash -c '
        exp_name=$(echo "{}" | cut -d" " -f1)
        options=$(echo "{}" | cut -d" " -f2-)
        result=$(run_single_experiment "$exp_name" "$options")
        echo "$result"
    ' >> "$results_file"

    # 统计结果
    local success_count=$(grep -c "^SUCCESS:" "$results_file" || echo 0)
    local fail_count=$(grep -c "^FAILED:" "$results_file" || echo 0)

    echo ""
    echo "阶段1统计: 成功=${success_count}, 失败=${fail_count}"

    # 显示失败的实验
    if [ $fail_count -gt 0 ]; then
        print_warning "失败的实验:"
        grep "^FAILED:" "$results_file" | sed 's/^FAILED:/  - /'
    fi

    # 调用Python脚本筛选候选
    print_section "筛选优秀候选（OR逻辑：sharpe_mean > base OR sharpe_median > base）"

    export CANDIDATES_DIR
    export CORE_OPTIONS_STR="${CORE_OPTIONS[*]}"

    python3 << 'PYTHON_FILTER_STAGE1'
import os
import sys
import glob
import pandas as pd
import json
from typing import List, Dict

BACKTEST_DIR = os.environ.get('BACKTEST_DIR')
CANDIDATES_DIR = os.environ.get('CANDIDATES_DIR')
CORE_OPTIONS = os.environ.get('CORE_OPTIONS_STR').split()

# 加载Baseline
baseline_json = os.path.join(CANDIDATES_DIR, 'baseline.json')
with open(baseline_json, 'r', encoding='utf-8') as f:
    baseline = json.load(f)

print(f"Baseline: sharpe_mean={baseline['sharpe_mean']:.4f}, sharpe_median={baseline['sharpe_median']:.4f}")

# 提取每个单变量的指标
candidates = []

for opt in CORE_OPTIONS:
    exp_name = f"single_{opt}"
    exp_dir = os.path.join(BACKTEST_DIR, exp_name)

    summary_pattern = os.path.join(exp_dir, 'summary', 'global_summary_*.csv')
    matches = glob.glob(summary_pattern)

    if not matches:
        print(f"  ⚠ {exp_name}: 未找到summary文件，跳过")
        continue

    summary_path = matches[0]

    try:
        df = pd.read_csv(summary_path, encoding='utf-8-sig')

        # 提取夏普指标
        sharpe_mean = None
        sharpe_median = None

        if len(df) == 1:
            # 汇总格式
            for col in ['夏普-均值', 'Sharpe Ratio Mean']:
                if col in df.columns:
                    sharpe_mean = float(df[col].iloc[0])
                    break
            for col in ['夏普-中位数', 'Sharpe Ratio Median']:
                if col in df.columns:
                    sharpe_median = float(df[col].iloc[0])
                    break
        else:
            # 详细格式
            for col in ['Sharpe Ratio', '夏普比率']:
                if col in df.columns:
                    sharpe_mean = float(df[col].mean())
                    sharpe_median = float(df[col].median())
                    break

        if sharpe_mean is None or sharpe_median is None:
            print(f"  ⚠ {exp_name}: 无法提取夏普指标，跳过")
            continue

        # OR逻辑判断
        passes = (sharpe_mean > baseline['sharpe_mean']) or (sharpe_median > baseline['sharpe_median'])

        status = "✓ 通过" if passes else "✗ 未通过"
        print(f"  {status} {opt}: sharpe_mean={sharpe_mean:.4f}, sharpe_median={sharpe_median:.4f}")

        if passes:
            candidates.append({
                'options': [opt],
                'sharpe_mean': sharpe_mean,
                'sharpe_median': sharpe_median,
                'exp_name': exp_name
            })

    except Exception as e:
        print(f"  ⚠ {exp_name}: 提取失败 - {e}")

# 保存候选池
if not candidates:
    print("\n✗ 错误: 阶段1没有任何候选通过筛选，流程终止")
    sys.exit(1)

candidates_json = os.path.join(CANDIDATES_DIR, 'candidates_k1.json')
with open(candidates_json, 'w', encoding='utf-8') as f:
    json.dump(candidates, f, indent=2, ensure_ascii=False)

print(f"\n✓ 阶段1完成: {len(candidates)}/{len(CORE_OPTIONS)} 个候选通过筛选")
print(f"✓ 候选池已保存到: {candidates_json}")

PYTHON_FILTER_STAGE1

    if [ $? -ne 0 ]; then
        print_error "阶段1筛选失败"
        exit 1
    fi

    print_success "阶段1完成"
}

# ============================================================================
# 阶段k：k变量筛选（k >= 2，并发执行）
# ============================================================================

run_stage_k() {
    local k=$1
    local prev_k=$((k - 1))

    print_stage "阶段${k}：${k}变量筛选（严格递增剪枝，并发度=${PARALLEL_JOBS}）"

    export BACKTEST_DIR LOGS_DIR COMMANDS_CSV CANDIDATES_DIR
    export K=$k

    # 检查前一阶段候选池是否存在
    local prev_candidates_json="${CANDIDATES_DIR}/candidates_k${prev_k}.json"
    if [ ! -f "$prev_candidates_json" ]; then
        print_error "前一阶段候选池不存在: $prev_candidates_json"
        return 1
    fi

    # 生成组合列表
    print_section "从阶段${prev_k}的候选生成${k}变量组合"

    local task_file="${OUTPUT_BASE_DIR}/.stage${k}_tasks.txt"

    python3 << PYTHON_GEN_COMBOS > "$task_file"
import os
import json
from itertools import combinations

K = int(os.environ.get('K'))
PREV_K = K - 1
CANDIDATES_DIR = os.environ.get('CANDIDATES_DIR')

prev_candidates_json = os.path.join(CANDIDATES_DIR, f'candidates_k{PREV_K}.json')
with open(prev_candidates_json, 'r', encoding='utf-8') as f:
    prev_candidates = json.load(f)

all_options = set()
for cand in prev_candidates:
    all_options.update(cand['options'])
all_options = sorted(list(all_options))

k_combinations = list(combinations(all_options, K))

experiments_to_run = []
for combo in k_combinations:
    combo_list = list(combo)
    sub_combos = list(combinations(combo_list, PREV_K))
    all_subs_passed = True

    for sub in sub_combos:
        sub_list = sorted(list(sub))
        found = False
        for cand in prev_candidates:
            if sorted(cand['options']) == sub_list:
                found = True
                break
        if not found:
            all_subs_passed = False
            break

    if all_subs_passed:
        experiments_to_run.append(combo_list)

for combo in experiments_to_run:
    exp_name = f"k{K}_" + "_".join(combo)
    options_str = " ".join(combo)
    print(f"{exp_name} {options_str}")
PYTHON_GEN_COMBOS

    local total_tasks=$(wc -l < "$task_file")

    if [ $total_tasks -eq 0 ]; then
        print_warning "阶段${k}: 无需测试的组合（所有组合的子组合都未全部通过前一阶段）"
        return 2  # 返回2表示无组合需要测试（非错误，而是正常终止条件）
    fi

    print_section "开始并发执行 ${total_tasks} 个实验..."

    # 并发执行并收集结果
    local results_file="${OUTPUT_BASE_DIR}/.stage${k}_results.txt"
    > "$results_file"

    grep -v '^$' "$task_file" | xargs -P $PARALLEL_JOBS -I {} bash -c '
        exp_name=$(echo "{}" | cut -d" " -f1)
        options=$(echo "{}" | cut -d" " -f2-)
        result=$(run_single_experiment "$exp_name" "$options")
        echo "$result"
    ' >> "$results_file"

    # 统计结果
    local success_count=$(grep -c "^SUCCESS:" "$results_file" || echo 0)
    local fail_count=$(grep -c "^FAILED:" "$results_file" || echo 0)

    echo ""
    echo "阶段${k}统计: 成功=${success_count}, 失败=${fail_count}"

    # 显示失败的实验
    if [ $fail_count -gt 0 ]; then
        print_warning "失败的实验:"
        grep "^FAILED:" "$results_file" | sed 's/^FAILED:/  - /'
    fi

    # 筛选候选（严格递增）
    print_section "筛选优秀候选（严格递增：两指标同时超过所有子组合最优值）"

    python3 << 'PYTHON_FILTER_STAGE_K'
import os
import sys
import glob
import json
import pandas as pd
from itertools import combinations

K = int(os.environ.get('K'))
PREV_K = K - 1
BACKTEST_DIR = os.environ.get('BACKTEST_DIR')
CANDIDATES_DIR = os.environ.get('CANDIDATES_DIR')

# 加载前一阶段候选池
prev_candidates_json = os.path.join(CANDIDATES_DIR, f'candidates_k{PREV_K}.json')
with open(prev_candidates_json, 'r', encoding='utf-8') as f:
    prev_candidates = json.load(f)

# 构建前一阶段候选的快速查找字典
prev_dict = {}
for cand in prev_candidates:
    key = tuple(sorted(cand['options']))
    prev_dict[key] = cand

# 查找所有阶段k的实验目录
stage_k_dirs = glob.glob(os.path.join(BACKTEST_DIR, f'k{K}_*'))

candidates_k = []

for exp_dir in stage_k_dirs:
    exp_name = os.path.basename(exp_dir)

    # 解析选项
    options_str = exp_name[len(f'k{K}_'):]
    options = options_str.split('_')

    # 查找summary
    summary_pattern = os.path.join(exp_dir, 'summary', 'global_summary_*.csv')
    matches = glob.glob(summary_pattern)

    if not matches:
        print(f"  ⚠ {exp_name}: 未找到summary文件，跳过")
        continue

    summary_path = matches[0]

    try:
        df = pd.read_csv(summary_path, encoding='utf-8-sig')

        # 提取夏普指标
        sharpe_mean = None
        sharpe_median = None

        if len(df) == 1:
            for col in ['夏普-均值', 'Sharpe Ratio Mean']:
                if col in df.columns:
                    sharpe_mean = float(df[col].iloc[0])
                    break
            for col in ['夏普-中位数', 'Sharpe Ratio Median']:
                if col in df.columns:
                    sharpe_median = float(df[col].iloc[0])
                    break
        else:
            for col in ['Sharpe Ratio', '夏普比率']:
                if col in df.columns:
                    sharpe_mean = float(df[col].mean())
                    sharpe_median = float(df[col].median())
                    break

        if sharpe_mean is None or sharpe_median is None:
            print(f"  ⚠ {exp_name}: 无法提取夏普指标，跳过")
            continue

        # 严格递增判断：必须同时超过所有子组合的最优值
        sub_combos = list(combinations(options, PREV_K))

        max_sub_sharpe_mean = -float('inf')
        max_sub_sharpe_median = -float('inf')

        for sub in sub_combos:
            sub_key = tuple(sorted(sub))
            if sub_key in prev_dict:
                sub_cand = prev_dict[sub_key]
                max_sub_sharpe_mean = max(max_sub_sharpe_mean, sub_cand['sharpe_mean'])
                max_sub_sharpe_median = max(max_sub_sharpe_median, sub_cand['sharpe_median'])

        # 严格递增：两个指标都要超过
        passes = (sharpe_mean > max_sub_sharpe_mean) and (sharpe_median > max_sub_sharpe_median)

        status = "✓ 通过" if passes else "✗ 未通过"
        print(f"  {status} {options_str}:")
        print(f"      当前: mean={sharpe_mean:.4f}, median={sharpe_median:.4f}")
        print(f"      子组合最优: mean={max_sub_sharpe_mean:.4f}, median={max_sub_sharpe_median:.4f}")

        if passes:
            candidates_k.append({
                'options': options,
                'sharpe_mean': sharpe_mean,
                'sharpe_median': sharpe_median,
                'exp_name': exp_name
            })

    except Exception as e:
        print(f"  ⚠ {exp_name}: 提取失败 - {e}")

# 保存候选池
if not candidates_k:
    print(f"\n✗ 阶段{K}: 没有任何候选通过严格递增筛选，流程终止")
    sys.exit(1)

candidates_json = os.path.join(CANDIDATES_DIR, f'candidates_k{K}.json')
with open(candidates_json, 'w', encoding='utf-8') as f:
    json.dump(candidates_k, f, indent=2, ensure_ascii=False)

print(f"\n✓ 阶段{K}完成: {len(candidates_k)}/{len(stage_k_dirs)} 个候选通过筛选")
print(f"✓ 候选池已保存到: {candidates_json}")

PYTHON_FILTER_STAGE_K

    local python_exit=$?
    if [ $python_exit -eq 1 ]; then
        print_warning "阶段${k}: 无候选通过筛选，终止递归"
        return 1
    fi

    print_success "阶段${k}完成"
    return 0
}

# ============================================================================
# 主执行流程
# ============================================================================

# 仅收集结果模式
collect_only_mode() {
    local experiment_root=$1

    if [ ! -d "$experiment_root" ]; then
        print_error "实验目录不存在: $experiment_root"
        exit 1
    fi

    print_header "仅收集模式：从已有实验目录收集结果"

    # 尝试读取元数据文件
    local metadata_file="$experiment_root/.experiment_metadata.json"
    if [ -f "$metadata_file" ]; then
        print_success "检测到实验元数据文件"

        # 提取实验类型
        local exp_type=$(python3 -c "import json; print(json.load(open('$metadata_file'))['experiment_type'])" 2>/dev/null)
        if [ -n "$exp_type" ]; then
            print_success "实验类型: $exp_type"
        else
            print_warning "无法解析实验类型，使用默认配置"
        fi
    else
        print_warning "未找到元数据文件，使用启发式方法检测"
    fi

    # 自动检测backtests子目录
    local backtest_dir="$experiment_root"
    if [ -d "$experiment_root/backtests" ]; then
        backtest_dir="$experiment_root/backtests"
        print_success "检测到backtests子目录: $backtest_dir"
    else
        print_success "使用实验根目录: $backtest_dir"
    fi

    # 设置结果CSV路径
    local result_csv="$experiment_root/mega_test_greedy_summary.csv"
    if [ -f "$result_csv" ]; then
        print_warning "结果文件已存在，将被覆盖: $result_csv"
    fi

    # 收集结果
    print_section "开始收集实验结果"

    export EXPERIMENT_DIR="$backtest_dir"
    export OUTPUT_CSV="$result_csv"
    export EXPERIMENT_METADATA_FILE="$metadata_file"

    ./scripts/collect_mega_test_results.sh "$backtest_dir" "$result_csv"

    if [ $? -eq 0 ]; then
        print_success "结果汇总完成: $result_csv"

        # 打印统计信息
        print_header "收集完成"
        local total_dirs=$(find "$backtest_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        echo "实验目录: ${experiment_root}"
        echo "回测子目录: ${backtest_dir}"
        echo "总实验数: ${total_dirs}"
        echo "结果CSV: ${result_csv}"

        if [ -f "$metadata_file" ]; then
            echo ""
            echo "实验元数据:"
            python3 << PYTHON_PRINT_META
import json
try:
    with open('$metadata_file', 'r') as f:
        meta = json.load(f)
    print(f"  类型: {meta.get('experiment_type', 'N/A')}")
    print(f"  创建时间: {meta.get('created_at', 'N/A')}")
    print(f"  描述: {meta.get('description', 'N/A')}")
    print(f"  并发度: {meta.get('parallel_jobs', 'N/A')}")
except:
    pass
PYTHON_PRINT_META
        fi

        echo ""
        print_success "可以使用以下命令查看结果："
        echo "  column -t -s, \"$result_csv\" | less -S"
    else
        print_error "结果汇总失败"
        exit 1
    fi
}

main() {
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -j|--jobs)
                PARALLEL_JOBS="$2"
                shift 2
                ;;
            --collect-only)
                if [ -z "$2" ]; then
                    print_error "用法: $0 --collect-only <实验目录>"
                    echo ""
                    echo "示例:"
                    echo "  $0 --collect-only results/mega_test_kama_greedy_20251123_143022"
                    exit 1
                fi
                collect_only_mode "$2"
                exit 0
                ;;
            *)
                print_error "未知参数: $1"
                echo "用法: $0 [-j <并发度>] [--collect-only <实验目录>]"
                exit 1
                ;;
        esac
    done

    # 正常执行模式
    print_header "KAMA策略贪心筛选超参组合测试（并发版本）"
    echo "并发度: ${PARALLEL_JOBS}"

    # 创建目录
    mkdir -p "$OUTPUT_BASE_DIR"
    mkdir -p "$CANDIDATES_DIR"
    mkdir -p "$REPORTS_DIR"
    mkdir -p "$BACKTEST_DIR"
    mkdir -p "$LOGS_DIR"

    print_success "创建输出目录: $OUTPUT_BASE_DIR"
    print_success "日志目录: $LOGS_DIR"

    # 创建实验元数据文件
    create_metadata "$METADATA_FILE"

    # 初始化实验命令记录CSV
    echo "exp_name,command" > "$COMMANDS_CSV"
    print_success "初始化命令记录文件: $COMMANDS_CSV"

    # 导出环境变量供Python使用
    export BACKTEST_DIR
    export CANDIDATES_DIR
    export LOGS_DIR
    export COMMANDS_CSV
    export CORE_OPTIONS_STR="${CORE_OPTIONS[*]}"

    # 记录开始时间
    local start_time=$(date +%s)

    # 阶段0: Baseline
    run_stage0_baseline

    # 阶段1: 单变量筛选
    run_stage1_single_var

    # 阶段k: k变量筛选（k >= 2，直到无候选通过）
    local k=2
    while true; do
        export K=$k
        run_stage_k $k
        local exit_code=$?

        if [ $exit_code -eq 1 ]; then
            print_warning "阶段${k}无候选通过筛选，贪心搜索终止"
            break
        elif [ $exit_code -eq 2 ]; then
            print_warning "阶段${k}无组合需要测试（所有组合的子组合未全部通过前一阶段），贪心搜索终止"
            break
        fi

        k=$((k + 1))
    done

    # 收集所有实验结果
    print_section "收集所有实验结果"

    export EXPERIMENT_DIR="$BACKTEST_DIR"
    export OUTPUT_CSV="$RESULT_CSV"

    ./scripts/collect_mega_test_results.sh "$BACKTEST_DIR" "$RESULT_CSV"

    if [ $? -eq 0 ]; then
        print_success "结果汇总完成: $RESULT_CSV"
    else
        print_error "结果汇总失败"
    fi

    # 复制脚本自身到输出目录存档
    cp "$0" "${OUTPUT_BASE_DIR}/"
    print_success "脚本已存档: ${OUTPUT_BASE_DIR}/$(basename $0)"

    # 计算总耗时
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))

    # 打印最终统计
    print_header "贪心筛选完成"

    local total_dirs=$(find "$BACKTEST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
    echo "总实验数: ${total_dirs}"
    echo "并发度: ${PARALLEL_JOBS}"
    echo "总耗时: ${minutes}分${seconds}秒"
    echo "输出目录: ${OUTPUT_BASE_DIR}"
    echo "结果CSV: ${RESULT_CSV}"
    echo "命令记录: ${COMMANDS_CSV}"
    echo "日志目录: ${LOGS_DIR}"
    echo ""
    echo "候选池文件:"
    ls -1 "${CANDIDATES_DIR}"/candidates_k*.json 2>/dev/null || echo "  无"
}

# ============================================================================
# 脚本入口
# ============================================================================

# 检查Python3
if ! command -v python3 &> /dev/null; then
    print_error "需要Python3来执行筛选逻辑"
    exit 1
fi

# 执行主函数
main "$@"
