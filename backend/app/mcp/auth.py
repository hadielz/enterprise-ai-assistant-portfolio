"""Cloud Run service-to-service authentication for the MCP HTTP transport."""

from __future__ import annotations

from app.core.config import settings
from app.observability.tracing import inject_trace_headers


def build_mcp_headers() -> dict[str, str]:
    """Build trusted transport headers without exposing credentials to the model."""

    headers: dict[str, str] = {}
    inject_trace_headers(headers)

    if settings.mcp_auth_mode == "none":
        return headers

    if settings.mcp_auth_mode != "google_identity":
        raise ValueError(f"Unsupported MCP auth mode: {settings.mcp_auth_mode}")

    import google.auth.transport.requests
    import google.oauth2.id_token

    auth_request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(
        auth_request,
        settings.mcp_audience,
    )
    # Cloud Run verifies this header and strips it before the request reaches
    # the container. Using X-Serverless-Authorization avoids conflicting with
    # MCP/OAuth Authorization semantics inside the application protocol.
    headers["X-Serverless-Authorization"] = f"Bearer {token}"
    return headers
