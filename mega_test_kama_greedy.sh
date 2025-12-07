#!/bin/bash
################################################################################
# KAMA策略贪心筛选超参组合测试脚本 - 串行版本（模块化重构）
#
# 功能：
# - 通过递归剪枝大幅减少实验次数（预计50-200个实验 vs 1024个完整因子设计）
# - 每个阶段结束后自动筛选优秀候选
# - 支持中断续传，可在任意阶段暂停分析
# - 生成详细的阶段分析报告
#
# 用法：
#   ./mega_test_kama_greedy.sh                    # 执行完整实验流程
#   ./mega_test_kama_greedy.sh --collect-only <实验目录>  # 仅收集已有结果
#
# 作者: Claude Code
# 日期: 2025-12-07 (模块化重构)
################################################################################

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载公共函数库
source "${SCRIPT_DIR}/greedy_search/greedy_lib.sh"

# ============================================================================
# 策略特定配置
# ============================================================================

STRATEGY_NAME="kama_cross"
STRATEGY_DESCRIPTION="KAMA策略贪心筛选超参组合测试（串行版本）"

# 串行模式标记
PARALLEL_JOBS=1

# 实验类型标识
EXPERIMENT_TYPE="mega_test_greedy"

# 基础路径配置
POOL_PATH="experiment/etf/selector_score/single_primary/single_adx_score_pool_2019_2021.csv"
DATA_DIR="data/chinese_etf/daily"
TEMP_PARAMS_PATH="config/test/kama_base_strategy_params.json"
OUTPUT_BASE_DIR="experiment/etf/selector_score/single_primary/mega_test_kama_single_adx_score_$(date +%Y%m%d_%H%M%S)"
START_DATE="20220102"
END_DATE="20240102"

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
# KAMA策略特定的实验执行函数
# ============================================================================

run_single_experiment() {
    local exp_name=$1
    local options_str=$2  # 空格分隔的选项字符串
    local output_dir="${BACKTEST_DIR}/${exp_name}"

    # 构建命令行
    local cmd=$(greedy_build_base_cmd "$STRATEGY_NAME" "$output_dir")

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

    # 记录命令到CSV
    echo "${exp_name},\"${cmd}\"" >> "$COMMANDS_CSV"

    # 执行命令
    echo "Command: $cmd"
    eval $cmd

    local exit_code=$?
    return $exit_code
}

# 导出函数和变量供公共函数使用
export -f run_single_experiment
export POOL_PATH DATA_DIR TEMP_PARAMS_PATH START_DATE END_DATE STRATEGY_NAME
export ADX_PERIOD ADX_THRESHOLD VOLUME_PERIOD VOLUME_RATIO SLOPE_LOOKBACK
export CONFIRM_BARS MAX_CONSECUTIVE_LOSSES PAUSE_BARS TRAILING_STOP_PCT
export ATR_PERIOD ATR_MULTIPLIER MIN_EFFICIENCY_RATIO MIN_SLOPE_PERIODS

# ============================================================================
# 主执行流程
# ============================================================================

main() {
    # 解析命令行参数
    if [ "$1" = "--collect-only" ]; then
        if [ -z "$2" ]; then
            greedy_print_error "用法: $0 --collect-only <实验目录>"
            exit 1
        fi
        greedy_collect_only_mode "$2"
        exit $?
    fi

    # 正常执行模式
    greedy_print_header "KAMA策略贪心筛选超参组合测试（串行版本）"
    echo "策略: $STRATEGY_NAME"
    echo "核心超参数量: ${#CORE_OPTIONS[@]}"

    # 初始化目录
    greedy_init_dirs "$OUTPUT_BASE_DIR"

    # 创建元数据
    greedy_create_metadata "$METADATA_FILE" "$EXPERIMENT_TYPE" "$STRATEGY_NAME" \
        "$STRATEGY_DESCRIPTION" "$PARALLEL_JOBS" CORE_OPTIONS

    # 导出环境变量
    export BACKTEST_DIR CANDIDATES_DIR LOGS_DIR COMMANDS_CSV OUTPUT_BASE_DIR

    # 记录开始时间
    local start_time=$(date +%s)

    # 阶段0: Baseline
    greedy_run_stage0 "$STRATEGY_NAME"
    [ $? -ne 0 ] && exit 1

    # 阶段1: 单变量筛选（串行）
    greedy_run_stage1_serial CORE_OPTIONS
    [ $? -ne 0 ] && exit 1

    # 阶段k: k变量筛选（k >= 2，直到无候选通过）
    local k=2
    while true; do
        greedy_run_stage_k_serial "$k"
        local exit_code=$?

        if [ $exit_code -eq 1 ]; then
            greedy_print_warning "阶段${k}无候选通过筛选，贪心搜索终止"
            break
        elif [ $exit_code -eq 2 ]; then
            greedy_print_warning "阶段${k}无组合需要测试，贪心搜索终止"
            break
        fi

        k=$((k + 1))
    done

    # 收集结果
    greedy_collect_results

    # 存档脚本
    cp "$0" "${OUTPUT_BASE_DIR}/"
    greedy_print_success "脚本已存档: ${OUTPUT_BASE_DIR}/$(basename $0)"

    # 打印最终统计
    greedy_print_final_stats "$STRATEGY_NAME" "$start_time" CORE_OPTIONS
}

# ============================================================================
# 脚本入口
# ============================================================================

# 检查Python3
if ! command -v python3 &> /dev/null; then
    greedy_print_error "需要Python3来执行筛选逻辑"
    exit 1
fi

# 执行主函数
main "$@"
