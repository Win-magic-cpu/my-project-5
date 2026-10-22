import asyncio
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from shopmate.api.dependencies import get_db, get_engine
from shopmate.api.errors import register_exception_handlers
from shopmate.api.middleware import register_trace_middleware
from shopmate.api.routers.chat_router import chat_router
from shopmate.api.routers.health_router import health_router
from shopmate.domain.messages import BotMessage
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.models.base import Base
from shopmate.models.dialogue_state import DialogueStateRecord  # noqa: F401
from shopmate.plan.models import (
    ChitchatTurnPlan,
    TaskTurnPlan,
    TurnPlan,
)
from shopmate.plan.validator import TurnPlanValidator
from shopmate.task.action.base import ActionResult
from shopmate.task.command.models import (
    SetSlotsCommand,
    StartFlowCommand,
)
from shopmate.task.command.processor import CommandProcessor
from shopmate.task.flow.conditions import ConditionEvaluator
from shopmate.task.flow.executor import FlowExecutor
from shopmate.task.handler import TaskHandler
from shopmate.task.lifecycle.responder import TaskLifecycleResponder
from shopmate.task.response.renderer import ResponseRenderer

TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class StubActionRunner:
    async def run(self, action_call, state):
        return ActionResult(
            slot_updates={
                "order_status": "已发货",
                "order_summary": "订单金额 ¥299.00。",
            }
        )


class ScriptedPlanner:
    """按用户输入返回固定计划，替代真实 LLM。"""

    async def predict(self, state, user_message, flows, knowledge_intents):
        text = (user_message.text or "").strip()
        if text == "帮我查订单状态":
            return TurnPlan(
                task=TaskTurnPlan(
                    commands=[
                        StartFlowCommand(
                            command="start_flow",
                            flow="order_status_query",
                        )
                    ]
                )
            )
        if text in {"你好", "在吗"}:
            return TurnPlan(chitchat=ChitchatTurnPlan())
        return TurnPlan(
            task=TaskTurnPlan(
                commands=[
                    SetSlotsCommand(
                        command="set_slots",
                        slots={"order_number": text},
                    )
                ]
            )
        )


class StubKnowledgeHandler:
    knowledge_intents = KNOWLEDGE_INTENTS

    async def handle(self, intents, state, user_message):
        return [BotMessage(text="知识回复占位")]


class StubChitchatHandler:
    async def handle(self, state, user_message):
        return [BotMessage(text="你好，我是 ShopMate 电商助手。")]


class StubClarifyResponder:
    async def respond(self, state, user_message, reason):
        return [BotMessage(text="你想对这个对象做什么呢？")]


def build_engine(flows) -> DialogueEngine:
    return DialogueEngine(
        turn_planner=ScriptedPlanner(),
        task_handler=TaskHandler(
            command_processor=CommandProcessor(),
            flows=flows,
            flow_executor=FlowExecutor(
                action_runner=StubActionRunner(),
                response_renderer=ResponseRenderer(llm=None),
                condition_evaluator=ConditionEvaluator(),
            ),
            lifecycle_responder=TaskLifecycleResponder(flows=flows),
        ),
        knowledge_handler=StubKnowledgeHandler(),
        chitchat_handler=StubChitchatHandler(),
        clarify_responder=StubClarifyResponder(),
        turn_plan_validator=TurnPlanValidator(),
    )


async def _create_tables(database_url: str):
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture
def client(flows):
    work_dir = TMP_ROOT / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+aiosqlite:///{work_dir / 'api.db'}"
    asyncio.run(_create_tables(database_url))

    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    dialogue_engine = build_engine(flows)

    app = FastAPI()
    register_exception_handlers(app)
    register_trace_middleware(app)
    app.include_router(chat_router)
    app.include_router(health_router)

    async def override_engine():
        return dialogue_engine

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_engine] = override_engine
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(engine.dispose())
    shutil.rmtree(work_dir, ignore_errors=True)


