#!/bin/bash
################################################################################
# 快速打开回测图表
################################################################################

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLOTS_DIR="$PROJECT_ROOT/results/plots"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}                    打开回测图表${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# 检查图表目录
if [ ! -d "$PLOTS_DIR" ]; then
    echo -e "${YELLOW}错误: 图表目录不存在: $PLOTS_DIR${NC}"
    exit 1
fi

# 列出可用的图表
echo -e "${YELLOW}可用的图表:${NC}"
echo ""
i=1
declare -a html_files
for file in "$PLOTS_DIR"/*.html; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "  $i. $filename"
        html_files[$i]="$file"
        ((i++))
    fi
done

if [ ${#html_files[@]} -eq 0 ]; then
    echo -e "${YELLOW}没有找到图表文件${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}选择:${NC}"
echo "  0. 打开所有图表"
echo "  1-$((i-1)). 打开指定图表"
echo "  q. 退出"
echo ""
read -p "请输入选项: " choice

case $choice in
    0)
        echo ""
        echo -e "${GREEN}正在打开所有图表...${NC}"
        for file in "$PLOTS_DIR"/*.html; do
            if [ -f "$file" ]; then
                win_path=$(wslpath -w "$file")
                echo "打开: $(basename "$file")"
                cmd.exe /c start "$win_path" 2>/dev/null
                sleep 0.5
            fi
        done
        ;;
    [1-9]*)
        if [ -n "${html_files[$choice]}" ]; then
            file="${html_files[$choice]}"
            win_path=$(wslpath -w "$file")
            echo ""
            echo -e "${GREEN}正在打开: $(basename "$file")${NC}"
            cmd.exe /c start "$win_path" 2>/dev/null
        else
            echo -e "${YELLOW}无效的选项${NC}"
            exit 1
        fi
        ;;
    q|Q)
        echo "退出"
        exit 0
        ;;
    *)
        echo -e "${YELLOW}无效的选项${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}图表已在浏览器中打开！${NC}"
echo ""
echo -e "${BLUE}======================================================================${NC}"
