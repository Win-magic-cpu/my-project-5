import httpx

# 全局共享的异步 HTTP 客户端，在应用启动时创建、关闭时释放
http_client: httpx.AsyncClient | None = None


def init_http_client() -> None:
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)


async def close_http_client() -> None:
    global http_client
    if http_client is not None:
        await http_client.aclose()
    http_client = None


def get_http_client() -> httpx.AsyncClient:
    """获取 HTTP 客户端；未初始化时自动创建，方便脚本和测试直接调用。"""
    if http_client is None:
        init_http_client()
    assert http_client is not None
    return http_client
