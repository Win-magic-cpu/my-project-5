from typing import Any

from pydantic import BaseModel, Field, model_validator


class ChatObject(BaseModel):
    type: str = Field(min_length=1)
    id: str = Field(min_length=1)
    title: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    sender_id: str = Field(min_length=1)
    text: str | None = None
    object: ChatObject | None = None
    message_id: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "ChatRequest":
        has_text = self.text is not None
        has_object = self.object is not None

        if has_text == has_object:
            raise ValueError("text 和 object 必须且只能传一个")

        if has_text and not (self.text or "").strip():
            raise ValueError("text 不能是空字符串或只包含空白字符")

        return self


class ChatBotMessage(BaseModel):
    text: str | None = None
    object: ChatObject | None = None


class ChatResponse(BaseModel):
    sender_id: str
    message_id: str
    messages: list[ChatBotMessage]


class HistoryMessage(BaseModel):
    role: str
    text: str | None = None
    object: ChatObject | None = None


class HistoryResponse(BaseModel):
    sender_id: str
    messages: list[HistoryMessage]
