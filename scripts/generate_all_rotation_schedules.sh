#!/bin/bash
# 批量生成多周期轮动表
# 用于动态池子轮动策略实验

set -e  # 遇到错误立即退出

# 配置参数
START_DATE="2024-01-02"
END_DATE="2024-05-06"
POOL_SIZE=20
DATA_DIR="data/chinese_etf"
OUTPUT_DIR="results/rotation_schedules"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

echo "=============================================================="
echo " 批量生成轮动表 - 动态池子轮动策略"
echo "=============================================================="
echo ""
echo "⚙️  配置参数:"
echo "  回测区间: $START_DATE 至 $END_DATE"
echo "  池子大小: $POOL_SIZE 只"
echo "  数据目录: $DATA_DIR"
echo "  输出目录: $OUTPUT_DIR"
echo ""

# 轮动周期列表
# PERIODS=(7 15 30 60)
PERIODS=(30)

# 逐个生成
for period in "${PERIODS[@]}"; do
    echo "=============================================================="
    echo "🚀 生成 ${period}天 轮动表..."
    echo "=============================================================="

    OUTPUT_FILE="$OUTPUT_DIR/rotation_${period}d.json"

    /home/zijunliu/miniforge3/condabin/conda run -n backtesting python scripts/prepare_rotation_schedule.py \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --rotation-period "$period" \
        --pool-size "$POOL_SIZE" \
        --data-dir "$DATA_DIR" \
        --output "$OUTPUT_FILE"

    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ ${period}天 轮动表生成成功: $OUTPUT_FILE"
        echo ""
    else
        echo ""
        echo "❌ ${period}天 轮动表生成失败"
        exit 1
    fi

    echo ""
done

echo "=============================================================="
echo "🎉 所有轮动表生成完成！"
echo "=============================================================="
echo ""
echo "📊 生成结果:"
for period in "${PERIODS[@]}"; do
    FILE="$OUTPUT_DIR/rotation_${period}d.json"
    if [ -f "$FILE" ]; then
        SIZE=$(du -h "$FILE" | cut -f1)
        echo "  ✅ rotation_${period}d.json ($SIZE)"
    else
        echo "  ❌ rotation_${period}d.json (未生成)"
    fi
done
echo ""

# 验证所有文件都已生成
MISSING=0
for period in "${PERIODS[@]}"; do
    if [ ! -f "$OUTPUT_DIR/rotation_${period}d.json" ]; then
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -eq 0 ]; then
    echo "✅ 验收通过: 所有 ${#PERIODS[@]} 个轮动表均已成功生成"
    exit 0
else
    echo "❌ 验收失败: 有 $MISSING 个轮动表生成失败"
    exit 1
fi
