"""
Enterprise agent powered by LangGraph.

Architecture Notes
------------------
Purpose:
    Move the assistant from manual service orchestration toward
    a graph-based agent workflow.

Why LangGraph:
    LangGraph makes state, steps, branching, and future multi-agent
    workflows explicit instead of hiding them inside one large function.

Current graph:
    load_context -> select_tool -> supervisor -> retrieve_rag/generate_answer

Controlled workflow seam:
    build_enterprise_agent() accepts AgentDependencies. Production uses the
    default dependency bundle; offline evaluations can build an isolated
    graph around the same nodes with deterministic dependencies.
"""

import logging

from langgraph.graph import END, START, StateGraph

from app.agents.dependencies import AgentDependencies
from app.agents.state import AgentState
from app.llm.errors import LLMProviderError
from app.prompts.rag_prompts import build_rag_prompt
from app.observability.logging import log_event
from app.observability.tracing import start_span
from app.tools.action_responses import committed_ticket_response
from app.tools.execution_context import ToolExecutionContext
from app.prompts.registry import (
    ASSISTANT_SYSTEM_PROMPT,
    RAG_ANSWER_PROMPT,
    TOOL_ANSWER_PROMPT,
)


logger = logging.getLogger(__name__)

DEFAULT_AGENT_DEPENDENCIES = AgentDependencies()


def load_context_node(
    state: AgentState,
    dependencies: AgentDependencies = DEFAULT_AGENT_DEPENDENCIES,
) -> AgentState:
    conversation_id = state["conversation_id"]
    user_id = state["user_id"]
    session = state["db_session"]

    recent_history = dependencies.get_recent_messages(
        session=session,
        user_id=user_id,
        public_id=conversation_id,
    )

    summary = dependencies.get_summary(
        session=session,
        user_id=user_id,
        public_id=conversation_id,
    )

    history = dependencies.build_history_context(
        summary,
        recent_history,
    )

    return {
        "history": history,
        "agent_steps": ["load_context"],
    }


def select_tool_node(
    state: AgentState,
    dependencies: AgentDependencies = DEFAULT_AGENT_DEPENDENCIES,
) -> AgentState:
    tool_result = dependencies.route_tool(
        state["message"],
        execution_context=ToolExecutionContext(
            user_id=state["user_id"],
            request_id=state["request_id"],
        ),
    )

    return {
        "tool_result": tool_result,
        "agent_steps": (
            state.get("agent_steps", [])
            + ["select_tool"]
        ),
    }


def retrieve_rag_node(
    state: AgentState,
    dependencies: AgentDependencies = DEFAULT_AGENT_DEPENDENCIES,
) -> AgentState:
    with start_span("agent.rag_retrieval"):
        retrieval = dependencies.retrieve_context(state["message"])

    return {
        "rag_context": retrieval["context"],
        "sources": retrieval["sources"],
        "used_rag": bool(retrieval["context"]),
        "agent_steps": (
            state.get("agent_steps", [])
            + ["retrieve_rag"]
        ),
    }


