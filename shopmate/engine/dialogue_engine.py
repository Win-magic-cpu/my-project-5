import time
from collections.abc import AsyncIterator

from shopmate.chitchat.handler import ChitchatHandler
from shopmate.clarify.responder import ClarifyResponder
from shopmate.conf.config import settings
from shopmate.domain.messages import (
    BotMessage,
    MessageType,
    ProcessResult,
    UserMessage,
)
from shopmate.domain.state import DialogueState, FocusedObject, Turn
from shopmate.domain.streaming import StreamEvent
from shopmate.knowledge.handler import KnowledgeHandler
from shopmate.obs.trace import (
    current_trace,
    finish_trace,
    mark_decision,
    stage,
    start_trace,
)
from shopmate.plan.models import ClarifyReason
from shopmate.plan.turn_planner import TurnPlanner
from shopmate.plan.validator import TurnPlanValidator
from shopmate.api.trace import current_trace_id, new_trace_id
from shopmate.task.command.models import Command, SetSlotsCommand
from shopmate.task.flow.models import FlowCatalog
from shopmate.task.flow.steps import CollectSlotStep
from shopmate.task.handler import TaskHandler


class DialogueEngine:
    """一条用户消息进入系统后的对话调度中心。"""

    def __init__(
        self,
        turn_planner: TurnPlanner,
        task_handler: TaskHandler,
        knowledge_handler: KnowledgeHandler,
        chitchat_handler: ChitchatHandler,
        clarify_responder: ClarifyResponder,
        turn_plan_validator: TurnPlanValidator,
    ) -> None:
        self.turn_planner = turn_planner
        self.task_handler = task_handler
        self.knowledge_handler = knowledge_handler
        self.chitchat_handler = chitchat_handler
        self.clarify_responder = clarify_responder
        self.turn_plan_validator = turn_plan_validator

    async def process_message(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> ProcessResult:
        start_trace(
            current_trace_id() or new_trace_id(),
            user_message.sender_id,
            user_message.message_id,
        )

        try:
            # 客户端超时重试：同一个 message_id 不再重复执行，直接回放上一轮结果
            duplicated_turn = self._find_duplicated_turn(
                state, user_message.message_id
            )
            if duplicated_turn is not None:
                mark_decision("replay")
                return ProcessResult(
                    sender_id=user_message.sender_id,
                    message_id=user_message.message_id,
                    messages=list(duplicated_turn.bot_messages),
                )

            with stage("session"):
                self._prepare_session(state)

            turn = Turn.create(user_message)

            if user_message.type is MessageType.TEXT:
                with stage("handle_text"):
                    messages = await self._handle_text_message(
                        state=state,
                        user_message=user_message,
                    )
            else:
                with stage("handle_object"):
                    message_object = user_message.object
                    if message_object is None:
                        raise ValueError("对象消息缺少 object 字段。")

                    state.shared.set_focused_object(
                        FocusedObject(
                            type=message_object.type,
                            id=message_object.id,
                            title=message_object.title,
                            attributes=dict(message_object.attributes),
                        )
                    )
                    messages = await self._handle_object_message(
                        message=user_message,
                        state=state,
                    )

            turn.bot_messages.extend(messages)
            state.shared.append_turn(turn)
            self._remember_message_id(state, user_message.message_id)

            return ProcessResult(
                sender_id=user_message.sender_id,
                message_id=user_message.message_id,
                messages=messages,
            )
        except Exception:
            mark_decision("error")
            raise
        finally:
            finish_trace()

    # ------------------------------------------------------------ 幂等辅助
    IDEMPOTENCY_WINDOW = 50

    @classmethod
    def _find_duplicated_turn(
        cls,
        state: DialogueState,
        message_id: str,
    ) -> "Turn | None":
        """在已提交的轮次里找回同一个 message_id 的处理结果。"""
        if message_id not in state.recent_message_ids:
            return None

        for session in reversed(state.shared.sessions):
            for turn in reversed(session.turns):
                if turn.user_message.message_id == message_id:
                    return turn
        return None

    @classmethod
    def _remember_message_id(
        cls,
        state: DialogueState,
        message_id: str,
    ) -> None:
        state.recent_message_ids.append(message_id)
        # 只保留最近 N 条，避免状态无限增长
        del state.recent_message_ids[: -cls.IDEMPOTENCY_WINDOW]

    # ------------------------------------------------------------------ 会话
    def _prepare_session(self, state: DialogueState) -> None:
        session = state.shared.current_session

        if session is None:
            state.shared.start_session()
        elif (
            time.time() - session.last_activity_at
            > settings.session_timeout_seconds
        ):
            state.shared.close_current_session()
            state.reset_runtime_state_for_new_session()
            state.shared.start_session()

    # ------------------------------------------------------------------ 文本
    async def _plan_turn(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ):
        with stage("plan"):
            turn_plan = await self.turn_planner.predict(
                state,
                user_message,
                self.task_handler.flows,
                self.knowledge_handler.knowledge_intents,
            )

        with stage("validate"):
            validation = self.turn_plan_validator.validate(
                turn_plan,
                state=state,
                flows=self.task_handler.flows,
                knowledge_intents=self.knowledge_handler.knowledge_intents,
            )

        return turn_plan, validation

    async def _handle_text_message(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[BotMessage]:
        turn_plan, validation = await self._plan_turn(
            state, user_message
        )

        if not validation.valid:
            assert validation.reason is not None
            mark_decision("clarify")
            return await self.clarify_responder.respond(
                state=state,
                user_message=user_message,
                reason=validation.reason,
            )

        if turn_plan.task is not None:
            mark_decision("task")
            return await self.task_handler.handle(
                commands=turn_plan.task.commands,
                state=state,
                user_message=user_message,
            )

        if turn_plan.knowledge is not None:
            mark_decision("knowledge")
            if state.tasks.active:
                state.tasks.suspend_active()
            return await self.knowledge_handler.handle(
                state=state,
                user_message=user_message,
                intents=turn_plan.knowledge.intents,
            )

        mark_decision("chitchat")
        if state.tasks.active:
            state.tasks.suspend_active()
        return await self.chitchat_handler.handle(
            state=state,
            user_message=user_message,
        )

    # ------------------------------------------------------------------ 流式
    async def stream_message(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> AsyncIterator[StreamEvent]:
        """SSE 版本：先 start，再 token/message，最后 done。

        任务型必须跑完 Flow 才知道回复内容，所以按条推送；
        知识/闲聊/澄清是模型生成，可以逐 token 推。
        """
        trace = start_trace(
            current_trace_id() or new_trace_id(),
            user_message.sender_id,
            user_message.message_id,
        )
        sink: list[BotMessage] = []

        try:
            yield StreamEvent(
                "start",
                {
                    "trace_id": trace.trace_id,
                    "message_id": user_message.message_id,
                },
            )

            duplicated = self._find_duplicated_turn(
                state, user_message.message_id
            )
            if duplicated is not None:
                mark_decision("replay")
                for index, message in enumerate(duplicated.bot_messages):
                    sink.append(message)
                    yield StreamEvent(
                        "message",
                        {"index": index, "text": message.text},
                    )
                yield self._done_event(message.message_id, len(sink))
                return

            with stage("session"):
                self._prepare_session(state)

            turn = Turn.create(user_message)

            if user_message.type is MessageType.TEXT:
                async for event in self._stream_text_turn(
                    state, user_message, sink
                ):
                    yield event
            else:
                async for event in self._stream_object_turn(
                    state, user_message, sink
                ):
                    yield event

            turn.bot_messages.extend(sink)
            state.shared.append_turn(turn)
            self._remember_message_id(state, user_message.message_id)

            yield self._done_event(user_message.message_id, len(sink))
        except Exception:
            mark_decision("error")
            yield StreamEvent(
                "error",
                {
                    "code": "internal_error",
                    "message": "服务内部错误，请稍后重试",
                },
            )
        finally:
            finish_trace()

    async def _stream_text_turn(
        self,
        state: DialogueState,
        user_message: UserMessage,
        sink: list[BotMessage],
    ) -> AsyncIterator[StreamEvent]:
        turn_plan, validation = await self._plan_turn(
            state, user_message
        )

        if not validation.valid:
            assert validation.reason is not None
            mark_decision("clarify")
            accumulated: list[str] = []
            async for delta in self.clarify_responder.stream(
                state, user_message, validation.reason
            ):
                accumulated.append(delta)
                yield StreamEvent("token", {"text": delta})
            sink.append(BotMessage(text="".join(accumulated)))
            return

        if turn_plan.task is not None:
            mark_decision("task")
            produced = await self.task_handler.handle(
                commands=turn_plan.task.commands,
                state=state,
                user_message=user_message,
            )
            for index, message in enumerate(produced):
                sink.append(message)
                yield StreamEvent(
                    "message", {"index": index, "text": message.text}
                )
            return

        if turn_plan.knowledge is not None:
            mark_decision("knowledge")
            if state.tasks.active:
                state.tasks.suspend_active()
            chunks = await self.knowledge_handler.retrieve_chunks(
                turn_plan.knowledge.intents, state, user_message
            )
            session = state.shared.current_session
            recent_turns = session.turns if session else []
            accumulated: list[str] = []
            async for delta in self.knowledge_handler.knowledge_responder.stream(
                user_message, recent_turns, chunks
            ):
                accumulated.append(delta)
                yield StreamEvent("token", {"text": delta})
            sink.append(
                BotMessage(text="".join(accumulated) or "未检索到相关信息")
            )
            return

        mark_decision("chitchat")
        if state.tasks.active:
            state.tasks.suspend_active()
        accumulated = []
        async for delta in self.chitchat_handler.stream(
            state, user_message
        ):
            accumulated.append(delta)
            yield StreamEvent("token", {"text": delta})
        sink.append(BotMessage(text="".join(accumulated)))

    async def _stream_object_turn(
        self,
        state: DialogueState,
        user_message: UserMessage,
        sink: list[BotMessage],
    ) -> AsyncIterator[StreamEvent]:
        message_object = user_message.object
        if message_object is None:
            raise ValueError("对象消息缺少 object 字段。")

        state.shared.set_focused_object(
            FocusedObject(
                type=message_object.type,
                id=message_object.id,
                title=message_object.title,
                attributes=dict(message_object.attributes),
            )
        )
        produced = await self._handle_object_message(
            message=user_message,
            state=state,
        )
        for index, message in enumerate(produced):
            sink.append(message)
            yield StreamEvent(
                "message", {"index": index, "text": message.text}
            )

    def _done_event(
        self,
        message_id: str,
        message_count: int,
    ) -> StreamEvent:
        trace = current_trace()
        return StreamEvent(
            "done",
            {
                "message_id": message_id,
                "decision": trace.decision if trace else "unknown",
                "total_ms": trace.total_ms if trace else 0,
                "messages": message_count,
            },
        )

    # ------------------------------------------------------------------ 对象
    async def _handle_object_message(
        self,
        message: UserMessage,
        state: DialogueState,
    ) -> list[BotMessage]:
        command = self._object_slot_command(
            message=message,
            state=state,
            flows=self.task_handler.flows,
        )

        if command is None:
            mark_decision("clarify")
            return await self.clarify_responder.respond(
                state=state,
                user_message=message,
                reason=ClarifyReason.OBJECT_REQUIRES_INTENT,
            )

        mark_decision("task")
        return await self.task_handler.handle(
            commands=[command],
            state=state,
            user_message=message,
        )

    def _object_slot_command(
        self,
        message: UserMessage,
        state: DialogueState,
        flows: FlowCatalog,
    ) -> Command | None:
        message_object = message.object
        if message_object is None:
            return None

        object_type = message_object.type.strip().lower()
        collect_slot_name = self._current_collect_slot_name(
            state=state,
            flows=flows,
        )

        if (
            object_type == "order"
            and collect_slot_name == "order_number"
        ):
            return SetSlotsCommand(
                command="set_slots",
                slots={"order_number": message_object.id},
            )

        if (
            object_type == "product"
            and collect_slot_name == "product_id"
        ):
            return SetSlotsCommand(
                command="set_slots",
                slots={"product_id": message_object.id},
            )

        return None

    @staticmethod
    def _current_collect_slot_name(
        state: DialogueState,
        flows: FlowCatalog,
    ) -> str | None:
        active_task = state.tasks.active
        if active_task is None or active_task.step_id is None:
            return None

        current_flow = flows.get_flow(active_task.flow_id)
        current_step = current_flow.get_step(active_task.step_id)
        if not isinstance(current_step, CollectSlotStep):
            return None

        return current_step.slot_name
