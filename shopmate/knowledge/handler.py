import asyncio
import logging

from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.knowledge.intents import KnowledgeIntent
from shopmate.knowledge.registry import KnowledgeProviderRegistry
from shopmate.knowledge.responder import KnowledgeResponder
from shopmate.obs.trace import stage

logger = logging.getLogger(__name__)


class KnowledgeHandler:
    """知识检索型对话的统一入口。"""

    def __init__(
        self,
        knowledge_intents: dict[str, KnowledgeIntent],
        provider_registry: KnowledgeProviderRegistry,
        knowledge_responder: KnowledgeResponder,
    ) -> None:
        self.knowledge_intents = knowledge_intents
        self.provider_registry = provider_registry
        self.knowledge_responder = knowledge_responder

    async def handle(
        self,
        intents: list[str],
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[BotMessage]:
        with stage("knowledge"):
            provider_ids = self._get_provider_ids_by_intents(intents)

            retrieve_coroutines = [
                self.provider_registry.get(provider_id).retrieve(
                    state,
                    user_message,
                )
                for provider_id in provider_ids
            ]
            # 单个知识源失败（超时、接口 5xx）不应该拖垮整轮对话，
            # 先跳过它，用剩下的资料继续回答。
            provider_chunks = await asyncio.gather(
                *retrieve_coroutines, return_exceptions=True
            )

            chunks = []
            for provider_id, current_chunks in zip(
                provider_ids, provider_chunks
            ):
                if isinstance(current_chunks, BaseException):
                    logger.warning(
                        "knowledge provider failed: %s (%s)",
                        provider_id,
                        type(current_chunks).__name__,
                    )
                    continue
                chunks.extend(current_chunks)

            session = state.shared.current_session
            recent_turns = session.turns if session else []

            return await self.knowledge_responder.respond(
                user_message=user_message,
                recent_turns=recent_turns,
                chunks=chunks,
            )

    def _get_provider_ids_by_intents(
        self,
        intents: list[str],
    ) -> list[str]:
        provider_ids: list[str] = []
        for intent in intents:
            provider_ids.extend(
                self.knowledge_intents[intent].provider_ids
            )
        return list(dict.fromkeys(provider_ids))
