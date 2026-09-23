"""
Agent state.

LangGraph passes a shared state object between nodes.
Each node reads from the state and returns state updates.
"""

from typing import TypedDict

from sqlalchemy.orm import Session


class AgentState(TypedDict, total=False):
    message: str
    conversation_id: str
    user_id: int
    db_session: Session

    request_id: str
    prompt_ids: list[str]

    history: list[dict]
    tool_result: dict | None
    rag_context: str
    sources: list[str]
    response: str

    used_rag: bool
    tool_used: str | None
    route: str

    provider: str
    model: str
    fallback_used: bool

    agent_steps: list[str]