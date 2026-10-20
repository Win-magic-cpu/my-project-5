from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shopmate.clients import database
from shopmate.engine.builder import build_dialogue_engine
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.repository.dialogue_state_repository import (
    DialogueStateRepository,
)
from shopmate.service.dialogue_service import DialogueService

_dialogue_engine: DialogueEngine | None = None


def init_dialogue_engine() -> None:
    global _dialogue_engine
    _dialogue_engine = build_dialogue_engine()


def get_engine() -> DialogueEngine:
    if _dialogue_engine is None:
        raise RuntimeError("DialogueEngine 尚未初始化。")
    return _dialogue_engine


async def get_db():
    if database.session_factory is None:
        raise RuntimeError("数据库引擎尚未初始化。")
    async with database.session_factory() as session:
        yield session


async def get_repository(
    db: AsyncSession = Depends(get_db),
) -> DialogueStateRepository:
    return DialogueStateRepository(db)


async def get_dialogue_service(
    engine: DialogueEngine = Depends(get_engine),
    repository: DialogueStateRepository = Depends(get_repository),
) -> DialogueService:
    return DialogueService(
        dialogue_state_repository=repository,
        dialogue_engine=engine,
    )
