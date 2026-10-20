from shopmate.task.action.base import Action


class ActionRegistry:
    """按 Action 名称保存实例。"""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}

    def register(self, action: Action) -> None:
        self._actions[action.name] = action

    def get(self, name: str) -> Action:
        return self._actions[name]

    @property
    def names(self) -> list[str]:
        return sorted(self._actions)
