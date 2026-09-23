"""
AI Quality v1C Phase 2 structured tool-selection tests.

These tests call the real production selector with a deterministic local
provider. They make no OpenAI, Gemini, Ollama, embedding, ChromaDB, or
external evaluation call.
"""

from __future__ import annotations

import pytest

from app.llm.base import BaseLLMProvider
from app.tools.tool_router import route_tool
from app.tools.tool_selector import (
    parse_tool_selection_response,
    select_tool,
)


class ControlledSelectionProvider(BaseLLMProvider):
    provider_name = "controlled-selection"
    model_name = "controlled-selection-v1"

    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        self.calls += 1
        return self.response


class FailingSelectionProvider(BaseLLMProvider):
    provider_name = "controlled-failure"
    model_name = "controlled-failure-v1"

    def generate(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        raise RuntimeError("controlled provider failure")


def select_from_raw(raw_response: str):
    provider = ControlledSelectionProvider(raw_response)

    result = select_tool(
        "Controlled tool-selection request",
        llm_provider=provider,
    )

    assert provider.calls == 1
    return result


def test_valid_calculator_selection():
    result = select_from_raw(
        '{"tool_name": "calculator", "tool_input": "10 + 15"}'
    )

    assert result.status == "selected"
    assert result.selected is True
    assert result.tool_name == "calculator"
    assert result.tool_input == "10 + 15"
    assert result.error is None
    assert result.valid_no_tool_decision is False


def test_valid_ticket_selection():
    result = select_from_raw(
        '{"tool_name": "ticket_creator", "tool_input": "WiFi issue"}'
    )

    assert result.status == "selected"
    assert result.selected is True
    assert result.tool_name == "ticket_creator"
    assert result.tool_input == "WiFi issue"


def test_valid_no_tool_decision():
    result = select_from_raw(
        '{"tool_name": "none", "tool_input": ""}'
    )

    assert result.status == "no_tool"
    assert result.selected is False
    assert result.tool_name is None
    assert result.tool_input == ""
    assert result.valid_no_tool_decision is True


def test_malformed_json_is_parse_error_not_no_tool():
    result = select_from_raw("calculator(10 + 15)")

    assert result.status == "parse_error"
    assert result.tool_name is None
    assert result.valid_no_tool_decision is False
    assert result.error is not None

    # Characterization of the pre-Phase-2 routing behavior: malformed JSON
    # previously became the legacy no-tool dictionary. The selector now keeps
    # parse_error observable while the compatibility adapter preserves that
    # downstream routing interpretation.
    assert result.to_legacy_decision() == {
        "tool_name": "none",
        "tool_input": "",
    }


def test_complete_fenced_json_is_accepted():
    raw_response = (
        "```json\n"
        "{\n"
        '  "tool_name": "ticket_creator",\n'
        '  "tool_input": "Problem with WiFi connection."\n'
        "}\n"
        "```"
    )

    result = select_from_raw(raw_response)

    assert result.status == "selected"
    assert result.tool_name == "ticket_creator"
    assert result.tool_input == "Problem with WiFi connection."
    assert result.valid_no_tool_decision is False
    assert result.raw_response == raw_response


def test_prose_wrapped_json_remains_parse_error():
    result = select_from_raw(
        "Here is the requested JSON:\n"
        '{"tool_name": "ticket_creator", '
        '"tool_input": "Problem with WiFi connection."}'
    )

    assert result.status == "parse_error"
    assert result.tool_name is None
    assert result.valid_no_tool_decision is False


def test_missing_field_is_invalid_schema():
    result = select_from_raw(
        '{"tool_name": "calculator"}'
    )

    assert result.status == "invalid_schema"
    assert result.tool_name is None
    assert result.valid_no_tool_decision is False
    assert "both 'tool_name' and 'tool_input'" in result.error


def test_invalid_field_type_is_invalid_schema():
    result = select_from_raw(
        '{"tool_name": "calculator", "tool_input": 25}'
    )

    assert result.status == "invalid_schema"
    assert result.tool_name is None
    assert result.valid_no_tool_decision is False
    assert "must both be strings" in result.error


def test_unsupported_tool_name_is_explicit():
    result = select_from_raw(
        '{"tool_name": "web_search", "tool_input": "enterprise AI"}'
    )

    assert result.status == "unsupported_tool"
    assert result.tool_name == "web_search"
    assert result.tool_input == "enterprise AI"
    assert result.valid_no_tool_decision is False
    assert result.error == "Unsupported tool name: web_search."


def test_non_object_json_is_invalid_schema():
    result = parse_tool_selection_response(
        '["calculator", "10 + 15"]'
    )

    assert result.status == "invalid_schema"
    assert result.valid_no_tool_decision is False

    # Before Phase 2, the production code attempted `.get()` on this parsed
    # list and failed. The compatibility adapter keeps such top-level values
    # from being silently converted to a no-tool decision.
    with pytest.raises(AttributeError):
        result.to_legacy_decision()


def test_provider_failure_still_propagates():
    """
    Provider errors do not belong to the selector schema in Phase 2.

    The resilient-provider layer owns provider/fallback behavior independently
    from selector protocol classification.
    """

    with pytest.raises(
        RuntimeError,
        match="controlled provider failure",
    ):
        select_tool(
            "Calculate 2 + 2",
            llm_provider=FailingSelectionProvider(),
        )


def test_router_preserves_legacy_parse_error_behavior():
    result = parse_tool_selection_response(
        "not-json"
    )

    routed = route_tool(
        "Calculate 2 + 2",
        tool_selector=lambda _: result,
    )

    assert routed is None


def test_router_still_accepts_phase1_legacy_selector_dict():
    routed = route_tool(
        "Calculate 8 * 7",
        tool_selector=lambda _: {
            "tool_name": "calculator",
            "tool_input": "8 * 7",
        },
        calculator=lambda expression: f"controlled: {expression}",
    )

    assert routed == {
        "tool_name": "calculator",
        "tool_result": "controlled: 8 * 7",
    }
