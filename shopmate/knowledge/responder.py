from collections.abc import AsyncIterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from shopmate.clients.llm import get_llm
from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import Turn
from shopmate.knowledge.providers import KnowledgeChunk
from shopmate.prompts.history_builder import HistoryBuilder
from shopmate.prompts.prompt_loader import load_prompt


class KnowledgeResponder:
    """根据知识片段 + 对话历史生成最终回复。"""

    async def respond(
        self,
        user_message: UserMessage,
        recent_turns: list[Turn],
        chunks: list[KnowledgeChunk],
    ) -> list[BotMessage]:
        chain, inputs = self._build(
            user_message, recent_turns, chunks
        )
        response = await chain.ainvoke(inputs)
        return [BotMessage(text=response)]

    async def stream(
        self,
        user_message: UserMessage,
        recent_turns: list[Turn],
        chunks: list[KnowledgeChunk],
    ) -> AsyncIterator[str]:
        """逐 token 产出，供 SSE 使用。"""
        chain, inputs = self._build(
            user_message, recent_turns, chunks
        )
        async for delta in chain.astream(inputs):
            if delta:
                yield delta

    def _build(
        self,
        user_message: UserMessage,
        recent_turns: list[Turn],
        chunks: list[KnowledgeChunk],
    ):
        rendered_user_message = HistoryBuilder.render_user_message(
            user_message
        )
        history = HistoryBuilder.build(recent_turns)
        knowledge_content = "\n\n".join(
            self._format_chunk(index, chunk)
            for index, chunk in enumerate(chunks, start=1)
        )

        prompt = PromptTemplate.from_template(
            load_prompt("knowledge_respond"),
            template_format="jinja2",
        )
        chain = prompt | get_llm() | StrOutputParser()
        return chain, {
            "user_message": rendered_user_message,
            "history": history,
            "knowledge_content": knowledge_content,
        }

    @staticmethod
    def _format_chunk(index: int, chunk: KnowledgeChunk) -> str:
        """给每段资料编号并标注来源，方便模型生成 [1] 这样的引用。"""
        header = f"[{index}]"
        if chunk.source:
            header += f" 来源：{chunk.source}"
        return f"{header}\n{chunk.content}"
