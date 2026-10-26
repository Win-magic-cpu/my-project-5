import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shopmate.api.routers.metrics_router import metrics_router
from shopmate.domain.messages import BotMessage, MessageType, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.obs.logging import JsonFormatter, TraceContextFilter
from shopmate.obs.metrics import REGISTRY
from shopmate.obs.trace import (
    finish_trace,
    mark_decision,
    stage,
    start_trace,
)
from shopmate.plan.models import ChitchatTurnPlan, TurnPlan
from shopmate.plan.validator import TurnPlanValidator


@pytest.fixture(autouse=True)
def _clean_metrics():
    REGISTRY.reset()
    yield
    REGISTRY.reset()


def test_stage_records_duration():
    trace = start_trace("t-1", "u1", "m1")

    with stage("plan"):
        pass
    with stage("plan"):
        pass

    assert "plan" in trace.stages
    # 同名阶段累加
    assert trace.stages["plan"] >= 0
    finish_trace()


def test_finish_trace_logs_and_records_metrics(caplog):
    caplog.set_level(logging.INFO, logger="shopmate.turn")
    start_trace("t-2", "u1", "m1")
    mark_decision("task")
    with stage("plan"):
        pass

    trace = finish_trace()

    assert trace is not None
    assert trace.total_ms >= 0
    assert trace.decision == "task"

    record = next(
        item for item in caplog.records if item.name == "shopmate.turn"
    )
    assert record.event == "turn.completed"
    assert record.decision == "task"
    assert record.trace_id == "t-2"

    counter = REGISTRY.counters["shopmate_turns_total"]
    assert counter.value({"decision": "task"}) == 1


def test_metrics_text_format():
    REGISTRY.counter("demo_total", "示例计数").inc({"kind": "a"})
    REGISTRY.histogram("demo_seconds", "示例耗时").observe(
        0.2, {"stage": "plan"}
    )

    text = REGISTRY.render()

    assert "# TYPE demo_total counter" in text
    assert 'demo_total{kind="a"} 1' in text
    assert "# TYPE demo_seconds histogram" in text
    assert 'demo_seconds_bucket{stage="plan",le="0.25"} 1' in text
    assert 'demo_seconds_bucket{stage="plan",le="+Inf"} 1' in text
    assert 'demo_seconds_count{stage="plan"} 1' in text
    assert "demo_seconds_sum{stage=\"plan\"} 0.2" in text


def test_json_formatter_includes_trace_id():
    record = logging.LogRecord(
        name="shopmate.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    TraceContextFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert "trace_id" in payload


class StubPlanner:
    async def predict(self, state, user_message, flows, knowledge_intents):
        return TurnPlan(chitchat=ChitchatTurnPlan())


class StubTaskHandler:
    flows = None


class StubKnowledgeHandler:
    knowledge_intents = KNOWLEDGE_INTENTS

    async def handle(self, intents, state, user_message):
        return [BotMessage(text="知识")]


class StubChitchatHandler:
    async def handle(self, state, user_message):
        return [BotMessage(text="你好")]


class StubClarifyResponder:
    async def respond(self, state, user_message, reason):
        return [BotMessage(text="澄清")]


@pytest.mark.asyncio
async def test_engine_records_stages_and_decision():
    engine = DialogueEngine(
        turn_planner=StubPlanner(),
        task_handler=StubTaskHandler(),
        knowledge_handler=StubKnowledgeHandler(),
        chitchat_handler=StubChitchatHandler(),
        clarify_responder=StubClarifyResponder(),
        turn_plan_validator=TurnPlanValidator(),
    )
    state = DialogueState(sender_id="u1")
    message = UserMessage(
        sender_id="u1",
        message_id="m1",
        type=MessageType.TEXT,
        text="你好",
    )

    await engine.process_message(state, message)

    counter = REGISTRY.counters["shopmate_turns_total"]
    assert counter.value({"decision": "chitchat"}) == 1

    stage_histogram = REGISTRY.histograms[
        "shopmate_stage_duration_seconds"
    ]
    labels = {
        key.strip("{}").split("=")[1].strip('"')
        for key in stage_histogram.counts
    }
    assert {"plan", "validate", "handle_text"} <= labels


def test_metrics_endpoint_returns_prometheus_text():
    REGISTRY.counter("shopmate_demo_total", "示例").inc()

    app = FastAPI()
    app.include_router(metrics_router)

    response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert "shopmate_demo_total" in response.text
    assert response.headers["content-type"].startswith("text/plain")
