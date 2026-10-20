from shopmate.domain.messages import ProcessResult, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.repository.dialogue_state_repository import (
    DialogueStateRepository,
)


class DialogueService:
    """组织一条用户消息的完整处理过程：加载状态 -> 引擎处理 -> 保存状态。"""

    def __init__(
        self,
        dialogue_state_repository: DialogueStateRepository,
        dialogue_engine: DialogueEngine,
    ) -> None:
        self.dialogue_state_repository = dialogue_state_repository
        self.dialogue_engine = dialogue_engine

    async def process_message(
        self,
        user_message: UserMessage,
    ) -> ProcessResult:
        state = await self.dialogue_state_repository.load_state(
            user_message.sender_id
        )

        process_result = await self.dialogue_engine.process_message(
            state,
            user_message,
        )

        await self.dialogue_state_repository.save_state(state)
        return process_result

    async def get_state(self, sender_id: str) -> DialogueState:
        """只读取状态，供历史记录接口使用。"""
        return await self.dialogue_state_repository.load_state(sender_id)
