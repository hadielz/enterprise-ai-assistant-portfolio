"""
Reusable test helpers.

These helpers call public API endpoints instead of manipulating JWTs
or authentication internals directly.
"""

from fastapi.testclient import TestClient


def register_user(
    client: TestClient,
    *,
    username: str,
    password: str = "secure-password-123",
    display_name: str | None = None,
):
    """
    Register one test user through the public API.
    """

    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": display_name or username.title(),
            "password": password,
        },
    )


def login_user(
    client: TestClient,
    *,
    username: str,
    password: str = "secure-password-123",
):
    """
    Login through the OAuth2 form endpoint.
    """

    return client.post(
        "/api/auth/login",
        data={
            "username": username,
            "password": password,
        },
    )


def create_authenticated_user(
    client: TestClient,
    *,
    username: str,
    password: str = "secure-password-123",
    display_name: str | None = None,
) -> dict:
    """
    Register a user, log in, and return useful authentication data.
    """

    registration_response = register_user(
        client,
        username=username,
        password=password,
        display_name=display_name,
    )

    assert registration_response.status_code == 201

    login_response = login_user(
        client,
        username=username,
        password=password,
    )

    assert login_response.status_code == 200

    token_data = login_response.json()

    return {
        "username": username,
        "password": password,
        "token": token_data["access_token"],
        "headers": {
            "Authorization": (
                f"Bearer {token_data['access_token']}"
            )
        },
    }