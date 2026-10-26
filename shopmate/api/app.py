from contextlib import asynccontextmanager

from fastapi import FastAPI

from shopmate.api.dependencies import init_dialogue_engine
from shopmate.api.errors import register_exception_handlers
from shopmate.api.middleware import register_trace_middleware
from shopmate.api.routers.chat_router import chat_router
from shopmate.api.routers.health_router import health_router
from shopmate.api.routers.metrics_router import metrics_router
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
from shopmate.obs.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

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

register_exception_handlers(app)
register_trace_middleware(app)

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(metrics_router)
