from typing import Any

from shopmate.clients.http_client import get_http_client
from shopmate.conf.config import settings
from shopmate.domain.state import DialogueState
from shopmate.task.action.base import Action, ActionResult


class RecommendSimilarProductsAction(Action):
    """相似商品推荐：当前版本只取商品标题生成占位说明。

    接入真实推荐服务时，只需替换本文件内部的接口调用与结果整理逻辑。
    """

    name = "action_recommend_similar_products"

    async def run(
        self,
        state: DialogueState,
        action_kwargs: dict[str, Any],
    ) -> ActionResult:
        if state.tasks.active is None:
            return ActionResult()

        product_id = state.tasks.active.slots.get("product_id")
        label = product_id or "这件商品"

        url = f"{settings.commerce_api_base_url}/products/{product_id}"
        response = await get_http_client().get(url)
        response.raise_for_status()
        payload = response.json()["data"]

        if payload:
            title = str(payload.get("title") or "").strip()
            label = title or label

        summary = (
            f'我已经收到你对"{label}"的相似商品推荐需求。'
            "不过当前版本还没有接入正式的推荐系统，"
            "稍后可以继续补上这部分能力。"
        )
        return ActionResult(
            slot_updates={"recommendation_summary": summary}
        )
