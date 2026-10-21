import pytest

from shopmate.domain.messages import BotMessage, MessageType, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.plan.models import ChitchatTurnPlan, TurnPlan
from shopmate.plan.validator import TurnPlanValidator
from shopmate.service.dialogue_service import DialogueService


class StubTaskHandler:
    flows = None


class StubKnowledgeHandler:
    knowledge_intents = KNOWLEDGE_INTENTS

    async def handle(self, intents, state, user_message):
        return [BotMessage(text="知识回复")]


class CountingChitchatHandler:
    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, state, user_message):
        self.calls += 1
        return [BotMessage(text=f"第 {self.calls} 次回复")]


class StubClarifyResponder:
    async def respond(self, state, user_message, reason):
        return [BotMessage(text="澄清")]


class ChitchatPlanner:
    async def predict(self, state, user_message, flows, knowledge_intents):
        return TurnPlan(chitchat=ChitchatTurnPlan())


class InMemoryRepository:
    def __init__(self) -> None:
        self.state: DialogueState | None = None

    async def load_state(self, sender_id: str) -> DialogueState:
        if self.state is None:
            self.state = DialogueState(sender_id=sender_id)
        return self.state

    async def save_state(self, state: DialogueState) -> None:
        self.state = state


def build_service():
    chitchat = CountingChitchatHandler()
    engine = DialogueEngine(
        turn_planner=ChitchatPlanner(),
        task_handler=StubTaskHandler(),
        knowledge_handler=StubKnowledgeHandler(),
        chitchat_handler=chitchat,
        clarify_responder=StubClarifyResponder(),
        turn_plan_validator=TurnPlanValidator(),
    )
    return DialogueService(InMemoryRepository(), engine), chitchat


def text_message(text: str, message_id: str) -> UserMessage:
    return UserMessage(
        sender_id="u1",
        message_id=message_id,
        type=MessageType.TEXT,
        text=text,
    )


@pytest.mark.asyncio
async def test_duplicate_message_id_is_replayed_not_reprocessed():
    service, chitchat = build_service()

    first = await service.process_message(text_message("你好", "m1"))
    second = await service.process_message(text_message("你好", "m1"))

    assert chitchat.calls == 1
    assert [m.text for m in second.messages] == [
        m.text for m in first.messages
    ]

    state = await service.get_state("u1")
    assert len(state.shared.current_session.turns) == 1


@pytest.mark.asyncio
async def test_new_message_id_is_processed_normally():
    service, chitchat = build_service()

    await service.process_message(text_message("你好", "m1"))
    await service.process_message(text_message("在吗", "m2"))

    assert chitchat.calls == 2
    state = await service.get_state("u1")
    assert len(state.shared.current_session.turns) == 2


def test_idempotency_window_keeps_only_recent_ids():
    state = DialogueState(sender_id="u1")

    for index in range(60):
        DialogueEngine._remember_message_id(state, f"m{index}")

    assert (
        len(state.recent_message_ids)
        == DialogueEngine.IDEMPOTENCY_WINDOW
    )
    assert state.recent_message_ids[0] == "m10"
    assert state.recent_message_ids[-1] == "m59"
