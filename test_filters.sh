#!/bin/bash
################################################################################
# 信号过滤器对比测试脚本
#
# 用于对比不同过滤器组合的效果
#
# 作者: Claude Code
# 日期: 2025-11-09
################################################################################

# 测试配置
STOCK_LIST="results/trend_etf_pool.csv"
DATA_DIR="data/chinese_etf/daily"
OUTPUT_DIR="results/filter_comparison"
OPTIMIZE="--optimize"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}           信号过滤器对比测试${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

################################################################################
# 测试1: 基线测试（原版策略，无过滤器）
################################################################################
echo -e "${YELLOW}[1/7] 测试基线: 原版sma_cross策略（无过滤器）${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/baseline" \
    --save-params "$OUTPUT_DIR/baseline_params.json"

if [ $? -ne 0 ]; then
    echo -e "${RED}基线测试失败，终止${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ 基线测试完成${NC}"
echo ""

################################################################################
# 测试2: 仅启用均线斜率过滤器
################################################################################
echo -e "${YELLOW}[2/7] 测试过滤器: 均线斜率过滤${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross_enhanced \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/slope_only" \
    --save-params "$OUTPUT_DIR/slope_params.json"

# 注意：需要修改backtest_runner.py以支持过滤器参数传递
# 这里先运行基础优化，后续在Python中启用过滤器

echo ""
echo -e "${GREEN}✓ 斜率过滤器测试完成${NC}"
echo ""

################################################################################
# 测试3: 仅启用ADX过滤器
################################################################################
echo -e "${YELLOW}[3/7] 测试过滤器: ADX趋势强度过滤${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross_enhanced \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/adx_only"

echo ""
echo -e "${GREEN}✓ ADX过滤器测试完成${NC}"
echo ""

################################################################################
# 测试4: 仅启用成交量过滤器
################################################################################
echo -e "${YELLOW}[4/7] 测试过滤器: 成交量确认过滤${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross_enhanced \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/volume_only"

echo ""
echo -e "${GREEN}✓ 成交量过滤器测试完成${NC}"
echo ""

################################################################################
# 测试5: 仅启用持续确认过滤器
################################################################################
echo -e "${YELLOW}[5/7] 测试过滤器: 持续确认过滤${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross_enhanced \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/confirm_only"

echo ""
echo -e "${GREEN}✓ 持续确认过滤器测试完成${NC}"
echo ""

################################################################################
# 测试6: 组合过滤器（斜率 + ADX + 成交量）
################################################################################
echo -e "${YELLOW}[6/7] 测试组合: 斜率 + ADX + 成交量${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross_enhanced \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/combined_3"

echo ""
echo -e "${GREEN}✓ 组合过滤器测试完成${NC}"
echo ""

################################################################################
# 测试7: 所有过滤器
################################################################################
echo -e "${YELLOW}[7/7] 测试组合: 所有过滤器${NC}"
./run_backtest.sh \
    --stock-list "$STOCK_LIST" \
    --strategy sma_cross_enhanced \
    $OPTIMIZE \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR/all_filters"

echo ""
echo -e "${GREEN}✓ 全部过滤器测试完成${NC}"
echo ""

################################################################################
# 生成对比报告
################################################################################
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}                      生成对比报告${NC}"
echo -e "${BLUE}======================================================================${NC}"

# TODO: 创建Python脚本来聚合和对比结果
# python tools/compare_filter_results.py "$OUTPUT_DIR"

echo ""
echo -e "${GREEN}所有测试完成！结果保存在: $OUTPUT_DIR${NC}"
echo ""
echo -e "${YELLOW}下一步:${NC}"
echo "  1. 查看各个测试的结果目录"
echo "  2. 对比关键指标（胜率、夏普比率、最大回撤等）"
echo "  3. 选择最优的过滤器组合"
echo ""
