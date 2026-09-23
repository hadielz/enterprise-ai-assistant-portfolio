"""Standalone internal Streamable-HTTP MCP server runner."""

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import settings
from app.database.session import engine
from app.mcp.server import mcp
from app.observability.setup import configure_observability


def _transport_security_settings() -> TransportSecuritySettings:
    """Configure Host/Origin protection for the active deployment boundary."""

    if settings.environment == "production":
        # In production, Cloud Run's managed reverse proxy and IAM invocation
        # policy are the service boundary and control access to this private
        # MCP service.
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )

    # Local Compose does not publish the MCP service to the host. Keep an
    # explicit allowlist for the internal Docker service name and localhost.
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "mcp-server:*",
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ],
        allowed_origins=[
            "http://mcp-server:*",
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ],
    )


def build_app():
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security_settings(),
    )
    configure_observability(app=None, engine=engine)

    if settings.otel_enabled:
        from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

        app = OpenTelemetryMiddleware(app)

    return app


if __name__ == "__main__":
    uvicorn.run(
        build_app(),
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
    )