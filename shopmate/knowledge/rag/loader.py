from pathlib import Path

from shopmate.knowledge.rag.models import DocumentChunk
from shopmate.knowledge.rag.splitter import MarkdownSplitter


def load_documents(
    directory: Path,
    splitter: MarkdownSplitter | None = None,
) -> list[DocumentChunk]:
    """读取目录下的 Markdown，并切分成带来源的 chunk。"""
    splitter = splitter or MarkdownSplitter()
    if not directory.exists():
        return []

    chunks: list[DocumentChunk] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chunks.extend(splitter.split(text, source=path.stem))

    return chunks
