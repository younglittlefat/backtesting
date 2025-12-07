#!/bin/bash
################################################################################
# 贪心搜索实验框架 - Shell公共函数库
#
# 提供超参组合贪心搜索的可复用Shell函数：
# - 颜色输出
# - 打印工具
# - 元数据管理
# - 实验执行框架
#
# 用法：
#   source greedy_search/greedy_lib.sh
#
# 作者: Claude Code
# 日期: 2025-12-07
################################################################################

# ============================================================================
# 颜色定义
# ============================================================================
export GREEDY_RED='\033[0;31m'
export GREEDY_GREEN='\033[0;32m'
export GREEDY_YELLOW='\033[1;33m'
export GREEDY_BLUE='\033[0;34m'
export GREEDY_CYAN='\033[0;36m'
export GREEDY_MAGENTA='\033[0;35m'
export GREEDY_NC='\033[0m' # No Color

# ============================================================================
# 打印工具函数
# ============================================================================

greedy_print_header() {
    echo -e "${GREEDY_BLUE}═══════════════════════════════════════════════════════════════════${GREEDY_NC}"
    echo -e "${GREEDY_BLUE}  $1${GREEDY_NC}"
    echo -e "${GREEDY_BLUE}═══════════════════════════════════════════════════════════════════${GREEDY_NC}"
}

greedy_print_stage() {
    echo -e "\n${GREEDY_MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${GREEDY_NC}"
    echo -e "${GREEDY_MAGENTA}  $1${GREEDY_NC}"
    echo -e "${GREEDY_MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${GREEDY_NC}\n"
}

greedy_print_section() {
    echo -e "\n${GREEDY_CYAN}▶ $1${GREEDY_NC}"
}

greedy_print_success() {
    echo -e "${GREEDY_GREEN}✓ $1${GREEDY_NC}"
}

greedy_print_warning() {
    echo -e "${GREEDY_YELLOW}⚠ $1${GREEDY_NC}"
}

greedy_print_error() {
    echo -e "${GREEDY_RED}✗ $1${GREEDY_NC}"
}

# ============================================================================
# 元数据管理
# ============================================================================

# 创建实验元数据文件
# 参数: $1=输出路径, $2=实验类型, $3=策略名, $4=描述, $5=并发度, $6=CORE_OPTIONS数组名
greedy_create_metadata() {
    local metadata_path=$1
    local experiment_type=$2
    local strategy_name=$3
    local description=$4
    local parallel_jobs=$5
    local -n options_array=$6  # nameref to array

    cat > "$metadata_path" << EOF
{
  "experiment_type": "$experiment_type",
  "experiment_version": "2.0-modular",
  "strategy": "$strategy_name",
  "created_at": "$(date -Iseconds)",
  "script": "$(basename $0)",
  "description": "$description",
  "parallel_jobs": $parallel_jobs,
  "config": {
    "pool_path": "$POOL_PATH",
    "data_dir": "$DATA_DIR",
    "start_date": "$START_DATE",
    "end_date": "$END_DATE",
    "core_options": [
$(printf '      "%s"' "${options_array[0]}")
$(for opt in "${options_array[@]:1}"; do printf ',\n      "%s"' "$opt"; done)
    ]
  }
}
EOF

    greedy_print_success "创建实验元数据: $metadata_path"
}

# ============================================================================
# 目录初始化
# ============================================================================

# 初始化实验目录结构
# 参数: $1=OUTPUT_BASE_DIR
greedy_init_dirs() {
    local base_dir=$1

    export CANDIDATES_DIR="${base_dir}/candidates"
    export REPORTS_DIR="${base_dir}/reports"
    export BACKTEST_DIR="${base_dir}/backtests"
    export LOGS_DIR="${base_dir}/logs"
    export RESULT_CSV="${base_dir}/mega_test_greedy_summary.csv"
    export COMMANDS_CSV="${base_dir}/experiment_commands.csv"
    export METADATA_FILE="${base_dir}/.experiment_metadata.json"

    mkdir -p "$base_dir"
    mkdir -p "$CANDIDATES_DIR"
    mkdir -p "$REPORTS_DIR"
    mkdir -p "$BACKTEST_DIR"
    mkdir -p "$LOGS_DIR"

    greedy_print_success "创建输出目录: $base_dir"
    greedy_print_success "日志目录: $LOGS_DIR"

    # 初始化命令记录CSV
    echo "exp_name,command" > "$COMMANDS_CSV"
    greedy_print_success "初始化命令记录文件: $COMMANDS_CSV"
}

