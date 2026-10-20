from shopmate.domain.state import DialogueState
from shopmate.domain.task import TaskInstance
from shopmate.domain.task_lifecycle import TaskEvent
from shopmate.task.command.models import (
    CancelTaskCommand,
    Command,
    ResumeTaskCommand,
    SetSlotsCommand,
    StartFlowCommand,
)
from shopmate.task.flow.models import FlowCatalog


class CommandProcessor:
    """按顺序执行本轮 Commands，修改任务状态并收集生命周期事件。"""

    def run(
        self,
        commands: list[Command],
        state: DialogueState,
        flows: FlowCatalog,
    ) -> list[TaskEvent]:
        events: list[TaskEvent] = []
        for command in commands:
            event = self._apply(command, state, flows)
            if event is not None:
                events.append(event)
        return events

    def _apply(
        self,
        command: Command,
        state: DialogueState,
        flows: FlowCatalog,
    ) -> TaskEvent | None:
        if isinstance(command, StartFlowCommand):
            flow = flows.get_flow(command.flow)
            task = TaskInstance(
                flow_id=flow.id,
                step_id=flow.get_start_step().id,
            )
            return state.tasks.start(task)

        if isinstance(command, SetSlotsCommand):
            state.tasks.set_slots(command.slots)
            return None

        if isinstance(command, CancelTaskCommand):
            return state.tasks.cancel(command.task_id)

        if isinstance(command, ResumeTaskCommand):
            return state.tasks.resume(command.task_id)

        raise TypeError(f"不支持的命令: {command!r}")
