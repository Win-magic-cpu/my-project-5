"""离线评估：跑 golden set，输出决策准确率与失败用例。

用法：
    uv run python eval/run_eval.py                    # 规则 baseline
    uv run python eval/run_eval.py --planner llm      # 真实模型（需要 Key）
    uv run python eval/run_eval.py --min-accuracy 0.9 # CI 阈值，低于则退出码 1
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.cases import EvalCase, load_cases  # noqa: E402
from eval.metrics import (  # noqa: E402
    EvalResult,
    render_report,
    summarize,
)
from eval.predictor import RuleBasedPlanner  # noqa: E402

from shopmate.domain.messages import (  # noqa: E402
    MessageType,
    UserMessage,
)
from shopmate.domain.state import DialogueState, FocusedObject  # noqa: E402
from shopmate.domain.task import TaskInstance  # noqa: E402
from shopmate.knowledge.intents import KNOWLEDGE_INTENTS  # noqa: E402
from shopmate.plan.validator import TurnPlanValidator  # noqa: E402
from shopmate.task.command.models import (  # noqa: E402
    SetSlotsCommand,
    StartFlowCommand,
)
from shopmate.task.flow.loader import FlowLoader  # noqa: E402

FLOW_FILE = PROJECT_ROOT / "shopmate" / "flow_config" / "user_flows.yml"


def build_state(case: EvalCase) -> DialogueState:
    state = DialogueState(sender_id=f"eval-{case.id}")
    state.shared.start_session()

    if case.focused_object:
        state.shared.set_focused_object(
            FocusedObject(**case.focused_object)
        )

    if case.active_task:
        state.tasks.active = TaskInstance(
            flow_id=case.active_task["flow_id"],
            step_id=case.active_task.get("step_id"),
            slots=dict(case.active_task.get("slots", {})),
        )

    return state


def extract_decision(plan, validation, state) -> dict:
    if not validation.valid:
        return {
            "decision": "clarify",
            "reason": validation.reason.value
            if validation.reason
            else None,
        }

    if plan.task is not None:
        flow = None
        slots: dict = {}
        for command in plan.task.commands:
            if isinstance(command, StartFlowCommand):
                flow = command.flow
            elif isinstance(command, SetSlotsCommand):
                slots.update(command.slots)
        if flow is None and state.tasks.active is not None:
            flow = state.tasks.active.flow_id
        return {"decision": "task", "flow": flow, "slots": slots}

    if plan.knowledge is not None:
        return {
            "decision": "knowledge",
            "intents": sorted(plan.knowledge.intents),
        }

    return {"decision": "chitchat"}


def matches(expected, actual: dict) -> bool:
    if expected.decision != actual.get("decision"):
        return False
    if expected.flow is not None and actual.get("flow") != expected.flow:
        return False
    if expected.intents and sorted(
        actual.get("intents", [])
    ) != sorted(expected.intents):
        return False
    if expected.slots and actual.get("slots") != expected.slots:
        return False
    if (
        expected.reason is not None
        and actual.get("reason") != expected.reason
    ):
        return False
    return True


async def evaluate(cases: list[EvalCase], planner) -> list[EvalResult]:
    flows = FlowLoader().load(FLOW_FILE)
    validator = TurnPlanValidator()
    results: list[EvalResult] = []

    for case in cases:
        state = build_state(case)
        message = UserMessage(
            sender_id=state.sender_id,
            message_id=case.id,
            type=MessageType.TEXT,
            text=case.text,
        )
        plan = await planner.predict(
            state, message, flows, KNOWLEDGE_INTENTS
        )
        validation = validator.validate(
            plan, state, flows, KNOWLEDGE_INTENTS
        )
        actual = extract_decision(plan, validation, state)

        results.append(
            EvalResult(
                case_id=case.id,
                category=case.expected.decision,
                text=case.text,
                passed=matches(case.expected, actual),
                expected={
                    "decision": case.expected.decision,
                    "flow": case.expected.flow,
                    "intents": list(case.expected.intents),
                    "slots": case.expected.slots,
                    "reason": case.expected.reason,
                },
                actual=actual,
            )
        )

    return results


def build_planner(name: str):
    if name == "llm":
        from shopmate.plan.turn_planner import TurnPlanner

        return TurnPlanner()
    return RuleBasedPlanner()


def main() -> int:
    parser = argparse.ArgumentParser(description="ShopMate 离线评估")
    parser.add_argument(
        "--planner",
        choices=["rule", "llm"],
        default="rule",
        help="rule=离线 baseline，llm=真实模型（需要 LLM_API_KEY）",
    )
    parser.add_argument(
        "--min-accuracy", type=float, default=0.9
    )
    parser.add_argument(
        "--report", default="docs/eval-report.md"
    )
    args = parser.parse_args()

    cases = load_cases()
    results = __import__("asyncio").run(
        evaluate(cases, build_planner(args.planner))
    )
    summary = summarize(results)

    report = render_report(
        results,
        summary,
        planner_name=(
            "rule-based（离线 baseline）"
            if args.planner == "rule"
            else "LLM TurnPlanner"
        ),
    )
    report_path = PROJECT_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(
        f"cases={summary.total} passed={summary.passed} "
        f"accuracy={summary.accuracy:.3f} "
        f"clarify_rate={summary.clarify_rate:.3f} "
        f"false_accepts={summary.false_accepts}"
    )
    print(f"report={report_path}")

    if summary.accuracy < args.min_accuracy:
        print(
            f"FAIL: accuracy {summary.accuracy:.3f} "
            f"< threshold {args.min_accuracy:.3f}"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
