import json
from dataclasses import asdict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from shopmate.clients.llm import get_llm
from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.plan.models import ClarifyReason
from shopmate.prompts.history_builder import HistoryBuilder
from shopmate.prompts.prompt_loader import load_prompt


class ClarifyResponder:
    """把澄清原因转成基础话术，再结合上下文自然化改写。"""

    def build_clarify_message(
        self,
        reason: ClarifyReason,
        state: DialogueState,
    ) -> str:
        if reason is ClarifyReason.MULTIPLE_TRACKS:
            return (
                "你这次同时提到了多个方向。我们先处理一个，"
                "你想先办业务还是先咨询信息呢？"
            )

        if reason is ClarifyReason.MISSING_FOCUSED_OBJECT:
            return "请先发送你想咨询的对象，我再继续帮你看。"

        if reason is ClarifyReason.MISSING_KNOWLEDGE_INTENT:
            return (
                "你是想了解商品信息、订单信息，还是售后配送规则呢？"
            )

        if reason is ClarifyReason.MISSING_TRACK:
            return "你是想先处理业务问题，还是先咨询信息呢？"

        if reason is ClarifyReason.MISSING_TASK_COMMANDS:
            return (
                "你这次是想办理什么业务呢？"
                "比如查订单、查物流，或者申请退款。"
            )

        if reason is ClarifyReason.INVALID_TASK_COMMAND:
            return (
                "当前任务状态不支持这个操作，"
                "请告诉我你想开始、继续还是取消哪个任务。"
            )

        if reason is ClarifyReason.UNKNOWN_KNOWLEDGE_INTENT:
            return (
                "我暂时无法识别这个咨询方向，"
                "你可以具体说说想了解的商品、订单或售后问题。"
            )

        if reason is ClarifyReason.OBJECT_REQUIRES_INTENT:
            focused_object = state.shared.focused_object
            if (
                focused_object is not None
                and focused_object.type == "order"
            ):
                return (
                    "我已经收到这个订单了。你想查订单状态、"
                    "查物流，还是申请退款呢？"
                )
            if (
                focused_object is not None
                and focused_object.type == "product"
            ):
                return (
                    "我已经收到这个商品了。你想了解它的商品信息、"
                    "发货情况，还是售后相关问题呢？"
                )

        return (
            "我还需要再确认一下你的意思，"
            "你可以换个更具体的说法告诉我。"
        )

    async def respond(
        self,
        state: DialogueState,
        user_message: UserMessage,
        reason: ClarifyReason,
    ) -> list[BotMessage]:
        clarify_message = self.build_clarify_message(
            reason=reason,
            state=state,
        )
        rendered_user_message = HistoryBuilder.render_user_message(
            user_message
        )
        session = state.shared.current_session
        history = HistoryBuilder.build(
            session.turns if session else []
        )
        focused_object = (
            json.dumps(
                asdict(state.shared.focused_object),
                ensure_ascii=False,
            )
            if state.shared.focused_object is not None
            else None
        )

        prompt = PromptTemplate.from_template(
            load_prompt("clarify_respond"),
            template_format="jinja2",
        )
        chain = prompt | get_llm() | StrOutputParser()

        rewritten = await chain.ainvoke(
            {
                "reason": reason.value,
                "clarify_message": clarify_message,
                "focused_object": focused_object,
                "history": history,
                "user_message": rendered_user_message,
            }
        )

        return [BotMessage(text=rewritten)]
