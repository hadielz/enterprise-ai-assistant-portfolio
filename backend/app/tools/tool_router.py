"""Tool selection and bounded execution.

The LLM proposes a tool. Deterministic application policy remains the authority
for side effects, and trusted execution context remains separate from model
output.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from inspect import signature
from typing import Any

from app.mcp.client import TicketCapabilityError
from app.observability.logging import log_event
from app.observability.tracing import start_span
from app.tools.calculator_tool import calculate
from app.tools.execution_context import ToolExecutionContext
from app.tools.safe_actions import (
    CONFIRMATION_REQUIRED_MESSAGE,
    TicketActionDecision,
    evaluate_ticket_action,
)
from app.tools.ticket_tool import create_ticket
from app.tools.tool_selection import ToolSelectionResult
from app.tools.tool_selector import select_tool

logger = logging.getLogger(__name__)

ToolSelector = Callable[[str], ToolSelectionResult | dict[str, Any]]
Calculator = Callable[[str], str]
TicketCreator = Callable[..., dict]
TicketActionPolicy = Callable[[str], TicketActionDecision]

TICKET_FAILURE_MESSAGE = (
    "The ticket could not be created because the ticket service did not "
    "confirm durable creation. Please try again later."
)


def _to_legacy_decision(
    selection: ToolSelectionResult | dict[str, Any],
) -> dict[str, Any]:
    if isinstance(selection, ToolSelectionResult):
        return selection.to_legacy_decision()
    return selection


def route_tool(
    message: str,
    *,
    execution_context: ToolExecutionContext | None = None,
    tool_selector: ToolSelector | None = None,
    calculator: Calculator | None = None,
    ticket_creator: TicketCreator | None = None,
    ticket_action_policy: TicketActionPolicy | None = None,
) -> dict | None:
    """Select and execute one bounded tool when appropriate."""

    selector = tool_selector or select_tool
    calculate_tool = calculator or calculate
    create_ticket_tool = ticket_creator or create_ticket
    decide_ticket_action = ticket_action_policy or evaluate_ticket_action

    decision = _to_legacy_decision(selector(message))
    tool_name = decision["tool_name"]
    tool_input = decision["tool_input"]

    if tool_name == "calculator":
        with start_span("tool.calculator.execute", **{"tool.name": "calculator"}):
            return {
                "tool_name": "calculator",
                "tool_result": calculate_tool(tool_input),
            }

    if tool_name == "ticket_creator":
        action_decision = decide_ticket_action(message)

        if action_decision.status == "troubleshooting":
            log_event(
                logger,
                logging.INFO,
                "safe_action_decision",
                tool_name="ticket_creator",
                action_status="rejected_troubleshooting",
            )
            return None

        if action_decision.confirmation_required:
            log_event(
                logger,
                logging.INFO,
                "safe_action_decision",
                tool_name="ticket_creator",
                action_status="confirmation_required",
            )
            return {
                "tool_name": None,
                "tool_result": None,
                "requested_tool_name": "ticket_creator",
                "action_status": "confirmation_required",
                "side_effect_executed": False,
                "confirmation_message": CONFIRMATION_REQUIRED_MESSAGE,
            }

        log_event(
            logger,
            logging.INFO,
            "safe_action_decision",
            tool_name="ticket_creator",
            action_status="allowed",
        )

        try:
            with start_span("tool.ticket.execute", **{"tool.name": "ticket_creator"}):
                if ticket_creator is None:
                    if execution_context is None:
                        raise TicketCapabilityError(
                            "Authenticated ticket execution context is required."
                        )
                    ticket = create_ticket_tool(
                        tool_input,
                        execution_context=execution_context,
                    )
                elif "execution_context" in signature(create_ticket_tool).parameters:
                    if execution_context is None:
                        raise TicketCapabilityError(
                            "Authenticated ticket execution context is required."
                        )
                    ticket = create_ticket_tool(
                        tool_input,
                        execution_context=execution_context,
                    )
                else:
                    ticket = create_ticket_tool(tool_input)
        except TicketCapabilityError as exc:
            log_event(
                logger,
                logging.ERROR,
                "ticket_action_failed",
                tool_name="ticket_creator",
                action_status="failed",
                error_class=type(exc).__name__,
            )
            return {
                "tool_name": None,
                "tool_result": None,
                "requested_tool_name": "ticket_creator",
                "action_status": "failed",
                "side_effect_executed": False,
                "failure_message": TICKET_FAILURE_MESSAGE,
            }

        log_event(
            logger,
            logging.INFO,
            "ticket_action_committed",
            tool_name="ticket_creator",
            action_status="committed",
            ticket_id=ticket["ticket_id"],
        )
        return {
            "tool_name": "ticket_creator",
            "tool_result": (
                f"Ticket {ticket['ticket_id']} was created successfully. "
                f"Status: {ticket['status']}. "
                f"Description: {ticket['description']}"
            ),
            "ticket_id": ticket["ticket_id"],
            "ticket_status": ticket["status"],
            "side_effect_executed": True,
        }

    return None
