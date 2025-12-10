#!/bin/bash
# 批量运行所有评分脚本生成池子

cd /mnt/d/git/backtesting

CONFIGS=(
    "single_adx_score"
    "single_liquidity_score"
    "single_momentum_12m"
    "single_momentum_3m"
    "single_price_efficiency"
    "single_trend_consistency"
    "single_trend_quality"
    "single_volume"
    "single_core_trend_excess_return_20d"
    "single_core_trend_excess_return_60d"
    "single_idr"
)

echo "=========================================="
echo "开始批量生成 2022-2023 评分池子"
echo "共有 ${#CONFIGS[@]} 个配置"
echo "=========================================="

SUCCESS=0
FAILED=0

for config in "${CONFIGS[@]}"; do
    echo ""
    echo ">>> 正在处理: ${config}"
    echo "----------------------------------------"

    /home/zijunliu/miniforge3/envs/backtesting/bin/python -m etf_selector.main \
        --config "experiment/etf/selector_score/pool_2022_2023/${config}.json"

    if [ $? -eq 0 ]; then
        echo "✓ ${config} 完成"
        ((SUCCESS++))
    else
        echo "✗ ${config} 失败"
        ((FAILED++))
    fi
done

echo ""
echo "=========================================="
echo "评分池子生成完成"
echo "成功: ${SUCCESS}/${#CONFIGS[@]}"
echo "失败: ${FAILED}/${#CONFIGS[@]}"
echo "=========================================="
