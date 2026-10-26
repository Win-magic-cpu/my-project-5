import logging

import pytest

from shopmate.domain.messages import (
    BotMessage,
    MessageType,
    UserMessage,
)
from shopmate.domain.state import DialogueState
from shopmate.knowledge.handler import KnowledgeHandler
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.knowledge.providers import KnowledgeChunk, KnowledgeProvider
from shopmate.knowledge.registry import KnowledgeProviderRegistry


class ExplodingProvider(KnowledgeProvider):
    provider_id = "rag.default"

    async def retrieve(self, state, user_message):
        raise RuntimeError("embedding 服务不可用")


class WorkingProvider(KnowledgeProvider):
    provider_id = "faq.default"

    async def retrieve(self, state, user_message):
        return [KnowledgeChunk(content="FAQ 命中", source="faq")]


class RecordingResponder:
    def __init__(self) -> None:
        self.chunks = None

    async def respond(self, user_message, recent_turns, chunks):
        self.chunks = chunks
        return [BotMessage(text="ok")]


@pytest.mark.asyncio
async def test_one_failed_provider_does_not_break_the_turn(caplog):
    caplog.set_level(logging.WARNING, logger="shopmate.knowledge.handler")
    responder = RecordingResponder()
    handler = KnowledgeHandler(
        knowledge_intents=KNOWLEDGE_INTENTS,
        provider_registry=KnowledgeProviderRegistry(
            [ExplodingProvider(), WorkingProvider()]
        ),
        knowledge_responder=responder,
    )

    state = DialogueState(sender_id="u1")
    state.shared.start_session()

    messages = await handler.handle(
        ["refund_policy"],
        state,
        UserMessage(
            sender_id="u1",
            message_id="m1",
            type=MessageType.TEXT,
            text="退款政策",
        ),
    )

    assert messages[0].text == "ok"
    # 挂掉的知识源被跳过，剩下的资料仍然参与回答
    assert [chunk.content for chunk in responder.chunks] == ["FAQ 命中"]
    assert any(
        "knowledge provider failed" in record.getMessage()
        for record in caplog.records
    )
