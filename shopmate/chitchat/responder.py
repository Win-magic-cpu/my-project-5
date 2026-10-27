from collections.abc import AsyncIterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from shopmate.clients.llm import get_llm
from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import Turn
from shopmate.prompts.history_builder import HistoryBuilder
from shopmate.prompts.prompt_loader import load_prompt


class ChitchatResponder:
    """结合当前消息与历史生成闲聊回复。"""

    async def respond(
        self,
        user_message: UserMessage,
        recent_turns: list[Turn],
    ) -> list[BotMessage]:
        chain, inputs = self._build(user_message, recent_turns)
        response = await chain.ainvoke(inputs)
        return [BotMessage(text=response)]

    async def stream(
        self,
        user_message: UserMessage,
        recent_turns: list[Turn],
    ) -> AsyncIterator[str]:
        chain, inputs = self._build(user_message, recent_turns)
        async for delta in chain.astream(inputs):
            if delta:
                yield delta

    @staticmethod
    def _build(
        user_message: UserMessage,
        recent_turns: list[Turn],
    ):
        rendered_user_message = HistoryBuilder.render_user_message(
            user_message
        )
        history = HistoryBuilder.build(recent_turns)

        prompt = PromptTemplate.from_template(
            load_prompt("chitchat_respond"),
            template_format="jinja2",
        )
        chain = prompt | get_llm() | StrOutputParser()
        return chain, {
            "user_message": rendered_user_message,
            "history": history,
        }
