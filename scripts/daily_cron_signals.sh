#!/usr/bin/env bash
# 每日自动获取数据、生成/执行信号并发送飞书通知
set -euo pipefail

# 时区与日期
export TZ="Asia/Shanghai"
TODAY=$(date +%Y%m%d)
START_TWO_YEARS_AGO=$(date -d "-2 years" +%Y%m%d)

# 路径与环境
CONDA_BIN="/home/zijunliu/miniforge3/condabin/conda"
CONDA_ENV="backtesting"
PYTHON_BIN="/home/zijunliu/miniforge3/envs/${CONDA_ENV}/bin/python"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
RUN_TS=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/daily_signals_${RUN_TS}.log"

# 日志重定向
exec > >(tee -a "$LOG_FILE") 2>&1

# 简易日志函数
log() {
    local level="$1"; shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
}

trap 'log ERROR "步骤失败，查看日志: $LOG_FILE"' ERR

log INFO "启动每日任务"
log INFO "项目目录: $PROJECT_ROOT"
log INFO "日志文件: $LOG_FILE"
log INFO "今日日期: $TODAY, 两年前起始: $START_TWO_YEARS_AGO"

# 运行并打标
run_step() {
    local desc="$1"; shift
    log INFO "开始: $desc"
    if "$@"; then
        log INFO "完成: $desc"
    else
        log ERROR "失败: $desc"
        return 1
    fi
}

cd "$PROJECT_ROOT"

# 1) 获取今日ETF日线
run_step "获取今日ETF日线" \
    "$CONDA_BIN" run -n "$CONDA_ENV" python scripts/fetch_tushare_data_v2.py \
    --start_date "$TODAY" --end_date "$TODAY" --daily_data --basic_info --data_type etf

# 2) 导出近两年ETF日线（先清空目录）
EXPORT_DIR="$PROJECT_ROOT/data/online_chinese_etf"
if [ -d "$EXPORT_DIR" ]; then
    log INFO "清理导出目录: $EXPORT_DIR"
    rm -rf "$EXPORT_DIR"
fi
mkdir -p "$EXPORT_DIR"

run_step "导出近两年ETF日线到 $EXPORT_DIR" \
    "$CONDA_BIN" run -n "$CONDA_ENV" python scripts/export_mysql_to_csv.py \
    --data_type etf --output_dir "$EXPORT_DIR" --export_daily --export_basic \
    --start_date "$START_TWO_YEARS_AGO" --end_date "$TODAY"

# 3) 执行KAMA调仓（执行模式）
run_step "执行KAMA调仓（execute）" \
    ./generate_daily_signals.sh --execute \
    --strategy kama_cross \
    --stock-list results/trend_etf_pool_2019_2021_optimized.csv \
    --portfolio-file positions/etf_kama_cross_portfolio.json \
    --load-params config/kama_strategy_params.json \
    --data-dir data/online_chinese_etf/daily \
    --end-date "$TODAY"

# 4) 执行MACD调仓（执行模式）
run_step "执行MACD调仓（execute）" \
    ./generate_daily_signals.sh --execute \
    --strategy macd_cross \
    --stock-list results/trend_etf_pool_2019_2021_optimized.csv \
    --portfolio-file positions/etf_macd_cross_portfolio.json \
    --load-params config/macd_strategy_params.json \
    --data-dir data/online_chinese_etf/daily \
    --end-date "$TODAY"

# 5) 发送飞书通知（包含持仓与调仓摘要，必须带关键词“肥叔叔的交易”）
FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/9e035bdf-0d61-4620-98ea-b915168f3c24"
log INFO "开始: 发送飞书通知"
export LOG_FILE FEISHU_WEBHOOK
LOG_FILE="$LOG_FILE" FEISHU_WEBHOOK="$FEISHU_WEBHOOK" \
cat <<'PY' | "$PYTHON_BIN" -
import json
import os
from datetime import datetime
from pathlib import Path
from urllib import request, error

log_path = Path(os.environ.get("LOG_FILE", ""))
webhook = os.environ.get("FEISHU_WEBHOOK", "")

def extract_section(text: str, title: str, max_lines: int = 40) -> str:
    """从日志中截取指定标题开始的若干行，默认取最后一次出现。"""
    idx = text.rfind(title)
    if idx == -1:
        return f"{title}: 未找到"
    snippet = text[idx:].splitlines()
    return "\n".join(snippet[:max_lines])

