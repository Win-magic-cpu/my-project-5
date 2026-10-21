import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.task import TaskState


@dataclass
class FocusedObject:
    """当前聚焦的业务对象（订单 / 商品）。"""

    type: str
    id: str
    title: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Turn:
    """一次用户输入 + 由它产生的全部客服回复。"""

    turn_id: str
    user_message: UserMessage
    bot_messages: list[BotMessage] = field(default_factory=list)

    @classmethod
    def create(cls, user_message: UserMessage) -> "Turn":
        return cls(
            turn_id=str(uuid.uuid4()),
            user_message=user_message,
            bot_messages=[],
        )


@dataclass
class Session:
    """一段连续的对话。"""

    session_id: str
    started_at: float
    last_activity_at: float
    closed_at: float | None = None
    turns: list[Turn] = field(default_factory=list)

    @classmethod
    def create(cls) -> "Session":
        now = time.time()
        return cls(
            session_id=str(uuid.uuid4()),
            started_at=now,
            last_activity_at=now,
        )

    def append_turn(self, turn: Turn) -> None:
        self.turns.append(turn)
        self.last_activity_at = time.time()

    def close(self) -> None:
        self.closed_at = time.time()


@dataclass
class SharedState:
    """三种对话轨道共用的全局状态。"""

    focused_object: FocusedObject | None = None
    sessions: list[Session] = field(default_factory=list)

    @property
    def current_session(self) -> Session | None:
        if not self.sessions:
            return None
        return self.sessions[-1]

    def start_session(self) -> Session:
        session = Session.create()
        self.sessions.append(session)
        return session

    def close_current_session(self) -> None:
        session = self.current_session
        if session is not None:
            session.close()

    def set_focused_object(self, focused_object: FocusedObject) -> None:
        self.focused_object = focused_object

    def clear_focus(self) -> None:
        self.focused_object = None

    def append_turn(self, turn: Turn) -> None:
        session = self.current_session
        if session is None:
            raise RuntimeError(
                "Cannot append a turn without an active session."
            )
        session.append_turn(turn)


@dataclass
class DialogueState:
    """某个用户的完整对话状态。"""

    sender_id: str
    shared: SharedState = field(default_factory=SharedState)
    tasks: TaskState = field(default_factory=TaskState)
    # 最近处理过的消息 ID，用于识别客户端重试（幂等窗口）
    recent_message_ids: list[str] = field(default_factory=list)

    def reset_runtime_state_for_new_session(self) -> None:
        """会话超时后清理只对旧会话有效的运行状态。"""
        self.tasks.reset()
        self.shared.clear_focus()
