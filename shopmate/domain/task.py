import uuid
from dataclasses import dataclass, field
from typing import Any

from shopmate.domain.task_lifecycle import (
    TaskCanceled,
    TaskEvent,
    TaskRef,
    TaskResumed,
    TaskStarted,
    TaskSwitched,
)


@dataclass
class TaskInstance:
    """某条 Flow 的一次具体执行。"""

    flow_id: str
    step_id: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_ref(self) -> TaskRef:
        return TaskRef(task_id=self.task_id, flow_id=self.flow_id)


@dataclass
class TaskState:
    """任务型对话的独立状态：最多一个活动任务，其余进入暂停列表。"""

    active: TaskInstance | None = None
    paused: list[TaskInstance] = field(default_factory=list)

    def start(self, task: TaskInstance) -> TaskEvent:
        if self.active is None:
            self.active = task
            return TaskStarted(task=task.to_ref())

        previous = self.active
        self.paused.append(previous)
        self.active = task
        return TaskSwitched(
            previous=previous.to_ref(),
            current=task.to_ref(),
        )

    def set_slots(self, slots: dict[str, Any]) -> None:
        if self.active is None:
            raise RuntimeError("当前没有活动任务，无法写入 Slot。")
        self.active.slots.update(slots)

    def remove_slot(self, slot_name: str) -> None:
        if self.active is None:
            return
        self.active.slots.pop(slot_name, None)

    def cancel(self, task_id: str) -> TaskCanceled:
        if self.active is not None and self.active.task_id == task_id:
            canceled = self.active
            self.active = None
            return TaskCanceled(task=canceled.to_ref())

        canceled = self._find_paused(task_id)
        self.paused.remove(canceled)
        return TaskCanceled(task=canceled.to_ref())

    def resume(self, task_id: str) -> TaskEvent:
        target = self._find_paused(task_id)
        self.paused.remove(target)

        if self.active is None:
            self.active = target
            return TaskResumed(task=target.to_ref())

        previous = self.active
        self.paused.append(previous)
        self.active = target
        return TaskSwitched(
            previous=previous.to_ref(),
            current=target.to_ref(),
        )

    def complete_active(self) -> None:
        self.active = None

    def suspend_active(self) -> None:
        """把当前活动任务移入暂停列表（切换对话轨道时使用，不产生事件）。"""
        if self.active is None:
            return
        self.paused.append(self.active)
        self.active = None

    def reset(self) -> None:
        self.active = None
        self.paused.clear()

    def _find_paused(self, task_id: str) -> TaskInstance:
        for task in self.paused:
            if task.task_id == task_id:
                return task
        raise KeyError(f"暂停任务中不存在 task_id={task_id}")
