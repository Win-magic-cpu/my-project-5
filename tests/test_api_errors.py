from fastapi import FastAPI
from fastapi.testclient import TestClient

from shopmate.api.errors import ApiError, register_exception_handlers
from shopmate.api.middleware import register_trace_middleware
from shopmate.api.routers.health_router import health_router


def build_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    register_trace_middleware(app)
    app.include_router(health_router)

    @app.get("/test/teapot")
    async def teapot():
        raise ApiError("teapot", "我是一个茶壶", 418)

    @app.get("/test/crash")
    async def crash():
        raise RuntimeError("boom")

    return TestClient(app)


def test_unknown_route_returns_unified_404():
    response = build_client().get("/not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "http_404"
    assert body["message"]
    assert body["trace_id"] == response.headers["X-Trace-Id"]


def test_api_error_keeps_its_status_and_code():
    response = build_client().get("/test/teapot")

    assert response.status_code == 418
    body = response.json()
    assert body["code"] == "teapot"
    assert body["message"] == "我是一个茶壶"
    assert body["trace_id"] == response.headers["X-Trace-Id"]


def test_unhandled_exception_becomes_internal_error():
    response = build_client().get("/test/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert body["message"] == "服务内部错误，请稍后重试"
    # 不能把堆栈或原始错误信息透给调用方
    assert "boom" not in body["message"]
    assert response.headers["X-Trace-Id"] == body["trace_id"]


def test_readyz_reports_not_ready_without_database():
    response = build_client().get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "not_ready"
    assert body["trace_id"]


def test_healthz_is_always_ok():
    response = build_client().get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
