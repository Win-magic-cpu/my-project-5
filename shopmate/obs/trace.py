import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator

from shopmate.obs.metrics import record_turn

logger = logging.getLogger("shopmate.turn")


@dataclass
class TurnTrace:
    """一轮对话的耗时画像。"""

    trace_id: str
    sender_id: str
    message_id: str
    decision: str | None = None
    stages: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)

    def record(self, stage_name: str, duration_ms: float) -> None:
        # 同名阶段累加，例如一次请求里调了两次 LLM
        self.stages[stage_name] = round(
            self.stages.get(stage_name, 0.0) + duration_ms, 2
        )

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 2)

    def to_log(self) -> dict:
        return {
            "event": "turn.completed",
            "trace_id": self.trace_id,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "decision": self.decision or "unknown",
            "stages": self.stages,
            "total_ms": self.total_ms,
        }


_TRACE: ContextVar[TurnTrace | None] = ContextVar(
    "turn_trace", default=None
)


def start_trace(
    trace_id: str,
    sender_id: str,
    message_id: str,
) -> TurnTrace:
    trace = TurnTrace(
        trace_id=trace_id,
        sender_id=sender_id,
        message_id=message_id,
    )
    _TRACE.set(trace)
    return trace


def current_trace() -> TurnTrace | None:
    return _TRACE.get()


def mark_decision(decision: str) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace.decision = decision


@contextmanager
def stage(name: str) -> Iterator[None]:
    """给一段代码计时；没有活动 trace 时是空操作。"""
    started = time.perf_counter()
    try:
        yield
    finally:
        trace = _TRACE.get()
        if trace is not None:
            trace.record(name, (time.perf_counter() - started) * 1000)


def finish_trace() -> TurnTrace | None:
    trace = _TRACE.get()
    if trace is None:
        return None

    payload = trace.to_log()
    logger.info("turn completed", extra=payload)
    record_turn(
        decision=payload["decision"],
        total_ms=trace.total_ms,
        stages=trace.stages,
    )
    _TRACE.set(None)
    return trace
