"""检索增强（RAG）：文档加载、切分、向量化与检索。"""

from shopmate.knowledge.rag.embedding import (
    DashScopeEmbedding,
    EmbeddingModel,
    HashingEmbedding,
)
from shopmate.knowledge.rag.loader import load_documents
from shopmate.knowledge.rag.models import (
    DocumentChunk,
    IndexedChunk,
    SearchHit,
)
from shopmate.knowledge.rag.splitter import MarkdownSplitter
from shopmate.knowledge.rag.store import VectorStore

__all__ = [
    "DashScopeEmbedding",
    "DocumentChunk",
    "EmbeddingModel",
    "HashingEmbedding",
    "IndexedChunk",
    "MarkdownSplitter",
    "SearchHit",
    "VectorStore",
    "load_documents",
]
