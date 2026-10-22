import uuid
from contextvars import ContextVar, Token

_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    """生成一个短 trace_id（够用且方便贴日志）。"""
    return uuid.uuid4().hex[:16]


def current_trace_id() -> str:
    return _TRACE_ID.get()


def set_trace_id(trace_id: str) -> Token:
    return _TRACE_ID.set(trace_id)


def reset_trace_id(token: Token) -> None:
    _TRACE_ID.reset(token)
