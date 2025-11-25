#!/usr/bin/env python
"""
飞书机器人连通性快速测试脚本

用法:
  python scripts/test_feishu_webhook.py --webhook <url> [--text "自定义文本"]
若不传 --webhook，则使用默认的真实 Webhook（来自需求文档）。
"""

import argparse
import json
import datetime
import sys
import textwrap
from urllib import request


DEFAULT_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/9e035bdf-0d61-4620-98ea-b915168f3c24"


def send(webhook: str, text: str) -> None:
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print("=== 即将发送的消息 ===")
    print(textwrap.indent(text, "  "))
    print("====================")
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"HTTP {resp.status}")
            print("响应体:", body)
    except Exception as exc:
        print("发送失败:", exc)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="飞书机器人测试")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK, help="飞书Webhook地址")
    parser.add_argument(
        "--text",
        help="自定义文本（需包含关键词“肥叔叔的交易”）",
    )
    args = parser.parse_args()

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S (Asia/Shanghai)")
    sample_text = textwrap.dedent(
        f"""
        【肥叔叔的交易】连通性测试
        时间: {now}
        持仓:
          - 无持仓
        调仓指令:
          - 今日无交易（测试消息）
        """
    ).strip()

    text = args.text.strip() if args.text else sample_text
    if "肥叔叔的交易" not in text:
        text = "【肥叔叔的交易】\n" + text

    send(args.webhook, text)


if __name__ == "__main__":
    main()
