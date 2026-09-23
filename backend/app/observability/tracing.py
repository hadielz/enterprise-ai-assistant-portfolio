"""Small vendor-neutral OpenTelemetry helpers used by R3 boundaries."""

from contextlib import contextmanager
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.trace import Status, StatusCode

TRACER_NAME = "enterprise-ai-assistant"


def get_tracer():
    return trace.get_tracer(TRACER_NAME)


@contextmanager
def start_span(name: str, **attributes: Any):
    with get_tracer().start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]:
    propagate.inject(headers)
    return headers
