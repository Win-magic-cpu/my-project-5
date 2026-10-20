import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from shopmate.clients.http_client import get_http_client
from shopmate.conf.config import settings
from shopmate.domain.messages import UserMessage
from shopmate.domain.state import DialogueState
from shopmate.knowledge.faq_data import DOC_SNIPPETS, FAQ_ENTRIES


@dataclass
class KnowledgeChunk:
    """一段可以提供给大模型的知识内容。"""

    content: str


class KnowledgeProvider(ABC):
    """统一的知识检索接口。"""

    provider_id = ""

    @abstractmethod
    async def retrieve(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        pass


class ProductAPIProvider(KnowledgeProvider):
    provider_id = "api.product"

    async def retrieve(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        focused_object = state.shared.focused_object
        if focused_object is None:
            raise ValueError("商品信息咨询需要先聚焦一个商品。")

        data: dict[str, Any] = (
            await self._get_product_info_by_id(focused_object.id)
        )
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return [KnowledgeChunk(content=f"商品信息:\n{text}")]

    async def _get_product_info_by_id(
        self,
        product_id: str,
    ) -> dict[str, Any]:
        url = f"{settings.commerce_api_base_url}/products/{product_id}"
        response = await get_http_client().get(url)
        response.raise_for_status()
        return response.json()["data"]


class OrderAPIProvider(KnowledgeProvider):
    provider_id = "api.order"

    async def retrieve(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        focused_object = state.shared.focused_object
        if focused_object is None:
            raise ValueError("订单信息咨询需要先聚焦一个订单。")

        order_number = focused_object.id
        order_payload, logistics_payload = await asyncio.gather(
            self._fetch_order(order_number),
            self._fetch_logistics(order_number),
        )

        content = json.dumps(
            {
                "order_number": order_number,
                "order": order_payload,
                "logistics": logistics_payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        return [KnowledgeChunk(content=f"订单与物流信息：\n{content}")]

    async def _fetch_order(self, order_number: str) -> dict[str, Any]:
        url = f"{settings.commerce_api_base_url}/orders/{order_number}"
        response = await get_http_client().get(url)
        response.raise_for_status()
        return response.json()["data"]

    async def _fetch_logistics(
        self,
        order_number: str,
    ) -> dict[str, Any]:
        url = (
            f"{settings.commerce_api_base_url}"
            f"/orders/{order_number}/logistics"
        )
        response = await get_http_client().get(url)
        response.raise_for_status()
        return response.json().get("data", {})


def _match_entries(
    entries: list[dict[str, object]],
    query: str,
    limit: int = 2,
) -> list[dict[str, object]]:
    """按关键词命中数做最简单的相关性排序。"""
    scored: list[tuple[int, dict[str, object]]] = []
    for entry in entries:
        keywords = entry.get("keywords", [])
        score = sum(1 for keyword in keywords if str(keyword) in query)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


class FAQProvider(KnowledgeProvider):
    provider_id = "faq.default"

    async def retrieve(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        query = (user_message.text or "").strip()
        matches = _match_entries(FAQ_ENTRIES, query)
        if not matches:
            return [KnowledgeChunk(content="未检索到相关常见问题")]

        return [
            KnowledgeChunk(
                content=f"Q: {entry['question']}\nA: {entry['answer']}"
            )
            for entry in matches
        ]


class RAGProvider(KnowledgeProvider):
    provider_id = "rag.default"

    async def retrieve(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        query = (user_message.text or "").strip()
        matches = _match_entries(DOC_SNIPPETS, query)
        if not matches:
            return [KnowledgeChunk(content="未检索到相关文档知识")]

        return [
            KnowledgeChunk(
                content=f"《{entry['title']}》\n{entry['content']}"
            )
            for entry in matches
        ]
