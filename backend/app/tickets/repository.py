"""PostgreSQL repository for persisted support tickets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Ticket


def get_ticket_by_public_id(session: Session, public_id: str) -> Ticket | None:
    return session.scalar(select(Ticket).where(Ticket.public_id == public_id))


def get_ticket_by_action_id(session: Session, action_id: str) -> Ticket | None:
    return session.scalar(select(Ticket).where(Ticket.action_id == action_id))


def list_tickets_for_requester(session: Session, requester_user_id: int) -> list[Ticket]:
    return list(
        session.scalars(
            select(Ticket)
            .where(Ticket.requester_user_id == requester_user_id)
            .order_by(Ticket.id.desc())
        )
    )


def list_all_tickets(session: Session) -> list[Ticket]:
    return list(session.scalars(select(Ticket).order_by(Ticket.id.desc())))


def create_ticket(
    session: Session,
    *,
    public_id: str,
    requester_user_id: int,
    description: str,
    status: str,
    action_id: str,
) -> Ticket:
    """Create one ticket, using action_id as a small idempotency key."""

    existing = get_ticket_by_action_id(session, action_id)
    if existing is not None:
        return existing

    ticket = Ticket(
        public_id=public_id,
        requester_user_id=requester_user_id,
        description=description,
        status=status,
        action_id=action_id,
    )
    session.add(ticket)

    try:
        session.commit()
    except IntegrityError:
        # A concurrent retry with the same action identity may win the race.
        session.rollback()
        existing = get_ticket_by_action_id(session, action_id)
        if existing is not None:
            return existing
        raise

    session.refresh(ticket)
    return ticket


def save_ticket(session: Session, ticket: Ticket) -> Ticket:
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket
