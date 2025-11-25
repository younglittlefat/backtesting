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

# 3) 生成KAMA信号（分析模式）
run_step "生成KAMA交易信号（analyze）" \
    ./generate_daily_signals.sh --analyze \
    --strategy kama_cross \
    --stock-list results/trend_etf_pool_2019_2021_optimized.csv \
    --portfolio-file positions/etf_kama_cross_portfolio.json \
    --load-params config/kama_strategy_params.json \
    --data-dir data/chinese_etf/daily \
    --end-date "$TODAY"

# 4) 执行KAMA调仓（执行模式）
run_step "执行KAMA调仓（execute）" \
    ./generate_daily_signals.sh --execute \
    --strategy kama_cross \
    --stock-list results/trend_etf_pool_2019_2021_optimized.csv \
    --portfolio-file positions/etf_kama_cross_portfolio.json \
    --load-params config/kama_strategy_params.json \
    --data-dir data/chinese_etf/daily \
    --end-date "$TODAY"

# 5) 生成MACD信号（分析模式）
run_step "生成MACD交易信号（analyze）" \
    ./generate_daily_signals.sh --analyze \
    --strategy macd_cross \
    --stock-list results/trend_etf_pool_2019_2021_optimized.csv \
    --portfolio-file positions/etf_macd_cross_portfolio.json \
    --load-params config/macd_strategy_params.json \
    --data-dir data/chinese_etf/daily \
    --end-date "$TODAY"

# 6) 执行MACD调仓（执行模式）
run_step "执行MACD调仓（execute）" \
    ./generate_daily_signals.sh --execute \
    --strategy macd_cross \
    --stock-list results/trend_etf_pool_2019_2021_optimized.csv \
    --portfolio-file positions/etf_macd_cross_portfolio.json \
    --load-params config/macd_strategy_params.json \
    --data-dir data/chinese_etf/daily \
    --end-date "$TODAY"

# 7) 发送飞书通知（包含持仓与调仓摘要，必须带关键词“肥叔叔的交易”）
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
cash_line = find(r"可用现金:\s*([^\n]+)", "未知")
asset_line = find(r"总资产:\s*([^\n]+)", "")
hold_count = find(r"持仓明细\s*\((\d+/\d+)\)", "?/?")
buy_warn = find(r"(买入信号数量（[^）]+）[^\n]*)", "")
sell_count = find(r"卖出操作\s*\((\d+)\)", "0")
buy_count = find(r"买入操作\s*\((\d+)\)", "0")

no_trade = "✅ 无需交易" in content_clean
trade_desc = "无需交易" if no_trade else f"买入 {buy_count} 笔 / 卖出 {sell_count} 笔"

# 分策略买卖计数（提取每个策略最后一次日志块）
def extract_strategy_counts(strategy: str):
    matches = re.findall(rf"策略名称:\s*{strategy}(.*?)(?:\n策略名称:|\Z)", content_clean, re.S)
    if not matches:
        return None, None
    block = matches[-1]
    buy_m = re.search(r"买入操作\s*\((\d+)\)", block)
    sell_m = re.search(r"卖出操作\s*\((\d+)\)", block)
    buy = int(buy_m.group(1)) if buy_m else (0 if "✅ 无需交易" in block else None)
    sell = int(sell_m.group(1)) if sell_m else (0 if "✅ 无需交易" in block else None)
    return buy, sell

message_lines = [
    "【肥叔叔的交易】每日信号",
    f"时间: {today_str}",
    f"数据日: {latest_price}  看盘起始: {lookback_start}",
    f"持仓概览: {hold_count} 持仓，{asset_line or '总资产未知'}，现金 {cash_line}",
    f"今日交易: {trade_desc}",
]

if buy_warn:
    message_lines.append(f"备注: {buy_warn}")

# 附加策略分项
for strategy in ["kama_cross", "macd_cross"]:
    buy_cnt, sell_cnt = extract_strategy_counts(strategy)
    if buy_cnt is not None or sell_cnt is not None:
        message_lines.append(
            f"{strategy.upper()}: 买入 {buy_cnt if buy_cnt is not None else '?'} 笔 / "
            f"卖出 {sell_cnt if sell_cnt is not None else '?'} 笔 (详见日志)"
        )

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
