from shopmate.domain.messages import BotMessage
from shopmate.domain.task_lifecycle import (
    TaskCanceled,
    TaskEvent,
    TaskResumed,
    TaskStarted,
    TaskSwitched,
)
from shopmate.task.flow.models import FlowCatalog


class TaskLifecycleResponder:
    """把任务生命周期事件转成用户可读的状态提示。"""

    def __init__(self, flows: FlowCatalog) -> None:
        self.flows = flows

    def respond(self, events: list[TaskEvent]) -> list[BotMessage]:
        return [self._message_for(event) for event in events]

    def _message_for(self, event: TaskEvent) -> BotMessage:
        if isinstance(event, TaskStarted):
            flow_name = self._flow_name(event.task.flow_id)
            return BotMessage(text=f"好的，我们先处理{flow_name}。")

        if isinstance(event, TaskSwitched):
            previous_name = self._flow_name(event.previous.flow_id)
            current_name = self._flow_name(event.current.flow_id)
            return BotMessage(
                text=(
                    f"好的，我们先把{previous_name}放一放，"
                    f"先处理{current_name}。"
                )
            )

        if isinstance(event, TaskResumed):
            flow_name = self._flow_name(event.task.flow_id)
            return BotMessage(text=f"好的，我们继续刚才的{flow_name}。")

        if isinstance(event, TaskCanceled):
            flow_name = self._flow_name(event.task.flow_id)
            return BotMessage(text=f"好的，{flow_name}先帮你取消。")

        raise TypeError(
            f"Unsupported task event: {type(event).__name__}"
        )

    def _flow_name(self, flow_id: str) -> str:
        flow = self.flows.get_flow(flow_id)
        return flow.name or flow.id
