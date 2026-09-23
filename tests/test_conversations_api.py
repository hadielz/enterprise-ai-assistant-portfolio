"""
Authenticated conversation-history API integration tests.
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.conversation_repository import add_exchange
from app.database.models import User
from tests.helpers import create_authenticated_user


def test_list_conversations_for_authenticated_user(
    client: TestClient,
    db_session: Session,
):
    authenticated_user = create_authenticated_user(
        client,
        username="list-user",
    )

    current_user_response = client.get(
        "/api/auth/me",
        headers=authenticated_user["headers"],
    )

    assert current_user_response.status_code == 200

    # Resolve the database ID through the test session.
    user = db_session.scalar(
        select(User).where(User.username == "list-user")
    )

    assert user is not None

    add_exchange(
        session=db_session,
        user_id=user.id,
        public_id="first-conversation",
        user_message="What is the travel policy?",
        assistant_message="The policy says...",
    )

    response = client.get(
        "/api/conversations",
        headers=authenticated_user["headers"],
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "conversation_id": "first-conversation",
            "preview": "What is the travel policy?",
            "message_count": 2,
        }
    ]


def test_open_conversation(
    client: TestClient,
    db_session: Session,
):
    authenticated_user = create_authenticated_user(
        client,
        username="open-user",
    )

    user = db_session.scalar(
        select(User).where(User.username == "open-user")
    )

    assert user is not None

    add_exchange(
        session=db_session,
        user_id=user.id,
        public_id="open-conversation",
        user_message="Hello",
        assistant_message="Hello!",
    )

    response = client.get(
        "/api/conversations/open-conversation",
        headers=authenticated_user["headers"],
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "open-conversation",
        "messages": [
            {
                "role": "user",
                "content": "Hello",
            },
            {
                "role": "assistant",
                "content": "Hello!",
            },
        ],
        "summary": "",
    }


def test_user_cannot_open_another_users_conversation(
    client: TestClient,
    db_session: Session,
):
    owner = create_authenticated_user(
        client,
        username="conversation-owner",
    )

    other_user = create_authenticated_user(
        client,
        username="conversation-outsider",
    )

    owner_record = db_session.scalar(
        select(User).where(
            User.username == owner["username"]
        )
    )

    assert owner_record is not None

    add_exchange(
        session=db_session,
        user_id=owner_record.id,
        public_id="owner-private-conversation",
        user_message="Private",
        assistant_message="Private response",
    )

    response = client.get(
        "/api/conversations/owner-private-conversation",
        headers=other_user["headers"],
    )

    # Return 404 so the API does not reveal that another user owns the ID.
    assert response.status_code == 404


def test_user_lists_only_their_own_conversations(
    client: TestClient,
    db_session: Session,
):
    first_user = create_authenticated_user(
        client,
        username="first-list-owner",
    )

    second_user = create_authenticated_user(
        client,
        username="second-list-owner",
    )

    first_record = db_session.scalar(
        select(User).where(
            User.username == first_user["username"]
        )
    )

    second_record = db_session.scalar(
        select(User).where(
            User.username == second_user["username"]
        )
    )

    assert first_record is not None
    assert second_record is not None

    add_exchange(
        session=db_session,
        user_id=first_record.id,
        public_id="first-private",
        user_message="First user message",
        assistant_message="First answer",
    )

    add_exchange(
        session=db_session,
        user_id=second_record.id,
        public_id="second-private",
        user_message="Second user message",
        assistant_message="Second answer",
    )

    first_response = client.get(
        "/api/conversations",
        headers=first_user["headers"],
    )

    second_response = client.get(
        "/api/conversations",
        headers=second_user["headers"],
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert [
        item["conversation_id"]
        for item in first_response.json()
    ] == ["first-private"]

    assert [
        item["conversation_id"]
        for item in second_response.json()
    ] == ["second-private"]


def test_delete_conversation(
    client: TestClient,
    db_session: Session,
):
    authenticated_user = create_authenticated_user(
        client,
        username="api-delete-user",
    )

    user = db_session.scalar(
        select(User).where(
            User.username == authenticated_user["username"]
        )
    )

    assert user is not None

    add_exchange(
        session=db_session,
        user_id=user.id,
        public_id="api-delete-conversation",
        user_message="Delete me",
        assistant_message="Temporary",
    )

    delete_response = client.delete(
        "/api/conversations/api-delete-conversation",
        headers=authenticated_user["headers"],
    )

    assert delete_response.status_code == 204

    read_response = client.get(
        "/api/conversations/api-delete-conversation",
        headers=authenticated_user["headers"],
    )

    assert read_response.status_code == 404


def test_user_cannot_delete_another_users_conversation(
    client: TestClient,
    db_session: Session,
):
    owner = create_authenticated_user(client, username="delete-owner")
    outsider = create_authenticated_user(client, username="delete-outsider")
    owner_record = db_session.scalar(
        select(User).where(User.username == owner["username"])
    )
    assert owner_record is not None

    add_exchange(
        session=db_session,
        user_id=owner_record.id,
        public_id="delete-private-conversation",
        user_message="Private",
        assistant_message="Private response",
    )

    response = client.delete(
        "/api/conversations/delete-private-conversation",
        headers=outsider["headers"],
    )
    assert response.status_code == 404

    owner_response = client.get(
        "/api/conversations/delete-private-conversation",
        headers=owner["headers"],
    )
    assert owner_response.status_code == 200
