import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    case_id: str
    category: str
    text: str
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]


@dataclass
class Summary:
    total: int = 0
    passed: int = 0
    by_category: dict[str, list[int]] = field(default_factory=dict)
    clarify_rate: float = 0.0
    false_accepts: int = 0

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


def summarize(results: list[EvalResult]) -> Summary:
    summary = Summary(total=len(results))
    clarify_hits = 0

    for result in results:
        if result.passed:
            summary.passed += 1

        bucket = summary.by_category.setdefault(result.category, [0, 0])
        bucket[1] += 1
        if result.passed:
            bucket[0] += 1

        if result.actual.get("decision") == "clarify":
            clarify_hits += 1
        if (
            result.expected.get("decision") == "clarify"
            and result.actual.get("decision") != "clarify"
        ):
            summary.false_accepts += 1

    summary.clarify_rate = (
        clarify_hits / summary.total if summary.total else 0.0
    )
    return summary


def _format(payload: dict[str, Any]) -> str:
    parts = [str(payload.get("decision"))]
    if payload.get("flow"):
        parts.append(f"flow={payload['flow']}")
    if payload.get("intents"):
        parts.append(f"intents={','.join(payload['intents'])}")
    if payload.get("slots"):
        parts.append(
            "slots="
            + json.dumps(payload["slots"], ensure_ascii=False)
        )
    if payload.get("reason"):
        parts.append(f"reason={payload['reason']}")
    return " / ".join(parts)


def render_report(
    results: list[EvalResult],
    summary: Summary,
    planner_name: str,
) -> str:
    lines: list[str] = [
        "# 离线评估报告",
        "",
        f"- 预测器：{planner_name}",
        f"- 用例数：{summary.total}",
        f"- 通过数：{summary.passed}",
        f"- 决策准确率：{summary.accuracy:.1%}",
        f"- 澄清率：{summary.clarify_rate:.1%}",
        f"- 错误接受（应澄清却放行）：{summary.false_accepts}",
        "",
        "## 分类准确率",
        "",
        "| 类别 | 用例 | 通过 | 准确率 |",
        "| --- | ---: | ---: | ---: |",
    ]

    for category in ("task", "knowledge", "chitchat", "clarify"):
        if category not in summary.by_category:
            continue
        passed, total = summary.by_category[category]
        lines.append(
            f"| {category} | {total} | {passed} | {passed / total:.0%} |"
        )

    failures = [result for result in results if not result.passed]
    lines.extend(["", "## 失败用例", ""])

    if not failures:
        lines.append("无。")
    else:
        lines.extend(
            [
                "| id | 输入 | 期望 | 实际 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for result in failures:
            lines.append(
                "| {id} | {text} | {expected} | {actual} |".format(
                    id=result.case_id,
                    text=result.text,
                    expected=_format(result.expected),
                    actual=_format(result.actual),
                )
            )

    return "\n".join(lines) + "\n"
