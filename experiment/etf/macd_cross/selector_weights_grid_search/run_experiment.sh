#!/bin/bash
# ETF筛选器权重网格搜索实验 - 快速启动脚本

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "ETF筛选器权重网格搜索实验"
echo "方案B: 无偏评分验证"
echo "========================================"
echo ""

# 检查conda环境
echo -e "${YELLOW}[1/5] 检查conda环境...${NC}"
if conda env list | grep -q "backtesting"; then
    echo -e "${GREEN}✓ backtesting环境存在${NC}"
else
    echo -e "${RED}✗ backtesting环境不存在${NC}"
    echo "请先创建环境: conda create -n backtesting python=3.9"
    exit 1
fi

# 激活环境
echo -e "${YELLOW}[2/5] 激活环境...${NC}"
eval "$(conda shell.bash hook)"
conda activate backtesting
echo -e "${GREEN}✓ 环境已激活${NC}"

# 检查项目目录
echo -e "${YELLOW}[3/5] 检查项目目录...${NC}"
PROJECT_ROOT="/mnt/d/git/backtesting"
if [ ! -d "$PROJECT_ROOT" ]; then
    echo -e "${RED}✗ 项目目录不存在: $PROJECT_ROOT${NC}"
    exit 1
fi
cd "$PROJECT_ROOT"
echo -e "${GREEN}✓ 项目目录: $PROJECT_ROOT${NC}"

# 检查数据目录
echo -e "${YELLOW}[4/5] 检查数据目录...${NC}"
if [ ! -d "data/chinese_etf" ]; then
    echo -e "${RED}✗ ETF数据目录不存在: data/chinese_etf${NC}"
    exit 1
fi
if [ ! -d "data/chinese_etf/daily" ]; then
    echo -e "${RED}✗ daily数据目录不存在: data/chinese_etf/daily${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 数据目录检查通过${NC}"

# 显示选项
echo ""
echo -e "${YELLOW}[5/5] 选择执行方式:${NC}"
echo "  1) 完整实验 (22个权重组合，需要2-4小时)"
echo "  2) 简化实验 (使用已有ETF池，快速验证，需要10-20分钟)"
echo "  3) 测试ETF筛选器 (调试用)"
echo "  4) 仅生成参数组合 (查看权重配置)"
echo "  5) 退出"
echo ""

read -p "请选择 [1-5]: " choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}开始完整实验...${NC}"
        echo "实验将在后台运行，日志文件: experiment/etf/macd_cross/selector_weights_grid_search/logs/"
        echo ""
        read -p "确认开始？(y/n): " confirm
        if [ "$confirm" = "y" ]; then
            nohup python experiment/etf/macd_cross/selector_weights_grid_search/unbiased_optimizer.py > /tmp/unbiased_exp.log 2>&1 &
            echo $! > /tmp/unbiased_exp.pid
            echo -e "${GREEN}✓ 实验已启动，进程ID: $(cat /tmp/unbiased_exp.pid)${NC}"
            echo "监控日志: tail -f /tmp/unbiased_exp.log"
            echo "停止实验: kill $(cat /tmp/unbiased_exp.pid)"
        fi
        ;;
    2)
        echo ""
        echo -e "${GREEN}开始简化实验...${NC}"
        python experiment/etf/macd_cross/selector_weights_grid_search/simplified_optimizer.py
        ;;
    3)
        echo ""
        echo -e "${GREEN}测试ETF筛选器...${NC}"
        python experiment/etf/macd_cross/selector_weights_grid_search/test_selector.py
        ;;
    4)
        echo ""
        echo -e "${GREEN}生成参数组合...${NC}"
        python experiment/etf/macd_cross/selector_weights_grid_search/parameter_generator.py
        echo ""
        echo "查看结果:"
        echo "cat experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased_weight_combinations.yaml"
        ;;
    5)
        echo ""
        echo "退出"
        exit 0
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}完成！${NC}"
echo ""
echo "查看结果:"
echo "  - 最优配置: experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/best_weights.json"
echo "  - 所有结果: experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/experiment_results.csv"
echo "  - 实验报告: experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/EXPERIMENT_REPORT.md"
echo "  - Agent总结: experiment/etf/macd_cross/selector_weights_grid_search/results/unbiased/AGENT_SUMMARY.md"
echo ""
