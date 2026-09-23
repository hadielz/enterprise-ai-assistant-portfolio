"""
PostgreSQL conversation repository.

Architecture Notes
------------------
Purpose:
    Centralize relational persistence for conversations, messages,
    and conversation summaries.

Ownership:
    Every operation requires both:
    - authenticated user ID
    - public conversation ID

This prevents one user from reading or modifying another user's data.

API isolation:
    HTTP routes and LangGraph nodes should not contain SQLAlchemy
    query details. They call this repository instead.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Conversation, Message


def utc_now() -> datetime:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


def get_conversation(
    session: Session,
    user_id: int,
    public_id: str,
) -> Conversation | None:
    """
    Retrieve one conversation owned by one user.
    """

    statement = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.public_id == public_id,
        )
        .options(selectinload(Conversation.messages))
    )

    return session.scalar(statement)


def get_or_create_conversation(
    session: Session,
    user_id: int,
    public_id: str,
) -> Conversation:
    """
    Retrieve an existing conversation or create a new one.
    """

    normalized_public_id = public_id.strip()

    if not normalized_public_id:
        raise ValueError("Conversation ID cannot be empty.")

    conversation = get_conversation(
        session=session,
        user_id=user_id,
        public_id=normalized_public_id,
    )

    if conversation is not None:
        return conversation

    conversation = Conversation(
        user_id=user_id,
        public_id=normalized_public_id,
        summary="",
    )

    session.add(conversation)
    session.flush()

    return conversation


def add_message(
    session: Session,
    user_id: int,
    public_id: str,
    role: str,
    content: str,
    *,
    commit: bool = True,
) -> Message:
    """
    Add one message to a user-owned conversation.
    """

    if role not in {"user", "assistant"}:
        raise ValueError(f"Unsupported message role: {role}")

    conversation = get_or_create_conversation(
        session=session,
        user_id=user_id,
        public_id=public_id,
    )

    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
    )

    conversation.updated_at = utc_now()
    session.add(message)

    if commit:
        session.commit()
        session.refresh(message)
    else:
        session.flush()

    return message


def add_exchange(
    session: Session,
    user_id: int,
    public_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """
    Persist one complete user/assistant exchange atomically.
    """

    conversation = get_or_create_conversation(
        session=session,
        user_id=user_id,
        public_id=public_id,
    )

    session.add_all(
        [
            Message(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            ),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_message,
            ),
        ]
    )

    conversation.updated_at = utc_now()
    session.commit()


def get_recent_messages(
    session: Session,
    user_id: int,
    public_id: str,
    max_messages: int = 6,
) -> list[dict]:
    """
    Return the newest messages in chronological order.
    """

    conversation = get_conversation(
        session=session,
        user_id=user_id,
        public_id=public_id,
    )

    if conversation is None:
        return []

    statement = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(max_messages)
    )

    messages = list(session.scalars(statement))
    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]


def get_full_history(
    session: Session,
    user_id: int,
    public_id: str,
) -> list[dict]:
    """
    Return the complete conversation transcript.
    """

    conversation = get_conversation(
        session=session,
        user_id=user_id,
        public_id=public_id,
    )

    if conversation is None:
        return []

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in conversation.messages
    ]


def get_summary(
    session: Session,
    user_id: int,
    public_id: str,
) -> str:
    """
    Return the stored conversation summary.
    """

    conversation = get_conversation(
        session=session,
        user_id=user_id,
        public_id=public_id,
    )

    if conversation is None:
        return ""

    return conversation.summary


def set_summary(
    session: Session,
    user_id: int,
    public_id: str,
    summary: str,
) -> None:
    """
    Update a conversation summary.
    """

    conversation = get_or_create_conversation(
        session=session,
        user_id=user_id,
        public_id=public_id,
    )

    conversation.summary = summary
    conversation.updated_at = utc_now()

    session.commit()


def conversation_exists(
    session: Session,
    user_id: int,
    public_id: str,
) -> bool:
    """
    Check whether a user owns the specified conversation.
    """

    statement = select(
        select(Conversation.id)
        .where(
            Conversation.user_id == user_id,
            Conversation.public_id == public_id,
        )
        .exists()
    )

    return bool(session.scalar(statement))


def list_conversations(
    session: Session,
    user_id: int,
) -> list[dict]:
    """
    Return lightweight conversation-list entries for one user.
    """

    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )

    conversations = list(session.scalars(statement))
    items = []

    for conversation in conversations:
        first_user_message_statement = (
            select(Message.content)
            .where(
                Message.conversation_id == conversation.id,
                Message.role == "user",
            )
            .order_by(Message.id)
            .limit(1)
        )

        preview = session.scalar(first_user_message_statement) or ""

        message_count_statement = select(
            func.count(Message.id)
        ).where(
            Message.conversation_id == conversation.id
        )

        message_count = session.scalar(
            message_count_statement
        ) or 0

        items.append(
            {
                "conversation_id": conversation.public_id,
                "preview": preview[:80],
                "message_count": message_count,
            }
        )

    return items


def delete_conversation(
    session: Session,
    user_id: int,
    public_id: str,
) -> bool:
    """
    Delete one user-owned conversation.

    Message rows are removed through the database cascade.
    """

    statement = (
        delete(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.public_id == public_id,
        )
        .returning(Conversation.id)
    )

    deleted_id = session.scalar(statement)

    if deleted_id is None:
        session.rollback()
        return False

    session.commit()
    return True