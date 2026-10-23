import shutil
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from shopmate.domain.messages import (
    BotMessage,
    MessageType,
    ProcessResult,
    UserMessage,
)
from shopmate.domain.state import DialogueState
from shopmate.models.base import Base
from shopmate.models.dialogue_state import DialogueStateRecord
from shopmate.repository.dialogue_state_repository import (
    DialogueStateRepository,
    StateConflictError,
)
from shopmate.service.dialogue_service import DialogueService

TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


@pytest_asyncio.fixture
async def session_factory():
    work_dir = TMP_ROOT / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{work_dir / 'conflict.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_stale_repository_cannot_overwrite(session_factory):
    async with session_factory() as session_a, session_factory() as session_b:
        repo_a = DialogueStateRepository(session_a)
        repo_b = DialogueStateRepository(session_b)

        # 两边同时读到同一个空状态（版本 0）
        state_a = await repo_a.load_state("u1")
        state_b = await repo_b.load_state("u1")

        await repo_a.save_state(state_a)  # 插入，版本变 1

        # B 手里还是"版本 0"的认知，插入必然撞主键
        with pytest.raises(StateConflictError):
            await repo_b.save_state(state_b)


@pytest.mark.asyncio
async def test_update_with_stale_version_is_rejected(session_factory):
    async with session_factory() as session_a, session_factory() as session_b:
        repo_a = DialogueStateRepository(session_a)
        state = await repo_a.load_state("u1")
        await repo_a.save_state(state)  # v1

        # 两个请求都读到 v1
        repo_reader = DialogueStateRepository(session_a)
        repo_writer = DialogueStateRepository(session_b)
        state_reader = await repo_reader.load_state("u1")
        state_writer = await repo_writer.load_state("u1")

        await repo_reader.save_state(state_reader)  # v1 -> v2

        with pytest.raises(StateConflictError):
            await repo_writer.save_state(state_writer)  # 仍以为自己是 v1


@pytest.mark.asyncio
async def test_version_increases_after_save(session_factory):
    async with session_factory() as session:
        repository = DialogueStateRepository(session)
        state = await repository.load_state("u1")
        await repository.save_state(state)

        record = (
            await session.execute(
                select(DialogueStateRecord).where(
                    DialogueStateRecord.sender_id == "u1"
                )
            )
        ).scalar_one()
        assert record.version == 1
        assert record.updated_at is not None

        await repository.save_state(state)  # 同一个仓库接着写，版本继续 +1
        await session.refresh(record)
        assert record.version == 2


class FlakyRepository:
    """前 N 次保存抛冲突，用来验证 Service 的重试。"""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.save_calls = 0
        self.load_calls = 0

    async def load_state(self, sender_id: str) -> DialogueState:
        self.load_calls += 1
        return DialogueState(sender_id=sender_id)

    async def save_state(self, state: DialogueState) -> None:
        self.save_calls += 1
        if self.save_calls <= self.failures:
            raise StateConflictError("模拟并发冲突")


class StubEngine:
    async def process_message(self, state, user_message) -> ProcessResult:
        state.shared.start_session()
        return ProcessResult(
            sender_id=user_message.sender_id,
            message_id=user_message.message_id,
            messages=[BotMessage(text="ok")],
        )


def user_message() -> UserMessage:
    return UserMessage(
        sender_id="u1",
        message_id="m1",
        type=MessageType.TEXT,
        text="你好",
    )


@pytest.mark.asyncio
async def test_service_retries_after_conflict():
    repository = FlakyRepository(failures=2)
    service = DialogueService(repository, StubEngine())

    result = await service.process_message(user_message())

    assert result.messages[0].text == "ok"
    assert repository.save_calls == 3
    assert repository.load_calls == 3


@pytest.mark.asyncio
async def test_service_gives_up_after_max_attempts():
    repository = FlakyRepository(failures=99)
    service = DialogueService(repository, StubEngine())

    with pytest.raises(StateConflictError):
        await service.process_message(user_message())

    assert repository.save_calls == DialogueService.MAX_SAVE_ATTEMPTS
