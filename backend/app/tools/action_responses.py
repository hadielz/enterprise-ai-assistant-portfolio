"""Deterministic user-facing fallbacks for already-committed side effects."""

from __future__ import annotations


def committed_ticket_response(ticket_id: str | None) -> str:
    """Confirm durable creation even when final LLM wording cannot be produced."""

    if ticket_id:
        return (
            f"Ticket {ticket_id} was created successfully and is persisted, "
            "but I could not generate the usual follow-up message. "
            "You can view the ticket in the ticket workspace."
        )

    return (
        "The ticket was created successfully and is persisted, but I could not "
        "generate the usual follow-up message. You can view it in the ticket "
        "workspace."
    )
