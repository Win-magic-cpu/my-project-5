from dataclasses import dataclass, field

from shopmate.task.flow.steps import FlowStep, FlowStepType


@dataclass
class FlowSlot:
    """Flow 可以使用的业务字段定义。"""

    name: str
    type: str = "any"
    label: str = ""
    description: str = ""


@dataclass
class Flow:
    """一项完整任务：基本信息 + Steps + 使用的 Slots。"""

    id: str
    description: str = ""
    steps: list[FlowStep] = field(default_factory=list)
    slots: list[FlowSlot] = field(default_factory=list)
    name: str | None = None

    def get_start_step(self) -> FlowStep:
        for step in self.steps:
            if step.type is FlowStepType.START:
                return step
        raise ValueError(f"Flow {self.id} 缺少 start Step")

    def get_step(self, step_id: str) -> FlowStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise ValueError(f"Flow {self.id} 中不存在 Step {step_id}")


@dataclass
class FlowCatalog:
    """所有 Flow 与 Slot 的集合。"""

    flows: dict[str, Flow] = field(default_factory=dict)
    slots: dict[str, FlowSlot] = field(default_factory=dict)

    def get_flow(self, flow_id: str) -> Flow:
        return self.flows[flow_id]
