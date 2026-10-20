"""模拟 OpenAI 兼容接口的大模型服务（离线演示 / 端到端验收用）。

它不认识自然语言，只是按提示词里的关键词返回确定性结果：
- 规划提示词（TurnPlan）-> 返回一个合法的 TurnPlan JSON
- 知识/闲聊/澄清提示词 -> 返回一段固定中文回复

启动：
    uv run python tools/mock_llm/main.py      # 监听 18083

配合 .env：
    LLM_BASE_URL=http://127.0.0.1:18083/v1
    LLM_API_KEY=mock
    LLM_MODEL=mock
"""

import json
import re

from fastapi import FastAPI, Request

app = FastAPI(title="模拟大模型服务", version="0.1.0")

ORDER_NUMBER = re.compile(r"^[A-Za-z]\d{6,}$")
PLAN_USER_MESSAGE = re.compile(
    r"<user_message>\s*(.+?)\s*</user_message>", re.S
)
LEGACY_USER_MESSAGE = re.compile(r'"""(.+?)"""', re.S)


def _extract_user_message(prompt: str) -> str:
    match = PLAN_USER_MESSAGE.search(prompt)
    if match:
        return match.group(1)
    match = LEGACY_USER_MESSAGE.search(prompt)
    return match.group(1) if match else ""


def _turn_plan_for(text: str) -> dict:
    stripped = text.strip()

    if ORDER_NUMBER.match(stripped):
        return {
            "task": {
                "commands": [
                    {
                        "command": "set_slots",
                        "slots": {"order_number": stripped},
                    }
                ]
            },
            "knowledge": None,
            "chitchat": None,
        }

    def start(flow: str) -> dict:
        return {
            "task": {
                "commands": [
                    {"command": "start_flow", "flow": flow}
                ]
            },
            "knowledge": None,
            "chitchat": None,
        }

    if "物流" in stripped or "快递" in stripped:
        return start("logistics_tracking")
    if "人工" in stripped or "转接" in stripped:
        return start("human_handoff")
    if "订单" in stripped or "查单" in stripped:
        return start("order_status_query")
    if "退款" in stripped and ("申请" in stripped or "我要退" in stripped):
        return start("refund_request")
    if "推荐" in stripped or "相似" in stripped:
        return start("similar_product_recommendation")

    intents = []
    if "退款" in stripped:
        intents.append("refund_policy")
    if "退货" in stripped:
        intents.append("return_policy")
    if "发货" in stripped or "包邮" in stripped or "配送" in stripped:
        intents.append("shipping_policy")
    if "规则" in stripped:
        intents.append("platform_rule")
    if intents:
        return {
            "task": None,
            "knowledge": {"intents": intents},
            "chitchat": None,
        }

    return {"task": None, "knowledge": None, "chitchat": {}}


def _reply_for(prompt: str) -> str:
    if "## 判断顺序" in prompt or "你的 TurnPlan" in prompt:
        user_text = _extract_user_message(prompt)
        return json.dumps(
            _turn_plan_for(user_text), ensure_ascii=False
        )

    if "建议回复" in prompt:
        match = re.search(r"建议回复：(.+)", prompt)
        return match.group(1).strip() if match else "请再说得具体一些。"

    if "已知信息" in prompt or "与用户问题相关的" in prompt:
        return (
            "（模拟模型）根据检索到的资料：支持 7 天无理由退货，"
            "质量问题由商家承担运费；退款一般 1-3 个工作日原路退回。"
        )

    return "你好，我是 ShopMate 电商助手，可以查订单、查物流、咨询商品或申请退款。"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    body = await request.json()
    messages = body.get("messages", [])
    prompt = "\n".join(
        str(message.get("content", "")) for message in messages
    )
    content = _reply_for(prompt)

    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 0,
        "model": body.get("model", "mock"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=18083)
