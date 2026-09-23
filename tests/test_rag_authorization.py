"""R1 authorization tests for privileged RAG indexing."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import User
from tests.helpers import create_authenticated_user


def _promote_to_support(db_session: Session, username: str) -> None:
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    user.role = "support"
    db_session.commit()


def test_rag_index_requires_authentication(client: TestClient):
    response = client.post("/api/rag/index")

    assert response.status_code == 401


def test_employee_cannot_index_rag(client: TestClient):
    employee = create_authenticated_user(
        client,
        username="rag-employee",
    )

    response = client.post(
        "/api/rag/index",
        headers=employee["headers"],
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Insufficient permissions for this operation."
    )


def test_support_user_can_index_rag_without_public_role_assignment_api(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    support = create_authenticated_user(
        client,
        username="rag-support",
    )
    _promote_to_support(db_session, "rag-support")

    calls: list[str] = []

    monkeypatch.setattr(
        "app.api.rag.index_documents",
        lambda: calls.append("indexed") or 7,
    )

    response = client.post(
        "/api/rag/index",
        headers=support["headers"],
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Documents indexed successfully",
        "indexed_chunks": 7,
    }
    assert calls == ["indexed"]
