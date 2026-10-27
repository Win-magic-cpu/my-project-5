# CHANGELOG

按迭代顺序记录每个阶段做了什么、为什么。提交粒度更细的历史见 `git log`。

## v1.0.0 — Day 10

- README 重写：项目速览、架构、接口、RAG、评估、可观测性、部署与压测
- 新增 3 篇 ADR：Flow 引擎、计划与校验分离、状态整存 JSON
- 新增 CHANGELOG

## Day 9 — 部署与压测

- Dockerfile（两阶段、非 root、HEALTHCHECK）、`.dockerignore`
- compose 编排 api + mysql + mock-commerce + mock-llm
- `perf/load_test.py`（零依赖）与 `perf/locustfile.py`
- SQLite 并发写加 busy timeout
- 实测：对话链路 ~55 RPS，`/healthz` 818 RPS，0 错误

## Day 8 — 流式与 Demo

- `POST /api/chat/stream`（SSE：start / token / message / done / error）
- 引擎 `stream_message`，知识/闲聊/澄清走 `astream`
- 单文件前端 `/demo/`，打字机效果
- mock LLM 支持 SSE 分块与 embeddings

## Day 7 — 可观测性

- `TurnTrace` 分段耗时、JSON 日志（自动带 trace_id）
- `/metrics`（Prometheus 文本，零新依赖）
- 知识 Provider 失败降级（`return_exceptions`）

## Day 6 — 评估体系

- 40 条 golden set（task / knowledge / chitchat / clarify）
- 决策准确率、分类准确率、澄清率、错误接受数
- CI 增加 `--min-accuracy 0.90`
- 规则 baseline：95%，误放行 0

## Day 5 — RAG

- Markdown 切分（240/40，带标题路径）
- 可插拔 embedding（DashScope / 本地哈希）
- 纯 Python 向量索引 + 来源与分数
- 回答带 `[n]` 引用；阈值 0.15 兜底

## Day 4 — 数据层

- Alembic 迁移（0001 建表、0002 加 version/updated_at）
- 状态乐观锁 + 冲突重试（指数退避）
- docker-compose 提供 MySQL

## Day 3 — 接口契约

- 统一错误模型 `{code, message, trace_id, details}`
- trace_id 中间件与 `X-Trace-Id`
- 历史分页（limit/offset + total/has_more）
- `/healthz`、`/readyz`

## Day 2 — 会话一致性

- `message_id` 幂等回放
- 按 sender 串行化（`SenderLockRegistry`）
- 并发与幂等测试，实测无锁会丢 9/10 条更新

## Day 1 — 意图路由

- 新增 `onboarding`、`human_handoff` 两条 Flow
- 相似商品推荐改为条件分支起点
- 规划提示词重写（判断顺序、few-shot、上下文隔离）
- `set_slots` 增加 Slot 白名单
- SQLite 目录自愈
