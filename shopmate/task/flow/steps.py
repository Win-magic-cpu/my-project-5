from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from shopmate.task.flow.links import (
    ConditionalLink,
    FallbackLink,
    FlowStepLink,
    StaticLink,
)
from shopmate.task.response.models import ResponseTemplate


class FlowStepType(Enum):
    START = "start"
    ACTION = "action"
    RESPONSE = "response"
    COLLECT = "collect"
    END = "end"


@dataclass
class SlotValidation:
    condition: str
    failure_template: ResponseTemplate


@dataclass
class FlowStep:
    """Flow 中的一个执行节点（父类，保存公共字段）。"""

    id: str
    type: FlowStepType
    next: list[FlowStepLink] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_dict(cls, step_data: dict[str, Any]) -> "FlowStep":
        step_class = STEP_TYPE_TO_CLASS[step_data["type"]]
        return step_class.from_dict(step_data)

    @staticmethod
    def base_fields(step_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": step_data["id"],
            "type": FlowStepType(step_data["type"]),
            "description": step_data.get("description", ""),
            "next": FlowStep.build_links(step_data.get("next", [])),
        }

    @staticmethod
    def build_links(
        next_data: str | list,
    ) -> list[FlowStepLink]:
        if isinstance(next_data, str):
            return [StaticLink(target=next_data)]

        links: list[FlowStepLink] = []
        for link_data in next_data:
            if "if" in link_data:
                links.append(
                    ConditionalLink(
                        target=link_data["then"],
                        condition=link_data["if"],
                    )
                )
            else:
                links.append(FallbackLink(target=link_data["else"]))
        return links


@dataclass
class StartFlowStep(FlowStep):
    @classmethod
    def from_dict(cls, step_data: dict[str, Any]) -> "StartFlowStep":
        return cls(**FlowStep.base_fields(step_data))


@dataclass
class ActionFlowStep(FlowStep):
    action: str = ""
    args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, step_data: dict[str, Any]) -> "ActionFlowStep":
        return cls(
            **FlowStep.base_fields(step_data),
            action=step_data["action"],
            args=step_data.get("args", {}),
        )


@dataclass
class ResponseFlowStep(FlowStep):
    template: ResponseTemplate = field(default_factory=ResponseTemplate)

    @classmethod
    def from_dict(cls, step_data: dict[str, Any]) -> "ResponseFlowStep":
        return cls(
            **FlowStep.base_fields(step_data),
            template=ResponseTemplate.from_dict(
                step_data.get("template", {})
            ),
        )


@dataclass
class CollectSlotStep(FlowStep):
    slot_name: str = ""
    template: ResponseTemplate = field(default_factory=ResponseTemplate)
    validation: SlotValidation | None = None

    @classmethod
    def from_dict(cls, step_data: dict[str, Any]) -> "CollectSlotStep":
        validation = None
        if "validation" in step_data:
            validation_data = step_data["validation"]
            validation = SlotValidation(
                condition=validation_data["condition"],
                failure_template=ResponseTemplate.from_dict(
                    validation_data["failure_template"]
                ),
            )

        return cls(
            **FlowStep.base_fields(step_data),
            slot_name=step_data["slot_name"],
            template=ResponseTemplate.from_dict(
                step_data["template"]
            ),
            validation=validation,
        )


@dataclass
class EndFlowStep(FlowStep):
    @classmethod
    def from_dict(cls, step_data: dict[str, Any]) -> "EndFlowStep":
        return cls(**FlowStep.base_fields(step_data))


STEP_TYPE_TO_CLASS: dict[str, type[FlowStep]] = {
    "start": StartFlowStep,
    "collect": CollectSlotStep,
    "action": ActionFlowStep,
    "response": ResponseFlowStep,
    "end": EndFlowStep,
}
