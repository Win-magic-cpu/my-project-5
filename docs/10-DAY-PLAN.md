# 10 天迭代计划

> 基线：当前仓库（完整可运行、79 个测试全绿、支持离线全链路演示）
> 目标：把「能跑」做成「能讲」——补齐一致性、数据层、RAG、评估、可观测性、交付与表达。
> 节奏：每天 2~4 小时，当天跑通测试并提交，打一个 `day-NN` 标签。

## 为什么要分 10 天

一次性堆完所有功能，代码会变成"什么都有一点、什么都讲不清"。拆成 10 天后：

- 每天的改动都能独立回滚、独立讲；
- `git log` 本身就是一份演进记录；
- 面试时可以直接翻某个 tag，说明当时为什么这么设计。

## 总览

| Day | 主题 | 关键产出 | 面试关键词 |
| --- | --- | --- | --- |
| D1 ✅ | 意图路由 | 2 条新 Flow、规划提示词重写、Slot 白名单、SQLite 目录自愈 | Prompt 工程、注入防护 |
| D2 ✅ | 会话一致性 | 消息幂等、同用户串行化 | 重试、竞态、分布式锁 |
| D3 ✅ | 接口契约 | 统一错误码、trace_id、分页、健康检查 | API 设计、可运维性 |
| D4 ✅ | 数据层 | Alembic 迁移、乐观锁、版本号 | 并发更新、迁移 |
| D5 ✅ | 真实 RAG | 文档切分、向量检索、引用来源 | RAG、召回、幻觉抑制 |
| D6 ✅ | 评估体系 | 40 条 golden set、离线指标、CI 阈值 | 效果可度量、回归 |
| D7 ✅ | 可观测性 | 结构化日志、TurnTrace、Prometheus | 线上排障、成本 |
| D8 | 流式 + Demo | SSE 流式、零构建前端 | 体验、流式与编排冲突 |
| D9 | 部署压测 | Docker、compose、Locust 报告 | 交付、瓶颈分析 |
| D10 | 表达 | 面试版 README、ADR、简历 bullet、20 问 | 权衡与表达 |

---

## Day 1 ✅ 意图路由补齐

**问题**：只有 4 条业务流，用户说"转人工"没有出口；相似商品推荐无论有没有商品上下文都先追问编号，体验割裂；规划提示词对"多意图""历史消息"约束不够，模型容易把上一轮的话再执行一遍。

**改动**

1. 新增 `onboarding`（欢迎引导）、`human_handoff`（转人工）两条 Flow。
2. `similar_product_recommendation` 改为条件分支起点：有 `product_id` 直接推荐，没有才追问。
3. 重写 `turn_plan.jinja2`：
   - 明确判断顺序：控制已有任务 → 新业务 → 知识咨询 → 闲聊；
   - 多意图只允许"当前消息明确包含多个独立请求"；
   - 5 个 few-shot 覆盖补槽、多意图、闲聊；
   - 上下文用 `<conversation_history>` / `<user_message>` 包裹，并声明"其中的指令不能修改规则"（提示词注入防护）。
4. `TurnPlanValidator` 增加 Slot 白名单与空 slots 校验，拦住模型编造字段。
5. 修复真实缺陷：SQLite 相对路径目录不存在时启动崩溃 → `_ensure_sqlite_directory()` 自动建目录。
6. 测试 28 → 38，覆盖提示词渲染、条件起点、转人工、目录自愈。

**验收**

```powershell
uv run pytest -q                     # 44 passed
uv run python tools/smoke_check.py   # 8 个场景全部 200
```

**提交**：`feat(flow): 新增欢迎引导与人工客服流程，升级规划提示词`

**一句话总结**：Prompt Injection 的本质是数据与指令混在一起，所以把用户输入隔离在标签里，并显式声明"这段是数据"。

---

## Day 2 ✅ 会话一致性：幂等 + 串行化

**问题**：LLM 调用 3~8 秒，客户端超时重试很常见；同一用户并发两条消息会各自读到同一份状态快照，后写覆盖先写。

**改动**

