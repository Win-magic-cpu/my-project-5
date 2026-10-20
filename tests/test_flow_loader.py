from shopmate.task.flow.links import (
    ConditionalLink,
    FallbackLink,
    StaticLink,
)
from shopmate.task.flow.steps import (
    ActionFlowStep,
    CollectSlotStep,
    FlowStep,
    ResponseFlowStep,
    StartFlowStep,
)


def test_load_all_flows(flows):
    assert set(flows.flows) == {
        "onboarding",
        "order_status_query",
        "logistics_tracking",
        "refund_request",
        "similar_product_recommendation",
        "human_handoff",
    }
    assert "order_number" in flows.slots
    assert flows.get_flow("order_status_query").name == "订单状态查询"
    assert flows.get_flow("human_handoff").name == "人工客服"


def test_flow_steps_parsed(flows):
    flow = flows.get_flow("order_status_query")
    assert flow.get_start_step().id == "start"
    assert [step.id for step in flow.steps] == [
        "start",
        "ask_order_number",
        "lookup_order_status",
        "show_order_status",
        "end",
    ]

    ask_step = flow.get_step("ask_order_number")
    assert isinstance(ask_step, CollectSlotStep)
    assert ask_step.slot_name == "order_number"
    assert ask_step.validation is not None
    assert ask_step.template.text == "请告诉我你的订单号。"

    action_step = flow.get_step("lookup_order_status")
    assert isinstance(action_step, ActionFlowStep)
    assert action_step.action == "action_lookup_order_status"

    assert isinstance(flow.get_step("start"), StartFlowStep)


def test_flow_slots_are_linked(flows):
    flow = flows.get_flow("refund_request")
    assert [slot.name for slot in flow.slots] == [
        "order_number",
        "refund_reason",
    ]


def test_build_links_supports_conditions():
    assert FlowStep.build_links("next_step") == [
        StaticLink(target="next_step")
    ]

    links = FlowStep.build_links(
        [
            {"if": "slots.get('product_id')", "then": "recommend"},
            {"else": "ask_product"},
        ]
    )
    assert isinstance(links[0], ConditionalLink)
    assert links[0].target == "recommend"
    assert links[0].condition == "slots.get('product_id')"
    assert isinstance(links[1], FallbackLink)
    assert links[1].target == "ask_product"


def test_conditional_start_step(flows):
    flow = flows.get_flow("similar_product_recommendation")
    start = flow.get_start_step()

    assert len(start.next) == 2
    assert isinstance(start.next[0], ConditionalLink)
    assert start.next[0].target == "respond"
    assert isinstance(start.next[1], FallbackLink)
    assert start.next[1].target == "ask_product_id"


def test_onboarding_and_handoff_use_static_templates(flows):
    expected = {
        "onboarding": (
            "你好，这里是 ShopMate 电商助手。"
            "我可以帮你查订单状态、查物流、了解商品信息，或者提交退款申请。"
        ),
        "human_handoff": "好的，我来为你转接人工客服，请稍等。",
    }

    for flow_id, text in expected.items():
        flow = flows.get_flow(flow_id)
        response_step = flow.get_step("respond")
        assert isinstance(response_step, ResponseFlowStep)
        assert response_step.template.text == text
        assert response_step.template.mode.value == "static"
