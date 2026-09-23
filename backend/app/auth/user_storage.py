"""
PostgreSQL-backed user persistence.

Architecture Notes
------------------
Purpose:
    Provide authentication-oriented operations without exposing
    SQLAlchemy query details to the API layer.

Boundary:
    Authentication routes use these helpers without exposing SQLAlchemy
    query details. User roles are stored here as database state and consumed
    by server-side authorization dependencies.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import User


def normalize_username(username: str) -> str:
    """
    Normalize usernames consistently before querying or storing them.
    """

    return username.strip().lower()


def user_to_dict(user: User) -> dict:
    """
    Convert a database model into the application-facing user shape.

    Password hashes are included only because login verification
    currently occurs in the authentication service.
    """

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "password_hash": user.password_hash,
        "role": user.role,
        "is_active": user.is_active,
    }


def get_user(
    session: Session,
    username: str,
) -> dict | None:
    """
    Retrieve one user by normalized username.
    """

    normalized_username = normalize_username(username)

    statement = select(User).where(
        User.username == normalized_username
    )

    user = session.scalar(statement)

    if user is None:
        return None

    return user_to_dict(user)


def create_user(
    session: Session,
    username: str,
    password_hash: str,
    display_name: str,
) -> dict:
    """
    Create and persist one user.

    Raises:
        ValueError: if the normalized username already exists.
    """

    user = User(
        username=normalize_username(username),
        display_name=display_name.strip(),
        password_hash=password_hash,
        is_active=True,
    )

    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("Username already exists.") from exc

    session.refresh(user)

    return user_to_dict(user)