"""Ticket MCP failure must never be converted into fabricated success."""

import pytest

from app.mcp.client import (
    TicketCapabilityError,
    _validate_ticket_payload,
)
from app.tools.execution_context import ToolExecutionContext
from app.tools.tool_router import route_tool


def test_mcp_failure_returns_deterministic_non_success_outcome():
    def selector(_):
        return {
            "tool_name": "ticket_creator",
            "tool_input": "WiFi issue",
        }

    def failing_creator(description, *, execution_context):
        raise TicketCapabilityError("controlled MCP outage")

    result = route_tool(
        "Create a ticket for my WiFi issue.",
        execution_context=ToolExecutionContext(
            user_id=7,
            request_id="r2-fail",
        ),
        tool_selector=selector,
        ticket_creator=failing_creator,
    )

    assert result["action_status"] == "failed"
    assert result["side_effect_executed"] is False
    assert "could not be created" in result["failure_message"]
    assert "created successfully" not in result["failure_message"]


def test_mcp_ticket_payload_must_match_trusted_context():
    context = ToolExecutionContext(
        user_id=7,
        request_id="trusted-action",
    )

    valid_payload = {
        "ticket_id": "TICKET-CONTROLLED",
        "requester_user_id": 7,
        "description": "WiFi issue",
        "status": "created",
        "action_id": "trusted-action",
    }

    assert _validate_ticket_payload(
        valid_payload,
        execution_context=context,
        requested_description="WiFi issue",
    ) == valid_payload

    wrong_requester = {
        **valid_payload,
        "requester_user_id": 999,
    }

    with pytest.raises(TicketCapabilityError):
        _validate_ticket_payload(
            wrong_requester,
            execution_context=context,
            requested_description="WiFi issue",
        )

    wrong_action = {
        **valid_payload,
        "action_id": "different-action",
    }

    with pytest.raises(TicketCapabilityError):
        _validate_ticket_payload(
            wrong_action,
            execution_context=context,
            requested_description="WiFi issue",
        )


def test_mcp_ticket_payload_rejects_invalid_business_result():
    context = ToolExecutionContext(
        user_id=7,
        request_id="trusted-action",
    )

    with pytest.raises(TicketCapabilityError):
        _validate_ticket_payload(
            {
                "ticket_id": "TICKET-CONTROLLED",
                "requester_user_id": 7,
                "description": "Different issue",
                "status": "created",
                "action_id": "trusted-action",
            },
            execution_context=context,
            requested_description="WiFi issue",
        )

    with pytest.raises(TicketCapabilityError):
        _validate_ticket_payload(
            {
                "ticket_id": "TICKET-CONTROLLED",
                "requester_user_id": 7,
                "description": "WiFi issue",
                "status": "unknown",
                "action_id": "trusted-action",
            },
            execution_context=context,
            requested_description="WiFi issue",
        )