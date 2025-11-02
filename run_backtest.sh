#!/bin/bash
################################################################################
# 美股回测执行脚本
#
# 使用backtesting.py框架对特斯拉和英伟达股票进行策略回测
#
# 作者: Claude Code
# 日期: 2025-10-30
################################################################################

# Conda配置
CONDA_PATH="/home/zijunliu/miniforge3/condabin/conda"
CONDA_ENV="backtesting"

# 项目路径
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$PROJECT_ROOT/backtest_runner.py"

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
${BLUE}美股回测系统${NC} - 使用backtesting.py对美股进行策略回测

${YELLOW}使用方法:${NC}
  $0 [选项]

${YELLOW}选项:${NC}
  -s, --stock <name>       股票名称: tesla, nvidia, all (默认: all)
  -t, --strategy <name>    策略名称: sma_cross, all (默认: sma_cross)
  -o, --optimize           启用参数优化
  -c, --commission <rate>  手续费率 (默认: 0.002, 即0.2%)
  -m, --cash <amount>      初始资金 (默认: 10000美元)
  -d, --output-dir <path>  输出目录 (默认: results)
  --data-dir <path>        数据目录 (默认: data/american_stocks)
  --start-date <date>      开始日期，格式：YYYY-MM-DD (例如: 2020-01-01)
  --end-date <date>        结束日期，格式：YYYY-MM-DD (例如: 2025-12-31)
  -h, --help               显示此帮助信息

${YELLOW}示例:${NC}
  ${GREEN}# 对特斯拉运行双均线策略${NC}
  $0 -s tesla -t sma_cross

  ${GREEN}# 对所有股票运行策略并优化参数${NC}
  $0 -s all -t sma_cross -o

  ${GREEN}# 对英伟达运行策略，自定义手续费和初始资金${NC}
  $0 -s nvidia -t sma_cross -c 0.001 -m 50000

  ${GREEN}# 只分析最近5年的数据${NC}
  $0 -s tesla --start-date 2020-01-01

  ${GREEN}# 分析特定时间段（2015-2020）${NC}
  $0 -s nvidia --start-date 2015-01-01 --end-date 2020-12-31

  ${GREEN}# 快速测试（特斯拉，不优化）${NC}
  $0 -s tesla

${YELLOW}可用股票:${NC}
  - tesla   : 特斯拉
  - nvidia  : 英伟达
  - all     : 所有股票

${YELLOW}可用策略:${NC}
  - sma_cross : 双均线交叉策略
  - all       : 所有策略

${YELLOW}环境要求:${NC}
  - Conda环境: $CONDA_ENV
  - Python 3.9+
  - 已安装backtesting.py及依赖

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
        echo -e "${YELLOW}请先创建环境:${NC}"
        echo "  conda create -n $CONDA_ENV python=3.9"
        echo "  conda activate $CONDA_ENV"
        echo "  pip install -e ."
        exit 1
    fi

    # 检查Python脚本是否存在
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        echo -e "${RED}错误: 未找到回测脚本 ($PYTHON_SCRIPT)${NC}"
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
    STOCK="all"
    STRATEGY="sma_cross"
    OPTIMIZE=""
    COMMISSION=""
    CASH=""
    OUTPUT_DIR=""
    DATA_DIR=""
    START_DATE=""
    END_DATE=""

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--stock)
                STOCK="$2"
                shift 2
                ;;
            -t|--strategy)
                STRATEGY="$2"
                shift 2
                ;;
            -o|--optimize)
                OPTIMIZE="--optimize"
                shift
                ;;
            -c|--commission)
                COMMISSION="--commission $2"
                shift 2
                ;;
            -m|--cash)
                CASH="--cash $2"
                shift 2
                ;;
            -d|--output-dir)
                OUTPUT_DIR="--output-dir $2"
                shift 2
                ;;
            --data-dir)
                DATA_DIR="--data-dir $2"
                shift 2
                ;;
            --start-date)
                START_DATE="--start-date $2"
                shift 2
                ;;
            --end-date)
                END_DATE="--end-date $2"
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

    # 检查环境
    check_environment

    # 显示配置
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}                        美股回测系统启动${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${YELLOW}项目目录:${NC} $PROJECT_ROOT"
    echo -e "${YELLOW}Conda环境:${NC} $CONDA_ENV"
    echo -e "${YELLOW}股票选择:${NC} $STOCK"
    echo -e "${YELLOW}策略选择:${NC} $STRATEGY"
    if [ -n "$OPTIMIZE" ]; then
        echo -e "${YELLOW}参数优化:${NC} ${GREEN}启用${NC}"
    else
        echo -e "${YELLOW}参数优化:${NC} 未启用"
    fi
    if [ -n "$START_DATE" ]; then
        echo -e "${YELLOW}开始日期:${NC} $(echo $START_DATE | cut -d' ' -f2)"
    fi
    if [ -n "$END_DATE" ]; then
        echo -e "${YELLOW}结束日期:${NC} $(echo $END_DATE | cut -d' ' -f2)"
    fi
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    # 激活conda环境并运行Python脚本
    echo -e "${BLUE}激活conda环境并开始回测...${NC}"
    echo ""

    # 构建Python命令 - 使用conda run来避免路径问题
    PYTHON_CMD="$CONDA_PATH run -n $CONDA_ENV python $PYTHON_SCRIPT --stock $STOCK --strategy $STRATEGY $OPTIMIZE $COMMISSION $CASH $OUTPUT_DIR $DATA_DIR $START_DATE $END_DATE"

    # 执行命令
    eval "$PYTHON_CMD"
    EXIT_CODE=$?

    # 检查执行结果
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}======================================================================${NC}"
        echo -e "${GREEN}                        回测完成！${NC}"
        echo -e "${GREEN}======================================================================${NC}"
    else
        echo -e "${RED}======================================================================${NC}"
        echo -e "${RED}                        回测失败 (错误码: $EXIT_CODE)${NC}"
        echo -e "${RED}======================================================================${NC}"
    fi

    return $EXIT_CODE
}

# 执行主函数
main "$@"
