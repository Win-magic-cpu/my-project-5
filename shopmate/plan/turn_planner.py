import json
from dataclasses import asdict
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from shopmate.clients.llm import get_llm
from shopmate.domain.messages import UserMessage
from shopmate.domain.state import DialogueState
from shopmate.knowledge.intents import KnowledgeIntent
from shopmate.plan.models import TurnPlan
from shopmate.prompts.history_builder import HistoryBuilder
from shopmate.prompts.prompt_loader import load_prompt
from shopmate.task.flow.models import Flow, FlowCatalog


class TurnPlanner:
    """理解文本消息，生成本轮处理计划。"""

    async def predict(
        self,
        state: DialogueState,
        user_message: UserMessage,
        flows: FlowCatalog,
        knowledge_intents: dict[str, KnowledgeIntent],
    ) -> TurnPlan:
        prompt_inputs = self._build_prompt_inputs(
            state,
            user_message,
            flows,
            knowledge_intents,
        )
        return await self._predict_from_prompt_inputs(prompt_inputs)

    def _build_prompt_inputs(
        self,
        state: DialogueState,
        user_message: UserMessage,
        flows: FlowCatalog,
        knowledge_intents: dict[str, KnowledgeIntent],
    ) -> dict[str, Any]:
        session = state.shared.current_session
        focused_object = state.shared.focused_object
        available_flows: list[Flow] = list(flows.flows.values())

        return {
            "user_message": HistoryBuilder.render_user_message(
                user_message
            ),
            "conversation_history": HistoryBuilder.build(
                session.turns if session else []
            ),
            "focused_object_json": json.dumps(
                asdict(focused_object)
                if focused_object is not None
                else None,
                ensure_ascii=False,
                indent=2,
            ),
            "task_state_json": json.dumps(
                asdict(state.tasks),
                ensure_ascii=False,
                indent=2,
            ),
            "knowledge_intents_json": json.dumps(
                [
                    {"id": intent.id, "description": intent.description}
                    for intent in knowledge_intents.values()
                ],
                ensure_ascii=False,
                indent=2,
            ),
            "flows_json": json.dumps(
                [
                    {
                        key: value
                        for key, value in asdict(flow).items()
                        if key != "steps"
                    }
                    for flow in available_flows
                ],
                ensure_ascii=False,
                indent=2,
            ),
        }

    async def _predict_from_prompt_inputs(
        self,
        prompt_inputs: dict[str, Any],
    ) -> TurnPlan:
        prompt = PromptTemplate.from_template(
            load_prompt("turn_plan"),
            template_format="jinja2",
        )
        chain = prompt | get_llm() | JsonOutputParser()
        llm_output = await chain.ainvoke(prompt_inputs)
        return TurnPlan.from_dict(llm_output)
