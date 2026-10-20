from typing import Any

from shopmate.clients.http_client import get_http_client
from shopmate.conf.config import settings
from shopmate.domain.state import DialogueState
from shopmate.task.action.base import Action, ActionResult


class LookupLogisticsAction(Action):
    name = "action_lookup_logistics"

    async def run(
        self,
        state: DialogueState,
        action_kwargs: dict[str, Any],
    ) -> ActionResult:
        if state.tasks.active is None:
            return ActionResult()

        order_number = state.tasks.active.slots.get("order_number")
        url = (
            f"{settings.commerce_api_base_url}"
            f"/orders/{order_number}/logistics"
        )
        response = await get_http_client().get(url)
        response.raise_for_status()
        payload = response.json().get("data", {})

        return ActionResult(
            slot_updates={
                "tracking_number": payload.get("tracking_number") or "未知",
                "logistics_company": (
                    payload.get("logistics_company") or "未知"
                ),
                "logistics_status": (
                    payload.get("status_desc")
                    or payload.get("status")
                    or "未知"
                ),
            }
        )
