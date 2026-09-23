"""
Business logic for chat.

This file is now the service entry point for chat requests.

Architecture Notes
------------------
Before LangGraph, this file manually handled:
- memory
- tool selection
- RAG retrieval
- LLM response generation

Now, normal chat responses are delegated to the LangGraph enterprise agent.
Streaming is intentionally handled here as a separate orchestration path.
AI Quality parity tests characterize differences from the LangGraph path.
"""

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.llm.errors import LLMProviderError
from app.prompts.rag_prompts import build_rag_prompt
from app.prompts.registry import (
    ASSISTANT_SYSTEM_PROMPT,
    RAG_ANSWER_PROMPT,
    TOOL_ANSWER_PROMPT,
)
from app.services.chat_dependencies import ChatServiceDependencies
from app.tools.action_responses import committed_ticket_response
from app.tools.execution_context import ToolExecutionContext
from app.observability.context import bind_request_context
from app.observability.logging import log_event
from app.observability.tracing import start_span


logger = logging.getLogger(__name__)


def generate_response(
    message: str,
    conversation_id: str,
    user_id: int,
    session: Session,
    *,
    dependencies: ChatServiceDependencies | None = None,
) -> dict:
    """
    Generate a response using the LangGraph enterprise agent.
    """

    resolved = dependencies or ChatServiceDependencies()
    request_id = str(uuid4())

    logger.info(
        "AI generation started request_id=%s user_id=%s "
        "conversation_id=%s",
        request_id,
        user_id,
        conversation_id,
    )

    try:
        with bind_request_context(
            request_id=request_id,
            conversation_id=conversation_id,
        ), start_span(
            "assistant.generate",
            **{
                "app.request_id": request_id,
                "conversation.id": conversation_id,
            },
        ) as span:
            result = resolved.enterprise_agent.invoke(
                {
                    "message": message,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "db_session": session,
                    "request_id": request_id,
                }
            )
            span.set_attribute("ai.route", result.get("route", "unknown"))
            span.set_attribute("ai.used_rag", result.get("used_rag", False))
            if result.get("tool_used"):
                span.set_attribute("ai.tool", result["tool_used"])

    except Exception:
        logger.exception(
            "AI generation failed request_id=%s user_id=%s "
            "conversation_id=%s",
            request_id,
            user_id,
            conversation_id,
        )
        raise

    logger.info(
        "AI generation completed request_id=%s route=%s "
        "used_rag=%s tool_used=%s prompt_ids=%s sources=%s",
        request_id,
        result.get("route", "unknown"),
        result.get("used_rag", False),
        result.get("tool_used"),
        result.get("prompt_ids", []),
        result.get("sources", []),
    )

    return {
        "response": result["response"],
        "used_rag": result.get("used_rag", False),
        "sources": result.get("sources", []),
        "conversation_id": conversation_id,
        "tool_used": result.get("tool_used"),
        "agent_steps": result.get("agent_steps", []),
    }


