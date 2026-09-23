"""Regression coverage for context-safe synchronous streaming."""

from contextvars import Context

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.observability.context import (
    bind_request_context,
    get_conversation_id,
    get_request_id,
    preserve_iterator_context,
)
from tests.helpers import create_authenticated_user


def test_preserved_stream_context_survives_different_caller_contexts():
    """
    A synchronous stream may be advanced from different caller contexts.

    The wrapped iterator must keep request correlation bound to one execution
    context so ContextVar tokens can be reset safely when the stream closes.
    """

    cleanup_completed = False

    def source():
        nonlocal cleanup_completed

        with bind_request_context(
            request_id="stream-request-123",
            conversation_id="stream-conversation-456",
        ):
            try:
                assert get_request_id() == "stream-request-123"
                assert get_conversation_id() == "stream-conversation-456"

                yield "first"
                yield "second"
            finally:
                cleanup_completed = True

    iterator = preserve_iterator_context(source())

    caller_context_one = Context()
    caller_context_two = Context()

    assert caller_context_one.run(next, iterator) == "first"
    assert caller_context_two.run(next, iterator) == "second"

    with pytest.raises(StopIteration):
        caller_context_one.run(next, iterator)

    assert cleanup_completed is True
    assert get_request_id() is None
    assert get_conversation_id() is None


def test_streaming_endpoint_preserves_context_through_starlette(
    client: TestClient,
    monkeypatch,
):
    """
    The real StreamingResponse boundary must complete a synchronous stream
    without resetting ContextVar tokens from a different execution context.
    """

    cleanup_completed = False

    def controlled_stream_response(
        message: str,
        conversation_id: str,
        user_id: int,
        session,
    ):
        nonlocal cleanup_completed

        with bind_request_context(
            request_id="http-stream-request-123",
            conversation_id=conversation_id,
        ):
            try:
                assert get_request_id() == "http-stream-request-123"
                assert get_conversation_id() == conversation_id

                yield "first"
                yield "second"
            finally:
                cleanup_completed = True

    monkeypatch.setattr(
        chat_api,
        "stream_response",
        controlled_stream_response,
    )

    auth = create_authenticated_user(
        client,
        username="stream-context-user",
    )

    response = client.post(
        "/api/chat/stream",
        headers=auth["headers"],
        json={
            "message": "Controlled streaming request",
            "conversation_id": "stream-context-conversation",
        },
    )

    assert response.status_code == 200
    assert response.text == "firstsecond"
    assert cleanup_completed is True
    assert get_request_id() is None
    assert get_conversation_id() is None