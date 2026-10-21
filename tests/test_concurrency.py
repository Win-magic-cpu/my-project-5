import asyncio
import copy

import pytest

from shopmate.domain.messages import BotMessage, MessageType, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.plan.models import ChitchatTurnPlan, TurnPlan
from shopmate.plan.validator import TurnPlanValidator
from shopmate.service.dialogue_service import DialogueService
from shopmate.service.locks import SenderLockRegistry


class StubTaskHandler:
    flows = None


class StubKnowledgeHandler:
    knowledge_intents = KNOWLEDGE_INTENTS

    async def handle(self, intents, state, user_message):
        return [BotMessage(text="知识回复")]


class StubClarifyResponder:
    async def respond(self, state, user_message, reason):
        return [BotMessage(text="澄清")]


class ChitchatPlanner:
    async def predict(self, state, user_message, flows, knowledge_intents):
        return TurnPlan(chitchat=ChitchatTurnPlan())


class EchoChitchatHandler:
    async def handle(self, state, user_message):
        await asyncio.sleep(0.001)
        return [BotMessage(text=f"回复：{user_message.text}")]


class SlowRepository:
    """在读写之间加入延迟，放大并发场景下的覆盖问题。"""

    def __init__(self) -> None:
        self.state: DialogueState | None = None
        self.save_count = 0

    async def load_state(self, sender_id: str) -> DialogueState:
        await asyncio.sleep(0.005)
        if self.state is None:
            return DialogueState(sender_id=sender_id)
        return copy.deepcopy(self.state)

    async def save_state(self, state: DialogueState) -> None:
        await asyncio.sleep(0.005)
        self.save_count += 1
        self.state = copy.deepcopy(state)


def build_service(repository: SlowRepository) -> DialogueService:
    engine = DialogueEngine(
        turn_planner=ChitchatPlanner(),
        task_handler=StubTaskHandler(),
        knowledge_handler=StubKnowledgeHandler(),
        chitchat_handler=EchoChitchatHandler(),
        clarify_responder=StubClarifyResponder(),
        turn_plan_validator=TurnPlanValidator(),
    )
    return DialogueService(repository, engine)


def text_message(index: int) -> UserMessage:
    return UserMessage(
        sender_id="u1",
        message_id=f"m{index}",
        type=MessageType.TEXT,
        text=f"消息{index}",
    )


@pytest.mark.asyncio
async def test_same_sender_requests_do_not_lose_updates():
    repository = SlowRepository()
    service = build_service(repository)

    await asyncio.gather(
        *[service.process_message(text_message(i)) for i in range(10)]
    )

    state = repository.state
    assert state is not None
    turns = state.shared.current_session.turns

    # 有锁：10 次读改写依次执行，10 条都不会丢
    assert len(turns) == 10
    assert sorted(turn.user_message.text for turn in turns) == [
        f"消息{i}" for i in range(10)
    ]

    # 每条回复都对应自己的输入，说明没有串状态
    for turn in turns:
        assert [m.text for m in turn.bot_messages] == [
            f"回复：{turn.user_message.text}"
        ]


def test_lock_registry_reuses_one_lock_per_sender():
    registry = SenderLockRegistry()

    assert registry.get("u1") is registry.get("u1")
    assert registry.get("u1") is not registry.get("u2")
    assert registry.size == 2
