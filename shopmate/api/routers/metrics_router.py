from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from shopmate.obs.metrics import REGISTRY

metrics_router = APIRouter(tags=["metrics"])


@metrics_router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus 文本格式，直接给采集端拉取。"""
    return REGISTRY.render()
