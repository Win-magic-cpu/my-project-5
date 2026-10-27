import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shopmate.api.dependencies import get_dialogue_service
from shopmate.api.routers.chat_router import chat_router, format_sse
from shopmate.domain.messages import BotMessage, MessageType, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.domain.streaming import StreamEvent
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.plan.models import (
    KnowledgeTurnPlan,
    TaskTurnPlan,
    TurnPlan,
)
from shopmate.plan.validator import TurnPlanValidator
from shopmate.task.action.base import ActionResult
from shopmate.task.command.models import StartFlowCommand
from shopmate.task.command.processor import CommandProcessor
from shopmate.task.flow.conditions import ConditionEvaluator
from shopmate.task.flow.executor import FlowExecutor
from shopmate.task.handler import TaskHandler
from shopmate.task.lifecycle.responder import TaskLifecycleResponder
from shopmate.task.response.renderer import ResponseRenderer


class StubPlanner:
    def __init__(self, plan: TurnPlan) -> None:
        self.plan = plan

    async def predict(self, state, user_message, flows, knowledge_intents):
        return self.plan


class StubActionRunner:
    async def run(self, action_call, state):
        return ActionResult(
            slot_updates={"order_status": "已发货"}
        )


class StubKnowledgeResponder:
    async def stream(self, user_message, recent_turns, chunks):
        for piece in ("退款", "一般", "1-3 天"):
            yield piece

    async def respond(self, user_message, recent_turns, chunks):
        return [BotMessage(text="退款一般 1-3 天")]


class StubKnowledgeHandler:
    knowledge_intents = KNOWLEDGE_INTENTS

    def __init__(self) -> None:
        self.knowledge_responder = StubKnowledgeResponder()

    async def retrieve_chunks(self, intents, state, user_message):
        return []

    async def handle(self, intents, state, user_message):
        return [BotMessage(text="知识")]


class StubChitchatHandler:
    async def stream(self, state, user_message):
        for piece in ("你好", "呀"):
            yield piece

    async def handle(self, state, user_message):
        return [BotMessage(text="你好呀")]


class StubClarifyResponder:
    async def stream(self, state, user_message, reason):
        for piece in ("你是想", "办什么？"):
            yield piece

    async def respond(self, state, user_message, reason):
        return [BotMessage(text="你是想办什么？")]


def build_engine(flows, plan: TurnPlan) -> DialogueEngine:
    return DialogueEngine(
        turn_planner=StubPlanner(plan),
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


def text_message(text: str = "你好") -> UserMessage:
    return UserMessage(
        sender_id="u1",
        message_id="m1",
        type=MessageType.TEXT,
        text=text,
    )


async def collect(stream):
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_stream_knowledge_track_emits_tokens(flows):
    engine = build_engine(
        flows,
        TurnPlan(
            knowledge=KnowledgeTurnPlan(intents=["refund_policy"])
        ),
    )
    state = DialogueState(sender_id="u1")

    events = await collect(engine.stream_message(state, text_message()))

    assert events[0].type == "start"
    assert events[-1].type == "done"
    tokens = "".join(
        event.data["text"] for event in events if event.type == "token"
    )
    assert tokens == "退款一般1-3 天"
    assert events[-1].data["decision"] == "knowledge"

    turn = state.shared.current_session.turns[-1]
    assert turn.bot_messages[0].text == tokens


@pytest.mark.asyncio
async def test_stream_task_track_emits_messages(flows):
    engine = build_engine(
        flows,
        TurnPlan(
            task=TaskTurnPlan(
                commands=[
                    StartFlowCommand(
                        command="start_flow",
                        flow="order_status_query",
                    )
                ]
            )
        ),
    )
    state = DialogueState(sender_id="u1")

    events = await collect(engine.stream_message(state, text_message()))

    message_texts = [
        event.data["text"]
        for event in events
        if event.type == "message"
    ]
    assert message_texts == [
        "好的，我们先处理订单状态查询。",
        "请告诉我你的订单号。",
    ]
    assert events[-1].data["decision"] == "task"
    assert state.tasks.active is not None


@pytest.mark.asyncio
async def test_stream_clarify_track_emits_tokens(flows):
    engine = build_engine(flows, TurnPlan())
    state = DialogueState(sender_id="u1")

    events = await collect(engine.stream_message(state, text_message()))

    tokens = "".join(
        event.data["text"] for event in events if event.type == "token"
    )
    assert tokens == "你是想办什么？"
    assert events[-1].data["decision"] == "clarify"


def test_format_sse_frame():
    frame = format_sse(
        StreamEvent("token", {"text": "你好"})
    )

    assert frame == 'event: token\ndata: {"text": "你好"}\n\n'


def test_stream_endpoint_returns_event_stream():
    class StubService:
        async def stream_message(self, user_message):
            yield StreamEvent("start", {"trace_id": "t-1"})
            yield StreamEvent("token", {"text": "你"})
            yield StreamEvent(
                "done",
                {
                    "message_id": "m1",
                    "decision": "chitchat",
                    "total_ms": 1,
                    "messages": 1,
                },
            )

    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_dialogue_service] = lambda: StubService()

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"sender_id": "u1", "text": "你好"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert "event: start" in response.text
    assert "event: token" in response.text
    assert "event: done" in response.text
