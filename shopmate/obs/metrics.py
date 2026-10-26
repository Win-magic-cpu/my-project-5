"""极简指标注册表：只实现项目用到的 Counter / Histogram。

不引入 prometheus_client，是为了让依赖保持精简；输出的就是标准
Prometheus 文本格式，采集端不需要区分实现。
"""

from dataclasses import dataclass, field

DEFAULT_BUCKETS = (
    0.01,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


def _label_key(labels: dict[str, str] | None) -> str:
    if not labels:
        return ""
    parts = ",".join(
        f'{key}="{value}"' for key, value in sorted(labels.items())
    )
    return "{" + parts + "}"


@dataclass
class Counter:
    name: str
    help: str
    values: dict[str, float] = field(default_factory=dict)

    def inc(
        self,
        labels: dict[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        key = _label_key(labels)
        self.values[key] = self.values.get(key, 0.0) + amount

    def value(self, labels: dict[str, str] | None = None) -> float:
        return self.values.get(_label_key(labels), 0.0)

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}",
                 f"# TYPE {self.name} counter"]
        for key, value in sorted(self.values.items()):
            lines.append(f"{self.name}{key} {value:g}")
        return lines


@dataclass
class Histogram:
    name: str
    help: str
    buckets: tuple[float, ...] = DEFAULT_BUCKETS
    counts: dict[str, list[int]] = field(default_factory=dict)
    sums: dict[str, float] = field(default_factory=dict)
    totals: dict[str, int] = field(default_factory=dict)

    def observe(
        self,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = _label_key(labels)
        bucket_counts = self.counts.setdefault(
            key, [0] * len(self.buckets)
        )
        for index, upper in enumerate(self.buckets):
            if value <= upper:
                bucket_counts[index] += 1
        self.sums[key] = self.sums.get(key, 0.0) + value
        self.totals[key] = self.totals.get(key, 0) + 1

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}",
                 f"# TYPE {self.name} histogram"]
        for key, bucket_counts in sorted(self.counts.items()):
            for index, upper in enumerate(self.buckets):
                labels = key[1:-1] if key else ""
                parts = f'{labels},le="{upper:g}"' if labels else f'le="{upper:g}"'
                lines.append(
                    f"{self.name}_bucket{{{parts}}} {bucket_counts[index]}"
                )
            total = self.totals.get(key, 0)
            labels = key[1:-1] if key else ""
            parts = f'{labels},le="+Inf"' if labels else 'le="+Inf"'
            lines.append(f"{self.name}_bucket{{{parts}}} {total}")
            lines.append(f"{self.name}_sum{key} {self.sums.get(key, 0.0):g}")
            lines.append(f"{self.name}_count{key} {total}")
        return lines


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, Counter] = {}
        self.histograms: dict[str, Histogram] = {}

    def counter(self, name: str, help_text: str) -> Counter:
        return self.counters.setdefault(
            name, Counter(name=name, help=help_text)
        )

    def histogram(
        self,
        name: str,
        help_text: str,
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> Histogram:
        return self.histograms.setdefault(
            name,
            Histogram(name=name, help=help_text, buckets=buckets),
        )

    def render(self) -> str:
        lines: list[str] = []
        for counter in self.counters.values():
            lines.extend(counter.render())
        for histogram in self.histograms.values():
            lines.extend(histogram.render())
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        self.counters.clear()
        self.histograms.clear()


REGISTRY = MetricsRegistry()


def record_turn(
    decision: str,
    total_ms: float,
    stages: dict[str, float],
) -> None:
    REGISTRY.counter(
        "shopmate_turns_total", "对话轮次总数（按最终决策）"
    ).inc({"decision": decision})
    REGISTRY.histogram(
        "shopmate_turn_duration_seconds", "单轮对话耗时"
    ).observe(total_ms / 1000)
    stage_histogram = REGISTRY.histogram(
        "shopmate_stage_duration_seconds", "各阶段耗时"
    )
    for name, duration_ms in stages.items():
        stage_histogram.observe(
            duration_ms / 1000, {"stage": name}
        )
