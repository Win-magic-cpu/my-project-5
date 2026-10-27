from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal["start", "token", "message", "done", "error"]


@dataclass
class StreamEvent:
    """SSE 事件：前端按 type 分支处理。"""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
