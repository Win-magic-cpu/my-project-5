import asyncio

from shopmate.domain.messages import ProcessResult, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.repository.dialogue_state_repository import (
    DialogueStateRepository,
    StateConflictError,
)
from shopmate.service.locks import SenderLockRegistry


class DialogueService:
    """组织一条用户消息的完整处理过程：加载状态 -> 引擎处理 -> 保存状态。"""

    MAX_SAVE_ATTEMPTS = 3

    def __init__(
        self,
        dialogue_state_repository: DialogueStateRepository,
        dialogue_engine: DialogueEngine,
        sender_locks: SenderLockRegistry | None = None,
    ) -> None:
        self.dialogue_state_repository = dialogue_state_repository
        self.dialogue_engine = dialogue_engine
        self.sender_locks = sender_locks or SenderLockRegistry()

    async def process_message(
        self,
        user_message: UserMessage,
    ) -> ProcessResult:
        # 同一用户串行：锁必须覆盖 load -> process -> save 整个过程，
        # 只锁其中一步等于没锁。
        async with self.sender_locks.get(user_message.sender_id):
            return await self._process_with_retry(user_message)

    async def _process_with_retry(
        self,
        user_message: UserMessage,
    ) -> ProcessResult:
        """多实例部署时，乐观锁冲突后重新读取状态再试。"""
        last_error: StateConflictError | None = None

        for attempt in range(self.MAX_SAVE_ATTEMPTS):
            try:
                state = await self.dialogue_state_repository.load_state(
                    user_message.sender_id
                )
                process_result = (
                    await self.dialogue_engine.process_message(
                        state, user_message
                    )
                )
                await self.dialogue_state_repository.save_state(state)
                return process_result
            except StateConflictError as exc:
                last_error = exc
                await asyncio.sleep(0.05 * (2**attempt))

        assert last_error is not None
        raise last_error

    async def get_state(self, sender_id: str) -> DialogueState:
        """只读取状态，供历史记录接口使用。"""
        return await self.dialogue_state_repository.load_state(sender_id)
