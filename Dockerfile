# syntax=docker/dockerfile:1

# ---------- 构建阶段：装依赖（利用 uv 缓存层） ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 先只拷依赖清单，依赖没变时可复用缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# ---------- 运行阶段 ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 shopmate

WORKDIR /app
COPY --from=builder --chown=shopmate:shopmate /app /app

USER shopmate

EXPOSE 18082

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18082/healthz')"

CMD ["uvicorn", "shopmate.api.app:app", "--host", "0.0.0.0", "--port", "18082"]