# ============================================================================
# 回测命令构建器
# ============================================================================

# 构建基础回测命令
# 参数: $1=策略名, $2=输出目录
greedy_build_base_cmd() {
    local strategy=$1
    local output_dir=$2

    local cmd="./run_backtest.sh"
    cmd="$cmd --stock-list \"$POOL_PATH\""
    cmd="$cmd --strategy $strategy"
    cmd="$cmd --optimize"
    cmd="$cmd --data-dir \"$DATA_DIR\""
    cmd="$cmd --save-params \"$TEMP_PARAMS_PATH\""
    cmd="$cmd --output-dir \"$output_dir\""
    cmd="$cmd --start-date $START_DATE"
    cmd="$cmd --end-date $END_DATE"

    echo "$cmd"
}

# ============================================================================
# 并发执行框架
# ============================================================================

# 并发执行任务文件中的实验
# 参数: $1=任务文件路径, $2=结果文件路径, $3=并发度
greedy_parallel_run_tasks() {
    local task_file=$1
    local results_file=$2
    local parallel_jobs=$3

    > "$results_file"

    # 使用 GNU parallel 或 xargs 逐行安全执行
    # 任务文件格式: "exp_name options_str"（空格分隔，options_str可包含多个空格分隔的选项）
    # 使用 NUL 分隔符避免空格导致的拆分问题
    grep -v '^$' "$task_file" | while IFS= read -r line; do
        printf '%s\0' "$line"
    done | xargs -0 -P "$parallel_jobs" -I {} bash -c '
        line="$1"
        exp_name="${line%% *}"
        options="${line#* }"
        # 如果没有空格，exp_name == line，options应为空
        if [ "$exp_name" = "$line" ]; then
            options=""
        fi
        run_single_experiment "$exp_name" "$options"
    ' _ {} >> "$results_file" 2>&1

    # 统计结果
    local success_count=$(grep -c "^SUCCESS:" "$results_file" 2>/dev/null || echo 0)
    local fail_count=$(grep -c "^FAILED:" "$results_file" 2>/dev/null || echo 0)

    echo ""
    echo "统计: 成功=${success_count}, 失败=${fail_count}"

    # 显示失败的实验
    if [ "$fail_count" -gt 0 ]; then
        greedy_print_warning "失败的实验:"
        grep "^FAILED:" "$results_file" | sed 's/^FAILED:/  - /'
    fi

    # 返回失败计数（用于调用方检测）
    if [ "$fail_count" -gt 0 ]; then
        return 1
    fi
    return 0
}

# ============================================================================
# 阶段执行框架
# ============================================================================

# 阶段0: Baseline测试
# 参数: $1=策略名
greedy_run_stage0() {
    local strategy=$1

    greedy_print_stage "阶段0：Baseline测试（无任何选项的纯${strategy}策略）"

    local baseline_name="baseline"
    greedy_print_section "实验: ${baseline_name}"

    # 注意：不能用 local result=$(...); local exit_code=$?
    # 因为 local 命令本身会覆盖 $?（成功时设为0）
    local result
    result=$(run_single_experiment "$baseline_name" "")
    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        greedy_print_error "Baseline实验失败，终止流程"
        echo "查看日志: ${LOGS_DIR}/${baseline_name}.log"
        return 1
    fi

    greedy_print_success "Baseline实验完成"

    # 使用Python模块提取指标
    greedy_print_section "提取Baseline性能指标"

    python3 -m greedy_search.cli extract_baseline "$BACKTEST_DIR" "${CANDIDATES_DIR}/baseline.json"

    if [ $? -ne 0 ]; then
        greedy_print_error "Baseline指标提取失败"
        return 1
    fi

    greedy_print_success "阶段0完成"
    return 0
}

