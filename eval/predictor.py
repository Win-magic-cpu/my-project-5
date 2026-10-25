"""规则版预测器：只用于离线评估的稳定 baseline。

它不代表线上模型的水平，作用是把「计划生成 → 校验 → 路由」这条流水线
固定下来做回归；接真实模型时换成 TurnPlanner，指标口径完全一致。
"""

import re

from shopmate.domain.messages import UserMessage
from shopmate.domain.state import DialogueState
from shopmate.plan.models import (
    ChitchatTurnPlan,
    KnowledgeTurnPlan,
    TaskTurnPlan,
    TurnPlan,
)
from shopmate.task.command.models import (
    Command,
    SetSlotsCommand,
    StartFlowCommand,
)

ORDER_NUMBER = re.compile(r"[A-Za-z]\d{6,}")

STEP_TO_SLOT = {
    "ask_order_number": "order_number",
    "ask_refund_reason": "refund_reason",
    "ask_product_id": "product_id",
}

KNOWLEDGE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("退款",), "refund_policy"),
    (("退货", "换货"), "return_policy"),
    (("发货", "包邮", "配送", "运费", "快递费"), "shipping_policy"),
    (("平台规则", "规则", "限制", "封号"), "platform_rule"),
    (("优惠券", "满减", "发票", "售后", "时效"), "general_ecommerce_info"),
    (("商品", "多少钱", "材质", "库存", "适合"), "product_info"),
)


class RuleBasedPlanner:
    """按关键词和任务上下文生成计划。"""

    async def predict(
        self,
        state: DialogueState,
        user_message: UserMessage,
        flows,
        knowledge_intents,
    ) -> TurnPlan:
        text = (user_message.text or "").strip()
        order_numbers = ORDER_NUMBER.findall(text)
        active = state.tasks.active

        # 1. 有活动任务：优先当作补槽
        if active is not None and active.step_id in STEP_TO_SLOT:
            slot = STEP_TO_SLOT[active.step_id]
            value = order_numbers[0] if order_numbers else text
            if value:
                return self._task_plan(
                    commands=[
                        SetSlotsCommand(
                            command="set_slots", slots={slot: value}
                        )
                    ]
                )

        commands: list[Command] = []
        intents: list[str] = []

        if "人工" in text or "转接" in text:
            commands.append(
                StartFlowCommand(
                    command="start_flow", flow="human_handoff"
                )
            )
        elif "推荐" in text or "相似" in text:
            commands.append(
                StartFlowCommand(
                    command="start_flow",
                    flow="similar_product_recommendation",
                )
            )
        elif "物流" in text or "快递" in text:
            commands.append(
                StartFlowCommand(
                    command="start_flow", flow="logistics_tracking"
                )
            )
        elif "退款" in text and (
            "申请" in text or "我要退" in text or "帮我退" in text
        ):
            commands.append(
                StartFlowCommand(
                    command="start_flow", flow="refund_request"
                )
            )
        elif "订单" in text or "查单" in text or "到哪" in text:
            commands.append(
                StartFlowCommand(
                    command="start_flow", flow="order_status_query"
                )
            )

        for keywords, intent in KNOWLEDGE_RULES:
            if any(keyword in text for keyword in keywords):
                intents.append(intent)

        # 用户同时提了业务和咨询（"查订单，再说说退款政策"）才保留两个轨道；
        # 否则"我要退款"会被拆成 task + knowledge 两个轨道，误判成冲突。
        if commands and intents:
            if not any(
                connector in text
                for connector in ("再", "另外", "顺便", "然后", "以及")
            ):
                intents = []

        if commands and order_numbers:
            commands.append(
                SetSlotsCommand(
                    command="set_slots",
                    slots={"order_number": order_numbers[0]},
                )
            )

        if commands or intents:
            return TurnPlan(
                task=TaskTurnPlan(commands=commands) if commands else None,
                knowledge=(
                    KnowledgeTurnPlan(intents=intents)
                    if intents
                    else None
                ),
            )

        if any(
            word in text
            for word in (
                "你好", "您好", "在吗", "谢谢", "再见",
                "叫什么", "天气", "你是谁",
            )
        ):
            return TurnPlan(chitchat=ChitchatTurnPlan())

        # 什么都不命中：交给校验器报 missing_track，走澄清
        return TurnPlan()

    @staticmethod
    def _task_plan(commands: list[Command]) -> TurnPlan:
        return TurnPlan(task=TaskTurnPlan(commands=commands))
