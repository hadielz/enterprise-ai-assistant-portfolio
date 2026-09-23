"""PostgreSQL ticket repository/business-service tests."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Ticket, User
from app.tickets.service import (
    TicketNotFoundError,
    TicketTransitionError,
    create_ticket_for_requester,
    get_ticket_for_actor,
    list_tickets_for_actor,
    transition_ticket_status,
)


def make_user(session: Session, username: str, role: str = "employee") -> User:
    user = User(
        username=username,
        display_name=username.title(),
        password_hash="test-hash",
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_ticket_creation_uses_uuid_public_id_and_action_idempotency(db_session: Session):
    user = make_user(db_session, "ticket-owner")

    first = create_ticket_for_requester(
        db_session,
        requester_user_id=user.id,
        description="VPN is unavailable",
        action_id="request-123",
    )
    second = create_ticket_for_requester(
        db_session,
        requester_user_id=user.id,
        description="VPN is unavailable",
        action_id="request-123",
    )

    assert first.id == second.id
    assert first.public_id.startswith("TICKET-")
    assert len(first.public_id) > len("TICKET-1234567890")
    assert first.status == "created"
    assert db_session.query(Ticket).count() == 1


def test_employee_ticket_visibility_is_owner_scoped(db_session: Session):
    owner = make_user(db_session, "owner")
    other = make_user(db_session, "other")
    support = make_user(db_session, "support", role="support")

    ticket = create_ticket_for_requester(
        db_session,
        requester_user_id=owner.id,
        description="Laptop issue",
        action_id="owner-action",
    )

    assert [item.id for item in list_tickets_for_actor(
        db_session, actor_user_id=owner.id, actor_role="employee"
    )] == [ticket.id]
    assert list_tickets_for_actor(
        db_session, actor_user_id=other.id, actor_role="employee"
    ) == []
    assert ticket.id in {
        item.id for item in list_tickets_for_actor(
            db_session, actor_user_id=support.id, actor_role="support"
        )
    }

    try:
        get_ticket_for_actor(
            db_session,
            actor_user_id=other.id,
            actor_role="employee",
            public_id=ticket.public_id,
        )
    except TicketNotFoundError:
        pass
    else:
        raise AssertionError("Cross-user ticket read should be hidden.")


def test_support_status_workflow_is_bounded(db_session: Session):
    owner = make_user(db_session, "workflow-owner")
    ticket = create_ticket_for_requester(
        db_session,
        requester_user_id=owner.id,
        description="Monitor failure",
        action_id="workflow-action",
    )

    in_progress = transition_ticket_status(
        db_session,
        actor_role="support",
        public_id=ticket.public_id,
        new_status="in_progress",
    )
    assert in_progress.status == "in_progress"

    resolved = transition_ticket_status(
        db_session,
        actor_role="support",
        public_id=ticket.public_id,
        new_status="resolved",
    )
    assert resolved.status == "resolved"

    try:
        transition_ticket_status(
            db_session,
            actor_role="support",
            public_id=ticket.public_id,
            new_status="created",
        )
    except TicketTransitionError:
        pass
    else:
        raise AssertionError("Resolved tickets must not reopen in R2.")
