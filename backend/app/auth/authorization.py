"""
Minimal enterprise authorization primitives.

Architecture Notes
------------------
Purpose:
    Keep role and privilege checks in application code derived from the
    authenticated database user. Prompts and model output never grant roles.

R1 scope:
    The reference application needs only two roles for v1.0:
    - employee: ordinary authenticated user
    - support: privileged operator allowed to run administrative RAG indexing

This is intentionally not a general IAM or policy-engine subsystem.
"""

from enum import Enum

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user


class UserRole(str, Enum):
    """Roles supported by the Portfolio v1.0 reference application."""

    EMPLOYEE = "employee"
    SUPPORT = "support"


DEFAULT_USER_ROLE = UserRole.EMPLOYEE.value
PRIVILEGED_SUPPORT_ROLE = UserRole.SUPPORT.value


def require_support_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Require the authenticated user to hold the support role.

    Authentication is still handled by get_current_user(). Reaching this
    dependency with an ordinary active user is therefore an authorization
    failure and returns HTTP 403 rather than HTTP 401.
    """

    if current_user.get("role") != PRIVILEGED_SUPPORT_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation.",
        )

    return current_user
