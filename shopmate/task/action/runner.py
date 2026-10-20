from dataclasses import dataclass, field
from typing import Any

from shopmate.domain.state import DialogueState
from shopmate.task.action.base import ActionResult
from shopmate.task.action.registry import ActionRegistry


@dataclass
class ActionCall:
    """对某个 Action 发起的一次调用。"""

    action_name: str
    action_kwargs: dict[str, Any] = field(default_factory=dict)


class ActionRunner:
    """按名称从注册表取 Action 并执行。"""

    def __init__(self, registry: ActionRegistry) -> None:
        self.registry = registry

    async def run(
        self,
        action_call: ActionCall,
        state: DialogueState,
    ) -> ActionResult:
        action = self.registry.get(action_call.action_name)
        return await action.run(state, action_call.action_kwargs)
