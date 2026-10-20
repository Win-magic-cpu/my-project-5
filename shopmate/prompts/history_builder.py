import json
from dataclasses import asdict

from shopmate.domain.messages import (
    BotMessage,
    MessageObject,
    MessageType,
    UserMessage,
)
from shopmate.domain.state import Turn


class HistoryBuilder:
    """把对话历史渲染成提示词可读的纯文本。"""

    @staticmethod
    def build(turns: list[Turn]) -> str:
        messages: list[str] = []

        for turn in turns:
            user_message = HistoryBuilder.render_user_message(
                turn.user_message
            )
            messages.append(f"USER: {user_message}")

            for bot_message in turn.bot_messages:
                rendered_bot_message = (
                    HistoryBuilder._render_bot_message(bot_message)
                )
                messages.append(f"BOT: {rendered_bot_message}")

        return "\n".join(messages)

    @staticmethod
    def render_user_message(user_message: UserMessage) -> str:
        if user_message.type is MessageType.TEXT:
            return HistoryBuilder._render_text(user_message.text)
        return HistoryBuilder._render_object(user_message.object)

    @staticmethod
    def _render_bot_message(bot_message: BotMessage) -> str:
        if bot_message.text:
            return HistoryBuilder._render_text(bot_message.text)
        return HistoryBuilder._render_object(bot_message.object)

    @staticmethod
    def _render_text(text: str | None) -> str:
        return (text or "").strip()

    @staticmethod
    def _render_object(
        message_object: MessageObject | None,
    ) -> str:
        if message_object is None:
            return ""
        return json.dumps(
            asdict(message_object),
            ensure_ascii=False,
        )
