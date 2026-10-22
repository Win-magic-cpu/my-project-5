import uuid

from fastapi import APIRouter, Depends, Query

from shopmate.api.dependencies import get_dialogue_service
from shopmate.api.schemas import (
    ChatBotMessage,
    ChatObject,
    ChatRequest,
    ChatResponse,
    HistoryMessage,
    HistoryResponse,
)
from shopmate.domain.messages import (
    MessageObject,
    MessageType,
    ProcessResult,
    UserMessage,
)
from shopmate.domain.state import DialogueState
from shopmate.service.dialogue_service import DialogueService

chat_router = APIRouter(tags=["chat"])


@chat_router.post("/api/chat")
async def chat(
    chat_request: ChatRequest,
    dialogue_service: DialogueService = Depends(get_dialogue_service),
) -> ChatResponse:
    user_message = _build_user_message(chat_request)
    process_result = await dialogue_service.process_message(user_message)
    return _build_chat_response(process_result)


@chat_router.get("/api/chat/history")
async def history(
    sender_id: str,
    limit: int = Query(50, ge=1, le=200, description="每页条数"),
    offset: int = Query(0, ge=0, description="跳过的条数"),
    dialogue_service: DialogueService = Depends(get_dialogue_service),
) -> HistoryResponse:
    state = await dialogue_service.get_state(sender_id)
    messages = _expand_history(state)
    total = len(messages)
    page = messages[offset : offset + limit]

    return HistoryResponse(
        sender_id=sender_id,
        messages=page,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(page) < total,
    )


def _expand_history(state: DialogueState) -> list[HistoryMessage]:
    """把 Sessions/Turns 展开成一维消息列表，顺序即前端展示顺序。"""
    messages: list[HistoryMessage] = []

    for session in state.shared.sessions:
        for turn in session.turns:
            messages.append(
                HistoryMessage(
                    role="user",
                    text=turn.user_message.text,
                    object=_build_chat_object(turn.user_message.object),
                )
            )
            messages.extend(
                [
                    HistoryMessage(
                        role="bot",
                        text=message.text,
                        object=_build_chat_object(message.object),
                    )
                    for message in turn.bot_messages
                ]
            )

    return messages


def _build_user_message(chat_request: ChatRequest) -> UserMessage:
    return UserMessage(
        sender_id=chat_request.sender_id,
        message_id=chat_request.message_id or str(uuid.uuid4()),
        type=(
            MessageType.TEXT
            if chat_request.text is not None
            else MessageType.OBJECT
        ),
        text=chat_request.text,
        object=(
            MessageObject(
                type=chat_request.object.type,
                id=chat_request.object.id,
                title=chat_request.object.title,
                attributes=dict(chat_request.object.attributes),
            )
            if chat_request.object is not None
            else None
        ),
    )


def _build_chat_response(process_result: ProcessResult) -> ChatResponse:
    return ChatResponse(
        sender_id=process_result.sender_id,
        message_id=process_result.message_id,
        messages=[
            ChatBotMessage(
                text=message.text,
                object=_build_chat_object(message.object),
            )
            for message in process_result.messages
        ],
    )


def _build_chat_object(
    message_object: MessageObject | None,
) -> ChatObject | None:
    if message_object is None:
        return None

    return ChatObject(
        type=message_object.type,
        id=message_object.id,
        title=message_object.title,
        attributes=dict(message_object.attributes),
    )
