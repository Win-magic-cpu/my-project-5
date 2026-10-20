from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.task.action.runner import ActionCall, ActionRunner
from shopmate.task.flow.conditions import ConditionEvaluator
from shopmate.task.flow.links import (
    ConditionalLink,
    FallbackLink,
    StaticLink,
)
from shopmate.task.flow.models import FlowCatalog
from shopmate.task.flow.steps import (
    ActionFlowStep,
    CollectSlotStep,
    EndFlowStep,
    FlowStep,
    ResponseFlowStep,
    StartFlowStep,
)
from shopmate.task.response.renderer import ResponseRenderer


class FlowExecutor:
    """从活动任务的当前 Step 开始推进，直到等待输入或任务完成。"""

    def __init__(
        self,
        action_runner: ActionRunner,
        response_renderer: ResponseRenderer,
        condition_evaluator: ConditionEvaluator,
        max_steps_per_turn: int = 100,
    ) -> None:
        self.action_runner = action_runner
        self.response_renderer = response_renderer
        self.condition_evaluator = condition_evaluator
        self.max_steps_per_turn = max_steps_per_turn

    async def run_task(
        self,
        state: DialogueState,
        flows: FlowCatalog,
        user_message: UserMessage,
    ) -> list[BotMessage]:
        messages: list[BotMessage] = []

        for _ in range(self.max_steps_per_turn):
            task = state.tasks.active
            if task is None:
                return messages

            flow = flows.get_flow(task.flow_id)
            assert task.step_id is not None
            step = flow.get_step(task.step_id)

            if isinstance(step, StartFlowStep):
                self._advance(step, state)
                continue

            if isinstance(step, ResponseFlowStep):
                message = await self.response_renderer.render(
                    step.template,
                    state,
                    user_message=user_message,
                )
                messages.append(message)
                self._advance(step, state)
                continue

            if isinstance(step, CollectSlotStep):
                should_wait = await self._run_collect_step(
                    step,
                    state,
                    messages,
                    user_message,
                )
                if should_wait:
                    return messages
                continue

            if isinstance(step, ActionFlowStep):
                action_call = ActionCall(
                    action_name=step.action,
                    action_kwargs=step.args,
                )
                result = await self.action_runner.run(action_call, state)
                state.tasks.set_slots(result.slot_updates)
                self._advance(step, state)
                continue

            if isinstance(step, EndFlowStep):
                state.tasks.complete_active()
                return messages

            raise TypeError(
                f"不支持的 Step 类型: {type(step).__name__}"
            )

        # 达到单轮最大步数，避免配置成环时死循环
        return messages

    def _advance(self, step: FlowStep, state: DialogueState) -> None:
        """按 next 规则把活动任务的 step_id 推进到下一个 Step。"""
        task = state.tasks.active
        if task is None:
            return

        for link in step.next:
            if isinstance(link, StaticLink):
                task.step_id = link.target
                return

            if isinstance(link, ConditionalLink) and self.condition_evaluator.evaluate(
                link.condition,
                {"slots": task.slots},
            ):
                task.step_id = link.target
                return

            if isinstance(link, FallbackLink):
                task.step_id = link.target
                return

        # 没有可走的连接：保持当前位置，等待下一轮
        return

    async def _run_collect_step(
        self,
        step: CollectSlotStep,
        state: DialogueState,
        messages: list[BotMessage],
        user_message: UserMessage,
    ) -> bool:
        """返回是否需要等待用户输入。"""
        self._try_to_fill_slot_from_focused_object(step, state)

        task = state.tasks.active
        if task is None:
            return True

        value = task.slots.get(step.slot_name)
        if value is None or value == "":
            messages.append(
                await self.response_renderer.render(
                    step.template,
                    state,
                    user_message=user_message,
                )
            )
            return True

        validation = step.validation
        if validation is not None and not self.condition_evaluator.evaluate(
            validation.condition,
            {"slots": task.slots},
        ):
            state.tasks.remove_slot(step.slot_name)
            messages.append(
                await self.response_renderer.render(
                    validation.failure_template,
                    state,
                    user_message=user_message,
                )
            )
            return True

        self._advance(step, state)
        return False

    @staticmethod
    def _try_to_fill_slot_from_focused_object(
        step: CollectSlotStep,
        state: DialogueState,
    ) -> None:
        """用户先选了订单/商品，再发起任务时，直接用聚焦对象补齐 Slot。"""
        focused_object = state.shared.focused_object
        if focused_object is None:
            return

        if (
            step.slot_name == "order_number"
            and focused_object.type == "order"
        ):
            state.tasks.set_slots(
                {step.slot_name: focused_object.id}
            )
        elif (
            step.slot_name == "product_id"
            and focused_object.type == "product"
        ):
            state.tasks.set_slots(
                {step.slot_name: focused_object.id}
            )
