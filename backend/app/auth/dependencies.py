"""
FastAPI authentication dependencies.

JWT validation identifies the username. PostgreSQL then verifies that
the corresponding user still exists and remains active. Authorization
dependencies build on this authenticated database identity; model text never
grants application roles.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.auth.user_storage import get_user
from app.database.session import get_db_session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """
    Return the active database user represented by a bearer token.
    """

    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        username = decode_access_token(token)
    except InvalidTokenError as exc:
        raise authentication_error from exc

    user = get_user(session, username)

    if not user or not user["is_active"]:
        raise authentication_error

    return user