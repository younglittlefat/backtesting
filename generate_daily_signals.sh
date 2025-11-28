#!/bin/bash
################################################################################
# 每日交易信号生成脚本 (简化版)
#
# 所有参数直接透传给 Python 入口脚本 generate_signals.py
# 参数解析、帮助文档、验证逻辑全部由 Python 端处理
#
# 作者: Claude Code
# 日期: 2025-11-27
#
# 注意: 原始 600 行版本已备份为 generate_daily_signals.sh.bak
################################################################################

set -e

# Conda 配置
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
# 环境检查
################################################################################
check_environment() {
    # 检查 conda 是否存在
    if [ ! -f "$CONDA_PATH" ]; then
        echo -e "${RED}错误: 未找到 conda ($CONDA_PATH)${NC}" >&2
        exit 1
    fi

    # 检查 conda 环境是否存在
    if ! "$CONDA_PATH" env list 2>/dev/null | grep -q "^$CONDA_ENV "; then
        echo -e "${RED}错误: Conda 环境 '$CONDA_ENV' 不存在${NC}" >&2
        echo -e "${YELLOW}请先创建环境:${NC}" >&2
        echo "  conda create -n $CONDA_ENV python=3.9" >&2
        echo "  conda activate $CONDA_ENV" >&2
        echo "  pip install -e ." >&2
        exit 1
    fi

    # 检查 Python 脚本是否存在
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        echo -e "${RED}错误: 未找到信号生成脚本 ($PYTHON_SCRIPT)${NC}" >&2
        exit 1
    fi
}

################################################################################
# 主函数
################################################################################
main() {
    # 环境检查
    check_environment

    # 显示启动信息（仅当不是 --help 时）
    if [[ ! " $* " =~ " -h " ]] && [[ ! " $* " =~ " --help " ]]; then
        echo -e "${BLUE}======================================================================${NC}"
        echo -e "${BLUE}                     每日交易信号生成${NC}"
        echo -e "${BLUE}======================================================================${NC}"
        echo -e "${YELLOW}运行时间:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
        echo -e "${YELLOW}项目目录:${NC} $PROJECT_ROOT"
        echo -e "${YELLOW}Conda环境:${NC} $CONDA_ENV"
        echo -e "${BLUE}======================================================================${NC}"
        echo ""
    fi

    # 直接透传所有参数给 Python 脚本
    # Python argparse 会处理所有参数解析、验证和帮助文档
    "$CONDA_PATH" run -n "$CONDA_ENV" python "$PYTHON_SCRIPT" "$@"
    local exit_code=$?

    # 显示完成信息
    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}======================================================================${NC}"
        echo -e "${GREEN}                        执行完成！${NC}"
        echo -e "${GREEN}======================================================================${NC}"
    else
        echo -e "${RED}======================================================================${NC}"
        echo -e "${RED}                        执行失败 (错误码: $exit_code)${NC}"
        echo -e "${RED}======================================================================${NC}"
    fi

    return $exit_code
}

# 执行主函数，传递所有命令行参数
main "$@"
