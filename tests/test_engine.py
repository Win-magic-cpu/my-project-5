import pytest

from shopmate.domain.messages import (
    BotMessage,
    MessageObject,
    MessageType,
    UserMessage,
)
from shopmate.domain.state import DialogueState
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.plan.models import (
    ChitchatTurnPlan,
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


class StubActionRunner:
    async def run(self, action_call, state):
        return ActionResult(
            slot_updates={
                "order_status": "已发货",
                "order_summary": "订单金额 ¥299.00。",
            }
        )


class FakePlanner:
    def __init__(self, plan: TurnPlan) -> None:
        self.plan = plan

    async def predict(self, state, user_message, flows, knowledge_intents):
        return self.plan


class StubKnowledgeHandler:
    knowledge_intents = KNOWLEDGE_INTENTS

    async def handle(self, intents, state, user_message):
        return [BotMessage(text="知识回复占位")]


class StubChitchatHandler:
    async def handle(self, state, user_message):
        return [BotMessage(text="你好，我是 ShopMate 电商助手。")]


class StubClarifyResponder:
    def __init__(self) -> None:
        self.reason = None

    async def respond(self, state, user_message, reason):
        self.reason = reason
        return [BotMessage(text="你想对这个对象做什么呢？")]


def build_engine(flows, plan: TurnPlan):
    task_handler = TaskHandler(
        command_processor=CommandProcessor(),
        flows=flows,
        flow_executor=FlowExecutor(
            action_runner=StubActionRunner(),
            response_renderer=ResponseRenderer(llm=None),
            condition_evaluator=ConditionEvaluator(),
        ),
        lifecycle_responder=TaskLifecycleResponder(flows=flows),
    )
    clarify = StubClarifyResponder()
    engine = DialogueEngine(
        turn_planner=FakePlanner(plan),
        task_handler=task_handler,
        knowledge_handler=StubKnowledgeHandler(),
        chitchat_handler=StubChitchatHandler(),
        clarify_responder=clarify,
        turn_plan_validator=TurnPlanValidator(),
    )
    return engine, clarify


def text_message(text: str, message_id: str = "m1") -> UserMessage:
    return UserMessage(
        sender_id="u1",
        message_id=message_id,
        type=MessageType.TEXT,
        text=text,
    )


@pytest.mark.asyncio
async def test_text_then_object_message_completes_flow(flows):
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[
                StartFlowCommand(
                    command="start_flow", flow="order_status_query"
                )
            ]
        )
    )
    engine, _ = build_engine(flows, plan)
    state = DialogueState(sender_id="u1")

    result = await engine.process_message(
        state, text_message("帮我查订单状态")
    )
    assert result.messages[-1].text == "请告诉我你的订单号。"
    assert state.shared.focused_object is None

    object_message = UserMessage(
        sender_id="u1",
        message_id="m2",
        type=MessageType.OBJECT,
        object=MessageObject(
            type="order",
            id="A20240315001",
            title="订单 A20240315001",
        ),
    )
    result = await engine.process_message(state, object_message)

    assert result.messages[-1].text == (
        "订单A20240315001当前状态是：已发货。订单金额 ¥299.00。"
    )
    assert state.shared.focused_object.id == "A20240315001"
    assert state.tasks.active is None
    assert len(state.shared.current_session.turns) == 2
    assert (
        state.shared.current_session.turns[1].bot_messages[-1].text
        == "订单A20240315001当前状态是：已发货。订单金额 ¥299.00。"
    )


@pytest.mark.asyncio
async def test_object_without_active_task_asks_for_intent(flows):
    plan = TurnPlan(chitchat=ChitchatTurnPlan())
    engine, clarify = build_engine(flows, plan)
    state = DialogueState(sender_id="u1")

    object_message = UserMessage(
        sender_id="u1",
        message_id="m2",
        type=MessageType.OBJECT,
        object=MessageObject(type="product", id="P1001"),
    )
    result = await engine.process_message(state, object_message)

    assert result.messages[0].text == "你想对这个对象做什么呢？"
    assert clarify.reason is not None
    assert clarify.reason.value == "object_requires_intent"
    assert state.shared.focused_object.type == "product"


@pytest.mark.asyncio
async def test_expired_session_is_reset(flows):
    plan = TurnPlan(chitchat=ChitchatTurnPlan())
    engine, _ = build_engine(flows, plan)
    state = DialogueState(sender_id="u1")

    await engine.process_message(state, text_message("你好"))
    old_session = state.shared.current_session
    assert old_session is not None
    old_session.last_activity_at -= 10_000

    await engine.process_message(state, text_message("还在吗", "m2"))

    assert len(state.shared.sessions) == 2
    assert state.shared.current_session is not old_session
    assert old_session.closed_at is not None
    assert len(state.shared.current_session.turns) == 1
    assert state.tasks.active is None
    assert state.shared.focused_object is None
