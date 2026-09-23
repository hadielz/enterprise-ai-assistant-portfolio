"""R4 input and process-local rate-limit contracts."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import User
from app.schemas.chat import ChatRequest
from app.security.rate_limit import InMemoryRateLimiter, rate_limiter
from app.tickets.service import create_ticket_for_requester
from tests.helpers import create_authenticated_user, login_user, register_user


def test_chat_message_has_explicit_maximum_length():
    assert ChatRequest(message="x" * 8000).message == "x" * 8000

    try:
        ChatRequest(message="x" * 8001)
    except Exception as exc:
        assert "8000" in str(exc)
    else:
        raise AssertionError("ChatRequest accepted more than 8000 characters")


def test_chat_endpoint_rejects_oversized_message_before_generation(
    client: TestClient,
    monkeypatch,
):
    user = create_authenticated_user(client, username="oversized-chat-user")

    def _unexpected_generation(**_kwargs):
        raise AssertionError("Generation must not run for an oversized chat input")

    monkeypatch.setattr("app.api.chat.generate_response", _unexpected_generation)

    response = client.post(
        "/api/chat",
        headers=user["headers"],
        json={"message": "x" * 8001, "conversation_id": "oversized-chat"},
    )

    assert response.status_code == 422


def test_limiter_window_and_retry_after_are_deterministic():
    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0], max_keys=10)

    assert limiter.check(scope="demo", key="user", limit=2, window_seconds=60).allowed
    assert limiter.check(scope="demo", key="user", limit=2, window_seconds=60).allowed

    blocked = limiter.check(scope="demo", key="user", limit=2, window_seconds=60)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 61

    now[0] = 161.0
    assert limiter.check(scope="demo", key="user", limit=2, window_seconds=60).allowed


def test_registration_rate_limit_returns_429_and_retry_after(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_register_limit", 2)
    monkeypatch.setattr(settings, "rate_limit_register_window_seconds", 60)

    assert register_user(client, username="rate-register-one").status_code == 201
    assert register_user(client, username="rate-register-two").status_code == 201
    blocked = register_user(client, username="rate-register-three")

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_login_per_username_rate_limit_returns_429(client: TestClient, monkeypatch):
    register_user(client, username="rate-login-user")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_global_limit", 100)
    monkeypatch.setattr(settings, "rate_limit_login_global_window_seconds", 60)
    monkeypatch.setattr(settings, "rate_limit_login_user_limit", 2)
    monkeypatch.setattr(settings, "rate_limit_login_user_window_seconds", 60)

    assert login_user(client, username="rate-login-user", password="wrong-one").status_code == 401
    assert login_user(client, username="rate-login-user", password="wrong-two").status_code == 401
    blocked = login_user(client, username="rate-login-user", password="wrong-three")

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_stream_and_nonstream_chat_share_one_user_rate_scope(
    client: TestClient,
    monkeypatch,
):
    user = create_authenticated_user(client, username="rate-chat-user")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_chat_limit", 2)
    monkeypatch.setattr(settings, "rate_limit_chat_window_seconds", 60)

    monkeypatch.setattr(
        "app.api.chat.generate_response",
        lambda **kwargs: {
            "response": "ok",
            "used_rag": False,
            "sources": [],
            "conversation_id": kwargs["conversation_id"],
            "tool_used": None,
            "agent_steps": [],
        },
    )
    monkeypatch.setattr(
        "app.api.chat.stream_response",
        lambda **_: iter(["ok"]),
    )

    first = client.post(
        "/api/chat",
        headers=user["headers"],
        json={"message": "hello", "conversation_id": "rate-one"},
    )
    second = client.post(
        "/api/chat/stream",
        headers=user["headers"],
        json={"message": "hello", "conversation_id": "rate-two"},
    )
    third = client.post(
        "/api/chat",
        headers=user["headers"],
        json={"message": "hello", "conversation_id": "rate-three"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_rag_index_has_separate_privileged_rate_scope(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    support = create_authenticated_user(client, username="rate-rag-support")
    user = db_session.scalar(select(User).where(User.username == "rate-rag-support"))
    assert user is not None
    user.role = "support"
    db_session.commit()

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_rag_index_limit", 1)
    monkeypatch.setattr(settings, "rate_limit_rag_index_window_seconds", 60)
    monkeypatch.setattr("app.api.rag.index_documents", lambda: 1)

    first = client.post("/api/rag/index", headers=support["headers"])
    second = client.post("/api/rag/index", headers=support["headers"])

    assert first.status_code == 200
    assert second.status_code == 429


def test_ticket_status_updates_have_separate_rate_scope(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    employee = create_authenticated_user(client, username="rate-ticket-owner")
    support = create_authenticated_user(client, username="rate-ticket-support")
    owner = db_session.scalar(select(User).where(User.username == employee["username"]))
    support_user = db_session.scalar(
        select(User).where(User.username == support["username"])
    )
    assert owner is not None
    assert support_user is not None
    support_user.role = "support"
    db_session.commit()

    ticket = create_ticket_for_requester(
        db_session,
        requester_user_id=owner.id,
        description="Rate-limit ticket status changes",
        action_id="rate-ticket-status-action",
    )

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_ticket_status_limit", 1)
    monkeypatch.setattr(settings, "rate_limit_ticket_status_window_seconds", 60)

    first = client.patch(
        f"/api/tickets/{ticket.public_id}/status",
        headers=support["headers"],
        json={"status": "in_progress"},
    )
    second = client.patch(
        f"/api/tickets/{ticket.public_id}/status",
        headers=support["headers"],
        json={"status": "resolved"},
    )

    assert first.status_code == 200
    assert second.status_code == 429


def test_rate_limiter_stays_disabled_for_normal_local_tests(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    rate_limiter.reset()

    # No exception even with intentionally unusable numeric values when the
    # runtime limiter is disabled; Settings.validate_runtime owns config validity.
    from app.security.rate_limit import enforce_rate_limit

    enforce_rate_limit(scope="disabled", key="demo", limit=1, window_seconds=1)
    enforce_rate_limit(scope="disabled", key="demo", limit=1, window_seconds=1)
