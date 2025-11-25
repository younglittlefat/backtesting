## 背景
现在已经通过回测选出最佳超参，需要在每天收盘后，获取最新的日线信息，算出第二天的信号，通过飞书的机器人api发送到我的群里，让我能收到信号进行手动交易

## 需求
1、参考README_BACKTESTING.md中没有注释的内容，生成一个shell脚本，供crontab每天定时调用，时间改为当前的时间点。脚本中需要打印关键信息，比如执行到哪一步，执行结果是什么，方便crontab时排查
2、完成脚本开发后，你需要亲自设置crontab，让它在一分钟后生效，来验证整个流程是否ok。你需要监控任务是否完成，并检查日志里是否符合预期
3、使用飞书机器人api，把持仓信息和调仓结果发出来

## 补充细节（根据现有命令）
1、数据获取：使用 README_BACKTESTING.md 中未注释的命令 `python scripts/fetch_tushare_data_v2.py --start_date <today> --end_date <today> --daily_data --basic_info --data_type etf` 拉取当天 ETF 日线（日期取当天）。
2、数据导出：导出最近两年日线到 `data/online_chinese_etf`，命令 `python scripts/export_mysql_to_csv.py --data_type etf --output_dir data/online_chinese_etf --export_daily --export_basic --start_date <today_minus_2_years> --end_date <today>`；导出前先删除 `data/online_chinese_etf` 目录，保证目录只包含最新数据。
3、信号生成（分析）：按 README 中未注释的 MACD 版本执行 `./generate_daily_signals.sh --analyze --strategy macd_cross --stock-list results/trend_etf_pool_2019_2021_optimized.csv --portfolio-file positions/etf_macd_cross_portfolio.json --load-params config/macd_strategy_params.json --data-dir data/chinese_etf/daily --end-date <today>`，生成最新一天的信号。
4、信号执行：随后执行 `./generate_daily_signals.sh --execute --strategy macd_cross --stock-list results/trend_etf_pool_2019_2021_optimized.csv --portfolio-file positions/etf_macd_cross_portfolio.json --load-params config/macd_strategy_params.json --data-dir data/chinese_etf/daily --end-date <today>`，完成调仓并记录操作。
5、日志与可观测性：脚本需逐步打印关键阶段（拉取、导出、分析、执行、发送飞书）及成功/失败信息，方便 crontab 场景排查。

## 进一步约束（飞书、Cron、日志）
1、飞书消息：内容需包含当日持仓列表与调仓指令，格式可复用 `generate_daily_signals` 输出；消息中必须带关键词“肥叔叔的交易”才能发送成功。
2、Cron 设置：东八区每天 19:00 运行，修改用户 `zijunliu` 的 crontab；脚本执行需激活 conda 环境 `backtesting`。
3、日志：所有日志统一输出到项目根目录下 `logs/` 目录（追加保存）。

## 相关文档
1、飞书发送参考代码：
import requests
import json
import datetime

# 1. 你的 Webhook 地址
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/9e035bdf-0d61-4620-98ea-b915168f3c24"  # 这个是真的url，可以直接使用

# 2. 定义发送函数
def send_feishu_text(content):
    headers = {"Content-Type": "application/json"}
    
    # 构建数据包
    data = {
        "msg_type": "text",
        "content": {
            # 这里的 text 里面必须包含你在飞书设置的【关键词】，比如 "交易"
            "text": content 
        }
    }
    
    try:
        # 发送 POST 请求
        response = requests.post(WEBHOOK_URL, headers=headers, json=data)
        result = response.json()
        
        # 检查飞书的返回码，0 代表成功
        if result.get("code") == 0:
            print(f"[{datetime.datetime.now()}] 消息发送成功")
        else:
            print(f"发送失败，错误信息: {result}")
            
    except Exception as e:
        print(f"网络请求出错: {e}")

# 3. 模拟量化系统发出信号
if __name__ == "__main__":
    # 假设这是你策略算出来的结果
    signal_msg = "【交易提醒】\n标的：螺纹钢主力 (RB2405)\n方向：多头开仓\n价格：3850\n时间：收盘后"
    
    send_feishu_text(signal_msg)

## 完成情况
- 已实现自动化脚本 `scripts/daily_cron_signals.sh`：按顺序执行“拉取当天ETF→清空并导出近两年数据→生成/执行MACD信号→精简飞书推送”，日志全量写入 `logs/`，推送包含关键词“肥叔叔的交易”且返回 code=0。
- 已配置 crontab（用户 zijunliu）每天东八区 19:00 触发；曾做过临时分钟级测试验证 end-to-end。
- 飞书推送已精简：仅包含时间、数据日/窗口、持仓概览、交易结论、必要备注和日志路径，避免长篇明细；完整明细仍保存在日志。
- 提供连通性测试脚本 `scripts/test_feishu_webhook.py`，可快速验证 Webhook。