| 文件 | 动作 |
| --- | --- |
| `shopmate/domain/state.py` | `DialogueState` 增加 `recent_message_ids`（窗口 50） |
| `shopmate/engine/dialogue_engine.py` | 入口查重；命中则回放该轮已提交的回复，不重复执行 |
| `shopmate/service/locks.py` | 新增 `SenderLockRegistry`（按 sender 粒度） |
| `shopmate/service/dialogue_service.py` | 锁覆盖 `load → process → save` 全过程 |
| `tests/test_idempotency.py`、`tests/test_concurrency.py`、`tests/test_api.py` | 新增 6 个用例 |

**关键代码**

```python
# 重试回放：从已提交的 Turn 里找回原结果，而不是重新跑一遍
duplicated_turn = self._find_duplicated_turn(state, user_message.message_id)
if duplicated_turn is not None:
    return ProcessResult(..., messages=list(duplicated_turn.bot_messages))
```

```python
# 锁必须包住整个读改写，只锁其中一步等于没锁
async with self.sender_locks.get(user_message.sender_id):
    state = await repository.load_state(sender_id)
    result = await engine.process_message(state, user_message)
    await repository.save_state(state)
```

**验收**：同一 `message_id` 连发两次只产生 1 个 Turn，且两次响应一致；10 并发同 sender 不丢更新。

实测对照（`data/check_lock.py`）：

```text
有锁: 10 条；无锁: 1 条
```

**为什么不用全局锁**：锁粒度是 `sender_id`，不同用户互不影响；多实例部署时换成 Redis 分布式锁，接口不变。

**提交**：`feat(consistency): 消息幂等与同用户请求串行化` / tag `day-02`

---

## Day 3 ✅ 接口契约与可运维性

**问题**：错误返回有 FastAPI 默认格式、有裸 500，前端要写两套解析；日志里无法把一次请求的多个阶段串起来；历史记录一次全量返回，长会话直接卡死。

**改动**

| 文件 | 动作 |
| --- | --- |
| `shopmate/api/errors.py` | `ApiError` + 4 个异常处理器，统一 `{code, message, trace_id}` |
| `shopmate/api/trace.py` | `contextvars` 保存 trace_id |
| `shopmate/api/middleware.py` | 生成/透传 `X-Trace-Id`，兜住未处理异常返回 500 |
| `shopmate/api/routers/health_router.py` | `/healthz`（存活）、`/readyz`（引擎 + 数据库就绪） |
| `shopmate/api/routers/chat_router.py` | 历史分页 `limit/offset`，返回 `total/has_more` |
| `tests/test_api_errors.py`、`tests/test_api.py` | 新增 9 个用例 |

**错误结构**

```json
{
  "code": "validation_error",
  "message": "text 和 object 必须且只能传一个",
  "trace_id": "9f2c1ab34de5f607",
  "details": [{"field": "body", "message": "..."}]
}
```

`code` 是稳定枚举（`validation_error` / `http_404` / `not_ready` / `internal_error` / 业务自定义），前端可直接 switch；`message` 只给人看。

**验收**

```powershell
curl.exe -i "http://127.0.0.1:18082/api/chat/history?sender_id=u1&limit=2"
# 响应头 X-Trace-Id，body 含 total / limit / offset / has_more
curl.exe -i -X POST http://127.0.0.1:18082/api/chat -H "Content-Type: application/json" -d '{\"sender_id\":\"u1\"}'
# 422 + 统一结构
curl.exe http://127.0.0.1:18082/readyz
```

实测：`53 passed`。

**取舍**：trace_id 用 `contextvars` 而不是往每个函数传参，避免污染业务签名；500 的 `message` 固定为中文兜底文案，堆栈只进日志——**不把内部信息透给调用方**。

**提交**：`feat(api): 统一错误模型、trace_id 与历史分页` / tag `day-03`

---

## Day 4 ✅ 数据层：迁移与乐观锁

**问题**：表结构靠 `create_all`，改字段只能删库重建；两个实例同时处理同一用户时，后写的会覆盖先写的（lost update）。

**改动**

