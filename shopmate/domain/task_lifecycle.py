from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class TaskRef:
    """任务引用：只描述任务身份，不依赖 TaskInstance。"""

    task_id: str
    flow_id: str


@dataclass(frozen=True)
class TaskStarted:
    task: TaskRef


@dataclass(frozen=True)
class TaskSwitched:
    previous: TaskRef
    current: TaskRef


@dataclass(frozen=True)
class TaskResumed:
    task: TaskRef


@dataclass(frozen=True)
class TaskCanceled:
    task: TaskRef


TaskEvent: TypeAlias = (
    TaskStarted | TaskSwitched | TaskResumed | TaskCanceled
)
