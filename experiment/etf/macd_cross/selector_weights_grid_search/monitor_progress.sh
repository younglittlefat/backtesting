#!/bin/bash
# Monitor experiment progress

LOG_FILE="/mnt/d/git/backtesting/experiment/etf/macd_cross/selector_weights_grid_search/logs/unbiased_experiment_20251110_150911.log"

echo "开始监控实验进度..."
echo "日志文件: $LOG_FILE"
echo ""

while true; do
    # 获取最新进度
    LAST_COMPLETED=$(grep -oP "实验 \K[0-9]+" "$LOG_FILE" | tail -1)
    REMAINING_TIME=$(grep "预计剩余时间" "$LOG_FILE" | tail -1)

    # 检查是否完成
    if grep -q "所有实验完成\|实验 21 完成\|实验全部完成" "$LOG_FILE"; then
        echo "✅ 实验已全部完成！"
        exit 0
    fi

    # 显示进度
    clear
    echo "========================================"
    echo "实验进度监控"
    echo "========================================"
    echo "最新完成: 实验 $LAST_COMPLETED / 21"
    echo "进度: $((LAST_COMPLETED * 100 / 22))%"
    echo "$REMAINING_TIME"
    echo ""
    echo "最新日志 (最后10行):"
    echo "----------------------------------------"
    tail -n 10 "$LOG_FILE"
    echo "----------------------------------------"
    echo ""
    echo "等待下一次检查 (60秒)..."

    sleep 60
done
