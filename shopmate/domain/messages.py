from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(Enum):
    TEXT = "text"
    OBJECT = "object"


@dataclass
class MessageObject:
    """消息携带的结构化对象，例如用户从页面点选的订单或商品。"""

    type: str
    id: str
    title: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserMessage:
    sender_id: str
    message_id: str
    type: MessageType
    text: str | None = None
    object: MessageObject | None = None


@dataclass
class BotMessage:
    text: str | None = None
    object: MessageObject | None = None


@dataclass
class ProcessResult:
    sender_id: str
    message_id: str
    messages: list[BotMessage] = field(default_factory=list)
