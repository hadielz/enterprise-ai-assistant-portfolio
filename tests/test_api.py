"""
Public API and authorization-boundary tests.

These tests intentionally avoid external LLM providers.
"""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert "message" in response.json()


def test_me_requires_authentication(client: TestClient):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_chat_requires_authentication(client: TestClient):
    response = client.post(
        "/api/chat",
        json={
            "message": "Hello",
            "conversation_id": "test-conversation",
        },
    )

    assert response.status_code == 401


def test_streaming_chat_requires_authentication(
    client: TestClient,
):
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "Hello",
            "conversation_id": "test-conversation",
        },
    )

    assert response.status_code == 401


def test_conversation_list_requires_authentication(
    client: TestClient,
):
    response = client.get("/api/conversations")

    assert response.status_code == 401


def test_conversation_detail_requires_authentication(
    client: TestClient,
):
    response = client.get(
        "/api/conversations/not-accessible"
    )

    assert response.status_code == 401


def test_conversation_delete_requires_authentication(
    client: TestClient,
):
    response = client.delete(
        "/api/conversations/not-accessible"
    )

    assert response.status_code == 401