"""MCP server for bounded enterprise capabilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database.session import SessionLocal
from app.health import database_is_ready
from app.observability.tracing import start_span
from app.tools.calculator_tool import calculate
from app.tickets.service import create_ticket_for_requester

TicketCreator = Callable[..., Any]


def _production_ticket_creator(
    *,
    description: str,
    requester_user_id: int,
    action_id: str,
) -> dict:
    with start_span(
        "ticket.create",
        **{"ticket.action_id": action_id, "ticket.requester_user_id": requester_user_id},
    ) as span:
        with SessionLocal() as session:
            ticket = create_ticket_for_requester(
                session,
                requester_user_id=requester_user_id,
                description=description,
                action_id=action_id,
            )
            span.set_attribute("ticket.id", ticket.public_id)
            span.set_attribute("ticket.status", ticket.status)
            return {
                "ticket_id": ticket.public_id,
                "requester_user_id": ticket.requester_user_id,
                "description": ticket.description,
                "status": ticket.status,
                "action_id": ticket.action_id,
            }


def build_mcp_server(ticket_creator: TicketCreator | None = None) -> MCPServer:
    create_persisted_ticket = ticket_creator or _production_ticket_creator
    server = MCPServer("Enterprise AI Assistant Tools")

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request):
        return JSONResponse({"status": "ok"})

    @server.custom_route("/ready", methods=["GET"])
    async def readiness(_request: Request):
        if not database_is_ready():
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ready"})

    @server.tool()
    def calculator(expression: str) -> str:
        return calculate(expression)

    @server.tool()
    def create_it_ticket(
        description: str,
        requester_user_id: int,
        action_id: str,
    ) -> dict[str, str | int]:
        return create_persisted_ticket(
            description=description,
            requester_user_id=requester_user_id,
            action_id=action_id,
        )

    return server


mcp = build_mcp_server()
