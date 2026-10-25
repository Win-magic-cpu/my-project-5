import pytest

from eval.cases import DECISIONS, Expected, load_cases
from eval.metrics import EvalResult, render_report, summarize
from eval.predictor import RuleBasedPlanner
from eval.run_eval import evaluate, matches
from shopmate.plan.models import ClarifyReason


def test_golden_set_is_well_formed():
    cases = load_cases()

    assert len(cases) == 40
    assert len({case.id for case in cases}) == 40
    assert all(case.expected.decision in DECISIONS for case in cases)
    assert sum(
        1 for case in cases if case.expected.decision == "clarify"
    ) == 6


@pytest.mark.asyncio
async def test_evaluate_covers_each_track():
    wanted = {"t-order-01", "k-refund-01", "c-hello-01", "cl-empty-01"}
    cases = [case for case in load_cases() if case.id in wanted]

    results = await evaluate(cases, RuleBasedPlanner())

    assert len(results) == 4
    assert all(result.passed for result in results)
    assert {result.category for result in results} == {
        "task",
        "knowledge",
        "chitchat",
        "clarify",
    }


@pytest.mark.asyncio
async def test_full_eval_meets_threshold_and_never_false_accepts():
    results = await evaluate(load_cases(), RuleBasedPlanner())
    summary = summarize(results)

    assert summary.total == 40
    assert summary.accuracy >= 0.9
    # 安全指标：没把握时应澄清，不能放行
    assert summary.false_accepts == 0


def test_summarize_counts_by_category():
    results = [
        EvalResult("a", "task", "x", True, {"decision": "task"}, {"decision": "task"}),
        EvalResult("b", "task", "y", False, {"decision": "task"}, {"decision": "clarify"}),
        EvalResult("c", "clarify", "z", True, {"decision": "clarify"}, {"decision": "clarify"}),
    ]

    summary = summarize(results)

    assert summary.total == 3
    assert summary.passed == 2
    assert summary.accuracy == pytest.approx(2 / 3)
    assert summary.by_category["task"] == [1, 2]
    assert summary.clarify_rate == pytest.approx(2 / 3)


def test_matches_compares_flow_intents_slots_and_reason():
    case = load_cases()[0]
    assert matches(case.expected, {"decision": "task", "flow": "order_status_query"})

    assert not matches(
        case.expected, {"decision": "task", "flow": "refund_request"}
    )
    assert not matches(
        Expected(decision="knowledge", intents=("refund_policy",)),
        {"decision": "knowledge", "intents": ["return_policy"]},
    )
    assert not matches(
        Expected(
            decision="task",
            flow="order_status_query",
            slots={"order_number": "A1001"},
        ),
        {
            "decision": "task",
            "flow": "order_status_query",
            "slots": {"order_number": "A1002"},
        },
    )
    assert not matches(
        Expected(
            decision="clarify",
            reason=ClarifyReason.MISSING_TRACK.value,
        ),
        {"decision": "clarify", "reason": "multiple_tracks"},
    )


def test_report_contains_summary_and_failures():
    results = [
        EvalResult("a", "task", "查订单", False, {"decision": "task"}, {"decision": "clarify", "reason": "missing_track"}),
    ]
    summary = summarize(results)
    report = render_report(results, summary, planner_name="rule-based")

    assert "决策准确率：0.0%" in report
    assert "| task | 1 | 0 | 0% |" in report
    assert "a | 查订单" in report
    assert "clarify" in report
