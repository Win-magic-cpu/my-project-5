from collections.abc import AsyncIterator

from shopmate.chitchat.responder import ChitchatResponder
from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.obs.trace import stage


class ChitchatHandler:
    """闲聊轨道入口。"""

    def __init__(self, responder: ChitchatResponder) -> None:
        self.responder = responder

    def recent_turns(self, state: DialogueState):
        session = state.shared.current_session
        return session.turns if session else []

    async def handle(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[BotMessage]:
        with stage("chitchat"):
            return await self.responder.respond(
                user_message=user_message,
                recent_turns=self.recent_turns(state),
            )

    async def stream(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> AsyncIterator[str]:
        with stage("chitchat"):
            async for delta in self.responder.stream(
                user_message=user_message,
                recent_turns=self.recent_turns(state),
            ):
                yield delta