# 阶段1: 单变量筛选（并发）
# 参数: $1=并发度, $2=CORE_OPTIONS数组名
greedy_run_stage1_parallel() {
    local parallel_jobs=$1
    local -n options_array=$2

    greedy_print_stage "阶段1：单变量筛选（测试${#options_array[@]}个独立选项，并发度=${parallel_jobs}）"

    # 生成任务列表
    local task_file="${OUTPUT_BASE_DIR}/.stage1_tasks.txt"
    > "$task_file"
    for opt in "${options_array[@]}"; do
        echo "single_${opt} $opt" >> "$task_file"
    done

    local total_tasks=$(wc -l < "$task_file")
    greedy_print_section "开始并发执行 ${total_tasks} 个实验..."

    # 并发执行
    local results_file="${OUTPUT_BASE_DIR}/.stage1_results.txt"
    greedy_parallel_run_tasks "$task_file" "$results_file" "$parallel_jobs"

    # 检测并发执行是否有失败
    if [ $? -ne 0 ]; then
        greedy_print_error "阶段1有实验失败，终止流程（数据不完整可能导致筛选结果失真）"
        greedy_print_warning "请检查失败原因后重新运行"
        return 1
    fi

    # 调用Python筛选
    greedy_print_section "筛选优秀候选（OR逻辑：sharpe_mean > base OR sharpe_median > base）"

    python3 -m greedy_search.cli filter_stage1 "$BACKTEST_DIR" "$CANDIDATES_DIR" "${options_array[@]}"

    if [ $? -ne 0 ]; then
        greedy_print_error "阶段1筛选失败"
        return 1
    fi

    greedy_print_success "阶段1完成"
    return 0
}

# 阶段k: k变量筛选（并发）
# 参数: $1=k, $2=并发度
greedy_run_stage_k_parallel() {
    local k=$1
    local parallel_jobs=$2
    local prev_k=$((k - 1))

    greedy_print_stage "阶段${k}：${k}变量筛选（严格递增剪枝，并发度=${parallel_jobs}）"

    # 检查前一阶段候选池
    local prev_candidates_json="${CANDIDATES_DIR}/candidates_k${prev_k}.json"
    if [ ! -f "$prev_candidates_json" ]; then
        greedy_print_error "前一阶段候选池不存在: $prev_candidates_json"
        return 1
    fi

    # 生成组合列表
    greedy_print_section "从阶段${prev_k}的候选生成${k}变量组合"

    local task_file="${OUTPUT_BASE_DIR}/.stage${k}_tasks.txt"
    python3 -m greedy_search.cli gen_combos "$CANDIDATES_DIR" "$k" > "$task_file"

    local total_tasks=$(wc -l < "$task_file")

    if [ $total_tasks -eq 0 ]; then
        greedy_print_warning "阶段${k}: 无需测试的组合（所有组合的子组合都未全部通过前一阶段）"
        return 2  # 返回2表示正常终止
    fi

    greedy_print_section "开始并发执行 ${total_tasks} 个实验..."

    # 并发执行
    local results_file="${OUTPUT_BASE_DIR}/.stage${k}_results.txt"
    greedy_parallel_run_tasks "$task_file" "$results_file" "$parallel_jobs"

    # 检测并发执行是否有失败
    if [ $? -ne 0 ]; then
        greedy_print_error "阶段${k}有实验失败，终止流程（数据不完整可能导致筛选结果失真）"
        greedy_print_warning "请检查失败原因后重新运行"
        return 1
    fi

    # 调用Python筛选
    greedy_print_section "筛选优秀候选（严格递增：两指标同时超过所有子组合最优值）"

    python3 -m greedy_search.cli filter_stage_k "$BACKTEST_DIR" "$CANDIDATES_DIR" "$k"

    local python_exit=$?
    if [ $python_exit -eq 1 ]; then
        greedy_print_warning "阶段${k}: 无候选通过筛选，终止递归"
        return 1
    fi

    greedy_print_success "阶段${k}完成"
    return 0
}

# ============================================================================
# 串行执行框架
# ============================================================================

