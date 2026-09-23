"""
Dependency bundle for chat service entry points.

Architecture Notes
------------------
Purpose:
    Keep HTTP-facing service behavior unchanged while allowing controlled
    offline execution of non-streaming and streaming paths.

Boundary:
    This bundle replaces only dependencies. It does not expose evaluation
    metadata through API schemas or the frontend.
"""

from dataclasses import dataclass
from typing import Any, Callable

from app.agents.enterprise_agent import enterprise_agent
from app.database.conversation_repository import (
    add_exchange,
    get_recent_messages,
    get_summary,
)
from app.llm.factory import get_llm_provider
from app.memory.conversation_summary import build_history_context
from app.memory.summarizer import maybe_summarize_conversation
from app.rag.retriever import retrieve_context
from app.tools.tool_router import route_tool


@dataclass(frozen=True)
class ChatServiceDependencies:
    """Callable and object boundaries used by chat service functions."""

    enterprise_agent: Any = enterprise_agent
    get_llm_provider: Callable[[], Any] = get_llm_provider

    get_recent_messages: Callable[..., list[dict]] = get_recent_messages
    get_summary: Callable[..., str] = get_summary
    build_history_context: Callable[..., list[dict]] = build_history_context

    route_tool: Callable[..., dict | None] = route_tool
    retrieve_context: Callable[[str], dict] = retrieve_context

    add_exchange: Callable[..., Any] = add_exchange
    maybe_summarize_conversation: Callable[..., Any] = (
        maybe_summarize_conversation
    )
