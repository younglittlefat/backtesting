#!/bin/bash
################################################################################
# 中国市场回测执行脚本
#
# 使用 backtesting.py 框架对中国市场 ETF / 基金等标的执行策略回测
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
${BLUE}中国市场回测系统${NC} - 使用 backtesting.py 对中国 ETF / 基金进行策略回测

${YELLOW}使用方法:${NC}
  $0 [选项]

${YELLOW}选项:${NC}
  -s, --stock <codes>          标的代码（逗号分隔），支持 category:etf 语法，默认 all
  --stock-list <csv_file>      从CSV文件读取标的列表（需包含ts_code列），优先级高于-s参数
  --category <names>           可选类别筛选（例如: etf,fund）
  -t, --strategy <name>        策略名称: sma_cross, sma_cross_enhanced, all (默认: sma_cross)
  -o, --optimize               启用参数优化
  --cost-model <model>         费用模型: default, cn_etf, cn_stock, us_stock, custom (默认: cn_etf)
  -c, --commission <rate>      自定义佣金率（覆盖cost-model配置）
  --spread <rate>              自定义滑点率（覆盖cost-model配置）
  -m, --cash <amount>          初始资金 (默认: 10000)
  -d, --output-dir <path>      输出目录 (默认: results)
  --data-dir <path>            数据目录 (默认: data/chinese_stocks，ETF数据使用 data/csv/daily)
  --aggregate-output <path>    聚合结果输出 CSV（预留批量汇总接口）
  --start-date <date>          开始日期 YYYY-MM-DD
  --end-date <date>            结束日期 YYYY-MM-DD
  --instrument-limit <n>       限制本次回测的标的数量，只取前 N 个
  --keep-negative              保留收益率为负的标的结果文件（默认会删除）
  --verbose                    输出详细日志（默认仅显示汇总）
  --save-params <file>         保存优化参数到配置文件（仅在--optimize时有效）

${YELLOW}过滤器选项（仅sma_cross_enhanced策略可用）:${NC}
  --enable-adx-filter          启用ADX趋势强度过滤器 ⭐推荐
  --enable-volume-filter       启用成交量确认过滤器 ⭐推荐
  --enable-slope-filter        启用均线斜率过滤器
  --enable-confirm-filter      启用持续确认过滤器
  --enable-loss-protection     启用连续止损保护过滤器
  --adx-threshold <value>      ADX阈值 (默认: 25)
  --adx-period <value>         ADX计算周期 (默认: 14)
  --volume-ratio <value>       成交量放大倍数 (默认: 1.2)
  --volume-period <value>      成交量均值周期 (默认: 20)
  --slope-lookback <value>     斜率回溯周期 (默认: 5)
  --confirm-bars <value>       持续确认K线数 (默认: 2)
  --max-losses <value>         触发保护的连续亏损次数 (默认: 3)
  --pause-bars <value>         触发保护后暂停的K线数 (默认: 10)

  -h, --help                   显示此帮助信息

