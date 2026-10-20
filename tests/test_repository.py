import shutil
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shopmate.domain.messages import (
    BotMessage,
    MessageObject,
    MessageType,
    UserMessage,
)
from shopmate.domain.state import DialogueState, FocusedObject, Turn
from shopmate.domain.task import TaskInstance
from shopmate.models.base import Base
from shopmate.models.dialogue_state import DialogueStateRecord  # noqa: F401
from shopmate.repository.dialogue_state_repository import (
    DialogueStateRepository,
)

TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


@pytest_asyncio.fixture
async def session():
    # 不使用 pytest 的 tmp_path：改为项目内临时目录，避免系统临时目录权限问题
    work_dir = TMP_ROOT / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{work_dir / 'state.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db_session:
            yield db_session
    finally:
        await engine.dispose()
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_missing_state_returns_empty_state(session: AsyncSession):
    repository = DialogueStateRepository(session)
    state = await repository.load_state("u1")
    assert state.sender_id == "u1"
    assert state.shared.sessions == []
    assert state.tasks.active is None


@pytest.mark.asyncio
async def test_save_and_load_roundtrip(session: AsyncSession):
    repository = DialogueStateRepository(session)
    state = DialogueState(sender_id="u1")
    session_state = state.shared.start_session()
    state.shared.set_focused_object(
        FocusedObject(type="order", id="A20240315001", title="订单")
    )
    state.tasks.active = TaskInstance(
        flow_id="order_status_query",
        step_id="ask_order_number",
        slots={"order_number": "A20240315001"},
    )
    session_state.append_turn(
        Turn.create(
            UserMessage(
                sender_id="u1",
                message_id="m1",
                type=MessageType.TEXT,
                text="帮我查订单",
            )
        )
    )
    session_state.turns[0].bot_messages.append(
        BotMessage(text="请告诉我你的订单号。")
    )

    await repository.save_state(state)

    loaded = await repository.load_state("u1")
    assert loaded == state
    assert loaded.tasks.active.flow_id == "order_status_query"
    assert loaded.shared.focused_object.id == "A20240315001"
    assert (
        loaded.shared.current_session.turns[0].bot_messages[0].text
        == "请告诉我你的订单号。"
    )


@pytest.mark.asyncio
async def test_save_state_updates_existing_row(session: AsyncSession):
    repository = DialogueStateRepository(session)
    state = DialogueState(sender_id="u1")
    state.shared.start_session()
    await repository.save_state(state)

    state.tasks.active = TaskInstance(flow_id="refund_request")
    await repository.save_state(state)

    loaded = await repository.load_state("u1")
    assert loaded.tasks.active.flow_id == "refund_request"

    rows = (await session.execute(
        DialogueStateRecord.__table__.select()
    )).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_object_message_roundtrip(session: AsyncSession):
    repository = DialogueStateRepository(session)
    state = DialogueState(sender_id="u2")
    turn = Turn.create(
        UserMessage(
            sender_id="u2",
            message_id="m2",
            type=MessageType.OBJECT,
            object=MessageObject(
                type="product",
                id="P1001",
                title="轻薄连帽防晒衣",
                attributes={"source": "product_list"},
            ),
        )
    )
    state.shared.start_session().append_turn(turn)
    await repository.save_state(state)

    loaded = await repository.load_state("u2")
    loaded_message = loaded.shared.current_session.turns[0].user_message
    assert loaded_message.type is MessageType.OBJECT
    assert loaded_message.object.id == "P1001"
    assert loaded_message.object.attributes == {"source": "product_list"}
