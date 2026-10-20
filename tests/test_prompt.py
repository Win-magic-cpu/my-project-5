import json

from langchain_core.prompts import PromptTemplate

from shopmate.domain.messages import MessageType, UserMessage
from shopmate.domain.state import DialogueState, FocusedObject
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.plan.turn_planner import TurnPlanner
from shopmate.prompts.prompt_loader import load_prompt


def build_inputs(flows):
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    state.shared.set_focused_object(
        FocusedObject(type="order", id="A20240315001")
    )
    user_message = UserMessage(
        sender_id="u1",
        message_id="m1",
        type=MessageType.TEXT,
        text="帮我查订单状态",
    )
    return TurnPlanner()._build_prompt_inputs(
        state,
        user_message,
        flows,
        KNOWLEDGE_INTENTS,
    )


def test_turn_plan_prompt_renders_with_all_variables(flows):
    inputs = build_inputs(flows)
    prompt = PromptTemplate.from_template(
        load_prompt("turn_plan"),
        template_format="jinja2",
    )

    rendered = prompt.format(**inputs)

    assert "<user_message>" in rendered
    assert "帮我查订单状态" in rendered
    assert "order_status_query" in rendered
    assert "refund_policy" in rendered


def test_turn_plan_inputs_are_valid_json(flows):
    inputs = build_inputs(flows)

    flows_payload = json.loads(inputs["flows_json"])
    assert {flow["id"] for flow in flows_payload} >= {
        "order_status_query",
        "human_handoff",
    }
    assert all("steps" not in flow for flow in flows_payload)
    assert all("slots" in flow for flow in flows_payload)

    task_state = json.loads(inputs["task_state_json"])
    assert task_state["active"] is None
    assert task_state["paused"] == []

    focused_object = json.loads(inputs["focused_object_json"])
    assert focused_object["id"] == "A20240315001"
    assert focused_object["type"] == "order"

    intents = json.loads(inputs["knowledge_intents_json"])
    assert {intent["id"] for intent in intents} >= {
        "product_info",
        "refund_policy",
    }
