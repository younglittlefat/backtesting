#!/bin/bash
################################################################################
# SMA Enhanced策略贪心筛选超参组合测试脚本 - 并发版本（模块化重构）
#
# 功能：
# - 通过递归剪枝大幅减少实验次数（预计30-100个实验 vs 256个完整因子设计）
# - 每个阶段结束后自动筛选优秀候选
# - 支持中断续传，可在任意阶段暂停分析
# - 生成详细的阶段分析报告
# - 支持阶段内并发执行，大幅提升实验效率
#
# 用法：
#   ./mega_test_sma_enhanced_greedy_parallel.sh                    # 执行完整实验流程（默认并发度3）
#   ./mega_test_sma_enhanced_greedy_parallel.sh -j 5               # 指定并发度为5
#   ./mega_test_sma_enhanced_greedy_parallel.sh --collect-only <实验目录>  # 仅收集已有结果
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

STRATEGY_NAME="sma_cross_enhanced"
STRATEGY_DESCRIPTION="SMA Enhanced策略贪心筛选超参组合测试（并发版本）"

# 并发度配置（可通过 -j 参数覆盖）
PARALLEL_JOBS=3

# 实验类型标识
EXPERIMENT_TYPE="mega_test_greedy"

# 基础路径配置
POOL_PATH="results/trend_etf_pool_2021_2023_optimized.csv"
DATA_DIR="data/chinese_etf/daily"
TEMP_PARAMS_PATH="config/test/sma_enhanced_base_strategy_params.json"
OUTPUT_BASE_DIR="results/mega_test_sma_enhanced_greedy_parallel_$(date +%Y%m%d_%H%M%S)"
START_DATE="20240102"
END_DATE="20251120"

# ============================================================================
# 定义8个核心超参开关（SMA Enhanced策略）
# ============================================================================
declare -a CORE_OPTIONS=(
    "enable-slope-filter"
    "enable-adx-filter"
    "enable-volume-filter"
    "enable-confirm-filter"
    "enable-loss-protection"
    "enable-trailing-stop"
    "enable-atr-stop"
    "confirm-bars"
)

# ============================================================================
# 固定超参（所有实验共享）
# ============================================================================
# 过滤器参数
SLOPE_LOOKBACK=5
ADX_PERIOD=14
ADX_THRESHOLD=25.0
VOLUME_PERIOD=20
VOLUME_RATIO=1.2
CONFIRM_BARS_VALUE=3  # confirm-bars开关启用时的值

# 止损保护参数
MAX_CONSECUTIVE_LOSSES=3
PAUSE_BARS=10

# 跟踪止损参数
TRAILING_STOP_PCT=0.05

# ATR自适应止损参数
ATR_PERIOD=14
ATR_MULTIPLIER=2.5

# ============================================================================
# SMA Enhanced策略特定的实验执行函数
# ============================================================================

run_single_experiment() {
    local exp_name=$1
    local options_str=$2  # 空格分隔的选项字符串
    local log_file="${LOGS_DIR}/${exp_name}.log"
    local output_dir="${BACKTEST_DIR}/${exp_name}"

    # 构建命令行
    local cmd=$(greedy_build_base_cmd "$STRATEGY_NAME" "$output_dir")

    # 添加选项开关
    if [ -n "$options_str" ]; then
        for opt in $options_str; do
            if [ "$opt" = "confirm-bars" ]; then
                # confirm-bars 需要同时启用 enable-confirm-filter 并设置值
                cmd="$cmd --enable-confirm-filter --confirm-bars $CONFIRM_BARS_VALUE"
            else
                cmd="$cmd --${opt}"
            fi
        done
    fi

    # 添加非store_true参数（当相应开关启用时）
    if [[ " $options_str " =~ " enable-slope-filter " ]]; then
        cmd="$cmd --slope-lookback $SLOPE_LOOKBACK"
    fi

    if [[ " $options_str " =~ " enable-adx-filter " ]]; then
        cmd="$cmd --adx-period $ADX_PERIOD --adx-threshold $ADX_THRESHOLD"
    fi

    if [[ " $options_str " =~ " enable-volume-filter " ]]; then
        cmd="$cmd --volume-period $VOLUME_PERIOD --volume-ratio $VOLUME_RATIO"
    fi

    if [[ " $options_str " =~ " enable-confirm-filter " ]] && [[ ! " $options_str " =~ " confirm-bars " ]]; then
        # 如果启用了confirm-filter但没有通过confirm-bars开关，使用默认值2
        cmd="$cmd --confirm-bars 2"
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
export POOL_PATH DATA_DIR TEMP_PARAMS_PATH START_DATE END_DATE STRATEGY_NAME
export SLOPE_LOOKBACK ADX_PERIOD ADX_THRESHOLD VOLUME_PERIOD VOLUME_RATIO
export MAX_CONSECUTIVE_LOSSES PAUSE_BARS TRAILING_STOP_PCT
export ATR_PERIOD ATR_MULTIPLIER CONFIRM_BARS_VALUE

# ============================================================================
# 主执行流程
# ============================================================================

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
                    greedy_print_error "用法: $0 --collect-only <实验目录>"
                    exit 1
                fi
                greedy_collect_only_mode "$2"
                exit $?
                ;;
            *)
                greedy_print_error "未知参数: $1"
                echo "用法: $0 [-j <并发度>] [--collect-only <实验目录>]"
                exit 1
                ;;
        esac
    done

    # 正常执行模式
    greedy_print_header "SMA Enhanced策略贪心筛选超参组合测试（并发版本）"
    echo "策略: $STRATEGY_NAME"
    echo "并发度: ${PARALLEL_JOBS}"
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

    # 阶段1: 单变量筛选
    greedy_run_stage1_parallel "$PARALLEL_JOBS" CORE_OPTIONS
    [ $? -ne 0 ] && exit 1

    # 阶段k: k变量筛选（k >= 2，直到无候选通过）
    local k=2
    while true; do
        greedy_run_stage_k_parallel "$k" "$PARALLEL_JOBS"
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
