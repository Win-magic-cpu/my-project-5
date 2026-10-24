import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from shopmate.knowledge.rag.embedding import EmbeddingModel
from shopmate.knowledge.rag.models import (
    DocumentChunk,
    IndexedChunk,
    SearchHit,
)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


@dataclass
class VectorStore:
    """极简向量索引：内存里算余弦，可序列化到 JSON。

    数据量在几百个 chunk 以内时足够；要上规模再换 pgvector / Chroma，
    接口（build / search）保持不变。
    """

    model: str
    items: list[IndexedChunk] = field(default_factory=list)

    @classmethod
    async def build(
        cls,
        chunks: list[DocumentChunk],
        embedding: EmbeddingModel,
    ) -> "VectorStore":
        vectors = await embedding.embed([chunk.text for chunk in chunks])
        items = [
            IndexedChunk(
                text=chunk.text,
                source=chunk.source,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        return cls(model=embedding.name, items=items)

    async def search(
        self,
        query: str,
        embedding: EmbeddingModel,
        top_k: int = 3,
    ) -> list[SearchHit]:
        if not self.items or not query.strip():
            return []

        query_vector = (await embedding.embed([query]))[0]
        scored = [
            (_cosine(query_vector, item.embedding), item)
            for item in self.items
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [
            SearchHit(
                chunk=DocumentChunk(text=item.text, source=item.source),
                score=score,
            )
            for score, item in scored[:top_k]
        ]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "dim": len(self.items[0].embedding) if self.items else 0,
            "items": [
                {
                    "text": item.text,
                    "source": item.source,
                    "embedding": item.embedding,
                }
                for item in self.items
            ],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path, model: str) -> "VectorStore | None":
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if payload.get("model") != model:
            # 换了 embedding 模型，旧索引不可用，交给调用方重建
            return None

        items = [
            IndexedChunk(
                text=item["text"],
                source=item["source"],
                embedding=list(item["embedding"]),
            )
            for item in payload.get("items", [])
        ]
        return cls(model=model, items=items)