def stream_response(
    message: str,
    conversation_id: str,
    user_id: int,
    session: Session,
    *,
    dependencies: ChatServiceDependencies | None = None,
):
    """
    Stream the assistant response progressively.

    Architecture Notes
    ------------------
    The streaming endpoint follows the same broad decision process as
    the normal endpoint:

    1. Load conversation memory.
    2. Select and execute a tool when needed.
    3. Otherwise retrieve RAG context.
    4. Stream the final LLM answer.
    5. Persist the complete exchange after streaming finishes.

    Streaming currently remains service-orchestrated rather than LangGraph-native.
    """

    resolved = dependencies or ChatServiceDependencies()
    request_id = str(uuid4())

    logger.info(
        "Streaming AI generation started request_id=%s "
        "user_id=%s conversation_id=%s",
        request_id,
        user_id,
        conversation_id,
    )

    request_context = bind_request_context(
        request_id=request_id,
        conversation_id=conversation_id,
    )
    request_context.__enter__()
    request_span = start_span(
        "assistant.stream",
        **{
            "app.request_id": request_id,
            "conversation.id": conversation_id,
        },
    )
    stream_span = request_span.__enter__()

    try:
        route = "chat"
        prompt_ids = [
            ASSISTANT_SYSTEM_PROMPT.prompt_id,
        ]
        tool_name = None
        sources = []

        recent_history = resolved.get_recent_messages(
            session=session,
            user_id=user_id,
            public_id=conversation_id,
        )

        summary = resolved.get_summary(
            session=session,
            user_id=user_id,
            public_id=conversation_id,
        )

        history = resolved.build_history_context(
            summary,
            recent_history,
        )

        tool_result = resolved.route_tool(
            message,
            execution_context=ToolExecutionContext(
                user_id=user_id,
                request_id=request_id,
            ),
        )

        if (
            tool_result
            and tool_result.get("action_status") in {"confirmation_required", "failed"}
        ):
            route = (
                "confirmation"
                if tool_result.get("action_status") == "confirmation_required"
                else "tool_failure"
            )
            prompt_ids = []
            final_message = None

            logger.info(
                "Streaming deterministic action outcome request_id=%s "
                "route=%s requested_tool=%s",
                request_id,
                route,
                tool_result.get("requested_tool_name"),
            )

        elif tool_result:
            route = "tool"
            tool_name = tool_result["tool_name"]

            prompt_ids.append(
                TOOL_ANSWER_PROMPT.prompt_id
            )

            final_message = TOOL_ANSWER_PROMPT.template.format(
                message=message,
                tool_name=tool_name,
                tool_result=tool_result["tool_result"],
            )

            logger.info(
                "Streaming route selected request_id=%s "
                "route=%s tool_name=%s prompt_ids=%s",
                request_id,
                route,
                tool_name,
                prompt_ids,
            )

            if tool_result.get("side_effect_executed"):
                log_event(
                    logger, logging.INFO, "tool_side_effect_committed",
                    tool_name=tool_name, action_status="committed",
                    ticket_id=tool_result.get("ticket_id"),
                )

        else:
            retrieval = resolved.retrieve_context(message)
            context = retrieval["context"]

            if context:
                route = "rag"
                sources = retrieval["sources"]

                prompt_ids.append(
                    RAG_ANSWER_PROMPT.prompt_id
                )

                final_message = build_rag_prompt(
                    message,
                    context,
                )

                logger.info(
                    "Streaming route selected request_id=%s "
                    "route=%s prompt_ids=%s sources=%s",
                    request_id,
                    route,
                    prompt_ids,
                    sources,
                )

            else:
                final_message = message

                logger.info(
                    "Streaming route selected request_id=%s "
                    "route=%s prompt_ids=%s",
                    request_id,
                    route,
                    prompt_ids,
                )

        full_response = ""

        if route in {"confirmation", "tool_failure"}:
            full_response = (
                tool_result["confirmation_message"]
                if route == "confirmation"
                else tool_result["failure_message"]
            )
            yield full_response

        else:
            llm_provider = resolved.get_llm_provider()

            try:
                for token in llm_provider.stream(
                    final_message,
                    history=history,
                ):
                    full_response += token
                    yield token

            except LLMProviderError:
                side_effect_committed = bool(
                    tool_result and tool_result.get("side_effect_executed")
                )
                if side_effect_committed:
                    log_event(
                        logger,
                        logging.ERROR,
                        "tool_answer_generation_failed_after_side_effect",
                        tool_name=tool_name,
                        action_status="committed_response_failed",
                        ticket_id=tool_result.get("ticket_id"),
                    )
                    failure_message = committed_ticket_response(
                        tool_result.get("ticket_id")
                    )
                else:
                    failure_message = (
                        "The assistant is temporarily unavailable because all configured "
                        "AI providers failed. Please try again shortly."
                    )

                logger.exception(
                    "Streaming AI generation failed request_id=%s "
                    "route=%s tool_name=%s prompt_ids=%s sources=%s",
                    request_id,
                    route,
                    tool_name,
                    prompt_ids,
                    sources,
                )

                suffix = ("\n\n" if full_response else "") + failure_message
                full_response += suffix
                yield suffix

            except Exception:
                logger.exception(
                    "Unexpected streaming AI generation failure "
                    "request_id=%s route=%s tool_name=%s "
                    "prompt_ids=%s sources=%s",
                    request_id,
                    route,
                    tool_name,
                    prompt_ids,
                    sources,
                )
                raise

        # Store only the original user message—not the enriched internal prompt.
        resolved.add_exchange(
            session=session,
            user_id=user_id,
            public_id=conversation_id,
            user_message=message,
            assistant_message=full_response,
        )

        resolved.maybe_summarize_conversation(
            session=session,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        logger.info(
            "Streaming AI generation completed request_id=%s "
            "route=%s tool_name=%s prompt_ids=%s sources=%s",
            request_id,
            route,
            tool_name,
            prompt_ids,
            sources,
        )
    finally:
        request_span.__exit__(None, None, None)
        request_context.__exit__(None, None, None)
