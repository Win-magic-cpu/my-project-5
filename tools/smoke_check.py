"""本地端到端验收脚本（需要 mock_llm + mock_commerce + API 都在运行）。

用法：
    uv run python tools/smoke_check.py
结果写入 data/smoke/result.json，便于查看中文内容。
"""

import json
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:18082"
OUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "smoke"
    / "result.json"
)


def chat(payload: dict) -> dict:
    response = httpx.post(f"{BASE}/api/chat", json=payload, timeout=60)
    return {"status": response.status_code, "body": response.json()}


def main() -> None:
    sender = "demo_user"
    results = []

    results.append(
        ("1. 发起查订单", chat({"sender_id": sender, "text": "帮我查一下订单状态", "message_id": "m1"}))
    )
    results.append(
        ("2. 补充订单号", chat({"sender_id": sender, "text": "A20240315001", "message_id": "m2"}))
    )
    results.append(
        ("3. 闲聊", chat({"sender_id": sender, "text": "你好", "message_id": "m3"}))
    )
    results.append(
        ("4. 知识检索", chat({"sender_id": sender, "text": "退款政策是什么", "message_id": "m4"}))
    )
    results.append(
        ("5. 转人工", chat({"sender_id": sender, "text": "帮我转人工", "message_id": "m5"}))
    )
    results.append(
        (
            "6. 商品对象",
            chat(
                {
                    "sender_id": sender,
                    "object": {
                        "type": "product",
                        "id": "P1001",
                        "title": "轻薄连帽防晒衣",
                    },
                    "message_id": "m6",
                }
            ),
        )
    )
    results.append(
        ("7. 相似推荐", chat({"sender_id": sender, "text": "推荐相似商品", "message_id": "m7"}))
    )
    history = httpx.get(
        f"{BASE}/api/chat/history", params={"sender_id": sender}, timeout=30
    )
    results.append(("8. 历史记录", {"status": history.status_code, "body": history.json()}))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for name, result in results:
        print(f"{name}: HTTP {result['status']}")


if __name__ == "__main__":
    main()
