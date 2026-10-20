from contextlib import asynccontextmanager

from fastapi import FastAPI

from shopmate.api.dependencies import init_dialogue_engine
from shopmate.api.routers.chat_router import chat_router
from shopmate.clients.database import (
    close_db_engine,
    create_all_tables,
    init_db_engine,
)
from shopmate.clients.http_client import (
    close_http_client,
    init_http_client,
)
from shopmate.conf.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：HTTP 客户端 -> 对话引擎 -> 数据库
    init_http_client()
    init_dialogue_engine()
    init_db_engine()
    if settings.auto_create_tables:
        await create_all_tables()

    yield

    # 关闭：先释放数据库，再释放 HTTP 客户端
    await close_db_engine()
    await close_http_client()


app = FastAPI(
    title="ShopMate · 智能客服对话引擎",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(chat_router)
