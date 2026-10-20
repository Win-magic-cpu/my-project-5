from pathlib import Path

from shopmate.chitchat.handler import ChitchatHandler
from shopmate.chitchat.responder import ChitchatResponder
from shopmate.clarify.responder import ClarifyResponder
from shopmate.clients.llm import llm
from shopmate.engine.dialogue_engine import DialogueEngine
from shopmate.knowledge.handler import KnowledgeHandler
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS
from shopmate.knowledge.providers import (
    FAQProvider,
    OrderAPIProvider,
    ProductAPIProvider,
    RAGProvider,
)
from shopmate.knowledge.registry import KnowledgeProviderRegistry
from shopmate.knowledge.responder import KnowledgeResponder
from shopmate.plan.turn_planner import TurnPlanner
from shopmate.plan.validator import TurnPlanValidator
from shopmate.task.action.builder import build_action_runner
from shopmate.task.command.processor import CommandProcessor
from shopmate.task.flow.conditions import ConditionEvaluator
from shopmate.task.flow.executor import FlowExecutor
from shopmate.task.flow.loader import FlowLoader
from shopmate.task.handler import TaskHandler
from shopmate.task.lifecycle.responder import TaskLifecycleResponder
from shopmate.task.response.renderer import ResponseRenderer

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_FLOW_CONFIG_FILE = _PACKAGE_ROOT / "flow_config" / "user_flows.yml"


def build_dialogue_engine() -> DialogueEngine:
    """自底向上组装整个对话引擎（应用启动时执行一次）。"""
    flows = FlowLoader().load(_FLOW_CONFIG_FILE)
    response_renderer = ResponseRenderer(llm=llm)
    action_runner = build_action_runner()

    return DialogueEngine(
        turn_planner=TurnPlanner(),
        task_handler=TaskHandler(
            flows=flows,
            command_processor=CommandProcessor(),
            flow_executor=FlowExecutor(
                action_runner=action_runner,
                response_renderer=response_renderer,
                condition_evaluator=ConditionEvaluator(),
            ),
            lifecycle_responder=TaskLifecycleResponder(flows=flows),
        ),
        knowledge_handler=KnowledgeHandler(
            knowledge_intents=KNOWLEDGE_INTENTS,
            knowledge_responder=KnowledgeResponder(),
            provider_registry=KnowledgeProviderRegistry(
                [
                    ProductAPIProvider(),
                    OrderAPIProvider(),
                    FAQProvider(),
                    RAGProvider(),
                ]
            ),
        ),
        chitchat_handler=ChitchatHandler(
            responder=ChitchatResponder(),
        ),
        clarify_responder=ClarifyResponder(),
        turn_plan_validator=TurnPlanValidator(),
    )
