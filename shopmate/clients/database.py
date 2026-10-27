from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shopmate.conf.config import PROJECT_ROOT, settings

engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_directory(database_url: str) -> None:
    """SQLite 不会自动建目录，启动前先把父目录补齐。"""
    if not database_url.startswith("sqlite"):
        return

    path_part = database_url.split("///", 1)[-1]
    if not path_part or path_part.startswith(":memory:"):
        return

    db_path = Path(path_part)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def init_db_engine() -> None:
    """创建异步引擎与会话工厂。"""
    global engine, session_factory
    _ensure_sqlite_directory(settings.database_url)

    connect_args: dict = {}
    if settings.database_url.startswith("sqlite"):
        # 并发写时不要立刻报 "database is locked"，交给 SQLite 排队
        connect_args = {"timeout": 30}

    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def close_db_engine() -> None:
    global engine, session_factory
    if engine is not None:
        await engine.dispose()
    engine = None
    session_factory = None


async def create_all_tables() -> None:
    """按 ORM 定义建表（幂等，已存在则跳过）。"""
    # 导入模型，确保它们已注册到 Base.metadata
    from shopmate.models import dialogue_state as _dialogue_state  # noqa: F401
    from shopmate.models.base import Base

    if engine is None:
        init_db_engine()

    assert engine is not None
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
