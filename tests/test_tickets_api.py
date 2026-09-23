"""Authenticated ticket API integration tests."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import User
from app.tickets.service import create_ticket_for_requester
from tests.helpers import create_authenticated_user


def _db_user(session: Session, username: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    assert user is not None
    return user


def test_employee_lists_only_own_tickets(client, db_session):
    first = create_authenticated_user(client, username="ticket-api-one")
    second = create_authenticated_user(client, username="ticket-api-two")
    first_user = _db_user(db_session, "ticket-api-one")
    second_user = _db_user(db_session, "ticket-api-two")

    own = create_ticket_for_requester(
        db_session,
        requester_user_id=first_user.id,
        description="First user ticket",
        action_id="api-action-one",
    )
    create_ticket_for_requester(
        db_session,
        requester_user_id=second_user.id,
        description="Second user ticket",
        action_id="api-action-two",
    )

    response = client.get("/api/tickets", headers=first["headers"])
    assert response.status_code == 200
    assert [item["ticket_id"] for item in response.json()] == [own.public_id]


def test_cross_user_ticket_read_returns_not_found(client, db_session):
    owner = create_authenticated_user(client, username="ticket-read-owner")
    other = create_authenticated_user(client, username="ticket-read-other")
    owner_user = _db_user(db_session, "ticket-read-owner")

    ticket = create_ticket_for_requester(
        db_session,
        requester_user_id=owner_user.id,
        description="Private ticket",
        action_id="private-ticket-action",
    )

    response = client.get(
        f"/api/tickets/{ticket.public_id}",
        headers=other["headers"],
    )
    assert response.status_code == 404


def test_support_can_list_and_transition_tickets(client, db_session):
    employee = create_authenticated_user(client, username="ticket-employee")
    support = create_authenticated_user(client, username="ticket-support")
    employee_user = _db_user(db_session, "ticket-employee")
    support_user = _db_user(db_session, "ticket-support")
    support_user.role = "support"
    db_session.commit()

    ticket = create_ticket_for_requester(
        db_session,
        requester_user_id=employee_user.id,
        description="Support-visible ticket",
        action_id="support-visible-action",
    )

    list_response = client.get("/api/tickets", headers=support["headers"])
    assert list_response.status_code == 200
    assert ticket.public_id in {item["ticket_id"] for item in list_response.json()}

    transition = client.patch(
        f"/api/tickets/{ticket.public_id}/status",
        headers=support["headers"],
        json={"status": "in_progress"},
    )
    assert transition.status_code == 200
    assert transition.json()["status"] == "in_progress"


def test_employee_cannot_update_ticket_status(client, db_session):
    employee = create_authenticated_user(client, username="ticket-no-update")
    user = _db_user(db_session, "ticket-no-update")
    ticket = create_ticket_for_requester(
        db_session,
        requester_user_id=user.id,
        description="No employee mutation",
        action_id="no-employee-update",
    )

    response = client.patch(
        f"/api/tickets/{ticket.public_id}/status",
        headers=employee["headers"],
        json={"status": "in_progress"},
    )
    assert response.status_code == 403

def test_ticket_api_requires_authentication(client):
    assert client.get("/api/tickets").status_code == 401