if not webhook:
    raise SystemExit("未配置 FEISHU_WEBHOOK")
if not log_path.exists():
    raise SystemExit(f"日志不存在: {log_path}")

content = log_path.read_text(encoding="utf-8", errors="ignore")
import re  # 需在使用前导入
# 去除ANSI颜色码，便于正则提取
content_clean = re.sub(r"\x1b\[[0-9;]*m", "", content)
today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S (Asia/Shanghai)")

def find(pattern: str, default: str = "") -> str:
    m = re.search(pattern, content_clean)
    return m.group(1).strip() if m else default

latest_price = find(r"最新价格日期:\s*([^\n]+)", "未知")
lookback_start = find(r"Lookback起始:\s*([^\n]+)", "未知")

# 提取策略执行块（execute模式的最后一次）
def extract_strategy_block(strategy: str) -> str:
    """提取指定策略的execute模式日志块"""
    # 策略名称到中文标识的映射
    strategy_cn_map = {
        "kama_cross": "KAMA",
        "macd_cross": "MACD",
        "sma_cross": "SMA",
        "sma_cross_enhanced": "SMA"
    }
    strategy_cn = strategy_cn_map.get(strategy, strategy.upper())
    # 匹配 "开始: 执行XXX调仓" 到 "执行完成！" 之间的内容
    pattern = rf"开始: 执行{strategy_cn}调仓(.*?)执行完成！"
    matches = re.findall(pattern, content_clean, re.S)
    return matches[-1] if matches else ""

def extract_portfolio_summary(block: str) -> dict:
    """从日志块中提取持仓概览信息"""
    def find_in_block(pattern: str, default: str = "") -> str:
        m = re.search(pattern, block)
        return m.group(1).strip() if m else default

    return {
        "hold_count": find_in_block(r"持仓明细\s*\((\d+/\d+)\)", "?/?"),
        "cash": find_in_block(r"可用现金:\s*([^\n]+)", "未知"),
        "total_asset": find_in_block(r"总资产:\s*([^\n]+)", "未知"),
        "market_value": find_in_block(r"持仓市值:\s*([^\n]+)", "¥0.00"),
        "pnl": find_in_block(r"持仓盈亏:\s*([^\n]+)", "+¥0.00"),
    }

def extract_trade_details(block: str, trade_type: str) -> list:
    """从日志块中提取交易详情列表"""
    trades = []
    # 使用多行匹配提取交易详情
    # 买入用"预计成本"，卖出用"预计收益"
    if trade_type == "买入":
        trade_pattern = r"\[(\d+)\]\s+(\d+\.\w+)\s*\n\s+操作:\s*买入\s*\n\s+价格:\s*([^\n]+)\s*\n\s+数量:\s*([^\n]+)\s*\n\s+预计成本:\s*([^\n]+)\s*\n\s+原因:\s*([^\n]+)"
    else:
        trade_pattern = r"\[(\d+)\]\s+(\d+\.\w+)\s*\n\s+操作:\s*卖出\s*\n\s+价格:\s*([^\n]+)\s*\n\s+数量:\s*([^\n]+)\s*\n\s+预计收益:\s*([^\n]+)\s*\n\s+原因:\s*([^\n]+)"

    for m in re.finditer(trade_pattern, block):
        trades.append({
            "idx": m.group(1),
            "code": m.group(2),
            "action": trade_type,
            "price": m.group(3).strip(),
            "quantity": m.group(4).strip(),
            "amount": m.group(5).strip(),
            "reason": m.group(6).strip()
        })
    return trades

def extract_executed_trades(block: str) -> list:
    """从幂等性检查的"已执行交易明细"中提取交易记录"""
    trades = []
    # 匹配格式: 🟢 买入 159825.SZ × 61100股 @ ¥0.818 = ¥49,989.80
    #          🔴 卖出 159825.SZ × 61100股 @ ¥0.818 = ¥49,989.80
    executed_pattern = r"([🟢🔴])\s*(买入|卖出)\s+(\d+\.\w+)\s*×\s*(\d+)股\s*@\s*¥([\d.]+)\s*=\s*¥([\d,.]+)"
    idx = 1
    for m in re.finditer(executed_pattern, block):
        icon, action, code, shares, price, amount = m.groups()
        trades.append({
            "idx": str(idx),
            "code": code,
            "action": action,
            "price": f"¥{price}",
            "quantity": f"{shares} 股",
            "amount": f"¥{amount}",
            "reason": "已执行"
        })
        idx += 1
    return trades