| 文件 | 动作 |
| --- | --- |
| `alembic.ini`、`migrations/` | 引入 Alembic；`env.py` 从应用配置注入 URL，支持异步引擎 |
| `migrations/versions/0001_initial.py` | 建表：`sender_id` + `state_json` |
| `migrations/versions/0002_state_version.py` | 增加 `version`、`updated_at`（带 server_default，可在线升级） |
| `shopmate/models/dialogue_state.py` | ORM 同步新增两列 |
| `shopmate/repository/dialogue_state_repository.py` | 读时记版本，写时 `WHERE version = ?`；影响 0 行抛 `StateConflictError` |
| `shopmate/service/dialogue_service.py` | 冲突重试 3 次，指数退避（50/100/200ms） |
| `docker-compose.yml` | 本地 MySQL 8.4（utf8mb4 + healthcheck） |
| `tests/test_state_conflict.py` | 新增 5 个用例 |

**为什么不用行锁**：状态是整块 JSON，行锁会把 LLM 的 5 秒等待也锁进事务；乐观锁只在 `UPDATE` 那一瞬间校验版本，冲突概率低、代价小。

**验收**

```powershell
uv run alembic upgrade head
uv run alembic current      # 0002_state_version (head)
uv run alembic check        # No new upgrade operations detected.
uv run pytest -q            # 58 passed
```

**取舍**：重试会重新读状态、重新跑一遍引擎（可能再调一次 LLM）。这是"正确性优先"的选择——丢更新比多花一次 token 更贵；配合 Day 2 的幂等窗口，重复执行不会产生两条记录。

**提交**：`feat(db): Alembic 迁移与状态乐观锁` / tag `day-04`

---

## Day 5 ✅ 真实 RAG

**问题**：政策类问题原来靠关键词硬匹配，换个说法就召回不到；回答也没有出处，无法判断是不是模型编的。

**改动**

| 文件 | 动作 |
| --- | --- |
| `docs/knowledge/*.md` | 五份政策文档：退款、退货、配送、平台规则、售后时效 |
| `shopmate/knowledge/rag/splitter.py` | 按标题切段 + 240 字滑窗 / 40 重叠，chunk 带标题路径 |
| `shopmate/knowledge/rag/embedding.py` | `EmbeddingModel` 协议：DashScope 正式实现 + 本地 hashing 离线实现 |
| `shopmate/knowledge/rag/store.py` | 纯 Python 余弦索引，可序列化；模型不匹配自动重建 |
| `shopmate/knowledge/rag/loader.py` / `factory.py` | 文档加载、embedding 选择、索引路径解析 |
| `shopmate/knowledge/providers.py` | `RAGProvider` 接向量检索；`KnowledgeChunk` 增加 `source`、`score` |
| `shopmate/knowledge/responder.py` | 资料编号 + 来源标注，喂给模型 |
| `shopmate/prompts/jinja2/knowledge_respond.jinja2` | 要求句末标注 `[1]`，禁止编造编号 |
| `scripts/ingest.py` | 一键重建索引 |
| `tests/test_rag.py` | 新增 8 个用例 |

**没有引入 Chroma / numpy**：20 个 chunk 的规模，纯 Python 点积足够；接口（build/search）不变，上量再换 pgvector。

**调参过程（面试可以讲）**

```text
chunk 500 / dim 256 / 阈值 0.12：
  退款多久能到账      -> refund 0.377 ✅
  多久发货，包邮吗    -> 未检索到    ❌（长 chunk 稀释）
  你们今天天气怎么样  -> platform 0.146 ❌（假阳性）

chunk 240 / dim 512 / 阈值 0.15：
  退款多久能到账      -> refund 0.335 ✅
  支持七天无理由退货吗 -> return 0.492 ✅
  多久发货，包邮吗    -> shipping 0.197 ✅
  优惠券可以叠加吗    -> platform 0.353 ✅
  你们今天天气怎么样  -> 未检索到    ✅（正确拒答）
```

**验收**

```powershell
uv run python scripts/ingest.py     # 20 个片段 -> data/rag_index.json
uv run pytest -q                    # 66 passed
```

**取舍**：没做重排（rerank），chunk 参数是按当前语料手调的；这两点写进 README 的"下一步"，比假装已经做好更可信。

**提交**：`feat(rag): 文档切分、向量检索与引用式回答` / tag `day-05`

---

