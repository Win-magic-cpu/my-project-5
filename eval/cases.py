import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GOLDEN_FILE = Path(__file__).resolve().parent / "golden.jsonl"

DECISIONS = {"task", "knowledge", "chitchat", "clarify"}


@dataclass(frozen=True)
class Expected:
    decision: str
    flow: str | None = None
    intents: tuple[str, ...] = ()
    slots: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


@dataclass(frozen=True)
class EvalCase:
    id: str
    text: str
    expected: Expected
    focused_object: dict[str, Any] | None = None
    active_task: dict[str, Any] | None = None


def _parse_case(raw: dict[str, Any]) -> EvalCase:
    expected_raw = raw["expected"]
    decision = expected_raw["decision"]
    if decision not in DECISIONS:
        raise ValueError(f"{raw['id']}: 未知决策 {decision}")

    return EvalCase(
        id=raw["id"],
        text=raw["text"],
        expected=Expected(
            decision=decision,
            flow=expected_raw.get("flow"),
            intents=tuple(expected_raw.get("intents", [])),
            slots=dict(expected_raw.get("slots", {})),
            reason=expected_raw.get("reason"),
        ),
        focused_object=raw.get("focused_object"),
        active_task=raw.get("active_task"),
    )


def load_cases(path: Path | None = None) -> list[EvalCase]:
    path = path or GOLDEN_FILE
    cases: list[EvalCase] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(_parse_case(json.loads(line)))

    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("golden set 中存在重复 id")

    return cases
