"""
AI Quality v1C Phase 3 controlled provider-fallback regression tests.

These tests exercise the real production ResilientLLMProvider and provider
factory seam with deterministic local provider doubles. They make no OpenAI,
Gemini, Ollama, embedding, ChromaDB, or external evaluation-service calls.
"""

from __future__ import annotations

import pytest

from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.llm.factory import get_llm_provider
from app.llm.resilient_provider import ResilientLLMProvider
from app.tools.tool_selector import parse_tool_selection_response


class ControlledProvider(BaseLLMProvider):
    """Deterministic provider that either returns text or raises."""

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        call_order: list[str],
        response: str = "",
        error: Exception | None = None,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.call_order = call_order
        self.response = response
        self.error = error

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        self.call_order.append(self.provider_name)

        if self.error is not None:
            raise self.error

        return self.response


def test_primary_provider_success_returns_identity_without_fallback():
    calls: list[str] = []

    resilient = ResilientLLMProvider(
        [
            (
                "primary",
                ControlledProvider(
                    provider_name="primary-provider",
                    model_name="primary-model",
                    call_order=calls,
                    response="primary response",
                ),
            ),
            (
                "fallback",
                ControlledProvider(
                    provider_name="fallback-provider",
                    model_name="fallback-model",
                    call_order=calls,
                    response="fallback response",
                ),
            ),
        ]
    )

    result = resilient.generate_with_metadata("Hello")

    assert result.content == "primary response"
    assert result.provider_name == "primary-provider"
    assert result.model_name == "primary-model"
    assert result.fallback_used is False
    assert calls == ["primary-provider"]

    # Existing production contract remains a plain string.
    calls.clear()
    assert resilient.generate("Hello") == "primary response"
    assert calls == ["primary-provider"]


def test_primary_failure_falls_back_to_second_provider():
    calls: list[str] = []

    resilient = ResilientLLMProvider(
        [
            (
                "primary",
                ControlledProvider(
                    provider_name="primary-provider",
                    model_name="primary-model",
                    call_order=calls,
                    error=RuntimeError("primary unavailable"),
                ),
            ),
            (
                "fallback",
                ControlledProvider(
                    provider_name="fallback-provider",
                    model_name="fallback-model",
                    call_order=calls,
                    response="fallback response",
                ),
            ),
        ]
    )

    result = resilient.generate_with_metadata("Hello")

    assert result.content == "fallback response"
    assert result.provider_name == "fallback-provider"
    assert result.model_name == "fallback-model"
    assert result.fallback_used is True
    assert calls == [
        "primary-provider",
        "fallback-provider",
    ]


def test_multiple_failures_are_attempted_in_order_before_success():
    calls: list[str] = []

    resilient = ResilientLLMProvider(
        [
            (
                "primary",
                ControlledProvider(
                    provider_name="primary-provider",
                    model_name="primary-model",
                    call_order=calls,
                    error=RuntimeError("primary unavailable"),
                ),
            ),
            (
                "fallback-one",
                ControlledProvider(
                    provider_name="fallback-one-provider",
                    model_name="fallback-one-model",
                    call_order=calls,
                    error=TimeoutError("fallback one timeout"),
                ),
            ),
            (
                "fallback-two",
                ControlledProvider(
                    provider_name="fallback-two-provider",
                    model_name="fallback-two-model",
                    call_order=calls,
                    response="third provider response",
                ),
            ),
        ]
    )

    result = resilient.generate_with_metadata("Hello")

    assert result.provider_name == "fallback-two-provider"
    assert result.model_name == "fallback-two-model"
    assert result.fallback_used is True
    assert calls == [
        "primary-provider",
        "fallback-one-provider",
        "fallback-two-provider",
    ]


def test_all_provider_failures_raise_existing_llm_provider_error():
    calls: list[str] = []

    resilient = ResilientLLMProvider(
        [
            (
                "primary",
                ControlledProvider(
                    provider_name="primary-provider",
                    model_name="primary-model",
                    call_order=calls,
                    error=RuntimeError("primary unavailable"),
                ),
            ),
            (
                "fallback",
                ControlledProvider(
                    provider_name="fallback-provider",
                    model_name="fallback-model",
                    call_order=calls,
                    error=RuntimeError("fallback unavailable"),
                ),
            ),
        ]
    )

    with pytest.raises(LLMProviderError) as exc_info:
        resilient.generate_with_metadata("Hello")

    assert calls == [
        "primary-provider",
        "fallback-provider",
    ]

    assert str(exc_info.value) == (
        "All configured LLM providers failed. "
        "primary-provider: primary unavailable | "
        "fallback-provider: fallback unavailable"
    )


def test_factory_preserves_configured_order_and_removes_duplicates():
    created: list[str] = []

    def creator(name: str) -> BaseLLMProvider:
        created.append(name)

        return ControlledProvider(
            provider_name=f"{name}-provider",
            model_name=f"{name}-model",
            call_order=[],
            response=name,
        )

    provider = get_llm_provider(
        provider_creator=creator,
        configured_provider_names=[
            " Primary ",
            "Fallback-One",
            "primary",
            "fallback-two",
            "fallback-one",
        ],
    )

    assert isinstance(provider, ResilientLLMProvider)
    assert created == [
        "primary",
        "fallback-one",
        "fallback-two",
    ]

    candidates = list(provider.iter_provider_candidates())

    assert [
        candidate.provider_name
        for candidate in candidates
    ] == [
        "primary-provider",
        "fallback-one-provider",
        "fallback-two-provider",
    ]

    assert [
        candidate.fallback_used
        for candidate in candidates
    ] == [False, True, True]


def test_successful_malformed_protocol_does_not_trigger_fallback():
    """
    Provider execution success and selector-protocol validity are separate.

    The primary provider successfully returns malformed selector text. The
    fallback provider must therefore not run. The caller may subsequently
    classify the text as parse_error using the Phase 2 parser.
    """

    calls: list[str] = []

    resilient = ResilientLLMProvider(
        [
            (
                "primary",
                ControlledProvider(
                    provider_name="primary-provider",
                    model_name="primary-model",
                    call_order=calls,
                    response="calculator(10 + 15)",
                ),
            ),
            (
                "fallback",
                ControlledProvider(
                    provider_name="fallback-provider",
                    model_name="fallback-model",
                    call_order=calls,
                    response=(
                        '{"tool_name": "calculator", '
                        '"tool_input": "10 + 15"}'
                    ),
                ),
            ),
        ]
    )

    generation = resilient.generate_with_metadata(
        "Calculate 10 + 15."
    )

    selection = parse_tool_selection_response(
        generation.content
    )

    assert generation.provider_name == "primary-provider"
    assert generation.fallback_used is False
    assert calls == ["primary-provider"]
    assert selection.status == "parse_error"
    assert selection.valid_no_tool_decision is False
