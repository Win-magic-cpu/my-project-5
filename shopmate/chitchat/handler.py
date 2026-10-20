from shopmate.chitchat.responder import ChitchatResponder
from shopmate.domain.messages import BotMessage, UserMessage
from shopmate.domain.state import DialogueState


class ChitchatHandler:
    """闲聊轨道入口。"""

    def __init__(self, responder: ChitchatResponder) -> None:
        self.responder = responder

    async def handle(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[BotMessage]:
        session = state.shared.current_session
        recent_turns = session.turns if session else []
        return await self.responder.respond(
            user_message=user_message,
            recent_turns=recent_turns,
        )
