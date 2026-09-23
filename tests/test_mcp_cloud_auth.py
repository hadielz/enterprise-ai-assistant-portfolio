from app.core.config import settings
from app.mcp import auth as mcp_auth


def test_local_mcp_auth_adds_no_cloud_identity_token(monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_mode", "none")
    headers = mcp_auth.build_mcp_headers()
    assert "X-Serverless-Authorization" not in headers


def test_google_identity_uses_configured_audience(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "mcp_auth_mode", "google_identity")
    monkeypatch.setattr(settings, "mcp_audience", "https://private-mcp.example")

    import google.oauth2.id_token

    def fake_fetch_id_token(_request, audience):
        calls.append(audience)
        return "signed-test-token"

    monkeypatch.setattr(google.oauth2.id_token, "fetch_id_token", fake_fetch_id_token)
    headers = mcp_auth.build_mcp_headers()

    assert calls == ["https://private-mcp.example"]
    assert headers["X-Serverless-Authorization"] == "Bearer signed-test-token"