def format_trade_detail(trade: dict) -> str:
    """格式化单笔交易详情"""
    return (
        f"  [{trade['idx']}] {trade['code']}\n"
        f"      {trade['action']} | {trade['price']} | {trade['quantity']}\n"
        f"      金额: {trade['amount']}\n"
        f"      原因: {trade['reason']}"
    )

# 先提取所有策略的交易和持仓信息，再汇总统计
all_strategy_data = {}
for strategy in ["kama_cross", "macd_cross"]:
    block = extract_strategy_block(strategy)
    if block:
        buy_trades = extract_trade_details(block, "买入")
        sell_trades = extract_trade_details(block, "卖出")

        # 如果常规交易详情为空，尝试从"已执行交易明细"中提取（幂等性检查场景）
        if not buy_trades and not sell_trades:
            executed_trades = extract_executed_trades(block)
            for t in executed_trades:
                if t["action"] == "买入":
                    buy_trades.append(t)
                else:
                    sell_trades.append(t)

        all_strategy_data[strategy] = {
            "buy": buy_trades,
            "sell": sell_trades,
            "portfolio": extract_portfolio_summary(block)
        }

# 计算所有策略的总买入/卖出笔数
total_buy = sum(len(t["buy"]) for t in all_strategy_data.values())
total_sell = sum(len(t["sell"]) for t in all_strategy_data.values())
trade_desc = "无需交易" if (total_buy == 0 and total_sell == 0) else f"买入 {total_buy} 笔 / 卖出 {total_sell} 笔"

message_lines = [
    "【肥叔叔的交易】每日信号",
    f"时间: {today_str}",
    f"数据日: {latest_price}  看盘起始: {lookback_start}",
    f"今日交易: {trade_desc}",
]

# 附加每个策略的详细交易信息
for strategy in ["kama_cross", "macd_cross"]:
    if strategy not in all_strategy_data:
        continue

    data = all_strategy_data[strategy]
    buy_trades = data["buy"]
    sell_trades = data["sell"]
    portfolio = data["portfolio"]

    # 策略标题
    strategy_name = strategy.upper().replace("_", " ")
    message_lines.append(f"\n{'='*30}")
    message_lines.append(f"{strategy_name}")
    message_lines.append(f"{'='*30}")

    # 持仓概览
    message_lines.append(f"💼 {portfolio['hold_count']} 持仓 | 总资产 {portfolio['total_asset']} | 现金 {portfolio['cash']}")

    if sell_trades:
        message_lines.append(f"📉 卖出 ({len(sell_trades)}笔)")
        for t in sell_trades:
            message_lines.append(format_trade_detail(t))

    if buy_trades:
        message_lines.append(f"📈 买入 ({len(buy_trades)}笔)")
        for t in buy_trades:
            message_lines.append(format_trade_detail(t))

    if not buy_trades and not sell_trades:
        message_lines.append("✅ 无需交易")

message_lines.append(f"日志: {log_path}")
message = "\n".join(message_lines)

payload_obj = {
    "msg_type": "text",
    "content": {"text": message}
}
payload = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")

print("==== 飞书发送内容预览 ====")
print(message)
print("==== 结束 ====")

req = request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
try:
    with request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print(f"HTTP {resp.status}")
        print("响应体:", body)
        try:
            body_json = json.loads(body)
            if body_json.get("code") != 0:
                raise SystemExit(f"飞书返回非0 code: {body_json}")
        except json.JSONDecodeError:
            raise SystemExit(f"飞书返回非JSON: {body}")
except error.HTTPError as exc:
    print(f"HTTPError: {exc.code} {exc.reason}")
    print(exc.read().decode("utf-8", errors="replace"))
    raise SystemExit(1)
except Exception as exc:
    print(f"发送异常: {exc}")
    raise
PY
log INFO "完成: 发送飞书通知"

log INFO "全部步骤完成，日志: $LOG_FILE"
