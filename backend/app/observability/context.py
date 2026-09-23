"""Request-scoped correlation context for logs and application spans."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from typing import TypeVar


_request_id: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)
_conversation_id: ContextVar[str | None] = ContextVar(
    "conversation_id",
    default=None,
)

T = TypeVar("T")


def get_request_id() -> str | None:
    return _request_id.get()


def get_conversation_id() -> str | None:
    return _conversation_id.get()


@contextmanager
def bind_request_context(
    *,
    request_id: str,
    conversation_id: str | None = None,
):
    request_token = _request_id.set(request_id)
    conversation_token = _conversation_id.set(conversation_id)

    try:
        yield
    finally:
        _request_id.reset(request_token)
        _conversation_id.reset(conversation_token)


class _ContextPreservingIterator(Iterator[T]):
    """Advance one iterator inside the same execution context every time."""

    def __init__(self, iterator: Iterator[T]):
        self._iterator = iter(iterator)
        self._context = copy_context()

    def __iter__(self) -> "_ContextPreservingIterator[T]":
        return self

    def __next__(self) -> T:
        return self._context.run(next, self._iterator)


def preserve_iterator_context(iterator: Iterator[T]) -> Iterator[T]:
    """
    Preserve ContextVar and OpenTelemetry context across sync stream iteration.

    Starlette may advance a synchronous StreamingResponse iterator through
    separate worker execution contexts. Running every iterator step inside one
    captured Context ensures context-manager enter/exit operations occur in the
    same logical context.
    """

    return _ContextPreservingIterator(iterator)