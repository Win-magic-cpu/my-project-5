import pytest

from shopmate.domain.messages import MessageType, UserMessage
from shopmate.domain.state import DialogueState, FocusedObject
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


class StubActionRunner:
    """不访问网络的 ActionRunner，只为验证 Flow 推进逻辑。"""

    async def run(self, action_call, state):
        if action_call.action_name == "action_lookup_order_status":
            return ActionResult(
                slot_updates={
                    "order_status": "已发货",
                    "order_summary": "订单金额 ¥299.00。",
                }
            )
        if action_call.action_name == "action_lookup_logistics":
            return ActionResult(
                slot_updates={
                    "tracking_number": "SF1234567890",
                    "logistics_company": "顺丰速运",
                    "logistics_status": "快件正在运输中",
                }
            )
        if action_call.action_name == "action_recommend_similar_products":
            product_id = state.tasks.active.slots.get("product_id")
            return ActionResult(
                slot_updates={
                    "recommendation_summary": (
                        f"已为你准备 {product_id} 的相似商品"
                    )
                }
            )
        raise AssertionError(f"未预期的 Action: {action_call.action_name}")


def build_task_handler(flows) -> TaskHandler:
    return TaskHandler(
        command_processor=CommandProcessor(),
        flows=flows,
        flow_executor=FlowExecutor(
            action_runner=StubActionRunner(),
            response_renderer=ResponseRenderer(llm=None),
            condition_evaluator=ConditionEvaluator(),
        ),
        lifecycle_responder=TaskLifecycleResponder(flows=flows),
    )


def text_message(text: str = "帮我查订单") -> UserMessage:
    return UserMessage(
        sender_id="u1",
        message_id="m1",
        type=MessageType.TEXT,
        text=text,
    )


@pytest.mark.asyncio
async def test_order_status_query_needs_two_turns(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    handler = build_task_handler(flows)

    messages = await handler.handle(
        [StartFlowCommand(command="start_flow", flow="order_status_query")],
        state,
        text_message(),
    )
    assert messages[0].text == "好的，我们先处理订单状态查询。"
    assert messages[-1].text == "请告诉我你的订单号。"
    assert state.tasks.active is not None
    assert state.tasks.active.step_id == "ask_order_number"

    messages = await handler.handle(
        [
            SetSlotsCommand(
                command="set_slots",
                slots={"order_number": "A20240315001"},
            )
        ],
        state,
        text_message("A20240315001"),
    )
    assert len(messages) == 1
    assert messages[0].text == (
        "订单A20240315001当前状态是：已发货。订单金额 ¥299.00。"
    )
    assert state.tasks.active is None


@pytest.mark.asyncio
async def test_collect_validation_rejects_bad_order_number(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    handler = build_task_handler(flows)

    await handler.handle(
        [StartFlowCommand(command="start_flow", flow="order_status_query")],
        state,
        text_message(),
    )

    messages = await handler.handle(
        [
            SetSlotsCommand(
                command="set_slots",
                slots={"order_number": "abc"},
            )
        ],
        state,
        text_message("abc"),
    )
    assert messages[0].text == "订单号看起来不太对，请重新输入完整订单号。"
    assert state.tasks.active is not None
    assert "order_number" not in state.tasks.active.slots
    assert state.tasks.active.step_id == "ask_order_number"


@pytest.mark.asyncio
async def test_collect_step_uses_focused_object(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    state.shared.set_focused_object(
        FocusedObject(type="order", id="A20240315001")
    )
    handler = build_task_handler(flows)

    messages = await handler.handle(
        [StartFlowCommand(command="start_flow", flow="order_status_query")],
        state,
        text_message("查一下这个订单"),
    )
    assert messages[0].text == "好的，我们先处理订单状态查询。"
    assert messages[-1].text == (
        "订单A20240315001当前状态是：已发货。订单金额 ¥299.00。"
    )
    assert state.tasks.active is None


@pytest.mark.asyncio
async def test_switch_task_pauses_previous(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    handler = build_task_handler(flows)

    await handler.handle(
        [StartFlowCommand(command="start_flow", flow="order_status_query")],
        state,
        text_message(),
    )
    messages = await handler.handle(
        [StartFlowCommand(command="start_flow", flow="logistics_tracking")],
        state,
        text_message("查物流"),
    )
    assert messages[0].text == (
        "好的，我们先把订单状态查询放一放，先处理物流查询。"
    )
    assert len(state.tasks.paused) == 1
    assert state.tasks.active.flow_id == "logistics_tracking"


@pytest.mark.asyncio
async def test_human_handoff_returns_static_message(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    handler = build_task_handler(flows)

    messages = await handler.handle(
        [StartFlowCommand(command="start_flow", flow="human_handoff")],
        state,
        text_message("转人工"),
    )

    assert [message.text for message in messages] == [
        "好的，我们先处理人工客服。",
        "好的，我来为你转接人工客服，请稍等。",
    ]
    assert state.tasks.active is None


@pytest.mark.asyncio
async def test_similar_product_recommendation_uses_focused_product(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    state.shared.set_focused_object(
        FocusedObject(type="product", id="P1001")
    )
    handler = build_task_handler(flows)

    messages = await handler.handle(
        [
            StartFlowCommand(
                command="start_flow",
                flow="similar_product_recommendation",
            )
        ],
        state,
        text_message("推荐相似商品"),
    )

    # 有商品上下文时不应再追问商品编号
    assert [message.text for message in messages] == [
        "好的，我们先处理相似商品推荐。",
        "已为你准备 P1001 的相似商品",
    ]
    assert state.tasks.active is None
