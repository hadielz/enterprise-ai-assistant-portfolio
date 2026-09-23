"""
PostgreSQL-backed authentication integration tests.
"""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import User
from tests.helpers import (
    create_authenticated_user,
    login_user,
    register_user,
)


def test_register_user(
    client: TestClient,
    db_session: Session,
):
    response = register_user(
        client,
        username="demo-user",
        display_name="Demo Employee",
    )

    assert response.status_code == 201
    assert response.json() == {
        "username": "demo-user",
        "display_name": "Demo Employee",
        "role": "employee",
        "is_active": True,
    }

    user = db_session.scalar(
        select(User).where(User.username == "demo-user")
    )

    assert user is not None
    assert user.display_name == "Demo Employee"
    assert user.password_hash != "secure-password-123"
    assert user.role == "employee"


def test_registration_cannot_self_assign_support_role(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "self-elevation",
            "display_name": "Self Elevation",
            "password": "secure-password-123",
            "role": "support",
        },
    )

    assert response.status_code == 201

    user = db_session.scalar(
        select(User).where(User.username == "self-elevation")
    )

    assert user is not None
    assert user.role == "employee"


def test_username_is_normalized(
    client: TestClient,
    db_session: Session,
):
    response = register_user(
        client,
        username="DeMo-User",
        display_name="Demo",
    )

    assert response.status_code == 201
    assert response.json()["username"] == "demo-user"

    user = db_session.scalar(
        select(User).where(User.username == "demo-user")
    )

    assert user is not None


def test_duplicate_username_returns_conflict(
    client: TestClient,
):
    first_response = register_user(
        client,
        username="duplicate-user",
    )

    second_response = register_user(
        client,
        username="duplicate-user",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert (
        second_response.json()["detail"]
        == "Username already exists."
    )


def test_login_returns_bearer_token(
    client: TestClient,
):
    register_user(
        client,
        username="login-user",
    )

    response = login_user(
        client,
        username="login-user",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in_minutes"] > 0


def test_login_rejects_incorrect_password(
    client: TestClient,
):
    register_user(
        client,
        username="wrong-password-user",
    )

    response = login_user(
        client,
        username="wrong-password-user",
        password="incorrect-password",
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Incorrect username or password."
    )


def test_me_returns_authenticated_user(
    client: TestClient,
):
    authenticated_user = create_authenticated_user(
        client,
        username="current-user",
        display_name="Current User",
    )

    response = client.get(
        "/api/auth/me",
        headers=authenticated_user["headers"],
    )

    assert response.status_code == 200
    assert response.json() == {
        "username": "current-user",
        "display_name": "Current User",
        "role": "employee",
        "is_active": True,
    }


def test_me_reflects_server_side_support_role(
    client: TestClient,
    db_session: Session,
):
    authenticated_user = create_authenticated_user(
        client,
        username="support-me-user",
        display_name="Support User",
    )

    user = db_session.scalar(
        select(User).where(User.username == "support-me-user")
    )
    assert user is not None
    user.role = "support"
    db_session.commit()

    response = client.get(
        "/api/auth/me",
        headers=authenticated_user["headers"],
    )

    assert response.status_code == 200
    assert response.json()["role"] == "support"


def test_disabled_user_cannot_access_me(
    client: TestClient,
    db_session: Session,
):
    authenticated_user = create_authenticated_user(
        client,
        username="disabled-user",
    )

    user = db_session.scalar(
        select(User).where(
            User.username == "disabled-user"
        )
    )

    assert user is not None

    user.is_active = False
    db_session.commit()

    response = client.get(
        "/api/auth/me",
        headers=authenticated_user["headers"],
    )

    assert response.status_code == 401


def test_database_starts_empty_for_each_test(
    db_session: Session,
):
    """
    This verifies that the previous test's transaction was rolled back.
    """

    user_count = db_session.scalar(
        select(func.count(User.id))
    )

    assert user_count == 0


def test_login_rejects_oversized_credentials_before_password_verification(
    client: TestClient,
    monkeypatch,
):
    register_user(client, username="bounded-login-user")

    def _unexpected_verify(*_args, **_kwargs):
        raise AssertionError("Password verification should not run for oversized input")

    monkeypatch.setattr("app.api.auth.verify_password", _unexpected_verify)

    response = login_user(
        client,
        username="bounded-login-user",
        password="x" * 129,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."


def test_login_rejects_oversized_username(client: TestClient):
    response = login_user(
        client,
        username="x" * 51,
        password="secure-password-123",
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."
