"""R4 CORS and browser-facing security configuration tests."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_cors_allows_expected_bearer_preflight(client: TestClient):
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_cors_rejects_unlisted_method(client: TestClient):
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
        },
    )
    assert response.status_code == 400


def test_cors_does_not_allow_untrusted_origin(client: TestClient):
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_frontend_nginx_has_bounded_security_headers():
    config = Path("frontend/nginx.conf").read_text(encoding="utf-8")

    assert 'server_tokens off;' in config

    for required in (
        'X-Content-Type-Options "nosniff"',
        'X-Frame-Options "DENY"',
        'Referrer-Policy "no-referrer"',
        'Permissions-Policy "camera=(), microphone=(), geolocation=()"',
        'Cache-Control "no-store"',
    ):
        assert required in config
