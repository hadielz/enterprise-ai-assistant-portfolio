"""Actual MCP Streamable-HTTP client/server round-trip for ticket creation."""

import asyncio
import contextlib
import socket
import threading
import time

import uvicorn
from mcp import Client
from starlette.applications import Starlette
from starlette.routing import Mount

from app.mcp.server import build_mcp_server


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_ticket_tool_round_trips_over_real_mcp_streamable_http():
    calls = []

    def bounded_creator(*, description, requester_user_id, action_id):
        calls.append((description, requester_user_id, action_id))
        return {
            "ticket_id": "TICKET-CONTROLLED-MCP",
            "requester_user_id": requester_user_id,
            "description": description,
            "status": "created",
            "action_id": action_id,
        }

    mcp_server = build_mcp_server(ticket_creator=bounded_creator)
    mcp_app = mcp_server.streamable_http_app(
        stateless_http=True,
        json_response=True,
    )

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with mcp_server.session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/server", app=mcp_app)],
        lifespan=lifespan,
    )

    port = _free_port()

    uvicorn_server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
    )

    thread = threading.Thread(
        target=uvicorn_server.run,
        daemon=True,
    )
    thread.start()

    deadline = time.time() + 5

    while (
        not uvicorn_server.started
        and time.time() < deadline
    ):
        time.sleep(0.02)

    assert uvicorn_server.started

    async def call_tool():
        async with Client(
            f"http://127.0.0.1:{port}/server/mcp"
        ) as client:
            return await client.call_tool(
                "create_it_ticket",
                {
                    "description": "Protocol test ticket",
                    "requester_user_id": 42,
                    "action_id": "protocol-action-1",
                },
            )

    try:
        result = asyncio.run(call_tool())
    finally:
        uvicorn_server.should_exit = True
        thread.join(timeout=5)

    assert result.is_error is False

    assert (
        result.structured_content["ticket_id"]
        == "TICKET-CONTROLLED-MCP"
    )

    assert (
        result.structured_content["action_id"]
        == "protocol-action-1"
    )

    assert calls == [
        ("Protocol test ticket", 42, "protocol-action-1")
    ]