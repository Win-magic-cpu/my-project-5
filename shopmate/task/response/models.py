from dataclasses import dataclass
from enum import StrEnum


class ResponseMode(StrEnum):
    STATIC = "static"
    REPHRASE = "rephrase"
    GENERATE = "generate"


@dataclass
class ResponseTemplate:
    mode: ResponseMode = ResponseMode.STATIC
    text: str | None = None
    prompt: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ResponseTemplate":
        return cls(
            mode=ResponseMode(data.get("mode", ResponseMode.STATIC)),
            text=data.get("text"),
            prompt=data.get("prompt"),
        )
