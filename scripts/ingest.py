"""重建 RAG 索引。

用法：
    uv run python scripts/ingest.py

索引文件路径由 RAG_INDEX_PATH 决定（默认 data/rag_index.json）。
切换 embedding 模型后需要重新执行一次，否则会因模型不一致而重建。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopmate.knowledge.rag.factory import (  # noqa: E402
    KNOWLEDGE_DIR,
    build_embedding,
    resolve_index_path,
)
from shopmate.knowledge.rag.loader import load_documents  # noqa: E402
from shopmate.knowledge.rag.store import VectorStore  # noqa: E402


async def main() -> None:
    embedding = build_embedding()
    chunks = load_documents(KNOWLEDGE_DIR)
    if not chunks:
        print(f"没有找到文档：{KNOWLEDGE_DIR}")
        return

    store = await VectorStore.build(chunks, embedding)
    path = resolve_index_path()
    store.save(path)

    print(f"模型：{embedding.name}")
    print(f"片段：{len(chunks)}")
    print(f"索引：{path}")


if __name__ == "__main__":
    asyncio.run(main())
