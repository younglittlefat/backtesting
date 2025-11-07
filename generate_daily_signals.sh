#!/bin/bash
################################################################################
# 每日交易信号生成脚本
#
# 每天收盘后运行，生成买入/卖出信号和资金分配建议
#
# 作者: Claude Code
# 日期: 2025-11-07
################################################################################

# Conda配置
CONDA_PATH="/home/zijunliu/miniforge3/condabin/conda"
CONDA_ENV="backtesting"

# 项目路径
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$PROJECT_ROOT/generate_signals.py"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# 显示使用帮助
################################################################################
show_help() {
    cat << EOF
${BLUE}每日交易信号生成系统${NC} - 分析股票池并生成买入/卖出建议

${YELLOW}使用方法:${NC}
  $0 [选项]

${YELLOW}选项:${NC}
  --stock-list <csv_file>      股票列表CSV文件（必需，需包含ts_code列）
  --strategy <name>            策略名称（默认: sma_cross）
  --cash <amount>              可用资金（默认: 100000）
  --positions <n>              目标持仓数量（默认: 10）
  --cost-model <model>         费用模型（默认: cn_etf）
  --data-dir <path>            数据目录（默认: data/csv/daily）
  --lookback-days <n>          回看天数（默认: 250）
  --output <file>              输出报告文件路径（可选）
  --csv <file>                 输出CSV文件路径（可选）
  --n1 <n>                     短期均线周期（覆盖策略默认值）
  --n2 <n>                     长期均线周期（覆盖策略默认值）
  -h, --help                   显示此帮助信息

${YELLOW}示例:${NC}
  ${GREEN}# 使用默认参数生成信号${NC}
  $0 --stock-list results/trend_etf_pool_20251107.csv

  ${GREEN}# 指定可用资金和目标持仓数${NC}
  $0 --stock-list results/trend_etf_pool_20251107.csv --cash 200000 --positions 15

  ${GREEN}# 使用自定义策略参数${NC}
  $0 --stock-list results/trend_etf_pool_20251107.csv --n1 5 --n2 20

  ${GREEN}# 保存报告到文件${NC}
  $0 --stock-list results/trend_etf_pool_20251107.csv --output signals/daily_report.txt --csv signals/signals.csv

${YELLOW}工作流程:${NC}
  1. 每天收盘后（15:30之后）运行此脚本
  2. 脚本会分析股票池中所有标的的最新数据
  3. 检测是否有金叉（买入）或死叉（卖出）信号
  4. 生成资金分配方案，告诉您买入哪些股票、买入多少股
  5. 根据建议执行交易

${YELLOW}环境要求:${NC}
  - Conda环境: $CONDA_ENV
  - Python 3.9+
  - 已安装 backtesting.py 及依赖
  - 数据已更新到最新交易日

EOF
}

################################################################################
# 检查环境
################################################################################
check_environment() {
    echo -e "${BLUE}检查环境...${NC}"

    # 检查conda是否存在
    if [ ! -f "$CONDA_PATH" ]; then
        echo -e "${RED}错误: 未找到conda ($CONDA_PATH)${NC}"
        exit 1
    fi

    # 检查conda环境是否存在
    if ! "$CONDA_PATH" env list | grep -q "^$CONDA_ENV "; then
        echo -e "${RED}错误: Conda环境 '$CONDA_ENV' 不存在${NC}"
        exit 1
    fi

    # 检查Python脚本是否存在
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        echo -e "${RED}错误: 未找到信号生成脚本 ($PYTHON_SCRIPT)${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ 环境检查通过${NC}"
    echo ""
}

