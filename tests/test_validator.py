from shopmate.domain.state import DialogueState, FocusedObject
from shopmate.domain.task import TaskInstance
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.plan.models import (
    ClarifyReason,
    ChitchatTurnPlan,
    KnowledgeTurnPlan,
    TaskTurnPlan,
    TurnPlan,
)
from shopmate.plan.validator import TurnPlanValidator
from shopmate.task.command.models import (
    CancelTaskCommand,
    SetSlotsCommand,
    StartFlowCommand,
)


def empty_state() -> DialogueState:
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    return state


def test_missing_track(flows):
    result = TurnPlanValidator().validate(
        TurnPlan(),
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.MISSING_TRACK


def test_multiple_tracks(flows):
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[
                StartFlowCommand(
                    command="start_flow", flow="order_status_query"
                )
            ]
        ),
        knowledge=KnowledgeTurnPlan(intents=["refund_policy"]),
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.MULTIPLE_TRACKS


def test_valid_chitchat(flows):
    result = TurnPlanValidator().validate(
        TurnPlan(chitchat=ChitchatTurnPlan()),
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is True


def test_unknown_flow_rejected(flows):
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[StartFlowCommand(command="start_flow", flow="nope")]
        )
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.INVALID_TASK_COMMAND


def test_set_slots_requires_active_task(flows):
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[
                SetSlotsCommand(
                    command="set_slots",
                    slots={"order_number": "A1001"},
                )
            ]
        )
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.INVALID_TASK_COMMAND


def test_cancel_unknown_task_rejected(flows):
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[
                CancelTaskCommand(command="cancel_task", task_id="missing")
            ]
        )
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.INVALID_TASK_COMMAND


def test_knowledge_requires_focused_object(flows):
    plan = TurnPlan(
        knowledge=KnowledgeTurnPlan(intents=["product_info"])
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.MISSING_FOCUSED_OBJECT

    state = empty_state()
    state.shared.set_focused_object(
        FocusedObject(type="product", id="P1001")
    )
    result = TurnPlanValidator().validate(
        plan,
        state,
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is True


def test_unknown_intent_rejected(flows):
    plan = TurnPlan(
        knowledge=KnowledgeTurnPlan(intents=["unknown_intent"])
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.UNKNOWN_KNOWLEDGE_INTENT


def test_start_flow_then_set_slots_valid(flows):
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[
                StartFlowCommand(
                    command="start_flow", flow="order_status_query"
                ),
                SetSlotsCommand(
                    command="set_slots",
                    slots={"order_number": "A1001"},
                ),
            ]
        )
    )
    result = TurnPlanValidator().validate(
        plan,
        empty_state(),
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is True


def test_set_slots_with_unknown_slot_rejected(flows):
    state = empty_state()
    state.tasks.active = TaskInstance(
        flow_id="order_status_query",
        step_id="ask_order_number",
    )
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[
                SetSlotsCommand(
                    command="set_slots",
                    slots={"nickname": "小明"},
                )
            ]
        )
    )
    result = TurnPlanValidator().validate(
        plan,
        state,
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.INVALID_TASK_COMMAND


def test_set_slots_with_empty_slots_rejected(flows):
    state = empty_state()
    state.tasks.active = TaskInstance(
        flow_id="order_status_query",
        step_id="ask_order_number",
    )
    plan = TurnPlan(
        task=TaskTurnPlan(
            commands=[SetSlotsCommand(command="set_slots", slots={})]
        )
    )
    result = TurnPlanValidator().validate(
        plan,
        state,
        flows,
        KNOWLEDGE_INTENTS,
    )
    assert result.valid is False
    assert result.reason is ClarifyReason.INVALID_TASK_COMMAND
