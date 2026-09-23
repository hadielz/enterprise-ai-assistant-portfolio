"""
Deterministic evaluation targets.

Architecture Notes
------------------
Purpose:
    Separate execution from evaluation.

The evaluator should not care whether output came from:
    - a fixture
    - LangGraph
    - a retriever
    - a provider fallback chain
    - a streaming workflow
    - an API boundary

v1B:
    ContractFixtureTarget validates evaluation-framework contracts without
    calling production workflows.

v1C Phase 2:
    ToolSelectorControlledTarget calls the real production tool selector
    while replacing only the LLM boundary with a deterministic local
    provider response.

v1C Phase 3:
    ProviderFallbackControlledTarget builds the real production
    ResilientLLMProvider through the production provider factory seam. Local
    deterministic providers simulate successful calls and provider execution
    failures. The real fallback loop, provider ordering, aggregate error,
    provider identity metadata, and tool-selection parser are exercised.

v1C Phase 4:
    RAGControlledTarget calls the real production retrieve_context() function
    and real RAG prompt constructor while replacing only the vector-search
    boundary with deterministic local retrieval data.

v1C Phase 5:
    LangGraphControlledTarget builds and executes the real production LangGraph
    workflow with controlled LLM, retrieval, memory, persistence, and ticket
    boundaries. The graph, supervisor, conditional edges, tool router, and
    calculator execution remain production code.

Future v1C phases:
    Streaming parity is connected deliberately in Phase 6.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.llm.factory import get_llm_provider
from app.llm.resilient_provider import ResilientLLMProvider
from app.prompts.rag_prompts import build_rag_prompt
from app.rag.retriever import retrieve_context
from app.tools.tool_selector import (
    parse_tool_selection_response,
    select_tool,
)
from evals.experiment import Experiment
from evals.schema import EvaluationCase, TargetResult


class EvaluationTarget(ABC):
    """Base interface for evaluation targets."""

    name: str

    @abstractmethod
    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        """Execute one case and return structured output."""

        raise NotImplementedError


class ContractFixtureTarget(EvaluationTarget):
    """
    Return a controlled output stored in the evaluation dataset.

    This target validates the v1B framework and evaluator contracts. It
    must not be confused with the production application workflow.
    """

    name = "contract_fixture"

    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        if case.fixture_output is None:
            raise ValueError(
                f"Fixture case '{case.case_id}' has no fixture_output."
            )

        started_at = perf_counter()

        output = dict(case.fixture_output)

        latency_ms = (
            perf_counter() - started_at
        ) * 1000

        return TargetResult(
            output=output,
            latency_ms=round(latency_ms, 3),
            configuration={
                "target": self.name,
                "provider": experiment.provider,
                "model": experiment.model,
                "deterministic": True,
            },
        )


class ControlledToolSelectionProvider(BaseLLMProvider):
    """
    Local provider returning one dataset-supplied tool-selection response.

    This class never initializes OpenAI, Gemini, Ollama, or another
    external provider.
    """

    provider_name = "controlled-tool-selector"
    model_name = "controlled-tool-selector-v1"

    def __init__(self, raw_response: str):
        self.raw_response = raw_response

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        return self.raw_response


class ToolSelectorControlledTarget(EvaluationTarget):
    """
    Execute the real tool-selection parser against controlled model output.

    The dataset supplies `provider_output`; production prompt construction,
    select_tool(), parsing, schema validation, and status classification are
    all exercised unchanged.
    """

    name = "tool_selector_controlled"

    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        message = case.input.get("message")
        provider_output = case.input.get("provider_output")

        if not isinstance(message, str) or not message:
            raise ValueError(
                f"Case '{case.case_id}' requires string input.message."
            )

        if not isinstance(provider_output, str):
            raise ValueError(
                f"Case '{case.case_id}' requires string "
                "input.provider_output."
            )

        provider = ControlledToolSelectionProvider(
            provider_output
        )

        started_at = perf_counter()

        result = select_tool(
            message,
            llm_provider=provider,
        )

        latency_ms = (
            perf_counter() - started_at
        ) * 1000

        return TargetResult(
            output={
                "selection_status": result.status,
                "tool_name": result.tool_name,
                "tool_input": result.tool_input,
                "valid_no_tool_decision": (
                    result.valid_no_tool_decision
                ),
                "selected": result.selected,
                "error": result.error,
                "raw_response": result.raw_response,
            },
            latency_ms=round(latency_ms, 3),
            configuration={
                "target": self.name,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "deterministic": True,
                "production_parser": True,
            },
        )


class ControlledFallbackProvider(BaseLLMProvider):
    """
    Deterministic local provider used by the Phase 3 fallback target.

    Supported behavior:
        return:
            Return the configured response string successfully.

        raise_error:
            Raise a local RuntimeError to simulate a provider execution
            failure such as timeout, quota, network, or API failure.

    A successful return is always a provider-layer success even when its
    content is malformed for the tool-selection protocol.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        behavior: str,
        response: str,
        call_order: list[str],
        error_message: str,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.behavior = behavior
        self.response = response
        self.call_order = call_order
        self.error_message = error_message

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        self.call_order.append(self.provider_name)

        if self.behavior == "raise_error":
            raise RuntimeError(self.error_message)

        if self.behavior == "return":
            return self.response

        raise ValueError(
            f"Unsupported controlled provider behavior: "
            f"{self.behavior}"
        )