################################################################################
# 主函数
################################################################################
main() {
    # 默认参数
    STOCK_LIST=""
    STRATEGY="sma_cross"
    CASH="100000"
    POSITIONS="10"
    COST_MODEL="cn_etf"
    DATA_DIR="data/csv/daily"
    LOOKBACK_DAYS="250"
    OUTPUT=""
    CSV=""
    N1=""
    N2=""

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --stock-list)
                STOCK_LIST="$2"
                shift 2
                ;;
            --strategy)
                STRATEGY="$2"
                shift 2
                ;;
            --cash)
                CASH="$2"
                shift 2
                ;;
            --positions)
                POSITIONS="$2"
                shift 2
                ;;
            --cost-model)
                COST_MODEL="$2"
                shift 2
                ;;
            --data-dir)
                DATA_DIR="$2"
                shift 2
                ;;
            --lookback-days)
                LOOKBACK_DAYS="$2"
                shift 2
                ;;
            --output)
                OUTPUT="$2"
                shift 2
                ;;
            --csv)
                CSV="$2"
                shift 2
                ;;
            --n1)
                N1="$2"
                shift 2
                ;;
            --n2)
                N2="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}错误: 未知选项 '$1'${NC}"
                echo "使用 -h 或 --help 查看帮助"
                exit 1
                ;;
        esac
    done

    # 检查必需参数
    if [ -z "$STOCK_LIST" ]; then
        echo -e "${RED}错误: 必须指定 --stock-list 参数${NC}"
        echo "使用 -h 或 --help 查看帮助"
        exit 1
    fi

    # 检查环境
    check_environment

    # 检查股票列表文件
    if [ ! -f "$STOCK_LIST" ]; then
        echo -e "${RED}错误: 股票列表文件不存在: $STOCK_LIST${NC}"
        exit 1
    fi

    # 显示配置
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}                     每日交易信号生成${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${YELLOW}运行时间:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${YELLOW}项目目录:${NC} $PROJECT_ROOT"
    echo -e "${YELLOW}股票列表:${NC} $STOCK_LIST"
    echo -e "${YELLOW}策略名称:${NC} $STRATEGY"
    echo -e "${YELLOW}可用资金:${NC} ¥$CASH"
    echo -e "${YELLOW}目标持仓:${NC} $POSITIONS"
    echo -e "${YELLOW}费用模型:${NC} $COST_MODEL"
    echo -e "${YELLOW}数据目录:${NC} $DATA_DIR"
    if [ -n "$N1" ]; then
        echo -e "${YELLOW}短期均线:${NC} $N1 日"
    fi
    if [ -n "$N2" ]; then
        echo -e "${YELLOW}长期均线:${NC} $N2 日"
    fi
    if [ -n "$OUTPUT" ]; then
        echo -e "${YELLOW}报告输出:${NC} $OUTPUT"
    fi
    if [ -n "$CSV" ]; then
        echo -e "${YELLOW}CSV输出:${NC} $CSV"
    fi
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    # 构建命令
    CMD=("$CONDA_PATH" "run" "-n" "$CONDA_ENV" "python" "$PYTHON_SCRIPT")
    CMD+=("--stock-list" "$STOCK_LIST")
    CMD+=("--strategy" "$STRATEGY")
    CMD+=("--cash" "$CASH")
    CMD+=("--positions" "$POSITIONS")
    CMD+=("--cost-model" "$COST_MODEL")
    CMD+=("--data-dir" "$DATA_DIR")
    CMD+=("--lookback-days" "$LOOKBACK_DAYS")

    if [ -n "$OUTPUT" ]; then
        # 确保输出目录存在
        mkdir -p "$(dirname "$OUTPUT")"
        CMD+=("--output" "$OUTPUT")
    fi

    if [ -n "$CSV" ]; then
        # 确保输出目录存在
        mkdir -p "$(dirname "$CSV")"
        CMD+=("--csv" "$CSV")
    fi

    if [ -n "$N1" ]; then
        CMD+=("--n1" "$N1")
    fi

    if [ -n "$N2" ]; then
        CMD+=("--n2" "$N2")
    fi

    # 执行
    echo -e "${BLUE}开始生成交易信号...${NC}"
    echo ""
    "${CMD[@]}"
    EXIT_CODE=$?

    # 检查执行结果
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}======================================================================${NC}"
        echo -e "${GREEN}                        信号生成完成！${NC}"
        echo -e "${GREEN}======================================================================${NC}"
    else
        echo -e "${RED}======================================================================${NC}"
        echo -e "${RED}                        信号生成失败 (错误码: $EXIT_CODE)${NC}"
        echo -e "${RED}======================================================================${NC}"
    fi

    return $EXIT_CODE
}

# 执行主函数
main "$@"
