"""
Conversation-repository integration tests.

These tests exercise real PostgreSQL constraints, transactions,
relationships, and cascade behavior.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.auth.user_storage import create_user
from app.database.conversation_repository import (
    add_exchange,
    add_message,
    conversation_exists,
    delete_conversation,
    get_full_history,
    get_recent_messages,
    get_summary,
    list_conversations,
    set_summary,
)
from app.database.models import Conversation, Message


def create_database_user(
    session: Session,
    username: str,
) -> dict:
    """
    Create a user directly for repository-level tests.
    """

    return create_user(
        session=session,
        username=username,
        display_name=username.title(),
        password_hash=hash_password(
            "secure-password-123"
        ),
    )


def test_add_exchange_creates_conversation_and_messages(
    db_session: Session,
):
    user = create_database_user(
        db_session,
        "repository-user",
    )

    add_exchange(
        session=db_session,
        user_id=user["id"],
        public_id="conversation-1",
        user_message="Hello",
        assistant_message="Hello! How can I help?",
    )

    conversations = list_conversations(
        session=db_session,
        user_id=user["id"],
    )

    assert conversations == [
        {
            "conversation_id": "conversation-1",
            "preview": "Hello",
            "message_count": 2,
        }
    ]

    history = get_full_history(
        session=db_session,
        user_id=user["id"],
        public_id="conversation-1",
    )

    assert history == [
        {
            "role": "user",
            "content": "Hello",
        },
        {
            "role": "assistant",
            "content": "Hello! How can I help?",
        },
    ]


def test_add_message_appends_in_order(
    db_session: Session,
):
    user = create_database_user(
        db_session,
        "ordered-user",
    )

    add_message(
        session=db_session,
        user_id=user["id"],
        public_id="ordered-conversation",
        role="user",
        content="First",
    )

    add_message(
        session=db_session,
        user_id=user["id"],
        public_id="ordered-conversation",
        role="assistant",
        content="Second",
    )

    history = get_full_history(
        session=db_session,
        user_id=user["id"],
        public_id="ordered-conversation",
    )

    assert [item["content"] for item in history] == [
        "First",
        "Second",
    ]


def test_recent_messages_returns_chronological_tail(
    db_session: Session,
):
    user = create_database_user(
        db_session,
        "recent-user",
    )

    for index in range(8):
        add_message(
            session=db_session,
            user_id=user["id"],
            public_id="recent-conversation",
            role="user" if index % 2 == 0 else "assistant",
            content=f"Message {index}",
        )

    recent_messages = get_recent_messages(
        session=db_session,
        user_id=user["id"],
        public_id="recent-conversation",
        max_messages=3,
    )

    assert [
        message["content"]
        for message in recent_messages
    ] == [
        "Message 5",
        "Message 6",
        "Message 7",
    ]


def test_summary_can_be_updated(
    db_session: Session,
):
    user = create_database_user(
        db_session,
        "summary-user",
    )

    add_exchange(
        session=db_session,
        user_id=user["id"],
        public_id="summary-conversation",
        user_message="My favorite framework is LangGraph.",
        assistant_message="Understood.",
    )

    set_summary(
        session=db_session,
        user_id=user["id"],
        public_id="summary-conversation",
        summary="The user prefers LangGraph.",
    )

    summary = get_summary(
        session=db_session,
        user_id=user["id"],
        public_id="summary-conversation",
    )

    assert summary == "The user prefers LangGraph."


def test_same_public_id_is_allowed_for_different_users(
    db_session: Session,
):
    first_user = create_database_user(
        db_session,
        "first-owner",
    )

    second_user = create_database_user(
        db_session,
        "second-owner",
    )

    add_exchange(
        session=db_session,
        user_id=first_user["id"],
        public_id="shared-public-id",
        user_message="First user's message",
        assistant_message="First response",
    )

    add_exchange(
        session=db_session,
        user_id=second_user["id"],
        public_id="shared-public-id",
        user_message="Second user's message",
        assistant_message="Second response",
    )

    first_history = get_full_history(
        session=db_session,
        user_id=first_user["id"],
        public_id="shared-public-id",
    )

    second_history = get_full_history(
        session=db_session,
        user_id=second_user["id"],
        public_id="shared-public-id",
    )

    assert first_history[0]["content"] == (
        "First user's message"
    )

    assert second_history[0]["content"] == (
        "Second user's message"
    )


def test_conversation_lookup_is_user_scoped(
    db_session: Session,
):
    owner = create_database_user(
        db_session,
        "owner",
    )

    other_user = create_database_user(
        db_session,
        "other-user",
    )

    add_exchange(
        session=db_session,
        user_id=owner["id"],
        public_id="private-conversation",
        user_message="Private message",
        assistant_message="Private response",
    )

    assert conversation_exists(
        session=db_session,
        user_id=owner["id"],
        public_id="private-conversation",
    )

    assert not conversation_exists(
        session=db_session,
        user_id=other_user["id"],
        public_id="private-conversation",
    )


def test_deleting_conversation_cascades_to_messages(
    db_session: Session,
):
    user = create_database_user(
        db_session,
        "delete-user",
    )

    add_exchange(
        session=db_session,
        user_id=user["id"],
        public_id="delete-conversation",
        user_message="Delete this",
        assistant_message="Temporary response",
    )

    conversation = db_session.scalar(
        select(Conversation).where(
            Conversation.user_id == user["id"],
            Conversation.public_id
            == "delete-conversation",
        )
    )

    assert conversation is not None

    conversation_id = conversation.id

    deleted = delete_conversation(
        session=db_session,
        user_id=user["id"],
        public_id="delete-conversation",
    )

    assert deleted is True

    message_count = db_session.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
    )

    assert message_count == 0


def test_deleting_missing_conversation_returns_false(
    db_session: Session,
):
    user = create_database_user(
        db_session,
        "missing-conversation-user",
    )

    deleted = delete_conversation(
        session=db_session,
        user_id=user["id"],
        public_id="does-not-exist",
    )

    assert deleted is False