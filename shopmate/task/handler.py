from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.task.command.models import Command
from shopmate.task.command.processor import CommandProcessor
from shopmate.task.flow.executor import FlowExecutor
from shopmate.task.flow.models import FlowCatalog
from shopmate.task.lifecycle.responder import TaskLifecycleResponder


class TaskHandler:
    """任务处理统一入口：执行 Commands -> 生成状态提示 -> 推进 Flow。"""

    def __init__(
        self,
        command_processor: CommandProcessor,
        flows: FlowCatalog,
        flow_executor: FlowExecutor,
        lifecycle_responder: TaskLifecycleResponder,
    ) -> None:
        self.command_processor = command_processor
        self.flows = flows
        self.flow_executor = flow_executor
        self.lifecycle_responder = lifecycle_responder

    async def handle(
        self,
        commands: list[Command],
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[BotMessage]:
        events = self.command_processor.run(
            commands,
            state,
            self.flows,
        )
        messages = self.lifecycle_responder.respond(events)
        messages.extend(
            await self.flow_executor.run_task(
                state,
                self.flows,
                user_message,
            )
        )
        return messages