# 阶段1: 单变量筛选（串行）
# 参数: $1=CORE_OPTIONS数组名
greedy_run_stage1_serial() {
    local -n options_array=$1

    greedy_print_stage "阶段1：单变量筛选（测试${#options_array[@]}个独立选项，串行执行）"

    local success_count=0
    local fail_count=0

    for opt in "${options_array[@]}"; do
        local exp_name="single_${opt}"
        greedy_print_section "实验: ${exp_name}"

        run_single_experiment "$exp_name" "$opt"

        if [ $? -eq 0 ]; then
            success_count=$((success_count + 1))
            greedy_print_success "实验 ${exp_name} 完成"
        else
            fail_count=$((fail_count + 1))
            greedy_print_error "实验 ${exp_name} 失败"
        fi
    done

    echo ""
    echo "阶段1统计: 成功=${success_count}, 失败=${fail_count}"

    # 调用Python筛选
    greedy_print_section "筛选优秀候选（OR逻辑：sharpe_mean > base OR sharpe_median > base）"

    python3 -m greedy_search.cli filter_stage1 "$BACKTEST_DIR" "$CANDIDATES_DIR" "${options_array[@]}"

    if [ $? -ne 0 ]; then
        greedy_print_error "阶段1筛选失败"
        return 1
    fi

    greedy_print_success "阶段1完成"
    return 0
}

# 阶段k: k变量筛选（串行）
# 参数: $1=k
greedy_run_stage_k_serial() {
    local k=$1
    local prev_k=$((k - 1))

    greedy_print_stage "阶段${k}：${k}变量筛选（严格递增剪枝，串行执行）"

    # 检查前一阶段候选池
    local prev_candidates_json="${CANDIDATES_DIR}/candidates_k${prev_k}.json"
    if [ ! -f "$prev_candidates_json" ]; then
        greedy_print_error "前一阶段候选池不存在: $prev_candidates_json"
        return 1
    fi

    # 生成组合列表
    greedy_print_section "从阶段${prev_k}的候选生成${k}变量组合"

    local combos=$(python3 -m greedy_search.cli gen_combos "$CANDIDATES_DIR" "$k")

    if [ -z "$combos" ]; then
        greedy_print_warning "阶段${k}: 无需测试的组合（所有组合的子组合都未全部通过前一阶段）"
        return 2  # 返回2表示正常终止
    fi

    local total_tasks=$(echo "$combos" | wc -l)
    greedy_print_section "开始串行执行 ${total_tasks} 个实验..."

    local success_count=0
    local fail_count=0

    while IFS= read -r line; do
        if [ -z "$line" ]; then
            continue
        fi

        local exp_name=$(echo "$line" | cut -d' ' -f1)
        local options_str=$(echo "$line" | cut -d' ' -f2-)

        greedy_print_section "实验: ${exp_name}"

        run_single_experiment "$exp_name" "$options_str"

        if [ $? -eq 0 ]; then
            success_count=$((success_count + 1))
            greedy_print_success "实验 ${exp_name} 完成"
        else
            fail_count=$((fail_count + 1))
            greedy_print_error "实验 ${exp_name} 失败"
        fi
    done <<< "$combos"

    echo ""
    echo "阶段${k}统计: 成功=${success_count}, 失败=${fail_count}"

    # 调用Python筛选
    greedy_print_section "筛选优秀候选（严格递增：两指标同时超过所有子组合最优值）"

    python3 -m greedy_search.cli filter_stage_k "$BACKTEST_DIR" "$CANDIDATES_DIR" "$k"

    local python_exit=$?
    if [ $python_exit -eq 1 ]; then
        greedy_print_warning "阶段${k}: 无候选通过筛选，终止递归"
        return 1
    fi

    greedy_print_success "阶段${k}完成"
    return 0
}

# ============================================================================
# 结果收集
# ============================================================================

# 收集所有实验结果
greedy_collect_results() {
    greedy_print_section "收集所有实验结果"

    export EXPERIMENT_DIR="$BACKTEST_DIR"
    export OUTPUT_CSV="$RESULT_CSV"

    ./scripts/collect_mega_test_results.sh "$BACKTEST_DIR" "$RESULT_CSV"

    if [ $? -eq 0 ]; then
        greedy_print_success "结果汇总完成: $RESULT_CSV"
        return 0
    else
        greedy_print_error "结果汇总失败"
        return 1
    fi
}

# ============================================================================
# 收集模式
# ============================================================================

