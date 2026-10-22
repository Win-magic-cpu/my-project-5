import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from shopmate.api.trace import current_trace_id

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """业务异常：带稳定错误码，交给统一异常处理器输出。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": current_trace_id(),
    }
    if details is not None:
        payload["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


def _humanize(error: dict[str, Any]) -> str:
    """把 pydantic 的英文错误整理成一句能直接给用户看的话。"""
    message = str(error.get("msg", "")).removeprefix("Value error, ")
    context = error.get("ctx") or {}

    if error.get("type") == "greater_than_equal" and "ge" in context:
        return f"不能小于 {context['ge']}"
    if error.get("type") == "less_than_equal" and "le" in context:
        return f"不能大于 {context['le']}"
    if error.get("type") == "string_too_short" and "min_length" in context:
        return f"长度不能少于 {context['min_length']}"

    return message


def register_exception_handlers(app: FastAPI) -> None:
    """把所有异常收敛成 {code, message, trace_id} 一种结构。"""

    @app.exception_handler(ApiError)
    async def handle_api_error(
        request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": _humanize(error),
            }
            for error in exc.errors()
        ]
        message = details[0]["message"] if details else "请求参数不合法"
        return error_response(422, "validation_error", message, details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return error_response(
            exc.status_code,
            f"http_{exc.status_code}",
            str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "unhandled error trace_id=%s", current_trace_id()
        )
        return error_response(
            500, "internal_error", "服务内部错误，请稍后重试"
        )
