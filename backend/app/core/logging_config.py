"""Compatibility wrapper around the R3 structured logging setup."""

from app.observability.logging import configure_structured_logging


def configure_logging() -> None:
    configure_structured_logging()
