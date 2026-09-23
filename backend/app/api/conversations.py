"""
PostgreSQL-backed authenticated conversation-history routes.

Every query is scoped by the authenticated user's database ID.
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.conversation_repository import (
    delete_conversation,
    get_conversation,
    list_conversations,
)
from app.database.session import get_db_session
from app.schemas.conversation import (
    ConversationDetail,
    ConversationMessage,
    ConversationSummaryItem,
)


router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
)


@router.get("", response_model=list[ConversationSummaryItem])
def read_conversation_list(
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    List conversations owned by the authenticated user.
    """

    return [
        ConversationSummaryItem(**item)
        for item in list_conversations(
            session=session,
            user_id=current_user["id"],
        )
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
def read_conversation(
    conversation_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    Open one user-owned conversation.
    """

    conversation = get_conversation(
        session=session,
        user_id=current_user["id"],
        public_id=conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return ConversationDetail(
        conversation_id=conversation.public_id,
        messages=[
            ConversationMessage(
                role=message.role,
                content=message.content,
            )
            for message in conversation.messages
        ],
        summary=conversation.summary,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_conversation(
    conversation_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    Delete one user-owned conversation.
    """

    was_deleted = delete_conversation(
        session=session,
        user_id=current_user["id"],
        public_id=conversation_id,
    )

    if not was_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)