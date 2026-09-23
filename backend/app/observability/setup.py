"""OpenTelemetry initialization for local and Cloud Run execution."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.observability.logging import configure_structured_logging

logger = logging.getLogger(__name__)
_configured = False


def configure_observability(*, app=None, engine=None) -> None:
    """Configure JSON logs always and OTel instrumentation when enabled."""

    global _configured
    if _configured:
        return

    configure_structured_logging()
    settings.validate_runtime()

    if not settings.otel_enabled:
        _configured = True
        return

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource_attributes = {
        "service.name": settings.otel_service_name,
        "service.version": settings.app_version,
        "deployment.environment.name": settings.environment,
    }
    if settings.google_cloud_project:
        resource_attributes["gcp.project_id"] = settings.google_cloud_project

    provider = TracerProvider(
        resource=Resource.create(resource_attributes),
        sampler=ParentBased(TraceIdRatioBased(settings.otel_sample_ratio)),
    )

    if settings.otel_exporter == "console":
        exporter = ConsoleSpanExporter()
    elif settings.otel_exporter == "gcp_otlp":
        import google.auth
        import google.auth.transport.grpc
        import google.auth.transport.requests
        import grpc
        from google.auth.transport.grpc import AuthMetadataPlugin
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        request = google.auth.transport.requests.Request()
        plugin = AuthMetadataPlugin(credentials=credentials, request=request)
        channel_creds = grpc.composite_channel_credentials(
            grpc.ssl_channel_credentials(),
            grpc.metadata_call_credentials(plugin),
        )
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_endpoint,
            credentials=channel_creds,
        )
    else:
        raise ValueError("OTEL_EXPORTER must be 'console' or 'gcp_otlp'.")

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    if engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine)

    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    HTTPXClientInstrumentor().instrument()
    RequestsInstrumentor().instrument()

    _configured = True
    logger.info("OpenTelemetry initialized", extra={"otel_exporter": settings.otel_exporter})
