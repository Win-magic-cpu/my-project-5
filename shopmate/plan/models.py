from dataclasses import dataclass, field
from enum import Enum

from shopmate.task.command.models import Command


@dataclass
class TaskTurnPlan:
    commands: list[Command] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TaskTurnPlan":
        return cls(
            commands=[
                Command.from_dict(command)
                for command in data["commands"]
            ]
        )


@dataclass
class KnowledgeTurnPlan:
    intents: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeTurnPlan":
        return cls(intents=data["intents"])


@dataclass
class ChitchatTurnPlan:
    pass


@dataclass
class TurnPlan:
    """本轮处理计划：task / knowledge / chitchat 三选一（或记录多个以便澄清）。"""

    task: TaskTurnPlan | None = None
    knowledge: KnowledgeTurnPlan | None = None
    chitchat: ChitchatTurnPlan | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "TurnPlan":
        return cls(
            task=(
                TaskTurnPlan.from_dict(data["task"])
                if data.get("task") is not None
                else None
            ),
            knowledge=(
                KnowledgeTurnPlan.from_dict(data["knowledge"])
                if data.get("knowledge") is not None
                else None
            ),
            chitchat=(
                ChitchatTurnPlan()
                if data.get("chitchat") is not None
                else None
            ),
        )


class ClarifyReason(str, Enum):
    MISSING_TRACK = "missing_track"
    MULTIPLE_TRACKS = "multiple_tracks"
    MISSING_TASK_COMMANDS = "missing_task_commands"
    MISSING_KNOWLEDGE_INTENT = "missing_knowledge_intent"
    MISSING_FOCUSED_OBJECT = "missing_focused_object"
    OBJECT_REQUIRES_INTENT = "object_requires_intent"
    INVALID_TASK_COMMAND = "invalid_task_command"
    UNKNOWN_KNOWLEDGE_INTENT = "unknown_knowledge_intent"


@dataclass
class TurnPlanValidationResult:
    valid: bool
    reason: ClarifyReason | None = None
