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
        rendered_user_message = HistoryBuilder.render_user_message(
            user_message
        )
        history = HistoryBuilder.build(recent_turns)
        knowledge_content = "\n\n".join(
            chunk.content for chunk in chunks
        )

        prompt = PromptTemplate.from_template(
            load_prompt("knowledge_respond"),
            template_format="jinja2",
        )
        chain = prompt | get_llm() | StrOutputParser()

        response = await chain.ainvoke(
            {
                "user_message": rendered_user_message,
                "history": history,
                "knowledge_content": knowledge_content,
            }
        )

        return [BotMessage(text=response)]
