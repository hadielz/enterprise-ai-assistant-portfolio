"""
Authenticated chat API routes.

Conversation ownership is now represented relationally through
users.id and conversations.user_id.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.config import settings
from app.security.rate_limit import enforce_rate_limit
from app.services.chat_service import (
    generate_response,
    stream_response,
)
from app.observability.context import preserve_iterator_context


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    Generate a complete authenticated response.
    """

    enforce_rate_limit(
        scope="chat.user",
        key=str(current_user["id"]),
        limit=settings.rate_limit_chat_limit,
        window_seconds=settings.rate_limit_chat_window_seconds,
    )

    result = generate_response(
        message=request.message,
        conversation_id=request.conversation_id,
        user_id=current_user["id"],
        session=session,
    )

    return ChatResponse(**result)


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    Stream an authenticated response.
    """

    enforce_rate_limit(
        scope="chat.user",
        key=str(current_user["id"]),
        limit=settings.rate_limit_chat_limit,
        window_seconds=settings.rate_limit_chat_window_seconds,
    )

    return StreamingResponse(
        preserve_iterator_context(
            stream_response(
                message=request.message,
                conversation_id=request.conversation_id,
                user_id=current_user["id"],
                session=session,
            )
        ),
        media_type="text/plain",
    )