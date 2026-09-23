"""
Authentication security utilities.

Architecture Notes
------------------
Responsibilities:
    - Hash and verify passwords.
    - Create signed JWT access tokens.
    - Validate and decode JWT access tokens.

The rest of the application should not manipulate passwords or JWT
implementation details directly.
"""

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Convert a plaintext password into a secure one-way hash.
    """

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against its stored hash.
    """

    return password_hasher.verify(password, password_hash)


def create_access_token(username: str) -> str:
    """
    Create a signed JWT containing the authenticated username.

    The `sub` claim identifies the token subject.
    The `exp` claim limits token lifetime.
    """

    if not settings.jwt_secret_key:
        raise RuntimeError(
            "JWT_SECRET_KEY is missing. Add it to the .env file."
        )

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": username,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    """
    Validate a token and return its username.

    Raises:
        InvalidTokenError: if the signature, expiration, or payload
        is invalid.
    """

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp"]},
    )

    username = payload.get("sub")

    if not isinstance(username, str) or not username:
        raise InvalidTokenError("Token subject is missing.")

    return username