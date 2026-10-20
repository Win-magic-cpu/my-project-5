from dataclasses import dataclass
from typing import Any


@dataclass
class Command:
    """Planning 输出的任务操作。"""

    command: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Command":
        command_class = COMMAND_NAME_TO_CLASS[data["command"]]
        return command_class(**data)


@dataclass
class StartFlowCommand(Command):
    flow: str


@dataclass
class SetSlotsCommand(Command):
    slots: dict[str, Any]


@dataclass
class CancelTaskCommand(Command):
    task_id: str


@dataclass
class ResumeTaskCommand(Command):
    task_id: str


COMMAND_NAME_TO_CLASS: dict[str, type[Command]] = {
    "start_flow": StartFlowCommand,
    "set_slots": SetSlotsCommand,
    "cancel_task": CancelTaskCommand,
    "resume_task": ResumeTaskCommand,
}
