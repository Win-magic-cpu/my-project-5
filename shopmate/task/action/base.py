from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from shopmate.domain.state import DialogueState


@dataclass
class ActionResult:
    """Action 执行结果：需要写回当前任务的 Slot。"""

    slot_updates: dict[str, Any] = field(default_factory=dict)


class Action(ABC):
    """自定义业务 Action 的统一接口。"""

    name: str

    @abstractmethod
    async def run(
        self,
        state: DialogueState,
        action_kwargs: dict[str, Any],
    ) -> ActionResult:
        pass
