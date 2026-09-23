"""Structured JSON logging with request/trace correlation and safe fields."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from opentelemetry import trace

from app.core.config import settings
from app.observability.context import get_conversation_id, get_request_id

_SENSITIVE_FIELD_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "database_url",
    "raw_response",
    "user_message",
    "rag_context",
    "document_content",
    "ticket_description",
)


def _is_sensitive_field(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in _SENSITIVE_FIELD_PARTS)


_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": settings.otel_service_name,
        }

        request_id = get_request_id()
        conversation_id = get_conversation_id()
        if request_id:
            payload["request_id"] = request_id
        if conversation_id:
            payload["conversation_id"] = conversation_id

        if span_context.is_valid:
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")
            payload["trace_id"] = trace_id
            payload["span_id"] = span_id
            if settings.google_cloud_project:
                payload["logging.googleapis.com/trace"] = (
                    f"projects/{settings.google_cloud_project}/traces/{trace_id}"
                )
                payload["logging.googleapis.com/spanId"] = span_id

        for key, value in record.__dict__.items():
            if (
                key not in _RESERVED
                and not key.startswith("_")
                and not _is_sensitive_field(key)
            ):
                payload[key] = value

        if record.exc_info:
            payload["error_class"] = record.exc_info[0].__name__

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_structured_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_event(logger: logging.Logger, level: int, event: str, **fields) -> None:
    safe_fields = {key: value for key, value in fields.items() if value is not None}
    logger.log(level, event, extra=safe_fields)
