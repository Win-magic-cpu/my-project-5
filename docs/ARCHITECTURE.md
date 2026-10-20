# 架构说明

## 1. 一条消息的旅程

```text
HTTP POST /api/chat
  └─ ChatRequest（Pydantic 校验：text / object 互斥）
       └─ DialogueService
            ├─ DialogueStateRepository.load_state(sender_id)
            ├─ DialogueEngine.process_message(state, user_message)
            │    ├─ 准备 Session（超时则关闭旧会话、清理运行时状态）
            │    ├─ 创建 Turn
            │    ├─ 文本 → TurnPlanner → TurnPlanValidator → 分流
            │    └─ 对象 → 记录 focused_object → 补槽或澄清
            ├─ DialogueStateRepository.save_state(state)
            └─ ProcessResult → ChatResponse
```

## 2. 三条轨道

| 轨道 | 入口 | 依赖 | 何时进入 |
| --- | --- | --- | --- |
| task | `TaskHandler` | FlowCatalog、ActionRunner、FlowExecutor | 计划含 `task.commands` |
| knowledge | `KnowledgeHandler` | Intent 配置、Provider 注册表、LLM | 计划含 `knowledge.intents` |
| chitchat | `ChitchatHandler` | LLM | 计划含 `chitchat` |

计划校验失败时，三条轨道都不执行，直接进 `ClarifyResponder`。进入 knowledge / chitchat 前会把活动任务 `suspend_active()`，用户之后可以恢复。

## 3. 为什么把「理解」和「执行」拆开

- `TurnPlanner` 只做一件事：把自然语言变成结构化计划（JSON）。
- `TurnPlanValidator` 用普通代码判断计划能不能执行：方向是否唯一、Flow 是否存在、命令顺序是否合法、Slot 是否在白名单、意图所需对象是否具备。
- `ClarifyResponder` 兜住所有"能理解但不能执行"的情况。

这样模型幻觉不会直接变成业务动作，而且校验规则可以单测覆盖——这是本项目测试量最大的部分。

## 4. 状态模型

```text
DialogueState
├─ shared: SharedState
│   ├─ focused_object: FocusedObject | None   # 当前关注的订单/商品
│   └─ sessions: list[Session]
│        └─ turns: list[Turn]
│             ├─ user_message: UserMessage
│             └─ bot_messages: list[BotMessage]
└─ tasks: TaskState
    ├─ active: TaskInstance | None
    └─ paused: list[TaskInstance]
```

几个约束：

- 同一时刻最多一个活动任务，切换时旧任务进 `paused`，进度不丢。
- `TaskInstance` 同时有 `flow_id`（办哪件事）和 `task_id`（哪一次执行），所以两次退款申请可以分别恢复/取消。
- 一轮对话可能产生多条客服消息，因此 `Turn.bot_messages` 是列表，整体提交。
- 整份状态序列化成 JSON 存一行，读写简单；代价是跨用户查询能力弱——这也是 Day 4 加版本号与迁移的原因。

## 5. Flow 引擎

YAML 描述任务，引擎负责推进：

```yaml
flows:
  order_status_query:
    steps:
      - {id: start, type: start, next: ask_order_number}
      - {id: ask_order_number, type: collect, slot_name: order_number, ...}
      - {id: lookup_order_status, type: action, action: action_lookup_order_status, ...}
      - {id: show_order_status, type: response, template: {...}, ...}
      - {id: end, type: end, next: []}
```

执行语义：

| Step | 行为 | 等待用户 |
| --- | --- | --- |
| start | 按 `next` 跳转 | 否 |
| collect | 有值且通过校验则跳转；否则提问并停留 | 是 |
| action | 调 Action，把 `slot_updates` 写回任务 | 否 |
| response | 渲染模板，产出消息 | 否 |
| end | 清空活动任务 | 结束 |

`collect` 在提问前会尝试用 `focused_object` 补槽：用户先点订单卡片再说"查状态"，就不必再报订单号。

## 6. 扩展点

| 想加什么 | 改哪里 | 是否改装配代码 |
| --- | --- | --- |
| 新业务流程 | `shopmate/flow_config/user_flows.yml` | 否 |
| 新业务动作 | `shopmate/task/action/custom/*.py`（启动自动扫描注册） | 否 |
| 新知识来源 | 实现 `KnowledgeProvider.retrieve()` 并注册 | 是（一行） |
| 新知识意图 | `shopmate/knowledge/intents.py` | 否 |
| 新回复模式 | `shopmate/task/response/` | 是 |

## 7. 关键取舍

1. **不用现成编排框架**：当前流程语义（Slot 校验、条件跳转、任务栈）比通用 Agent 框架更窄，自己实现约 400 行，换来完全可控的重试与错误处理。
2. **计划与校验分离**：模型负责理解，代码负责约束；两者都能独立测试。
3. **状态整存 JSON**：一次对话读写一条记录，避免多表 join；代价是分析能力弱，后续用迁移补齐。
4. **对象消息不猜测意图**：只有当前任务正收集对应 Slot 时才直接补槽，否则澄清——宁可多问一句，也不替用户做决定。