def test_chat_text_flow_and_history(client):
    first = client.post(
        "/api/chat",
        json={
            "sender_id": "u1",
            "text": "帮我查订单状态",
            "message_id": "msg_001",
        },
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["sender_id"] == "u1"
    assert payload["message_id"] == "msg_001"
    assert [message["text"] for message in payload["messages"]] == [
        "好的，我们先处理订单状态查询。",
        "请告诉我你的订单号。",
    ]

    second = client.post(
        "/api/chat",
        json={"sender_id": "u1", "text": "A20240315001"},
    )
    assert second.status_code == 200
    assert second.json()["messages"][0]["text"] == (
        "订单A20240315001当前状态是：已发货。订单金额 ¥299.00。"
    )

    history = client.get(
        "/api/chat/history", params={"sender_id": "u1"}
    )
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == [
        "user",
        "bot",
        "bot",
        "user",
        "bot",
    ]
    assert messages[0]["text"] == "帮我查订单状态"
    assert messages[-1]["text"] == (
        "订单A20240315001当前状态是：已发货。订单金额 ¥299.00。"
    )


def test_chat_rejects_both_text_and_object(client):
    response = client.post(
        "/api/chat",
        json={
            "sender_id": "u1",
            "text": "你好",
            "object": {"type": "order", "id": "A1"},
        },
    )
    assert response.status_code == 422


def test_chat_rejects_blank_text(client):
    response = client.post(
        "/api/chat",
        json={"sender_id": "u1", "text": "   "},
    )
    assert response.status_code == 422


def test_object_message_persists_focused_object(client):
    response = client.post(
        "/api/chat",
        json={
            "sender_id": "u2",
            "object": {
                "type": "order",
                "id": "A20240315001",
                "title": "订单 A20240315001",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["messages"][0]["text"] == (
        "你想对这个对象做什么呢？"
    )

    history = client.get(
        "/api/chat/history", params={"sender_id": "u2"}
    )
    messages = history.json()["messages"]
    assert messages[0]["role"] == "user"
    assert messages[0]["object"]["id"] == "A20240315001"


def test_duplicate_message_id_is_idempotent(client):
    payload = {
        "sender_id": "u9",
        "text": "帮我查订单状态",
        "message_id": "dup-001",
    }

    first = client.post("/api/chat", json=payload)
    second = client.post("/api/chat", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["messages"] == second.json()["messages"]

    history = client.get(
        "/api/chat/history", params={"sender_id": "u9"}
    ).json()
    # 只记录一轮：1 条用户消息 + 2 条机器人回复
    assert len(history["messages"]) == 3


def test_history_pagination(client):
    for index in range(3):
        response = client.post(
            "/api/chat",
            json={
                "sender_id": "p1",
                "text": "你好",
                "message_id": f"p{index}",
            },
        )
        assert response.status_code == 200

    first_page = client.get(
        "/api/chat/history",
        params={"sender_id": "p1", "limit": 2, "offset": 0},
    ).json()
    assert first_page["total"] == 6
    assert len(first_page["messages"]) == 2
    assert first_page["has_more"] is True
    assert first_page["limit"] == 2
    assert first_page["offset"] == 0

    last_page = client.get(
        "/api/chat/history",
        params={"sender_id": "p1", "limit": 2, "offset": 4},
    ).json()
    assert len(last_page["messages"]) == 2
    assert last_page["has_more"] is False

    beyond = client.get(
        "/api/chat/history",
        params={"sender_id": "p1", "limit": 2, "offset": 99},
    ).json()
    assert beyond["messages"] == []
    assert beyond["has_more"] is False


def test_history_rejects_invalid_pagination(client):
    response = client.get(
        "/api/chat/history",
        params={"sender_id": "p1", "limit": 0},
    )
    assert response.status_code == 422

    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"]
    assert body["trace_id"] == response.headers["X-Trace-Id"]


def test_health_endpoints(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/healthz").status_code == 200


def test_validation_error_uses_unified_envelope(client):
    response = client.post("/api/chat", json={"sender_id": "u1"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"]
    assert body["trace_id"] == response.headers["X-Trace-Id"]
