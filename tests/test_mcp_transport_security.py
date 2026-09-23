"""Regression tests for MCP Streamable-HTTP transport security."""

from starlette.testclient import TestClient

from app.core.config import settings
from app.mcp import run_server


def test_local_mcp_transport_security_allows_compose_service(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")

    security = run_server._transport_security_settings()

    assert security.enable_dns_rebinding_protection is True
    assert "mcp-server:*" in security.allowed_hosts
    assert "localhost:*" in security.allowed_hosts


def test_production_mcp_transport_security_delegates_to_cloud_run(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")

    security = run_server._transport_security_settings()

    assert security.enable_dns_rebinding_protection is False


def test_build_app_passes_explicit_transport_security(monkeypatch):
    captured = {}
    dummy_app = object()
    security = object()

    class DummyMCP:
        def streamable_http_app(self, **kwargs):
            captured.update(kwargs)
            return dummy_app

    monkeypatch.setattr(run_server, "mcp", DummyMCP())
    monkeypatch.setattr(
        run_server,
        "_transport_security_settings",
        lambda: security,
    )
    monkeypatch.setattr(
        run_server,
        "configure_observability",
        lambda **_: None,
    )
    monkeypatch.setattr(settings, "otel_enabled", False)

    app = run_server.build_app()

    assert app is dummy_app
    assert captured["transport_security"] is security
    assert captured["streamable_http_path"] == "/mcp"
    assert captured["stateless_http"] is True
    assert captured["json_response"] is True


def test_production_mcp_accepts_cloud_run_host(monkeypatch):
    """Cloud Run's external Host header must not be rejected with HTTP 421."""

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "otel_enabled", False)

    app = run_server.build_app()

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={
                "host": "enterprise-ai-demo-mcp.example.europe-west1.run.app",
                "content-type": "application/json",
            },
            content="{}",
        )

    # The malformed MCP payload may legitimately fail protocol validation,
    # but it must reach that layer rather than being rejected by Host checking.
    assert response.status_code != 421


def test_local_mcp_rejects_untrusted_host(monkeypatch):
    """Local MCP keeps DNS-rebinding Host protection enabled."""

    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "otel_enabled", False)

    app = run_server.build_app()

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={
                "host": "untrusted.example",
                "content-type": "application/json",
            },
            content="{}",
        )

    assert response.status_code == 421