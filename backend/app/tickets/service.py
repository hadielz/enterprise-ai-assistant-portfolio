"""Bounded business service for the persisted ticket workflow.

The LLM never receives a Session or repository. Authenticated application
identity is supplied by trusted backend/MCP context and ownership/status rules
are enforced here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorization import PRIVILEGED_SUPPORT_ROLE
from app.database.models import Ticket, User
from app.tickets import repository
from app.observability.logging import log_event
from app.observability.tracing import start_span


logger = logging.getLogger(__name__)

TICKET_STATUS_CREATED = "created"
TICKET_STATUS_IN_PROGRESS = "in_progress"
TICKET_STATUS_RESOLVED = "resolved"
TICKET_STATUSES = {
    TICKET_STATUS_CREATED,
    TICKET_STATUS_IN_PROGRESS,
    TICKET_STATUS_RESOLVED,
}
_ALLOWED_TRANSITIONS = {
    TICKET_STATUS_CREATED: {TICKET_STATUS_IN_PROGRESS},
    TICKET_STATUS_IN_PROGRESS: {TICKET_STATUS_RESOLVED},
    TICKET_STATUS_RESOLVED: set(),
}


class TicketError(RuntimeError):
    """Base exception for bounded ticket-domain failures."""


class TicketNotFoundError(TicketError):
    pass


class TicketAuthorizationError(TicketError):
    pass


class TicketValidationError(TicketError):
    pass


class TicketTransitionError(TicketError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_description(description: str) -> str:
    normalized = " ".join(description.split())
    if not normalized:
        raise TicketValidationError("Ticket description cannot be empty.")
    if len(normalized) > 2000:
        raise TicketValidationError("Ticket description is too long.")
    return normalized


def create_ticket_for_requester(
    session: Session,
    *,
    requester_user_id: int,
    description: str,
    action_id: str,
) -> Ticket:
    """Create exactly one ticket for one trusted action identity."""

    normalized_action_id = action_id.strip()
    if not normalized_action_id:
        raise TicketValidationError("Ticket action ID cannot be empty.")

    requester = session.scalar(
        select(User).where(
            User.id == requester_user_id,
            User.is_active.is_(True),
        )
    )
    if requester is None:
        raise TicketValidationError("Ticket requester is not an active user.")

    existing = repository.get_ticket_by_action_id(session, normalized_action_id)
    if existing is not None:
        if existing.requester_user_id != requester_user_id:
            raise TicketAuthorizationError(
                "Ticket action identity belongs to another requester."
            )
        log_event(
            logger, logging.INFO, "ticket_idempotent_replay",
            ticket_id=existing.public_id, action_status="idempotent_replay",
        )
        return existing

    with start_span(
        "ticket.repository.create",
        **{"ticket.action_id": normalized_action_id},
    ) as span:
        ticket = repository.create_ticket(
            session,
            public_id=f"TICKET-{uuid4()}",
            requester_user_id=requester_user_id,
            description=_normalize_description(description),
            status=TICKET_STATUS_CREATED,
            action_id=normalized_action_id,
        )
        span.set_attribute("ticket.id", ticket.public_id)
        span.set_attribute("ticket.status", ticket.status)
    log_event(
        logger, logging.INFO, "ticket_created",
        ticket_id=ticket.public_id, action_status="created",
    )
    return ticket


def list_tickets_for_actor(
    session: Session,
    *,
    actor_user_id: int,
    actor_role: str,
) -> list[Ticket]:
    if actor_role == PRIVILEGED_SUPPORT_ROLE:
        return repository.list_all_tickets(session)
    return repository.list_tickets_for_requester(session, actor_user_id)


def get_ticket_for_actor(
    session: Session,
    *,
    actor_user_id: int,
    actor_role: str,
    public_id: str,
) -> Ticket:
    ticket = repository.get_ticket_by_public_id(session, public_id)
    if ticket is None:
        raise TicketNotFoundError("Ticket not found.")
    if (
        actor_role != PRIVILEGED_SUPPORT_ROLE
        and ticket.requester_user_id != actor_user_id
    ):
        # Do not reveal another employee's ticket existence.
        raise TicketNotFoundError("Ticket not found.")
    return ticket


def transition_ticket_status(
    session: Session,
    *,
    actor_role: str,
    public_id: str,
    new_status: str,
) -> Ticket:
    if actor_role != PRIVILEGED_SUPPORT_ROLE:
        raise TicketAuthorizationError("Support role is required.")
    if new_status not in TICKET_STATUSES:
        raise TicketValidationError("Unsupported ticket status.")

    ticket = repository.get_ticket_by_public_id(session, public_id)
    if ticket is None:
        raise TicketNotFoundError("Ticket not found.")

    if ticket.status == new_status:
        return ticket

    if new_status not in _ALLOWED_TRANSITIONS[ticket.status]:
        raise TicketTransitionError(
            f"Ticket cannot transition from {ticket.status} to {new_status}."
        )

    old_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = utc_now()
    saved = repository.save_ticket(session, ticket)
    log_event(
        logger, logging.INFO, "ticket_status_transition",
        ticket_id=saved.public_id, old_status=old_status, new_status=new_status,
    )
    return saved
