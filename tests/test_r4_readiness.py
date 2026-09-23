"""R4 liveness/readiness contracts."""

from contextlib import contextmanager

from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from app.core.config import settings
from app.health import database_is_ready
from app.mcp import run_server


class _Connection:
    def execute(self, _statement):
        return 1


@contextmanager
def _working_connection():
    yield _Connection()


def _failing_connection():
    raise RuntimeError("database unavailable")


def test_database_readiness_helper_distinguishes_success_and_failure():
    assert database_is_ready(connection_factory=_working_connection) is True
    assert database_is_ready(connection_factory=_failing_connection) is False


def test_backend_liveness_does_not_depend_on_database(client: TestClient, monkeypatch):
    monkeypatch.setattr("backend.app.main.database_is_ready", lambda: False)
    assert client.get("/health").status_code == 200


def test_backend_readiness_returns_503_when_database_is_unavailable(
    client: TestClient,
    monkeypatch,
):
    monkeypatch.setattr("backend.app.main.database_is_ready", lambda: False)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_backend_readiness_returns_200_when_database_is_available(
    client: TestClient,
    monkeypatch,
):
    monkeypatch.setattr("backend.app.main.database_is_ready", lambda: True)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_mcp_readiness_uses_same_database_contract(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "otel_enabled", False)
    monkeypatch.setattr("app.mcp.server.database_is_ready", lambda: False)

    app = run_server.build_app()
    with StarletteTestClient(app) as client:
        response = client.get("/ready", headers={"host": "localhost"})

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_mcp_liveness_does_not_depend_on_database(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "otel_enabled", False)
    monkeypatch.setattr("app.mcp.server.database_is_ready", lambda: False)

    app = run_server.build_app()
    with StarletteTestClient(app) as client:
        response = client.get("/health", headers={"host": "localhost"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mcp_readiness_returns_200_when_database_is_available(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "otel_enabled", False)
    monkeypatch.setattr("app.mcp.server.database_is_ready", lambda: True)

    app = run_server.build_app()
    with StarletteTestClient(app) as client:
        response = client.get("/ready", headers={"host": "localhost"})

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