## Day 6 ✅ 评估体系

**问题**：改提示词、调路由规则时只能"感觉好像更好了"，没有回归基线；线上把该澄清的请求放行，也没人发现。

**改动**

| 文件 | 动作 |
| --- | --- |
| `eval/golden.jsonl` | 40 条用例：task 14、knowledge 14、chitchat 6、clarify 6 |
| `eval/cases.py` | 用例模型 + 加载校验（重复 id、未知决策直接报错） |
| `eval/predictor.py` | 规则 baseline（关键词 + 上下文补槽），可在 CI 离线跑 |
| `eval/metrics.py` | 决策准确率、分类准确率、澄清率、错误接受数、markdown 报告 |
| `eval/run_eval.py` | 跑 plan→validate→decision，`--planner rule/llm`、`--min-accuracy` |
| `docs/eval-report.md` | 每次运行自动生成的结果 |
| `.github/workflows/ci.yml` | 增加 `--min-accuracy 0.90` 步骤 |
| `tests/test_eval.py` | 6 个用例（用例集完整性、四轨道覆盖、阈值、指标、报告渲染） |

**指标口径**

| 指标 | 含义 |
| --- | --- |
| decision accuracy | 最终决策（task/knowledge/chitchat/clarify）与期望一致的比例 |
| false accepts | 应该澄清却被放行的用例数（安全指标，必须为 0） |
| clarify rate | 实际走澄清的比例 |

**结果（规则 baseline）**

```text
cases=40 passed=38 accuracy=0.950 clarify_rate=0.200 false_accepts=0

task      14 / 13 / 93%
knowledge 14 / 13 / 93%
chitchat   6 /  6 / 100%
clarify    6 /  6 / 100%
```

两个失败用例都是同义改写："我上次买的那件衣服什么时候能到"（没有"物流/快递"）、
"钱什么时候能退回来"（没有"退款"）。**这正好说明为什么需要 LLM 做意图理解**——规则能保证安全边界，但覆盖不了自然语言变体。

**验收**

```powershell
uv run python eval/run_eval.py --min-accuracy 0.90   # 退出码 0
uv run pytest -q                                     # 72 passed
```

**取舍**：评估器把"预测"抽象成可插拔，CI 跑规则 baseline 保证流水线不回归；有 Key 时 `--planner llm` 用同一套指标评真实模型，避免"两套口径没法比"。

**提交**：`test(eval): 40 条 golden set 与离线评估脚本` / tag `day-06`

---

## Day 7 ✅ 可观测性

**问题**：一次回复慢，不知道慢在 planner、校验还是知识检索；用户报"刚才那条错了"，日志里也串不起来是哪次请求。

**改动**

| 文件 | 动作 |
| --- | --- |
| `shopmate/obs/trace.py` | `TurnTrace`：trace_id、各阶段耗时、最终决策；`stage()` 上下文管理器计时 |
| `shopmate/obs/metrics.py` | 极简 Counter / Histogram，输出 Prometheus 文本（不引入 prometheus_client） |
| `shopmate/obs/logging.py` | JSON 格式化 + trace_id 注入 |
| `shopmate/api/routers/metrics_router.py` | `GET /metrics` |
| `shopmate/engine/dialogue_engine.py` | 起止 trace、`plan` / `validate` / `session` / `handle_*` 阶段、决策标记 |
| `task` / `knowledge` / `chitchat` / `clarify` handler | 各自加 `stage()`，任务轨道可细分到 handler |
| `shopmate/knowledge/handler.py` | Provider 失败降级（`return_exceptions=True`，跳过并 warning） |
| `tests/test_obs.py`、`tests/test_knowledge_resilience.py` | 新增 7 个用例 |

**真实日志（一次 knowledge 轮次）**

```json
{"level":"INFO","logger":"shopmate.turn","message":"turn completed","event":"turn.completed",
 "trace_id":"56f65a3a5e6049e3","sender_id":"obs","message_id":"obs-m3","decision":"knowledge",
 "stages":{"session":0.03,"plan":58.26,"validate":0.01,"knowledge":51.53,"handle_text":109.83},
 "total_ms":109.91}
```

**指标**