class ProviderFallbackControlledTarget(EvaluationTarget):
    """
    Exercise the real non-streaming provider-fallback control flow.

    The target uses get_llm_provider() with Phase 1's provider-construction
    seam, so production ordering/deduplication and the real
    ResilientLLMProvider are used. Only provider implementations are replaced
    with deterministic local doubles.

    The successful provider's raw response is then parsed with the real Phase
    2 tool-selection parser. Parsing never causes provider fallback here.
    """

    name = "provider_fallback_controlled"

    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        message = case.input.get("message")
        raw_providers = case.input.get("providers")

        if not isinstance(message, str) or not message:
            raise ValueError(
                f"Case '{case.case_id}' requires string input.message."
            )

        if not isinstance(raw_providers, list) or not raw_providers:
            raise ValueError(
                f"Case '{case.case_id}' requires a non-empty "
                "input.providers list."
            )

        provider_specs: dict[str, dict[str, Any]] = {}
        configured_names: list[str] = []

        for index, raw_spec in enumerate(raw_providers):
            if not isinstance(raw_spec, dict):
                raise ValueError(
                    f"Case '{case.case_id}' provider #{index} must be "
                    "an object."
                )

            configured_name = raw_spec.get("configured_name")
            provider_name = raw_spec.get("provider_name")
            model_name = raw_spec.get("model_name")
            behavior = raw_spec.get("behavior")
            response = raw_spec.get("response", "")
            error_message = raw_spec.get(
                "error_message",
                "controlled provider failure",
            )

            string_fields = {
                "configured_name": configured_name,
                "provider_name": provider_name,
                "model_name": model_name,
                "behavior": behavior,
                "response": response,
                "error_message": error_message,
            }

            for field_name, field_value in string_fields.items():
                if not isinstance(field_value, str):
                    raise ValueError(
                        f"Case '{case.case_id}' provider #{index} field "
                        f"'{field_name}' must be a string."
                    )

            if behavior not in {"return", "raise_error"}:
                raise ValueError(
                    f"Case '{case.case_id}' provider #{index} has "
                    f"unsupported behavior '{behavior}'."
                )

            normalized_name = configured_name.strip().lower()

            if not normalized_name:
                raise ValueError(
                    f"Case '{case.case_id}' provider #{index} requires a "
                    "non-empty configured_name."
                )

            if normalized_name in provider_specs:
                raise ValueError(
                    f"Case '{case.case_id}' defines duplicate controlled "
                    f"provider '{normalized_name}'."
                )

            configured_names.append(normalized_name)
            provider_specs[normalized_name] = {
                "provider_name": provider_name,
                "model_name": model_name,
                "behavior": behavior,
                "response": response,
                "error_message": error_message,
            }

        call_order: list[str] = []

        def create_controlled_provider(
            configured_name: str,
        ) -> BaseLLMProvider:
            spec = provider_specs[configured_name]

            return ControlledFallbackProvider(
                provider_name=spec["provider_name"],
                model_name=spec["model_name"],
                behavior=spec["behavior"],
                response=spec["response"],
                call_order=call_order,
                error_message=spec["error_message"],
            )

        provider = get_llm_provider(
            provider_creator=create_controlled_provider,
            configured_provider_names=configured_names,
        )

        if not isinstance(provider, ResilientLLMProvider):
            raise TypeError(
                "Controlled fallback target requires "
                "ResilientLLMProvider."
            )

        started_at = perf_counter()

        try:
            generation = provider.generate_with_metadata(
                message
            )

            selection = parse_tool_selection_response(
                generation.content
            )

            output = {
                "provider_succeeded": True,
                "provider": generation.provider_name,
                "model": generation.model_name,
                "fallback_used": generation.fallback_used,
                "provider_call_order": list(call_order),
                "response": generation.content,
                "selection_status": selection.status,
                "tool_name": selection.tool_name,
                "tool_input": selection.tool_input,
                "valid_no_tool_decision": (
                    selection.valid_no_tool_decision
                ),
                "error_type": None,
                "error_message": None,
            }

        except LLMProviderError as exc:
            output = {
                "provider_succeeded": False,
                "provider": None,
                "model": None,
                "fallback_used": None,
                "provider_call_order": list(call_order),
                "response": None,
                "selection_status": None,
                "tool_name": None,
                "tool_input": None,
                "valid_no_tool_decision": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

        latency_ms = (
            perf_counter() - started_at
        ) * 1000

        return TargetResult(
            output=output,
            latency_ms=round(latency_ms, 3),
            configuration={
                "target": self.name,
                "provider": "controlled-fallback-chain",
                "model": "deterministic-local-providers",
                "deterministic": True,
                "production_factory": True,
                "production_fallback": True,
                "production_tool_parser": True,
            },
        )


class RAGControlledTarget(EvaluationTarget):
    """
    Exercise the real production retrieval boundary with local deterministic data.

    Scope:
        - Calls app.rag.retriever.retrieve_context().
        - Supplies a controlled searcher through the Phase 1 retrieval seam.
        - Uses the real build_rag_prompt() function when context is available.
        - Preserves source ordering exactly as returned by retrieval.

    Deliberate boundary:
        This target does not execute the supervisor or compiled LangGraph. Route
        selection therefore remains a Phase 5 contract rather than being
        fabricated by the evaluation target.

    External services:
        No embedding client, ChromaDB collection, LLM provider, or external
        evaluation service is used.
    """

    name = "rag_controlled"

    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        message = case.input.get("message")
        raw_documents = case.input.get("controlled_documents", [])
        behavior = case.input.get("retrieval_behavior", "return")
        error_message = case.input.get(
            "retrieval_error_message",
            "controlled retrieval failure",
        )
        top_k = case.input.get("top_k", 3)

        if not isinstance(message, str) or not message:
            raise ValueError(
                f"Case '{case.case_id}' requires string input.message."
            )

        if not isinstance(raw_documents, list):
            raise ValueError(
                f"Case '{case.case_id}' controlled_documents must be a list."
            )

        if behavior not in {"return", "raise_error"}:
            raise ValueError(
                f"Case '{case.case_id}' has unsupported retrieval_behavior "
                f"'{behavior}'."
            )

        if not isinstance(error_message, str):
            raise ValueError(
                f"Case '{case.case_id}' retrieval_error_message must be a "
                "string."
            )

        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError(
                f"Case '{case.case_id}' top_k must be a positive integer."
            )

        documents: list[dict[str, str]] = []

        for index, raw_document in enumerate(raw_documents):
            if not isinstance(raw_document, dict):
                raise ValueError(
                    f"Case '{case.case_id}' controlled document #{index} "
                    "must be an object."
                )

            source = raw_document.get("source")
            content = raw_document.get("content")

            if not isinstance(source, str) or not source:
                raise ValueError(
                    f"Case '{case.case_id}' controlled document #{index} "
                    "requires string source."
                )

            if not isinstance(content, str):
                raise ValueError(
                    f"Case '{case.case_id}' controlled document #{index} "
                    "requires string content."
                )

            documents.append(
                {
                    "source": source,
                    "content": content,
                }
            )

        search_calls: list[dict[str, Any]] = []

        def controlled_searcher(
            question: str,
            *,
            top_k: int,
        ) -> dict:
            search_calls.append(
                {
                    "question": question,
                    "top_k": top_k,
                }
            )

            if behavior == "raise_error":
                raise RuntimeError(error_message)

            selected = documents[:top_k]

            return {
                "context": "\n\n".join(
                    document["content"]
                    for document in selected
                ),
                "sources": [
                    document["source"]
                    for document in selected
                ],
            }

        started_at = perf_counter()

        try:
            retrieval = retrieve_context(
                message,
                top_k=top_k,
                searcher=controlled_searcher,
            )

            context = retrieval["context"]
            sources = retrieval["sources"]
            used_rag = bool(context)

            rag_prompt = (
                build_rag_prompt(message, context)
                if used_rag
                else None
            )

            output = {
                "retrieval_succeeded": True,
                "used_rag": used_rag,
                "rag_context": context,
                "sources": sources,
                "rag_prompt": rag_prompt,
                "search_calls": list(search_calls),
                "error_type": None,
                "error_message": None,
            }

        except Exception as exc:
            output = {
                "retrieval_succeeded": False,
                "used_rag": False,
                "rag_context": "",
                "sources": [],
                "rag_prompt": None,
                "search_calls": list(search_calls),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

        latency_ms = (
            perf_counter() - started_at
        ) * 1000

        return TargetResult(
            output=output,
            latency_ms=round(latency_ms, 3),
            configuration={
                "target": self.name,
                "provider": "none",
                "model": "none",
                "deterministic": True,
                "production_retriever": True,
                "production_rag_prompt": True,
                "controlled_vector_search": True,
                "langgraph_routing_executed": False,
                "external_embedding_calls": False,
                "external_chroma_calls": False,
            },
        )


class ControlledAgentAnswerProvider(BaseLLMProvider):
    """Deterministic provider used only for final controlled graph answers."""

    provider_name = "controlled-agent-answer"
    model_name = "controlled-agent-answer-v1"

    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        self.calls.append(
            {
                "message": message,
                "history": history,
            }
        )
        return self.response


class LangGraphControlledTarget(EvaluationTarget):
    """
    Execute the real compiled enterprise LangGraph with controlled boundaries.

    Production code exercised:
        - build_enterprise_agent() and the compiled StateGraph
        - load_context_node
        - select_tool_node
        - route_tool()
        - the Phase 2 structured tool selector and compatibility adapter
        - the real calculator implementation
        - supervisor_node and conditional graph edges
        - retrieve_rag_node
        - generate_answer_node and versioned answer prompt construction

    Controlled boundaries:
        - tool-selection provider output
        - final answer provider output
        - retrieval data
        - conversation reads/writes and summarization
        - ticket creation side effects

    Scope boundary:
        This target is non-streaming only. Streaming/non-streaming parity remains
        Phase 6. It also does not introduce ticket-confirmation policy; it
        characterizes the graph's existing behavior under controlled selector
        outcomes.
    """

    name = "langgraph_controlled"

    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        # Lazy imports keep the generic evaluation framework independent from
        # LangGraph until this target is actually executed.
        from app.agents.dependencies import AgentDependencies
        from app.agents.enterprise_agent import build_enterprise_agent
        from app.tools.tool_router import route_tool

        message = case.input.get("message")
        selector_output = case.input.get("selector_output")
        assistant_response = case.input.get(
            "assistant_response",
            "Controlled assistant response.",
        )
        retrieval_context = case.input.get(
            "retrieval_context",
            "",
        )
        retrieval_sources = case.input.get(
            "retrieval_sources",
            [],
        )
        recent_history = case.input.get("recent_history", [])
        summary = case.input.get("summary", "")

        if not isinstance(message, str) or not message:
            raise ValueError(
                f"Case '{case.case_id}' requires string input.message."
            )

        if not isinstance(selector_output, str):
            raise ValueError(
                f"Case '{case.case_id}' requires string "
                "input.selector_output."
            )

        if not isinstance(assistant_response, str):
            raise ValueError(
                f"Case '{case.case_id}' assistant_response must be a string."
            )

        if not isinstance(retrieval_context, str):
            raise ValueError(
                f"Case '{case.case_id}' retrieval_context must be a string."
            )

        if not isinstance(retrieval_sources, list) or not all(
            isinstance(source, str)
            for source in retrieval_sources
        ):
            raise ValueError(
                f"Case '{case.case_id}' retrieval_sources must be a string list."
            )

        if not isinstance(recent_history, list):
            raise ValueError(
                f"Case '{case.case_id}' recent_history must be a list."
            )

        if not isinstance(summary, str):
            raise ValueError(
                f"Case '{case.case_id}' summary must be a string."
            )

        selection_provider = ControlledToolSelectionProvider(selector_output)
        answer_provider = ControlledAgentAnswerProvider(assistant_response)

        selection_results = []
        route_calls: list[str] = []
        retrieval_calls: list[str] = []
        ticket_calls: list[str] = []
        persisted_exchanges: list[dict[str, Any]] = []
        summary_calls: list[dict[str, Any]] = []

        def controlled_selector(tool_message: str):
            selection = select_tool(
                tool_message,
                llm_provider=selection_provider,
            )
            selection_results.append(selection)
            return selection

        def controlled_ticket_creator(description: str) -> dict:
            ticket_calls.append(description)
            return {
                "ticket_id": "CONTROLLED-TICKET-1",
                "status": "created",
                "description": description,
            }

        def controlled_route_tool(tool_message: str, **_):
            route_calls.append(tool_message)
            return route_tool(
                tool_message,
                tool_selector=controlled_selector,
                # Deliberately do not inject calculator: calculator requests
                # therefore execute the real production calculate() function.
                ticket_creator=controlled_ticket_creator,
            )

        def controlled_retrieve_context(rag_message: str) -> dict:
            retrieval_calls.append(rag_message)
            return {
                "context": retrieval_context,
                "sources": list(retrieval_sources),
            }

        dependencies = AgentDependencies(
            get_recent_messages=lambda **_: list(recent_history),
            get_summary=lambda **_: summary,
            # Use the production history-construction function by leaving the
            # default injected by AgentDependencies in place is not possible
            # once constructing the bundle explicitly, so import its existing
            # default value from a fresh bundle.
            build_history_context=AgentDependencies().build_history_context,
            route_tool=controlled_route_tool,
            retrieve_context=controlled_retrieve_context,
            get_llm_provider=lambda: answer_provider,
            add_exchange=lambda **kwargs: persisted_exchanges.append(kwargs),
            maybe_summarize_conversation=lambda **kwargs: summary_calls.append(
                kwargs
            ),
        )

        agent = build_enterprise_agent(dependencies)

        started_at = perf_counter()

        result = agent.invoke(
            {
                "message": message,
                "conversation_id": "controlled-conversation",
                "user_id": 1,
                "db_session": object(),
                "request_id": "controlled-request",
            }
        )

        latency_ms = (
            perf_counter() - started_at
        ) * 1000

        selection = (
            selection_results[0]
            if selection_results
            else None
        )
        tool_result = result.get("tool_result")
        tool_used = result.get("tool_used")
        used_rag = result.get("used_rag", False)

        if tool_used:
            effective_answer_mode = "tool"
        elif used_rag:
            effective_answer_mode = "rag"
        else:
            effective_answer_mode = "chat"

        return TargetResult(
            output={
                "route": result.get("route"),
                "effective_answer_mode": effective_answer_mode,
                "tool_name": tool_used,
                "tool_result": tool_result,
                "action_status": (
                    tool_result.get("action_status")
                    if isinstance(tool_result, dict)
                    else None
                ),
                "confirmation_message": (
                    tool_result.get("confirmation_message")
                    if isinstance(tool_result, dict)
                    else None
                ),
                "side_effect_executed": (
                    tool_result.get("side_effect_executed")
                    if isinstance(tool_result, dict)
                    else None
                ),
                "selection_status": (
                    selection.status
                    if selection is not None
                    else None
                ),
                "valid_no_tool_decision": (
                    selection.valid_no_tool_decision
                    if selection is not None
                    else False
                ),
                "selected_tool_name": (
                    selection.tool_name
                    if selection is not None
                    else None
                ),
                "selected_tool_input": (
                    selection.tool_input
                    if selection is not None
                    else None
                ),
                "used_rag": used_rag,
                "sources": result.get("sources", []),
                "prompt_ids": result.get("prompt_ids", []),
                "agent_steps": result.get("agent_steps", []),
                "response": result.get("response"),
                "route_calls": list(route_calls),
                "retrieval_calls": list(retrieval_calls),
                "ticket_created": bool(ticket_calls),
                "ticket_calls": list(ticket_calls),
                "persisted_exchange_count": len(persisted_exchanges),
                "summary_call_count": len(summary_calls),
                "generation_calls": list(answer_provider.calls),
            },
            latency_ms=round(latency_ms, 3),
            configuration={
                "target": self.name,
                "provider": answer_provider.provider_name,
                "model": answer_provider.model_name,
                "deterministic": True,
                "production_langgraph": True,
                "production_supervisor": True,
                "production_conditional_edges": True,
                "production_tool_router": True,
                "production_tool_selector_parser": True,
                "production_calculator": True,
                "controlled_ticket_side_effect": True,
                "controlled_retrieval": True,
                "controlled_memory": True,
                "controlled_persistence": True,
                "streaming_executed": False,
                "external_llm_calls": False,
                "external_embedding_calls": False,
                "external_chroma_calls": False,
                "external_ticket_calls": False,
            },
        )


class ControlledParityProvider(BaseLLMProvider):
    """Deterministic provider candidate used by the Phase 6 parity target."""

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        behavior: str,
        response: str,
        chunks: list[str],
        call_order: list[str],
        generation_calls: list[dict[str, Any]],
        error_message: str,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.behavior = behavior
        self.response = response
        self.chunks = chunks
        self.call_order = call_order
        self.generation_calls = generation_calls
        self.error_message = error_message

    def _record(
        self,
        mode: str,
        message: str,
        history: list[dict] | None,
    ) -> None:
        self.call_order.append(self.provider_name)
        self.generation_calls.append(
            {
                "mode": mode,
                "provider": self.provider_name,
                "message": message,
                "history": history,
            }
        )

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        self._record("generate", message, history)

        if self.behavior == "raise_error":
            raise RuntimeError(self.error_message)

        if self.behavior != "return":
            raise ValueError(
                f"Unsupported controlled provider behavior: {self.behavior}"
            )

        return self.response

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        self._record("stream", message, history)

        if self.behavior == "raise_error":
            raise RuntimeError(self.error_message)

        if self.behavior != "return":
            raise ValueError(
                f"Unsupported controlled provider behavior: {self.behavior}"
            )

        for chunk in self.chunks:
            yield chunk


class StreamingParityControlledTarget(EvaluationTarget):
    """
    Execute both real production chat pathways with controlled dependencies.

    Non-streaming:
        chat_service.generate_response() -> real compiled LangGraph.

    Streaming:
        chat_service.stream_response() -> current manual orchestration.

    The target deliberately does not force identical internal route labels.
    It compares product semantics and records known representation differences,
    especially the current no-tool + empty-retrieval case where LangGraph keeps
    route="rag" while streaming effectively behaves as ordinary chat.
    """

    name = "streaming_parity_controlled"

    def execute(
        self,
        case: EvaluationCase,
        experiment: Experiment,
    ) -> TargetResult:
        from app.agents.dependencies import AgentDependencies
        from app.agents.enterprise_agent import build_enterprise_agent
        from app.prompts.registry import (
            ASSISTANT_SYSTEM_PROMPT,
            RAG_ANSWER_PROMPT,
            TOOL_ANSWER_PROMPT,
        )
        from app.services.chat_dependencies import ChatServiceDependencies
        from app.services.chat_service import generate_response, stream_response
        from app.tools.tool_router import route_tool

        message = case.input.get("message")
        selector_output = case.input.get("selector_output")
        retrieval_context = case.input.get("retrieval_context", "")
        retrieval_sources = case.input.get("retrieval_sources", [])
        recent_history = case.input.get("recent_history", [])
        summary = case.input.get("summary", "")
        raw_answer_providers = case.input.get(
            "answer_providers",
            [
                {
                    "provider_name": "controlled-answer",
                    "model_name": "controlled-answer-v1",
                    "behavior": "return",
                    "response": "Controlled assistant response.",
                    "chunks": ["Controlled ", "assistant response."],
                    "error_message": "controlled answer provider failure",
                }
            ],
        )

        if not isinstance(message, str) or not message:
            raise ValueError(
                f"Case '{case.case_id}' requires string input.message."
            )

        if not isinstance(selector_output, str):
            raise ValueError(
                f"Case '{case.case_id}' requires string input.selector_output."
            )

        if not isinstance(retrieval_context, str):
            raise ValueError(
                f"Case '{case.case_id}' retrieval_context must be a string."
            )

        if not isinstance(retrieval_sources, list) or not all(
            isinstance(source, str) for source in retrieval_sources
        ):
            raise ValueError(
                f"Case '{case.case_id}' retrieval_sources must be a string list."
            )

        if not isinstance(recent_history, list):
            raise ValueError(
                f"Case '{case.case_id}' recent_history must be a list."
            )

        if not isinstance(summary, str):
            raise ValueError(
                f"Case '{case.case_id}' summary must be a string."
            )

        if not isinstance(raw_answer_providers, list) or not raw_answer_providers:
            raise ValueError(
                f"Case '{case.case_id}' answer_providers must be a non-empty list."
            )

        provider_specs: list[dict[str, Any]] = []
        for index, raw_spec in enumerate(raw_answer_providers):
            if not isinstance(raw_spec, dict):
                raise ValueError(
                    f"Case '{case.case_id}' answer provider #{index} must be an object."
                )

            provider_name = raw_spec.get("provider_name")
            model_name = raw_spec.get("model_name")
            behavior = raw_spec.get("behavior", "return")
            response = raw_spec.get("response", "")
            chunks = raw_spec.get("chunks", [response])
            error_message = raw_spec.get(
                "error_message", "controlled answer provider failure"
            )

            if not all(
                isinstance(value, str)
                for value in (
                    provider_name,
                    model_name,
                    behavior,
                    response,
                    error_message,
                )
            ):
                raise ValueError(
                    f"Case '{case.case_id}' answer provider #{index} has invalid string fields."
                )

            if behavior not in {"return", "raise_error"}:
                raise ValueError(
                    f"Case '{case.case_id}' answer provider #{index} has unsupported behavior '{behavior}'."
                )

            if not isinstance(chunks, list) or not all(
                isinstance(chunk, str) for chunk in chunks
            ):
                raise ValueError(
                    f"Case '{case.case_id}' answer provider #{index} chunks must be strings."
                )

            provider_specs.append(
                {
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "behavior": behavior,
                    "response": response,
                    "chunks": list(chunks),
                    "error_message": error_message,
                }
            )

        def build_answer_provider(
            call_order: list[str],
            generation_calls: list[dict[str, Any]],
        ) -> ResilientLLMProvider:
            providers = []
            for index, spec in enumerate(provider_specs):
                provider = ControlledParityProvider(
                    provider_name=spec["provider_name"],
                    model_name=spec["model_name"],
                    behavior=spec["behavior"],
                    response=spec["response"],
                    chunks=spec["chunks"],
                    call_order=call_order,
                    generation_calls=generation_calls,
                    error_message=spec["error_message"],
                )
                providers.append((f"controlled-{index}", provider))
            return ResilientLLMProvider(providers)

        def run_path(*, streaming: bool) -> dict[str, Any]:
            selection_provider = ControlledToolSelectionProvider(selector_output)
            selection_results = []
            route_calls: list[str] = []
            retrieval_calls: list[str] = []
            ticket_calls: list[str] = []
            persisted_exchanges: list[dict[str, Any]] = []
            summary_calls: list[dict[str, Any]] = []
            provider_call_order: list[str] = []
            generation_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            answer_provider = build_answer_provider(
                provider_call_order,
                generation_calls,
            )

            def controlled_selector(tool_message: str):
                selection = select_tool(
                    tool_message,
                    llm_provider=selection_provider,
                )
                selection_results.append(selection)
                return selection

            def controlled_ticket_creator(description: str) -> dict:
                ticket_calls.append(description)
                return {
                    "ticket_id": "CONTROLLED-TICKET-1",
                    "status": "created",
                    "description": description,
                }

            def controlled_route_tool(tool_message: str, **_):
                route_calls.append(tool_message)
                result = route_tool(
                    tool_message,
                    tool_selector=controlled_selector,
                    ticket_creator=controlled_ticket_creator,
                )
                tool_results.append(result)
                return result

            def controlled_retrieve_context(rag_message: str) -> dict:
                retrieval_calls.append(rag_message)
                return {
                    "context": retrieval_context,
                    "sources": list(retrieval_sources),
                }

            def record_exchange(**kwargs):
                persisted_exchanges.append(
                    {
                        "user_id": kwargs.get("user_id"),
                        "public_id": kwargs.get("public_id"),
                        "user_message": kwargs.get("user_message"),
                        "assistant_message": kwargs.get("assistant_message"),
                    }
                )

            def record_summary(**kwargs):
                summary_calls.append(kwargs)

            if streaming:
                dependencies = ChatServiceDependencies(
                    enterprise_agent=ChatServiceDependencies().enterprise_agent,
                    get_llm_provider=lambda: answer_provider,
                    get_recent_messages=lambda **_: list(recent_history),
                    get_summary=lambda **_: summary,
                    build_history_context=ChatServiceDependencies().build_history_context,
                    route_tool=controlled_route_tool,
                    retrieve_context=controlled_retrieve_context,
                    add_exchange=record_exchange,
                    maybe_summarize_conversation=record_summary,
                )

                chunks: list[str] = []
                status = "completed"
                error_type = None
                error_message = None

                try:
                    chunks = list(
                        stream_response(
                            message=message,
                            conversation_id="controlled-conversation",
                            user_id=1,
                            session=object(),
                            dependencies=dependencies,
                        )
                    )
                except Exception as exc:
                    status = "error"
                    error_type = type(exc).__name__
                    error_message = str(exc)

                response = "".join(chunks)
                tool_result = tool_results[0] if tool_results else None
                tool_name = (
                    tool_result.get("tool_name")
                    if isinstance(tool_result, dict)
                    else None
                )
                action_status = (
                    tool_result.get("action_status")
                    if isinstance(tool_result, dict)
                    else None
                )
                used_rag = bool(retrieval_calls and retrieval_context)
                sources = list(retrieval_sources) if used_rag else []

                if action_status == "confirmation_required":
                    effective_mode = "confirmation"
                    effective_route = "confirmation"
                    prompt_contract_ids = []
                elif tool_name:
                    effective_mode = "tool"
                    effective_route = "tool"
                    prompt_contract_ids = [
                        ASSISTANT_SYSTEM_PROMPT.prompt_id,
                        TOOL_ANSWER_PROMPT.prompt_id,
                    ]
                elif used_rag:
                    effective_mode = "rag"
                    effective_route = "rag"
                    prompt_contract_ids = [
                        ASSISTANT_SYSTEM_PROMPT.prompt_id,
                        RAG_ANSWER_PROMPT.prompt_id,
                    ]
                else:
                    effective_mode = "chat"
                    effective_route = "chat"
                    prompt_contract_ids = [ASSISTANT_SYSTEM_PROMPT.prompt_id]

                # LLMProviderError is intentionally converted by the production
                # streaming service into a user-visible failure message and then
                # persisted. Detect that documented completion mode explicitly.
                if (
                    status == "completed"
                    and response.startswith(
                        "The assistant is temporarily unavailable because all configured "
                    )
                ):
                    status = "completed_with_failure_message"

                route = effective_route
                prompt_ids = None
                agent_steps: list[str] = []

            else:
                agent_dependencies = AgentDependencies(
                    get_recent_messages=lambda **_: list(recent_history),
                    get_summary=lambda **_: summary,
                    build_history_context=AgentDependencies().build_history_context,
                    route_tool=controlled_route_tool,
                    retrieve_context=controlled_retrieve_context,
                    get_llm_provider=lambda: answer_provider,
                    add_exchange=record_exchange,
                    maybe_summarize_conversation=record_summary,
                )
                real_agent = build_enterprise_agent(agent_dependencies)

                class RecordingAgent:
                    def __init__(self, wrapped):
                        self.wrapped = wrapped
                        self.last_result = None

                    def invoke(self, state):
                        self.last_result = self.wrapped.invoke(state)
                        return self.last_result

                recording_agent = RecordingAgent(real_agent)

                dependencies = ChatServiceDependencies(
                    enterprise_agent=recording_agent,
                    get_llm_provider=lambda: answer_provider,
                    get_recent_messages=lambda **_: list(recent_history),
                    get_summary=lambda **_: summary,
                    build_history_context=ChatServiceDependencies().build_history_context,
                    route_tool=controlled_route_tool,
                    retrieve_context=controlled_retrieve_context,
                    add_exchange=record_exchange,
                    maybe_summarize_conversation=record_summary,
                )

                status = "completed"
                error_type = None
                error_message = None
                response = None
                result = None

                try:
                    service_result = generate_response(
                        message=message,
                        conversation_id="controlled-conversation",
                        user_id=1,
                        session=object(),
                        dependencies=dependencies,
                    )
                    response = service_result["response"]
                    result = recording_agent.last_result
                except Exception as exc:
                    status = "error"
                    error_type = type(exc).__name__
                    error_message = str(exc)
                    result = recording_agent.last_result

                result = result or {}
                route = result.get("route")
                tool_name = result.get("tool_used")
                tool_result = result.get("tool_result")
                action_status = (
                    tool_result.get("action_status")
                    if isinstance(tool_result, dict)
                    else None
                )
                used_rag = result.get("used_rag", False)
                sources = result.get("sources", [])
                prompt_ids = result.get("prompt_ids", [])
                prompt_contract_ids = list(prompt_ids)
                agent_steps = result.get("agent_steps", [])

                if action_status == "confirmation_required":
                    effective_mode = "confirmation"
                elif tool_name:
                    effective_mode = "tool"
                elif used_rag:
                    effective_mode = "rag"
                else:
                    effective_mode = "chat"

                effective_route = effective_mode

            selection = selection_results[0] if selection_results else None

            return {
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                "route": route,
                "effective_route": effective_route,
                "effective_answer_mode": effective_mode,
                "tool_name": tool_name,
                "tool_result": tool_result,
                "action_status": (
                    tool_result.get("action_status")
                    if isinstance(tool_result, dict)
                    else None
                ),
                "confirmation_message": (
                    tool_result.get("confirmation_message")
                    if isinstance(tool_result, dict)
                    else None
                ),
                "selection_status": selection.status if selection else None,
                "valid_no_tool_decision": (
                    selection.valid_no_tool_decision if selection else False
                ),
                "used_rag": used_rag,
                "sources": sources,
                "prompt_ids": prompt_ids,
                "prompt_contract_ids": prompt_contract_ids,
                "agent_steps": agent_steps,
                "response": response,
                "route_calls": list(route_calls),
                "retrieval_calls": list(retrieval_calls),
                "ticket_calls": list(ticket_calls),
                "ticket_created": bool(ticket_calls),
                "persisted_exchange_count": len(persisted_exchanges),
                "persisted_exchanges": list(persisted_exchanges),
                "summary_call_count": len(summary_calls),
                "provider_call_order": list(provider_call_order),
                "generation_calls": list(generation_calls),
            }

        started_at = perf_counter()
        non_streaming = run_path(streaming=False)
        streaming = run_path(streaming=True)
        latency_ms = (perf_counter() - started_at) * 1000

        route_equal = non_streaming["route"] == streaming["route"]
        semantic_mode_equal = (
            non_streaming["effective_answer_mode"]
            == streaming["effective_answer_mode"]
        )
        tool_equal = non_streaming["tool_name"] == streaming["tool_name"]
        tool_result_equal = (
            non_streaming["tool_result"] == streaming["tool_result"]
        )
        selection_status_equal = (
            non_streaming["selection_status"] == streaming["selection_status"]
        )
        retrieval_used_equal = (
            bool(non_streaming["retrieval_calls"])
            == bool(streaming["retrieval_calls"])
        )
        sources_equal = non_streaming["sources"] == streaming["sources"]
        prompt_contract_equal = (
            non_streaming["prompt_contract_ids"]
            == streaming["prompt_contract_ids"]
        )
        known_route_representation_difference = (
            not route_equal
            and semantic_mode_equal
            and non_streaming["route"] == "rag"
            and streaming["route"] == "chat"
            and not non_streaming["used_rag"]
            and not streaming["used_rag"]
        )

        return TargetResult(
            output={
                "non_streaming": non_streaming,
                "streaming": streaming,
                "route_equal": route_equal,
                "semantic_mode_equal": semantic_mode_equal,
                "tool_equal": tool_equal,
                "tool_result_equal": tool_result_equal,
                "selection_status_equal": selection_status_equal,
                "retrieval_used_equal": retrieval_used_equal,
                "sources_equal": sources_equal,
                "prompt_contract_equal": prompt_contract_equal,
                "persistence_equal": (
                    non_streaming["persisted_exchange_count"]
                    == streaming["persisted_exchange_count"]
                ),
                "persistence_once_each": (
                    non_streaming["persisted_exchange_count"] == 1
                    and streaming["persisted_exchange_count"] == 1
                ),
                "summary_once_each": (
                    non_streaming["summary_call_count"] == 1
                    and streaming["summary_call_count"] == 1
                ),
                "ticket_side_effect_once_each": (
                    (not non_streaming["ticket_created"] and not streaming["ticket_created"])
                    or (
                        len(non_streaming["ticket_calls"]) == 1
                        and len(streaming["ticket_calls"]) == 1
                    )
                ),
                "known_route_representation_difference": (
                    known_route_representation_difference
                ),
            },
            latency_ms=round(latency_ms, 3),
            configuration={
                "target": self.name,
                "deterministic": True,
                "production_non_streaming_service": True,
                "production_streaming_service": True,
                "production_langgraph_non_streaming": True,
                "production_manual_streaming_orchestration": True,
                "production_tool_router": True,
                "production_tool_selector_parser": True,
                "production_calculator": True,
                "controlled_ticket_side_effect": True,
                "controlled_retrieval": True,
                "controlled_memory": True,
                "controlled_persistence": True,
                "production_provider_fallback": True,
                "streaming_prompt_ids_directly_exposed": False,
                "streaming_prompt_contract_inferred_from_observed_branch": True,
                "external_llm_calls": False,
                "external_embedding_calls": False,
                "external_chroma_calls": False,
                "external_ticket_calls": False,
                "external_evaluation_services": False,
            },
        )


class TargetRegistry:
    """Registry of locally available evaluation targets."""

    def __init__(self) -> None:
        self._targets: dict[str, EvaluationTarget] = {}

    def register(
        self,
        target: EvaluationTarget,
    ) -> None:
        if target.name in self._targets:
            raise ValueError(
                f"Evaluation target '{target.name}' is already "
                "registered."
            )

        self._targets[target.name] = target

    def get(
        self,
        name: str,
    ) -> EvaluationTarget:
        try:
            return self._targets[name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown evaluation target '{name}'."
            ) from exc


def build_default_target_registry() -> TargetRegistry:
    """
    Build the deterministic v1B/v1C Phase 6 target registry.
    """

    registry = TargetRegistry()
    registry.register(ContractFixtureTarget())
    registry.register(ToolSelectorControlledTarget())
    registry.register(ProviderFallbackControlledTarget())
    registry.register(RAGControlledTarget())
    registry.register(LangGraphControlledTarget())
    registry.register(StreamingParityControlledTarget())

    return registry
