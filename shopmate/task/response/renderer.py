from typing import Any

from jinja2 import Template
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from shopmate.clients.llm import get_llm
from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.prompts.history_builder import HistoryBuilder
from shopmate.task.response.models import ResponseMode, ResponseTemplate


class ResponseRenderer:
    """把 ResponseTemplate 渲染成最终的 BotMessage。"""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    async def render(
        self,
        template: ResponseTemplate,
        state: DialogueState,
        user_message: UserMessage | None = None,
    ) -> BotMessage:
        if template.mode is ResponseMode.STATIC:
            return BotMessage(text=self._render_text(template, state))

        if template.mode is ResponseMode.REPHRASE:
            rendered_text = self._render_text(template, state)
            text = await self._call_llm(
                template.prompt or "",
                state,
                user_message,
                current_response=rendered_text,
            )
            return BotMessage(text=text)

        if template.mode is ResponseMode.GENERATE:
            text = await self._call_llm(
                template.prompt or "",
                state,
                user_message,
            )
            return BotMessage(text=text)

        raise ValueError(f"不支持的回复模式: {template.mode}")

    @staticmethod
    def _render_text(
        template: ResponseTemplate,
        state: DialogueState,
    ) -> str:
        slots = state.tasks.active.slots if state.tasks.active else {}
        return Template(template.text or "").render(slots=slots)

    async def _call_llm(
        self,
        prompt_text: str,
        state: DialogueState,
        user_message: UserMessage | None,
        current_response: str = "",
    ) -> str:
        prompt = PromptTemplate.from_template(
            prompt_text,
            template_format="jinja2",
        )
        chain = prompt | (self.llm or get_llm()) | StrOutputParser()
        session = state.shared.current_session
        turns = session.turns if session else []
        return await chain.ainvoke(
            {
                "history": HistoryBuilder.build(turns),
                "user_message": (
                    HistoryBuilder.render_user_message(user_message)
                    if user_message is not None
                    else ""
                ),
                "current_response": current_response,
            }
        )
