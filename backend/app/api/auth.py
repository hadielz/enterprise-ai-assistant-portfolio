"""
Authentication API routes.

Endpoints:
    POST /api/auth/register
    POST /api/auth/login
    GET  /api/auth/me
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.auth.user_storage import create_user, get_user
from app.core.config import settings
from app.database.session import get_db_session
from app.security.rate_limit import enforce_rate_limit
from app.schemas.auth import (
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    Register a PostgreSQL-backed application user.
    """

    enforce_rate_limit(
        scope="auth.register",
        key="global",
        limit=settings.rate_limit_register_limit,
        window_seconds=settings.rate_limit_register_window_seconds,
    )

    try:
        user = create_user(
            session=session,
            username=request.username,
            display_name=request.display_name,
            password_hash=hash_password(request.password),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse(
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        is_active=user["is_active"],
    )


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db_session)],
):
    """
    Validate OAuth2 form credentials against PostgreSQL.
    """

    enforce_rate_limit(
        scope="auth.login.global",
        key="global",
        limit=settings.rate_limit_login_global_limit,
        window_seconds=settings.rate_limit_login_global_window_seconds,
    )

    normalized_username = form_data.username.strip().lower()
    if (
        not normalized_username
        or len(normalized_username) > 50
        or len(form_data.password) > 128
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    enforce_rate_limit(
        scope="auth.login.user",
        key=normalized_username,
        limit=settings.rate_limit_login_user_limit,
        window_seconds=settings.rate_limit_login_user_window_seconds,
    )

    user = get_user(session, normalized_username)

    if not user or not verify_password(
        form_data.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user["username"])

    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Return the user represented by the current bearer token.
    """

    return UserResponse(
        username=current_user["username"],
        display_name=current_user["display_name"],
        role=current_user["role"],
        is_active=current_user["is_active"],
    )