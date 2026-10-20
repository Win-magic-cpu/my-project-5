from pathlib import Path

import yaml

from shopmate.task.flow.models import Flow, FlowCatalog, FlowSlot
from shopmate.task.flow.steps import CollectSlotStep, FlowStep


class FlowLoader:
    """把 YAML 配置加载成 FlowCatalog。"""

    def load(self, path: Path) -> FlowCatalog:
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        slots = self._load_slots(data.get("slots", {}))
        flows = self._load_flows(data.get("flows", {}), slots)
        return FlowCatalog(flows=flows, slots=slots)

    def load_many(self, paths: list[Path]) -> FlowCatalog:
        flows: dict[str, Flow] = {}
        slots: dict[str, FlowSlot] = {}

        for path in paths:
            catalog = self.load(path)
            flows.update(catalog.flows)
            slots.update(catalog.slots)

        return FlowCatalog(flows=flows, slots=slots)

    def _load_slots(
        self,
        slots_data: dict[str, dict],
    ) -> dict[str, FlowSlot]:
        slots: dict[str, FlowSlot] = {}
        for slot_name, slot_data in slots_data.items():
            slots[slot_name] = FlowSlot(**slot_data, name=slot_name)
        return slots

    def _load_flows(
        self,
        flows_data: dict[str, dict],
        slots: dict[str, FlowSlot],
    ) -> dict[str, Flow]:
        flows: dict[str, Flow] = {}
        for flow_id, flow_data in flows_data.items():
            flows[flow_id] = self._load_flow(flow_id, flow_data, slots)
        return flows

    def _load_flow(
        self,
        flow_id: str,
        flow_data: dict,
        slots: dict[str, FlowSlot],
    ) -> Flow:
        steps = [
            FlowStep.from_dict(step_data)
            for step_data in flow_data["steps"]
        ]
        flow_slots = [
            slots[step.slot_name]
            for step in steps
            if isinstance(step, CollectSlotStep)
        ]
        return Flow(
            id=flow_id,
            name=flow_data.get("name"),
            description=flow_data.get("description", ""),
            steps=steps,
            slots=flow_slots,
        )
