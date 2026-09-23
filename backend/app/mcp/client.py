"""Production MCP client for the persisted ticket capability."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.core.config import settings
from app.mcp.auth import build_mcp_headers
from app.observability.logging import log_event
from app.observability.tracing import start_span
from app.tools.execution_context import ToolExecutionContext

logger = logging.getLogger(__name__)


class TicketCapabilityError(RuntimeError):
    """Raised when durable ticket creation is not confirmed through MCP."""


def _normalize_description(description: str) -> str:
    return " ".join(description.split())


def _validate_ticket_payload(
    payload: Any,
    *,
    execution_context: ToolExecutionContext,
    requested_description: str,
) -> dict:
    if not isinstance(payload, dict):
        raise TicketCapabilityError("MCP ticket tool returned no structured result.")

    required = {
        "ticket_id": str,
        "requester_user_id": int,
        "description": str,
        "status": str,
        "action_id": str,
    }
    for field, expected_type in required.items():
        if not isinstance(payload.get(field), expected_type):
            raise TicketCapabilityError(
                f"MCP ticket tool returned invalid field: {field}."
            )

    if payload["requester_user_id"] != execution_context.user_id:
        raise TicketCapabilityError(
            "MCP ticket result does not match the authenticated requester."
        )
    if payload["action_id"] != execution_context.request_id:
        raise TicketCapabilityError(
            "MCP ticket result does not match the requested action identity."
        )
    if payload["status"] not in {"created", "in_progress", "resolved"}:
        raise TicketCapabilityError("MCP ticket result returned an unsupported status.")
    if not payload["ticket_id"].startswith("TICKET-"):
        raise TicketCapabilityError("MCP ticket result returned an invalid public ticket ID.")
    if payload["description"] != _normalize_description(requested_description):
        raise TicketCapabilityError(
            "MCP ticket result does not match the requested description."
        )
    return payload


async def _create_ticket_async(
    description: str,
    execution_context: ToolExecutionContext,
) -> dict:
    with start_span(
        "mcp.ticket.create",
        **{
            "mcp.operation": "create_it_ticket",
            "ticket.action_id": execution_context.request_id,
        },
    ) as span:
        try:
            headers = build_mcp_headers()
            async with httpx2.AsyncClient(
                headers=headers,
                follow_redirects=True,
                timeout=httpx2.Timeout(30.0, read=300.0),
            ) as http_client:
                transport = streamable_http_client(
                    settings.mcp_ticket_url,
                    http_client=http_client,
                )
                async with Client(transport) as client:
                    result = await client.call_tool(
                        "create_it_ticket",
                        {
                            "description": description,
                            "requester_user_id": execution_context.user_id,
                            "action_id": execution_context.request_id,
                        },
                    )
        except Exception as exc:
            span.set_attribute("mcp.outcome", "unavailable")
            log_event(
                logger,
                logging.ERROR,
                "mcp_ticket_call_failed",
                error_class=type(exc).__name__,
            )
            raise TicketCapabilityError(
                "The ticket service is currently unavailable."
            ) from exc

        if result.is_error:
            span.set_attribute("mcp.outcome", "tool_error")
            raise TicketCapabilityError("The ticket service did not create a ticket.")

        try:
            payload = _validate_ticket_payload(
                result.structured_content,
                execution_context=execution_context,
                requested_description=description,
            )
        except TicketCapabilityError:
            span.set_attribute("mcp.outcome", "validation_failed")
            raise

        span.set_attribute("mcp.outcome", "success")
        span.set_attribute("ticket.id", payload["ticket_id"])
        return payload


def create_ticket_via_mcp(
    description: str,
    *,
    execution_context: ToolExecutionContext,
) -> dict:
    if execution_context is None:
        raise TicketCapabilityError("Authenticated ticket context is required.")
    return asyncio.run(_create_ticket_async(description, execution_context))
