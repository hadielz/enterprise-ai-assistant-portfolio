"""Liveness/readiness helpers for HTTP and MCP service endpoints."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text

from app.database.session import engine


ConnectionFactory = Callable[[], object]


def database_is_ready(
    *,
    connection_factory: ConnectionFactory | None = None,
) -> bool:
    """Return whether the application's critical PostgreSQL dependency responds."""

    connect = connection_factory or engine.connect
    try:
        with connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
