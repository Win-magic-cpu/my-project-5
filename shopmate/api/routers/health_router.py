from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shopmate.api.dependencies import get_engine
from shopmate.api.errors import ApiError
from shopmate.clients import database

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
async def healthz() -> dict:
    """存活探针：进程在跑就算健康。"""
    return {"status": "ok"}


@health_router.get("/readyz")
async def readyz() -> dict:
    """就绪探针：引擎已构建、数据库可读才对外提供服务。"""
    if database.session_factory is None:
        raise ApiError("not_ready", "数据库未初始化", 503)

    try:
        get_engine()
    except RuntimeError as exc:
        raise ApiError("not_ready", "对话引擎未初始化", 503) from exc

    try:
        async with database.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ApiError("not_ready", "数据库不可用", 503) from exc

    return {"status": "ready"}
