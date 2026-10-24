from pathlib import Path

from shopmate.conf.config import PROJECT_ROOT, settings
from shopmate.knowledge.rag.embedding import (
    DashScopeEmbedding,
    EmbeddingModel,
    HashingEmbedding,
)

KNOWLEDGE_DIR = PROJECT_ROOT / "docs" / "knowledge"


def build_embedding() -> EmbeddingModel:
    """按配置选择向量模型：auto 时有 Key 用 DashScope，否则本地哈希。"""
    provider = settings.embedding_provider.strip().lower()

    if provider == "hashing":
        return HashingEmbedding(dim=settings.embedding_dim)
    if provider == "dashscope":
        return DashScopeEmbedding()
    if settings.llm_api_key:
        return DashScopeEmbedding()
    return HashingEmbedding(dim=settings.embedding_dim)


def resolve_index_path() -> Path:
    path = Path(settings.rag_index_path)
    return path if path.is_absolute() else PROJECT_ROOT / path
