import re
from dataclasses import dataclass

from shopmate.knowledge.rag.models import DocumentChunk

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class _Section:
    heading: str
    body: str


class MarkdownSplitter:
    """按标题切段，再按长度滑窗切分。

    每个 chunk 都带上所属标题路径，避免"切出来的一段话不知道在讲什么"。
    """

    def __init__(self, chunk_size: int = 240, overlap: int = 40) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须在 [0, chunk_size) 之间")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, source: str) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []

        for section in self._split_sections(text):
            for piece in self._split_body(section.body):
                content = (
                    f"{section.heading}\n{piece}"
                    if section.heading
                    else piece
                ).strip()
                if content:
                    chunks.append(
                        DocumentChunk(text=content, source=source)
                    )

        return chunks

    def _split_sections(self, text: str) -> list[_Section]:
        sections: list[_Section] = []
        stack: list[tuple[int, str]] = []
        body_lines: list[str] = []

        def flush() -> None:
            body = "\n".join(body_lines).strip()
            if body:
                heading = " > ".join(title for _, title in stack)
                sections.append(_Section(heading=heading, body=body))
            body_lines.clear()

        for line in text.splitlines():
            match = HEADING_PATTERN.match(line.strip())
            if match is None:
                body_lines.append(line)
                continue

            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))

        flush()
        return sections

    def _split_body(self, body: str) -> list[str]:
        body = body.strip()
        if len(body) <= self.chunk_size:
            return [body] if body else []

        pieces: list[str] = []
        start = 0
        while start < len(body):
            end = min(start + self.chunk_size, len(body))
            window = body[start:end]

            # 尽量在段落/句号处断开，读起来更自然
            if end < len(body):
                for separator in ("\n\n", "\n", "。", "；"):
                    cut = window.rfind(separator)
                    if cut > self.chunk_size // 2:
                        window = window[: cut + len(separator)]
                        end = start + len(window)
                        break

            pieces.append(window.strip())
            if end >= len(body):
                break

            start = max(end - self.overlap, start + 1)

        return [piece for piece in pieces if piece]