${YELLOW}示例:${NC}
  ${GREEN}# 使用筛选器生成的ETF池进行回测（需指定data-dir）${NC}
  $0 --stock-list results/trend_etf_pool_20251107.csv -t sma_cross -o --data-dir data/csv/daily

  ${GREEN}# 使用增强版策略 + ADX和成交量过滤器（推荐配置）${NC}
  $0 --stock-list results/trend_etf_pool.csv -t sma_cross_enhanced -o \
     --enable-adx-filter --enable-volume-filter --data-dir data/chinese_etf/daily

  ${GREEN}# 测试不同的ADX阈值${NC}
  $0 -s 561160.SH -t sma_cross_enhanced -o --enable-adx-filter \
     --adx-threshold 30 --data-dir data/chinese_etf/daily

  ${GREEN}# 启用所有过滤器${NC}
  $0 --stock-list results/trend_etf_pool.csv -t sma_cross_enhanced -o \
     --enable-adx-filter --enable-volume-filter --enable-slope-filter \
     --data-dir data/chinese_etf/daily

  ${GREEN}# 回测并保存优化参数到配置文件${NC}
  $0 --stock-list results/trend_etf_pool_20251107.csv -t sma_cross -o --save-params config/strategy_params.json

  ${GREEN}# 对 159001.SZ 运行双均线策略（使用默认ETF费用）${NC}
  $0 -s 159001.SZ -t sma_cross

  ${GREEN}# 批量回测所有 ETF 并优化参数${NC}
  $0 --category etf -t sma_cross -o

  ${GREEN}# 使用框架缺省配置（零成本），用于对比分析${NC}
  $0 -s 510300.SH -t sma_cross --cost-model default

  ${GREEN}# 回测个股，使用包含印花税的cn_stock模型${NC}
  $0 -s 600519.SH -t sma_cross --cost-model cn_stock

  ${GREEN}# 使用cn_etf模型但提高滑点${NC}
  $0 -s 159001.SZ --cost-model cn_etf --spread 0.0005

  ${GREEN}# 自定义费用参数${NC}
  $0 -s 510300.SH --cost-model custom -c 0.002 --spread 0.001

  ${GREEN}# 限定日期范围并导出聚合摘要${NC}
  $0 -s all --start-date 2020-01-01 --aggregate-output results/summary.csv

  ${GREEN}# 仅回测筛选到的前 5 只标的${NC}
  $0 --category etf --instrument-limit 5

  ${GREEN}# 查看详细日志输出${NC}
  $0 --category etf --instrument-limit 5 --verbose

  ${GREEN}# 保留负收益率标的的结果文件${NC}
  $0 --category etf --keep-negative

${YELLOW}示例标的:${NC}
  - 159001.SZ : 华夏上证50ETF
  - 510300.SH : 华泰柏瑞沪深300ETF
  - 000001.OF : 华夏成长基金
  - category:etf : 所有 ETF

