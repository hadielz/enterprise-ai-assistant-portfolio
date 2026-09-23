import json
import logging

from app.observability.context import bind_request_context
from app.observability.logging import StructuredJsonFormatter


def test_structured_log_contains_safe_correlation_without_user_content():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ticket_action_committed",
        args=(),
        exc_info=None,
    )
    record.tool_name = "ticket_creator"
    record.ticket_id = "TICKET-safe-id"
    record.authorization = "Bearer should-never-be-logged"
    record.user_message = "sensitive user content"
    record.database_url = "postgresql://secret"

    with bind_request_context(
        request_id="request-123",
        conversation_id="conversation-456",
    ):
        payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "request-123"
    assert payload["conversation_id"] == "conversation-456"
    assert payload["tool_name"] == "ticket_creator"
    assert payload["ticket_id"] == "TICKET-safe-id"
    assert "password" not in payload
    assert "token" not in payload
    assert "authorization" not in payload
    assert "user_message" not in payload
    assert "database_url" not in payload