def generate_answer_node(
    state: AgentState,
    dependencies: AgentDependencies = DEFAULT_AGENT_DEPENDENCIES,
) -> AgentState:
    message = state["message"]
    history = state.get("history", [])
    conversation_id = state["conversation_id"]
    user_id = state["user_id"]
    session = state["db_session"]

    tool_result = state.get("tool_result")
    rag_context = state.get("rag_context", "")

    prompt_ids = [
        ASSISTANT_SYSTEM_PROMPT.prompt_id,
    ]

    if (
        tool_result
        and tool_result.get("action_status") in {"confirmation_required", "failed"}
    ):
        # This response is deterministic application policy, not model output.
        # No prompt authorizes or performs the side effect.
        response = (
            tool_result["confirmation_message"]
            if tool_result.get("action_status") == "confirmation_required"
            else tool_result["failure_message"]
        )
        prompt_ids = []
        tool_used = None
        used_rag = False
        sources = []

    elif tool_result:
        llm_provider = dependencies.get_llm_provider()

        prompt_ids.append(
            TOOL_ANSWER_PROMPT.prompt_id
        )

        final_message = TOOL_ANSWER_PROMPT.template.format(
            message=message,
            tool_name=tool_result["tool_name"],
            tool_result=tool_result["tool_result"],
        )

        if tool_result.get("side_effect_executed"):
            log_event(
                logger, logging.INFO, "tool_side_effect_committed",
                tool_name=tool_result.get("tool_name"),
                action_status="committed",
                ticket_id=tool_result.get("ticket_id"),
            )

        try:
            response = llm_provider.generate(
                final_message,
                history=history,
            )
        except LLMProviderError:
            if not tool_result.get("side_effect_executed"):
                raise
            log_event(
                logger,
                logging.ERROR,
                "tool_answer_generation_failed_after_side_effect",
                tool_name=tool_result.get("tool_name"),
                action_status="committed_response_failed",
                ticket_id=tool_result.get("ticket_id"),
            )
            response = committed_ticket_response(tool_result.get("ticket_id"))
        except Exception:
            if tool_result.get("side_effect_executed"):
                log_event(
                    logger,
                    logging.ERROR,
                    "tool_answer_generation_failed_after_side_effect",
                    tool_name=tool_result.get("tool_name"),
                    action_status="committed_response_failed",
                    ticket_id=tool_result.get("ticket_id"),
                )
            raise

        tool_used = tool_result["tool_name"]
        used_rag = False
        sources = []

    elif rag_context:
        llm_provider = dependencies.get_llm_provider()

        prompt_ids.append(
            RAG_ANSWER_PROMPT.prompt_id
        )

        final_message = build_rag_prompt(
            message,
            rag_context,
        )

        response = llm_provider.generate(
            final_message,
            history=history,
        )

        tool_used = None
        used_rag = True
        sources = state.get("sources", [])

    else:
        llm_provider = dependencies.get_llm_provider()

        response = llm_provider.generate(
            message,
            history=history,
        )

        tool_used = None
        used_rag = False
        sources = []

    dependencies.add_exchange(
        session=session,
        user_id=user_id,
        public_id=conversation_id,
        user_message=message,
        assistant_message=response,
    )

    dependencies.maybe_summarize_conversation(
        session=session,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    return {
        "response": response,
        "tool_used": tool_used,
        "used_rag": used_rag,
        "sources": sources,
        "prompt_ids": prompt_ids,
        "agent_steps": (
            state.get("agent_steps", [])
            + ["generate_answer"]
        ),
    }


def supervisor_node(state: AgentState) -> AgentState:
    """
    Decide whether the request should use the tool or RAG workflow.
    """

    tool_result = state.get("tool_result")

    if tool_result and tool_result.get("action_status") == "confirmation_required":
        route = "confirmation"
    elif tool_result and tool_result.get("action_status") == "failed":
        route = "tool_failure"
    elif tool_result:
        route = "tool"
    else:
        route = "rag"

    return {
        "route": route,
        "agent_steps": (
            state.get("agent_steps", [])
            + ["supervisor"]
        ),
    }


def route_after_tool_selection(state: AgentState) -> str:
    """Route after the supervisor decision."""

    if state.get("route") in {"tool", "confirmation", "tool_failure"}:
        return "generate_answer"

    return "retrieve_rag"


def build_enterprise_agent(
    dependencies: AgentDependencies | None = None,
):
    """
    Build and compile the LangGraph workflow.

    A new graph is built for each controlled dependency bundle. The module's
    global production graph continues to use the existing defaults.
    """

    resolved = dependencies or DEFAULT_AGENT_DEPENDENCIES

    graph = StateGraph(AgentState)

    graph.add_node(
        "load_context",
        lambda state: load_context_node(state, resolved),
    )
    graph.add_node(
        "select_tool",
        lambda state: select_tool_node(state, resolved),
    )
    graph.add_node("supervisor", supervisor_node)
    graph.add_node(
        "retrieve_rag",
        lambda state: retrieve_rag_node(state, resolved),
    )
    graph.add_node(
        "generate_answer",
        lambda state: generate_answer_node(state, resolved),
    )

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "select_tool")
    graph.add_edge("select_tool", "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_tool_selection,
        {
            "generate_answer": "generate_answer",
            "retrieve_rag": "retrieve_rag",
        },
    )

    graph.add_edge("retrieve_rag", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


enterprise_agent = build_enterprise_agent()
