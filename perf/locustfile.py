"""Locust 压测脚本（可选依赖）。

安装：
    uv sync --extra perf
运行：
    uv run locust -f perf/locustfile.py --headless -u 20 -r 2 -t 3m \
        --host http://127.0.0.1:18082

注意：默认打的是 /api/chat（非流式）。若要压流式接口，把 task 换成
self.client.post("/api/chat/stream", ...)，并给客户端设置更长超时。
"""

import uuid

from locust import HttpUser, between, task


class ChatUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.sender_id = f"perf-{uuid.uuid4().hex[:8]}"

    @task(4)
    def chat(self) -> None:
        self.client.post(
            "/api/chat",
            json={
                "sender_id": self.sender_id,
                "text": "你好",
                "message_id": str(uuid.uuid4()),
            },
            name="/api/chat",
        )

    @task(1)
    def history(self) -> None:
        self.client.get(
            f"/api/chat/history?sender_id={self.sender_id}&limit=20",
            name="/api/chat/history",
        )