${YELLOW}环境要求:${NC}
  - Conda环境: $CONDA_ENV
  - Python 3.9+
  - 已安装 backtesting.py 及依赖

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
# 清理负收益率标的结果文件
################################################################################
cleanup_negative_returns() {
    local output_dir="$1"
    local stats_deleted=0
    local plots_deleted=0

    if [ ! -d "$output_dir" ]; then
        echo -e "${YELLOW}警告: 输出目录不存在: $output_dir${NC}"
        return 0
    fi

    # 遍历所有类别子目录
    for category_dir in "$output_dir"/*; do
        if [ ! -d "$category_dir" ]; then
            continue
        fi

        local category_name=$(basename "$category_dir")
        if [ "$category_name" = "summary" ]; then
            continue  # 跳过summary目录
        fi

        local stats_dir="$category_dir/stats"
        local plots_dir="$category_dir/plots"

        if [ ! -d "$stats_dir" ]; then
            continue
        fi

        # 处理stats目录中的CSV文件
        for stats_file in "$stats_dir"/*.csv; do
            if [ ! -f "$stats_file" ]; then
                continue
            fi

            # 跳过trades文件
            if [[ "$stats_file" == *"_trades.csv" ]]; then
                continue
            fi

            # 读取CSV文件，检查收益率列（第12列）
            # 使用tail跳过标题行，然后用cut提取收益率列
            local return_rate=$(tail -n +2 "$stats_file" | cut -d',' -f12 | head -n 1)

            # 检查是否为数字且为负数
            if [[ "$return_rate" =~ ^-[0-9]+\.?[0-9]*$ ]]; then
                # 提取文件名中的标的代码和策略名
                local filename=$(basename "$stats_file")
                local instrument_code=$(echo "$filename" | cut -d'_' -f1)
                local strategy_name=$(echo "$filename" | cut -d'_' -f2)

                echo -e "${YELLOW}  删除负收益率标的: $instrument_code (收益率: ${return_rate}%)${NC}"

                # 删除stats文件
                rm -f "$stats_file"
                stats_deleted=$((stats_deleted + 1))

                # 删除对应的trades文件（如果存在）
                local trades_file="${stats_file%%.csv}_trades.csv"
                if [ -f "$trades_file" ]; then
                    rm -f "$trades_file"
                fi

                # 删除对应的plots文件
                if [ -d "$plots_dir" ]; then
                    local plot_file="$plots_dir/${instrument_code}_${strategy_name}.html"
                    if [ -f "$plot_file" ]; then
                        rm -f "$plot_file"
                        plots_deleted=$((plots_deleted + 1))
                    fi
                fi
            fi
        done
    done

    if [ $stats_deleted -gt 0 ] || [ $plots_deleted -gt 0 ]; then
        echo -e "${GREEN}清理完成: 删除了 $stats_deleted 个统计文件和 $plots_deleted 个图表文件${NC}"
    else
        echo -e "${GREEN}无需清理: 未发现负收益率标的${NC}"
    fi
}

################################################################################
# 主函数
################################################################################
main() {
    # 默认参数
    STOCK="all"
    STOCK_LIST_VALUE=""
    STOCK_LIST_ARGS=()
    STRATEGY="sma_cross"
    OPTIMIZE_FLAG=0

    CATEGORY_VALUE=""
    CATEGORY_ARGS=()

    COST_MODEL_VALUE="cn_etf"
    COST_MODEL_ARGS=("--cost-model" "cn_etf")

    COMMISSION_VALUE=""
    COMMISSION_ARGS=()

    SPREAD_VALUE=""
    SPREAD_ARGS=()

    CASH_VALUE="10000"
    CASH_ARGS=()

    OUTPUT_DIR_VALUE="results"
    OUTPUT_DIR_ARGS=()

    DATA_DIR_VALUE="data/chinese_stocks"
    DATA_DIR_ARGS=("--data-dir" "$DATA_DIR_VALUE")

    AGGREGATE_VALUE=""
    AGGREGATE_ARGS=()

    START_DATE_VALUE=""
    START_DATE_ARGS=()

    END_DATE_VALUE=""
    END_DATE_ARGS=()

    INSTRUMENT_LIMIT_VALUE=""
    INSTRUMENT_LIMIT_ARGS=()

    KEEP_NEGATIVE_FLAG=0

    SAVE_PARAMS_VALUE=""
    SAVE_PARAMS_ARGS=()

    VERBOSE_FLAG=0

    # 过滤器参数初始化
    ENABLE_ADX_FILTER_FLAG=0
    ENABLE_VOLUME_FILTER_FLAG=0
    ENABLE_SLOPE_FILTER_FLAG=0
    ENABLE_CONFIRM_FILTER_FLAG=0
    ENABLE_LOSS_PROTECTION_FLAG=0

    ADX_THRESHOLD_VALUE="25"
    ADX_THRESHOLD_ARGS=()

    ADX_PERIOD_VALUE="14"
    ADX_PERIOD_ARGS=()

    VOLUME_RATIO_VALUE="1.2"
    VOLUME_RATIO_ARGS=()

    VOLUME_PERIOD_VALUE="20"
    VOLUME_PERIOD_ARGS=()

    SLOPE_LOOKBACK_VALUE="5"
    SLOPE_LOOKBACK_ARGS=()

    CONFIRM_BARS_VALUE="2"
    CONFIRM_BARS_ARGS=()

    MAX_LOSSES_VALUE="3"
    MAX_LOSSES_ARGS=()

    PAUSE_BARS_VALUE="10"
    PAUSE_BARS_ARGS=()

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--stock)
                STOCK="$2"
                shift 2
                ;;
            --stock-list)
                STOCK_LIST_VALUE="$2"
                STOCK_LIST_ARGS=("--stock-list" "$2")
                shift 2
                ;;
            -t|--strategy)
                STRATEGY="$2"
                shift 2
                ;;
            -o|--optimize)
                OPTIMIZE_FLAG=1
                shift
                ;;
            --cost-model)
                COST_MODEL_VALUE="$2"
                COST_MODEL_ARGS=("--cost-model" "$2")
                shift 2
                ;;
            -c|--commission)
                COMMISSION_VALUE="$2"
                COMMISSION_ARGS=("--commission" "$2")
                shift 2
                ;;
            --spread)
                SPREAD_VALUE="$2"
                SPREAD_ARGS=("--spread" "$2")
                shift 2
                ;;
            -m|--cash)
                CASH_VALUE="$2"
                CASH_ARGS=("--cash" "$2")
                shift 2
                ;;
            -d|--output-dir)
                OUTPUT_DIR_VALUE="$2"
                OUTPUT_DIR_ARGS=("--output-dir" "$2")
                shift 2
                ;;
            --category)
                CATEGORY_VALUE="$2"
                CATEGORY_ARGS=("--category" "$2")
                shift 2
                ;;
            --data-dir)
                DATA_DIR_VALUE="$2"
                DATA_DIR_ARGS=("--data-dir" "$2")
                shift 2
                ;;
            --aggregate-output)
                AGGREGATE_VALUE="$2"
                AGGREGATE_ARGS=("--aggregate-output" "$2")
                shift 2
                ;;
            --start-date)
                START_DATE_VALUE="$2"
                START_DATE_ARGS=("--start-date" "$2")
                shift 2
                ;;
            --end-date)
                END_DATE_VALUE="$2"
                END_DATE_ARGS=("--end-date" "$2")
                shift 2
                ;;
            --instrument-limit)
                INSTRUMENT_LIMIT_VALUE="$2"
                INSTRUMENT_LIMIT_ARGS=("--instrument-limit" "$2")
                shift 2
                ;;
            --keep-negative)
                KEEP_NEGATIVE_FLAG=1
                shift
                ;;
            --verbose)
                VERBOSE_FLAG=1
                shift
                ;;
            --save-params)
                SAVE_PARAMS_VALUE="$2"
                SAVE_PARAMS_ARGS=("--save-params" "$2")
                shift 2
                ;;
            --enable-adx-filter)
                ENABLE_ADX_FILTER_FLAG=1
                shift
                ;;
            --enable-volume-filter)
                ENABLE_VOLUME_FILTER_FLAG=1
                shift
                ;;
            --enable-slope-filter)
                ENABLE_SLOPE_FILTER_FLAG=1
                shift
                ;;
            --enable-confirm-filter)
                ENABLE_CONFIRM_FILTER_FLAG=1
                shift
                ;;
            --enable-loss-protection)
                ENABLE_LOSS_PROTECTION_FLAG=1
                shift
                ;;
            --adx-threshold)
                ADX_THRESHOLD_VALUE="$2"
                ADX_THRESHOLD_ARGS=("--adx-threshold" "$2")
                shift 2
                ;;
            --adx-period)
                ADX_PERIOD_VALUE="$2"
                ADX_PERIOD_ARGS=("--adx-period" "$2")
                shift 2
                ;;
            --volume-ratio)
                VOLUME_RATIO_VALUE="$2"
                VOLUME_RATIO_ARGS=("--volume-ratio" "$2")
                shift 2
                ;;
            --volume-period)
                VOLUME_PERIOD_VALUE="$2"
                VOLUME_PERIOD_ARGS=("--volume-period" "$2")
                shift 2
                ;;
            --slope-lookback)
                SLOPE_LOOKBACK_VALUE="$2"
                SLOPE_LOOKBACK_ARGS=("--slope-lookback" "$2")
                shift 2
                ;;
            --confirm-bars)
                CONFIRM_BARS_VALUE="$2"
                CONFIRM_BARS_ARGS=("--confirm-bars" "$2")
                shift 2
                ;;
            --max-losses)
                MAX_LOSSES_VALUE="$2"
                MAX_LOSSES_ARGS=("--max-losses" "$2")
                shift 2
                ;;
            --pause-bars)
                PAUSE_BARS_VALUE="$2"
                PAUSE_BARS_ARGS=("--pause-bars" "$2")
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

    # 检查股票列表文件（如果指定）
    if [ -n "$STOCK_LIST_VALUE" ]; then
        if [ ! -f "$STOCK_LIST_VALUE" ]; then
            echo -e "${RED}错误: 股票列表文件不存在: $STOCK_LIST_VALUE${NC}"
            exit 1
        fi

        # 检查CSV文件是否包含ts_code列
        if ! head -n 1 "$STOCK_LIST_VALUE" | grep -q "ts_code"; then
            echo -e "${RED}错误: 股票列表文件缺少 'ts_code' 列: $STOCK_LIST_VALUE${NC}"
            exit 1
        fi

        # 统计股票数量（减去标题行）
        local stock_count=$(tail -n +2 "$STOCK_LIST_VALUE" | wc -l)
        echo -e "${GREEN}✓ 股票列表文件有效: $stock_count 只标的${NC}"
        echo ""
    fi

    # 显示配置
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}                     中国市场回测系统启动${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${YELLOW}项目目录:${NC} $PROJECT_ROOT"
    echo -e "${YELLOW}Conda环境:${NC} $CONDA_ENV"
    if [ -n "$STOCK_LIST_VALUE" ]; then
        echo -e "${YELLOW}股票列表:${NC} $STOCK_LIST_VALUE (优先级高于-s参数)"
    else
        echo -e "${YELLOW}标的选择:${NC} $STOCK"
    fi
    if [ -n "$CATEGORY_VALUE" ]; then
        echo -e "${YELLOW}类别筛选:${NC} $CATEGORY_VALUE"
    else
        echo -e "${YELLOW}类别筛选:${NC} 不限"
    fi
    echo -e "${YELLOW}策略选择:${NC} $STRATEGY"
    if [ $OPTIMIZE_FLAG -eq 1 ]; then
        echo -e "${YELLOW}参数优化:${NC} ${GREEN}启用${NC}"
    else
        echo -e "${YELLOW}参数优化:${NC} 未启用"
    fi
    echo -e "${YELLOW}费用模型:${NC} $COST_MODEL_VALUE"
    if [ -n "$COMMISSION_VALUE" ]; then
        echo -e "${YELLOW}佣金覆盖:${NC} $COMMISSION_VALUE"
    fi
    if [ -n "$SPREAD_VALUE" ]; then
        echo -e "${YELLOW}滑点覆盖:${NC} $SPREAD_VALUE"
    fi
    echo -e "${YELLOW}初始资金:${NC} $CASH_VALUE"
    echo -e "${YELLOW}数据目录:${NC} $DATA_DIR_VALUE"
    echo -e "${YELLOW}输出目录:${NC} $OUTPUT_DIR_VALUE"
    if [ -n "$AGGREGATE_VALUE" ]; then
        echo -e "${YELLOW}聚合输出:${NC} $AGGREGATE_VALUE"
    fi
    if [ -n "$START_DATE_VALUE" ]; then
        echo -e "${YELLOW}开始日期:${NC} $START_DATE_VALUE"
    fi
    if [ -n "$END_DATE_VALUE" ]; then
        echo -e "${YELLOW}结束日期:${NC} $END_DATE_VALUE"
    fi
    if [ -n "$INSTRUMENT_LIMIT_VALUE" ]; then
        echo -e "${YELLOW}标的数量限制:${NC} $INSTRUMENT_LIMIT_VALUE"
    fi
    if [ $KEEP_NEGATIVE_FLAG -eq 1 ]; then
        echo -e "${YELLOW}负收益结果:${NC} ${GREEN}保留${NC}"
    else
        echo -e "${YELLOW}负收益结果:${NC} 删除"
    fi
    if [ $VERBOSE_FLAG -eq 1 ]; then
        echo -e "${YELLOW}详细日志:${NC} ${GREEN}启用${NC}"
    else
        echo -e "${YELLOW}详细日志:${NC} 关闭"
    fi
    if [ -n "$SAVE_PARAMS_VALUE" ]; then
        echo -e "${YELLOW}参数保存:${NC} $SAVE_PARAMS_VALUE"
    fi
    if [ $ENABLE_ADX_FILTER_FLAG -eq 1 ] || [ $ENABLE_VOLUME_FILTER_FLAG -eq 1 ] || [ $ENABLE_SLOPE_FILTER_FLAG -eq 1 ] || [ $ENABLE_CONFIRM_FILTER_FLAG -eq 1 ] || [ $ENABLE_LOSS_PROTECTION_FLAG -eq 1 ]; then
        echo -e "${YELLOW}过滤器配置:${NC}"
        if [ $ENABLE_ADX_FILTER_FLAG -eq 1 ]; then
            echo -e "  ADX过滤器: 启用 (阈值=$ADX_THRESHOLD_VALUE, 周期=$ADX_PERIOD_VALUE)"
        fi
        if [ $ENABLE_VOLUME_FILTER_FLAG -eq 1 ]; then
            echo -e "  成交量过滤器: 启用 (放大倍数=$VOLUME_RATIO_VALUE, 周期=$VOLUME_PERIOD_VALUE)"
        fi
        if [ $ENABLE_SLOPE_FILTER_FLAG -eq 1 ]; then
            echo -e "  斜率过滤器: 启用 (回溯周期=$SLOPE_LOOKBACK_VALUE)"
        fi
        if [ $ENABLE_CONFIRM_FILTER_FLAG -eq 1 ]; then
            echo -e "  持续确认过滤器: 启用 (K线数=$CONFIRM_BARS_VALUE)"
        fi
        if [ $ENABLE_LOSS_PROTECTION_FLAG -eq 1 ]; then
            echo -e "  连续止损保护: 启用 (连续亏损次数=$MAX_LOSSES_VALUE, 暂停K线数=$PAUSE_BARS_VALUE)"
        fi
    fi
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    echo -e "${BLUE}激活conda环境并开始回测...${NC}"
    echo ""

    # 设置环境变量以减少进度条输出噪音
    export BACKTESTING_DISABLE_PROGRESS=true

    # 构建命令，根据是否有股票列表文件选择不同的股票参数
    if [ -n "$STOCK_LIST_VALUE" ]; then
        CMD=("$CONDA_PATH" "run" "-n" "$CONDA_ENV" "python" "$PYTHON_SCRIPT" "${STOCK_LIST_ARGS[@]}" "--strategy" "$STRATEGY")
    else
        CMD=("$CONDA_PATH" "run" "-n" "$CONDA_ENV" "python" "$PYTHON_SCRIPT" "--stock" "$STOCK" "--strategy" "$STRATEGY")
    fi

    if [ -n "$CATEGORY_VALUE" ]; then
        CMD+=("${CATEGORY_ARGS[@]}")
    fi
    if [ $OPTIMIZE_FLAG -eq 1 ]; then
        CMD+=("--optimize")
    fi
    if [ ${#COST_MODEL_ARGS[@]} -gt 0 ]; then
        CMD+=("${COST_MODEL_ARGS[@]}")
    fi
    if [ -n "$COMMISSION_VALUE" ]; then
        CMD+=("${COMMISSION_ARGS[@]}")
    fi
    if [ -n "$SPREAD_VALUE" ]; then
        CMD+=("${SPREAD_ARGS[@]}")
    fi
    if [ ${#CASH_ARGS[@]} -gt 0 ]; then
        CMD+=("${CASH_ARGS[@]}")
    fi
    if [ ${#OUTPUT_DIR_ARGS[@]} -gt 0 ]; then
        CMD+=("${OUTPUT_DIR_ARGS[@]}")
    fi
    if [ ${#DATA_DIR_ARGS[@]} -gt 0 ]; then
        CMD+=("${DATA_DIR_ARGS[@]}")
    fi
    if [ -n "$AGGREGATE_VALUE" ]; then
        CMD+=("${AGGREGATE_ARGS[@]}")
    fi
    if [ -n "$START_DATE_VALUE" ]; then
        CMD+=("${START_DATE_ARGS[@]}")
    fi
    if [ -n "$END_DATE_VALUE" ]; then
        CMD+=("${END_DATE_ARGS[@]}")
    fi
    if [ -n "$INSTRUMENT_LIMIT_VALUE" ]; then
        CMD+=("${INSTRUMENT_LIMIT_ARGS[@]}")
    fi
    if [ $VERBOSE_FLAG -eq 1 ]; then
        CMD+=("--verbose")
    fi
    if [ -n "$SAVE_PARAMS_VALUE" ]; then
        CMD+=("${SAVE_PARAMS_ARGS[@]}")
    fi

    # 添加过滤器开关参数
    if [ $ENABLE_ADX_FILTER_FLAG -eq 1 ]; then
        CMD+=("--enable-adx-filter")
    fi
    if [ $ENABLE_VOLUME_FILTER_FLAG -eq 1 ]; then
        CMD+=("--enable-volume-filter")
    fi
    if [ $ENABLE_SLOPE_FILTER_FLAG -eq 1 ]; then
        CMD+=("--enable-slope-filter")
    fi
    if [ $ENABLE_CONFIRM_FILTER_FLAG -eq 1 ]; then
        CMD+=("--enable-confirm-filter")
    fi
    if [ $ENABLE_LOSS_PROTECTION_FLAG -eq 1 ]; then
        CMD+=("--enable-loss-protection")
    fi

    # 添加过滤器配置参数
    if [ ${#ADX_THRESHOLD_ARGS[@]} -gt 0 ]; then
        CMD+=("${ADX_THRESHOLD_ARGS[@]}")
    fi
    if [ ${#ADX_PERIOD_ARGS[@]} -gt 0 ]; then
        CMD+=("${ADX_PERIOD_ARGS[@]}")
    fi
    if [ ${#VOLUME_RATIO_ARGS[@]} -gt 0 ]; then
        CMD+=("${VOLUME_RATIO_ARGS[@]}")
    fi
    if [ ${#VOLUME_PERIOD_ARGS[@]} -gt 0 ]; then
        CMD+=("${VOLUME_PERIOD_ARGS[@]}")
    fi
    if [ ${#SLOPE_LOOKBACK_ARGS[@]} -gt 0 ]; then
        CMD+=("${SLOPE_LOOKBACK_ARGS[@]}")
    fi
    if [ ${#CONFIRM_BARS_ARGS[@]} -gt 0 ]; then
        CMD+=("${CONFIRM_BARS_ARGS[@]}")
    fi
    if [ ${#MAX_LOSSES_ARGS[@]} -gt 0 ]; then
        CMD+=("${MAX_LOSSES_ARGS[@]}")
    fi
    if [ ${#PAUSE_BARS_ARGS[@]} -gt 0 ]; then
        CMD+=("${PAUSE_BARS_ARGS[@]}")
    fi

    echo -e "${YELLOW}执行命令:${NC} ${CMD[*]}"
    "${CMD[@]}"
    EXIT_CODE=$?

    # 检查执行结果
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        # 如果回测成功且未启用keep-negative标志，则删除负收益率的结果文件
        if [ $KEEP_NEGATIVE_FLAG -eq 0 ]; then
            echo -e "${BLUE}正在清理负收益率标的结果文件...${NC}"
            cleanup_negative_returns "$OUTPUT_DIR_VALUE"
        fi

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
