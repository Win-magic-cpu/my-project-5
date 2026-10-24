from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentChunk:
    """切分后的一段文档，source 保留来源文件名/标题。"""

    text: str
    source: str


@dataclass(frozen=True)
class IndexedChunk:
    text: str
    source: str
    embedding: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class SearchHit:
    chunk: DocumentChunk
    score: float