```text
shopmate_turns_total{decision="knowledge"} 1
shopmate_stage_duration_seconds_sum{stage="plan"} 0.05826
shopmate_stage_duration_seconds_sum{stage="knowledge"} 0.05153
shopmate_turn_duration_seconds_count 1
```

**顺带修的真 bug**：mock embedding 接口 404 时，知识轨道整个 500。现在 Provider 并发调用用
`asyncio.gather(return_exceptions=True)`，挂掉的知识源记 warning 后跳过，剩余资料照常回答。

**验收**

```powershell
curl.exe -i -X POST http://127.0.0.1:18082/api/chat -H "Content-Type: application/json" -d '{\"sender_id\":\"u1\",\"text\":\"退款多久到账\"}'
# 响应头 X-Trace-Id；日志里同一个 trace 有 plan/validate/knowledge 三段
curl.exe http://127.0.0.1:18082/metrics
uv run pytest -q    # 79 passed
```

**取舍**：没接 OpenTelemetry，也没算 token 成本——当前没有稳定的 usage 回调；先把"哪一段慢"解决，token 统计留到接真实模型时用 callback 补。

**提交**：`feat(obs): 结构化日志、TurnTrace 与指标端点` / tag `day-07`

---

## Day 8 流式输出与 Demo

**关键取舍**：任务型必须先跑完 Flow 才知道回复内容，所以只有 knowledge/chitchat 真正逐 token 流式；任务轨道用多段事件模拟渐进反馈。

**改动**

| 文件 | 动作 |
| --- | --- |
| `shopmate/api/routers/chat_router.py` | `POST /api/chat/stream`，`text/event-stream` |
| `shopmate/engine/dialogue_engine.py` | `stream_message` |
| `web/index.html` | 原生 JS + `ReadableStream`，零构建 |
| `docs/demo.png` | 截图 |

**提交**：`feat(stream): SSE 流式回复与最小前端` / tag `day-08`

---

## Day 9 部署与压测

**改动**

| 文件 | 动作 |
| --- | --- |
| `Dockerfile` | 多阶段构建、非 root 运行 |
| `docker-compose.yml` | api + mysql + mock-commerce + mock-llm |
| `perf/locustfile.py` | 20 并发 5 分钟 |
| `docs/perf.md` | p50/p95、错误率、瓶颈分析 |

**验收**

```powershell
docker compose up -d
locust -f perf/locustfile.py --headless -u 20 -r 2 -t 3m --host http://127.0.0.1:18082
```

**提交**：`build: Docker 多阶段镜像与压测报告` / tag `day-09`

---

## Day 10 表达与面试包

**改动**

| 文件 | 动作 |
| --- | --- |
| `README.md` | 价值 → 架构 → 指标 → 快速开始 → 目录 → 决策 |
| `docs/adr/0001-自研-flow-引擎的取舍.md` | 对比硬编码与通用编排框架 |
| `docs/adr/0002-计划与校验为什么分离.md` | LLM 理解 vs 代码约束 |
| `docs/adr/0003-状态整存-json-的取舍.md` | 读写模式与迁移成本 |
| `docs/interview/简历.md` | 3 条带数字的 bullet |
| `docs/interview/追问.md` | 20 个高频问题 |
| `CHANGELOG.md` | 按天汇总 |

**提交**：`docs: 面试版 README、ADR 与问答手册` / tag `v1.0.0`

---

## 每天的固定动作

```powershell
git pull --rebase

git switch -c feat/day-05-rag
# 改代码
uv run pytest -q

git add -A
git commit -m "feat(rag): 文档切分与向量检索"

git switch main
git merge --no-ff feat/day-05-rag
git tag day-05
git push origin main --tags
```

## 时间不够时的最小集

D1（已完成）+ D4 + D5 + D6 + D10：并发、RAG、评估、表达四件事齐了，足够撑一场 40 分钟面试。其余作为"下一步计划"讲，比做一半更好。

## 三条纪律

1. **每天结束时必须可运行**：`uv sync && uv run pytest -q` 全绿。
2. **提交信息写“为什么”**，不要写"fix bug"。
3. **指标只认脚本算出来的数**，不写"效果显著提升"这种话。
