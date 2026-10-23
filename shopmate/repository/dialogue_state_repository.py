from datetime import datetime, timezone

from pydantic import TypeAdapter
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shopmate.domain.state import DialogueState
from shopmate.models.dialogue_state import DialogueStateRecord

DIALOGUE_STATE_ADAPTER: TypeAdapter[DialogueState] = TypeAdapter(
    DialogueState
)


class StateConflictError(RuntimeError):
    """并发保存冲突：数据库里的版本已经比本地读到的新。"""


class DialogueStateRepository:
    """对话状态的读取与保存。

    每个用户一行，完整状态以 JSON 保存；`version` 列用于乐观锁：

    - 读取时记住版本号；
    - 写入时用 `UPDATE ... WHERE version = 读到的版本`；
    - 影响行数为 0 说明期间被别的请求改过，抛冲突交给上层重试。

    这样只在写入的一瞬间校验，不会把 LLM 的秒级等待锁进事务。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._versions: dict[str, int] = {}

    async def load_state(self, sender_id: str) -> DialogueState:
        statement = select(DialogueStateRecord).where(
            DialogueStateRecord.sender_id == sender_id
        )
        result = await self.session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            self._versions[sender_id] = 0
            return DialogueState(sender_id=sender_id)

        self._versions[sender_id] = record.version
        return DIALOGUE_STATE_ADAPTER.validate_json(record.state_json)

    async def save_state(self, state: DialogueState) -> None:
        state_json = DIALOGUE_STATE_ADAPTER.dump_json(state).decode("utf-8")
        expected = self._versions.get(state.sender_id, 0)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if expected == 0:
            await self._insert(state.sender_id, state_json, now)
        else:
            await self._update(
                state.sender_id, state_json, expected, now
            )

        await self.session.commit()
        self._versions[state.sender_id] = expected + 1

    async def _insert(
        self,
        sender_id: str,
        state_json: str,
        now: datetime,
    ) -> None:
        statement = insert(DialogueStateRecord).values(
            sender_id=sender_id,
            state_json=state_json,
            version=1,
            updated_at=now,
        )
        try:
            await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            raise StateConflictError(
                f"{sender_id} 的状态已被其他请求创建"
            ) from exc

    async def _update(
        self,
        sender_id: str,
        state_json: str,
        expected: int,
        now: datetime,
    ) -> None:
        statement = (
            update(DialogueStateRecord)
            .where(
                DialogueStateRecord.sender_id == sender_id,
                DialogueStateRecord.version == expected,
            )
            .values(
                state_json=state_json,
                version=expected + 1,
                updated_at=now,
            )
        )
        result = await self.session.execute(statement)

        if result.rowcount == 0:
            await self.session.rollback()
            raise StateConflictError(
                f"{sender_id} 的状态已被其他请求修改（期望版本 {expected}）"
            )