# 仅收集结果模式
greedy_collect_only_mode() {
    local experiment_root=$1

    if [ ! -d "$experiment_root" ]; then
        greedy_print_error "实验目录不存在: $experiment_root"
        return 1
    fi

    greedy_print_header "仅收集模式：从已有实验目录收集结果"

    # 检测元数据
    local metadata_file="$experiment_root/.experiment_metadata.json"
    if [ -f "$metadata_file" ]; then
        greedy_print_success "检测到实验元数据文件"
        local exp_type=$(python3 -c "import json; print(json.load(open('$metadata_file'))['experiment_type'])" 2>/dev/null)
        [ -n "$exp_type" ] && greedy_print_success "实验类型: $exp_type"
    fi

    # 检测backtests子目录
    local backtest_dir="$experiment_root"
    if [ -d "$experiment_root/backtests" ]; then
        backtest_dir="$experiment_root/backtests"
        greedy_print_success "检测到backtests子目录: $backtest_dir"
    fi

    local result_csv="$experiment_root/mega_test_greedy_summary.csv"
    [ -f "$result_csv" ] && greedy_print_warning "结果文件已存在，将被覆盖: $result_csv"

    greedy_print_section "开始收集实验结果"

    export EXPERIMENT_DIR="$backtest_dir"
    export OUTPUT_CSV="$result_csv"
    export EXPERIMENT_METADATA_FILE="$metadata_file"

    ./scripts/collect_mega_test_results.sh "$backtest_dir" "$result_csv"

    if [ $? -eq 0 ]; then
        greedy_print_success "结果汇总完成: $result_csv"

        greedy_print_header "收集完成"
        local total_dirs=$(find "$backtest_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        echo "实验目录: ${experiment_root}"
        echo "回测子目录: ${backtest_dir}"
        echo "总实验数: ${total_dirs}"
        echo "结果CSV: ${result_csv}"

        if [ -f "$metadata_file" ]; then
            echo ""
            echo "实验元数据:"
            python3 -c "
import json
with open('$metadata_file', 'r') as f:
    meta = json.load(f)
print(f\"  类型: {meta.get('experiment_type', 'N/A')}\")
print(f\"  策略: {meta.get('strategy', 'N/A')}\")
print(f\"  创建时间: {meta.get('created_at', 'N/A')}\")
print(f\"  并发度: {meta.get('parallel_jobs', 'N/A')}\")
" 2>/dev/null
        fi

        echo ""
        greedy_print_success "可以使用以下命令查看结果："
        echo "  column -t -s, \"$result_csv\" | less -S"
        return 0
    else
        greedy_print_error "结果汇总失败"
        return 1
    fi
}

# ============================================================================
# 最终统计打印
# ============================================================================

greedy_print_final_stats() {
    local strategy=$1
    local start_time=$2
    local -n options_array=$3

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))

    greedy_print_header "贪心筛选完成"

    local total_dirs=$(find "$BACKTEST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
    echo "策略: $strategy"
    echo "总实验数: ${total_dirs}"
    echo "并发度: ${PARALLEL_JOBS}"
    echo "总耗时: ${minutes}分${seconds}秒"
    echo "输出目录: ${OUTPUT_BASE_DIR}"
    echo "结果CSV: ${RESULT_CSV}"
    echo "命令记录: ${COMMANDS_CSV}"
    echo "日志目录: ${LOGS_DIR}"
    echo ""
    echo "核心超参:"
    for opt in "${options_array[@]}"; do
        echo "  - ${opt}"
    done
    echo ""
    echo "候选池文件:"
    ls -1 "${CANDIDATES_DIR}"/candidates_k*.json 2>/dev/null || echo "  无"
}

# ============================================================================
# 导出所有函数
# ============================================================================

export -f greedy_print_header
export -f greedy_print_stage
export -f greedy_print_section
export -f greedy_print_success
export -f greedy_print_warning
export -f greedy_print_error
export -f greedy_create_metadata
export -f greedy_init_dirs
export -f greedy_build_base_cmd
export -f greedy_parallel_run_tasks
export -f greedy_run_stage0
export -f greedy_run_stage1_parallel
export -f greedy_run_stage_k_parallel
export -f greedy_run_stage1_serial
export -f greedy_run_stage_k_serial
export -f greedy_collect_results
export -f greedy_collect_only_mode
export -f greedy_print_final_stats
