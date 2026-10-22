import logging

from fastapi import FastAPI, Request
from fastapi.responses import Response

from shopmate.api.errors import error_response
from shopmate.api.trace import (
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)

logger = logging.getLogger(__name__)


def register_trace_middleware(app: FastAPI) -> None:
    """为每个请求分配 trace_id，写回响应头，并兜住未处理异常。"""

    @app.middleware("http")
    async def trace_middleware(
        request: Request,
        call_next,
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        token = set_trace_id(trace_id)

        try:
            try:
                response = await call_next(request)
            except Exception:
                # 兜底：保证 500 也是统一结构，且一定带 trace_id
                logger.exception("unhandled error trace_id=%s", trace_id)
                response = error_response(
                    500, "internal_error", "服务内部错误，请稍后重试"
                )

            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            reset_trace_id(token)
