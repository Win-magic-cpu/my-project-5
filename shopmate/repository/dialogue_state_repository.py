from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shopmate.domain.state import DialogueState
from shopmate.models.dialogue_state import DialogueStateRecord

DIALOGUE_STATE_ADAPTER: TypeAdapter[DialogueState] = TypeAdapter(
    DialogueState
)


class DialogueStateRepository:
    """对话状态的读取与保存。

    每个用户在数据库中对应一条记录，完整状态以 JSON 字符串保存。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_state(self, sender_id: str) -> DialogueState:
        statement = select(DialogueStateRecord).where(
            DialogueStateRecord.sender_id == sender_id
        )
        result = await self.session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return DialogueState(sender_id=sender_id)

        return DIALOGUE_STATE_ADAPTER.validate_json(record.state_json)

    async def save_state(self, state: DialogueState) -> None:
        state_json = DIALOGUE_STATE_ADAPTER.dump_json(state).decode("utf-8")
        statement = self._build_upsert(state.sender_id, state_json)
        await self.session.execute(statement)
        await self.session.commit()

    def _build_upsert(self, sender_id: str, state_json: str):
        """MySQL 使用 ON DUPLICATE KEY，SQLite 使用 ON CONFLICT。"""
        dialect = self.session.get_bind().dialect.name
        values = {"sender_id": sender_id, "state_json": state_json}

        if dialect == "mysql":
            statement = mysql_insert(DialogueStateRecord).values(**values)
            return statement.on_duplicate_key_update(
                state_json=statement.inserted.state_json
            )

        if dialect == "sqlite":
            statement = sqlite_insert(DialogueStateRecord).values(**values)
            return statement.on_conflict_do_update(
                index_elements=["sender_id"],
                set_={"state_json": state_json},
            )

        raise NotImplementedError(f"暂不支持的数据库方言: {dialect}")
