"""
AI Quality v1C Phase 1 dependency-seam tests.

These tests exercise production code with controlled local dependencies.
They make no provider, embedding, vector-store, or external service calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.dependencies import AgentDependencies
from app.agents.enterprise_agent import build_enterprise_agent
from app.llm.base import BaseLLMProvider
from app.llm.factory import get_llm_provider
from app.rag.retriever import retrieve_context
from app.services.chat_dependencies import ChatServiceDependencies
from app.services.chat_service import generate_response, stream_response
from app.tools.tool_router import route_tool
from app.tools.tool_selector import select_tool


class ControlledProvider(BaseLLMProvider):
    provider_name = "controlled"
    model_name = "controlled-v1"

    def __init__(self, response: str = "controlled response"):
        self.response = response
        self.generated_messages: list[tuple[str, list[dict] | None]] = []
        self.streamed_messages: list[tuple[str, list[dict] | None]] = []

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        self.generated_messages.append((message, history))
        return self.response

    def stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ):
        self.streamed_messages.append((message, history))
        yield "controlled "
        yield "stream"


class ControlledAgent:
    def __init__(self, result: dict):
        self.result = result
        self.inputs: list[dict] = []

    def invoke(self, state: dict) -> dict:
        self.inputs.append(state)
        return self.result


def test_tool_selector_accepts_controlled_provider():
    provider = ControlledProvider(
        '{"tool_name": "calculator", "tool_input": "2 + 3"}'
    )

    decision = select_tool(
        "Calculate 2 + 3.",
        llm_provider=provider,
    )

    assert decision.status == "selected"
    assert decision.tool_name == "calculator"
    assert decision.tool_input == "2 + 3"
    assert decision.valid_no_tool_decision is False
    assert len(provider.generated_messages) == 1
    assert "Calculate 2 + 3." in provider.generated_messages[0][0]


def test_tool_router_accepts_controlled_selector_and_calculator():
    selected_messages: list[str] = []
    calculated_inputs: list[str] = []

    def selector(message: str) -> dict:
        selected_messages.append(message)
        return {
            "tool_name": "calculator",
            "tool_input": "8 * 7",
        }

    def calculator(expression: str) -> str:
        calculated_inputs.append(expression)
        return "controlled result: 56"

    result = route_tool(
        "Calculate 8 * 7.",
        tool_selector=selector,
        calculator=calculator,
    )

    assert result == {
        "tool_name": "calculator",
        "tool_result": "controlled result: 56",
    }
    assert selected_messages == ["Calculate 8 * 7."]
    assert calculated_inputs == ["8 * 7"]


def test_tool_router_accepts_controlled_ticket_creator():
    descriptions: list[str] = []

    def selector(_: str) -> dict:
        return {
            "tool_name": "ticket_creator",
            "tool_input": "WiFi unavailable",
        }

    def ticket_creator(description: str) -> dict:
        descriptions.append(description)
        return {
            "ticket_id": "CONTROLLED-1",
            "status": "created",
            "description": description,
        }

    result = route_tool(
        "Create a WiFi ticket.",
        tool_selector=selector,
        ticket_creator=ticket_creator,
    )

    assert descriptions == ["WiFi unavailable"]
    assert result is not None
    assert result["tool_name"] == "ticket_creator"
    assert "CONTROLLED-1" in result["tool_result"]


def test_retriever_accepts_controlled_searcher():
    calls: list[tuple[str, int]] = []

    def searcher(question: str, *, top_k: int) -> dict:
        calls.append((question, top_k))
        return {
            "context": "Controlled policy context",
            "sources": ["controlled.txt#chunk-1"],
        }

    result = retrieve_context(
        "What is the policy?",
        top_k=2,
        searcher=searcher,
    )

    assert calls == [("What is the policy?", 2)]
    assert result["sources"] == ["controlled.txt#chunk-1"]


def test_provider_factory_accepts_controlled_creator_and_names():
    created: list[str] = []

    def creator(name: str) -> BaseLLMProvider:
        created.append(name)
        return ControlledProvider(response=name)

    provider = get_llm_provider(
        provider_creator=creator,
        configured_provider_names=[
            "primary",
            "fallback",
            "primary",
        ],
    )

    assert created == ["primary", "fallback"]
    candidates = list(provider.iter_provider_candidates())
    assert len(candidates) == 2
    assert candidates[0].fallback_used is False
    assert candidates[1].fallback_used is True


def test_controlled_enterprise_agent_uses_injected_boundaries():
    provider = ControlledProvider("The controlled answer is 42.")
    calls: dict[str, list] = {
        "route": [],
        "retrieval": [],
        "writes": [],
        "summaries": [],
    }

    dependencies = AgentDependencies(
        get_recent_messages=lambda **_: [],
        get_summary=lambda **_: "",
        build_history_context=lambda summary, messages: [],
        route_tool=lambda message, **_: calls["route"].append(message) or None,
        retrieve_context=lambda message: (
            calls["retrieval"].append(message)
            or {"context": "", "sources": []}
        ),
        get_llm_provider=lambda: provider,
        add_exchange=lambda **kwargs: calls["writes"].append(kwargs),
        maybe_summarize_conversation=lambda **kwargs: (
            calls["summaries"].append(kwargs)
        ),
    )

    agent = build_enterprise_agent(dependencies)
    result = agent.invoke(
        {
            "message": "Explain controlled workflows.",
            "conversation_id": "conversation-1",
            "user_id": 7,
            "db_session": object(),
            "request_id": "request-1",
        }
    )

    assert calls["route"] == ["Explain controlled workflows."]
    assert calls["retrieval"] == ["Explain controlled workflows."]
    assert result["route"] == "rag"
    assert result["used_rag"] is False
    assert result["response"] == "The controlled answer is 42."
    assert calls["writes"][0]["assistant_message"] == (
        "The controlled answer is 42."
    )
    assert len(calls["summaries"]) == 1


def test_non_streaming_service_accepts_controlled_agent():
    agent = ControlledAgent(
        {
            "response": "controlled non-streaming response",
            "route": "chat",
            "used_rag": False,
            "sources": [],
            "tool_used": None,
            "prompt_ids": ["assistant.system.v1"],
            "agent_steps": ["controlled"],
        }
    )

    result = generate_response(
        "Hello",
        "conversation-1",
        3,
        object(),
        dependencies=ChatServiceDependencies(
            enterprise_agent=agent,
        ),
    )

    assert result["response"] == "controlled non-streaming response"
    assert result["agent_steps"] == ["controlled"]
    assert agent.inputs[0]["message"] == "Hello"


def test_streaming_service_accepts_all_controlled_boundaries():
    provider = ControlledProvider()
    writes: list[dict] = []
    summaries: list[dict] = []
    retrieval_calls: list[str] = []

    dependencies = ChatServiceDependencies(
        get_llm_provider=lambda: provider,
        get_recent_messages=lambda **_: [
            {"role": "user", "content": "Earlier message"}
        ],
        get_summary=lambda **_: "Controlled summary",
        build_history_context=lambda summary, messages: messages,
        route_tool=lambda _, **__: None,
        retrieve_context=lambda message: (
            retrieval_calls.append(message)
            or {"context": "", "sources": []}
        ),
        add_exchange=lambda **kwargs: writes.append(kwargs),
        maybe_summarize_conversation=lambda **kwargs: summaries.append(
            kwargs
        ),
    )

    tokens = list(
        stream_response(
            "Hello",
            "conversation-1",
            3,
            object(),
            dependencies=dependencies,
        )
    )

    assert tokens == ["controlled ", "stream"]
    assert retrieval_calls == ["Hello"]
    assert provider.streamed_messages[0][0] == "Hello"
    assert writes[0]["user_message"] == "Hello"
    assert writes[0]["assistant_message"] == "controlled stream"
    assert len(summaries) == 1
