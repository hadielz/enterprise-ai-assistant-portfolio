"""Authenticated REST API for the bounded R2 ticket workflow."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.models import Ticket
from app.database.session import get_db_session
from app.schemas.ticket import TicketResponse, TicketStatusUpdateRequest
from app.core.config import settings
from app.security.rate_limit import enforce_rate_limit
from app.tickets.service import (
    TicketAuthorizationError,
    TicketNotFoundError,
    TicketTransitionError,
    TicketValidationError,
    get_ticket_for_actor,
    list_tickets_for_actor,
    transition_ticket_status,
)


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _to_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse(
        ticket_id=ticket.public_id,
        requester_username=ticket.requester.username,
        description=ticket.description,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    return [
        _to_response(ticket)
        for ticket in list_tickets_for_actor(
            session,
            actor_user_id=current_user["id"],
            actor_role=current_user["role"],
        )
    ]


@router.get("/{ticket_id}", response_model=TicketResponse)
def read_ticket(
    ticket_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    try:
        ticket = get_ticket_for_actor(
            session,
            actor_user_id=current_user["id"],
            actor_role=current_user["role"],
            public_id=ticket_id,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(ticket)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: str,
    request: TicketStatusUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
):
    enforce_rate_limit(
        scope="tickets.status.user",
        key=str(current_user["id"]),
        limit=settings.rate_limit_ticket_status_limit,
        window_seconds=settings.rate_limit_ticket_status_window_seconds,
    )

    try:
        ticket = transition_ticket_status(
            session,
            actor_role=current_user["role"],
            public_id=ticket_id,
            new_status=request.status,
        )
    except TicketAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TicketTransitionError, TicketValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_response(ticket)
