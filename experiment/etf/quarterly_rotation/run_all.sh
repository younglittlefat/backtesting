#!/bin/bash
#
# 季度轮动ETF池实验一键运行脚本
#
# 使用方法:
#   ./run_all.sh
#
# 步骤:
# 1. 生成8个季度的配置文件
# 2. 生成8个季度的ETF池子
# 3. 运行轮动组和固定组回测
# 4. 分析结果并生成报告
#

set -e  # 遇到错误立即退出

# 项目根目录
PROJECT_ROOT="/mnt/d/git/backtesting"
EXPERIMENT_DIR="$PROJECT_ROOT/experiment/etf/quarterly_rotation"
SCRIPTS_DIR="$EXPERIMENT_DIR/scripts"

# Python 解释器
PYTHON="/home/zijunliu/miniforge3/envs/backtesting/bin/python"

# 切换到项目根目录
cd "$PROJECT_ROOT"

echo "============================================================"
echo "季度轮动ETF池实验"
echo "============================================================"
echo "项目目录: $PROJECT_ROOT"
echo "实验目录: $EXPERIMENT_DIR"
echo "============================================================"

# 步骤1: 生成配置文件
echo ""
echo "[步骤1/4] 生成配置文件..."
echo "------------------------------------------------------------"
$PYTHON "$SCRIPTS_DIR/generate_configs.py"

# 步骤2: 生成池子
echo ""
echo "[步骤2/4] 生成ETF池子..."
echo "------------------------------------------------------------"
$PYTHON "$SCRIPTS_DIR/generate_pools.py"

# 步骤3: 运行回测
echo ""
echo "[步骤3/4] 运行回测..."
echo "------------------------------------------------------------"
$PYTHON "$SCRIPTS_DIR/run_backtests.py"

# 步骤4: 分析结果
echo ""
echo "[步骤4/4] 分析结果..."
echo "------------------------------------------------------------"
$PYTHON "$SCRIPTS_DIR/analyze_results.py"

echo ""
echo "============================================================"
echo "实验完成！"
echo "============================================================"
echo "结果目录: $EXPERIMENT_DIR/results/comparison/"
echo "分析报告: $EXPERIMENT_DIR/results/comparison/ANALYSIS_REPORT.md"
echo "============================================================"
