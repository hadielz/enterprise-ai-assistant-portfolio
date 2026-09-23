"""
Dependency bundle for the enterprise-agent workflow.

Architecture Notes
------------------
Purpose:
    Provide narrow, request-safe replacement points around external or
    stateful boundaries while keeping the LangGraph workflow itself real.

Production behavior:
    Every field defaults to the existing production implementation.
    The global enterprise agent is built with these defaults.

Evaluation behavior:
    v1C targets can build a separate graph with controlled providers,
    retrieval, persistence, and side-effect functions. No global monkey
    patching or external service call is required.
"""

from dataclasses import dataclass
from typing import Any, Callable

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
class AgentDependencies:
    """Callable boundaries used by enterprise-agent nodes."""

    get_recent_messages: Callable[..., list[dict]] = get_recent_messages
    get_summary: Callable[..., str] = get_summary
    build_history_context: Callable[..., list[dict]] = build_history_context

    route_tool: Callable[..., dict | None] = route_tool
    retrieve_context: Callable[[str], dict] = retrieve_context
    get_llm_provider: Callable[[], Any] = get_llm_provider

    add_exchange: Callable[..., Any] = add_exchange
    maybe_summarize_conversation: Callable[..., Any] = (
        maybe_summarize_conversation
    )
