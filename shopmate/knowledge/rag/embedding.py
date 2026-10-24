import hashlib
import math
import re
from typing import Protocol

from shopmate.clients.http_client import get_http_client
from shopmate.conf.config import settings

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
WORD_PATTERN = re.compile(r"[a-z0-9]+")


class EmbeddingModel(Protocol):
    """向量化接口：同一个向量空间里才能比较相似度。"""

    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class HashingEmbedding:
    """特征哈希向量，零依赖、确定性，用于离线演示与单元测试。

    中文按字 bigram、英文按词，映射到固定维度后做 L2 归一化。
    它不理解语义，只反映字面重合度，因此生产环境应换成真实 embedding。
    """

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("dim 必须大于 0")
        self.dim = dim
        self.name = f"hashing-{dim}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim

        for token in self._tokenize(text):
            digest = hashlib.blake2b(
                token.encode("utf-8"), digest_size=8
            ).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        lowered = text.lower()
        characters = CJK_PATTERN.findall(lowered)
        bigrams = [
            characters[index] + characters[index + 1]
            for index in range(len(characters) - 1)
        ]
        words = WORD_PATTERN.findall(lowered)
        return bigrams + words


class DashScopeEmbedding:
    """DashScope 的 OpenAI 兼容向量接口。"""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or settings.embedding_model
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.name = f"dashscope-{self.model}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError(
                "未配置 LLM_API_KEY，无法调用 DashScope 向量接口"
            )

        response = await get_http_client().post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "input": texts,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        payload = response.json()["data"]
        payload.sort(key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in payload]
