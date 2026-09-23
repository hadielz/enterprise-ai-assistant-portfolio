"""
LLM-based tool selector.

Instead of hardcoded keyword rules, we ask the LLM which tool
should be used for the user request.

Architecture Notes
------------------
Dependency seam:
    Tests and offline evaluations may supply a controlled LLM provider.
    Production callers omit it and continue using the configured provider
    factory exactly as before.

Structured contract:
    AI Quality v1C Phase 2 distinguishes a valid tool selection or no-tool
    decision from malformed JSON, invalid schemas, and unsupported tools.
    Provider exceptions still propagate exactly as before and remain the
    responsibility of the provider/fallback layer.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm.base import BaseLLMProvider
from app.llm.factory import get_llm_provider
from app.prompts.tool_prompts import build_tool_selection_prompt
from app.observability.logging import log_event
from app.observability.tracing import start_span
from app.tools.tool_selection import (
    SUPPORTED_TOOL_NAMES,
    ToolSelectionResult,
)


logger = logging.getLogger(__name__)

def _build_invalid_schema_result(
    *,
    raw_response: str,
    error: str,
    parsed_value: Any,
) -> ToolSelectionResult:
    """Build an invalid-schema result while preserving legacy semantics."""

    if isinstance(parsed_value, dict):
        return ToolSelectionResult(
            status="invalid_schema",
            tool_name=None,
            tool_input="",
            raw_response=raw_response,
            error=error,
            _legacy_tool_name=parsed_value.get("tool_name", "none"),
            _legacy_tool_input=parsed_value.get("tool_input", ""),
            _legacy_mapping_available=True,
        )

    return ToolSelectionResult(
        status="invalid_schema",
        tool_name=None,
        tool_input="",
        raw_response=raw_response,
        error=error,
        _legacy_mapping_available=False,
    )


def _unwrap_complete_json_fence(raw_response: str) -> str:
    """
    Unwrap a response only when the entire model output is one JSON code fence.

    Arbitrary prose around JSON is intentionally not repaired.
    """

    stripped = raw_response.strip()

    if not stripped.startswith("```") or not stripped.endswith("```"):
        return raw_response

    lines = stripped.splitlines()

    if len(lines) < 3:
        return raw_response

    opening_fence = lines[0].strip().lower()

    if opening_fence not in {"```json", "```"}:
        return raw_response

    return "\n".join(lines[1:-1]).strip()


def tool_selection_normalization(raw_response: str) -> str:
    candidate = _unwrap_complete_json_fence(raw_response)
    return "complete_markdown_fence" if candidate != raw_response else "bare"


def parse_tool_selection_response(
    raw_response: str,
) -> ToolSelectionResult:
    """
    Parse and validate one raw tool-selection model response.

    Bare JSON is accepted directly. A single Markdown code fence wrapping
    the entire JSON response is also accepted because real providers may
    add that formatting despite a JSON-only prompt.

    Arbitrary prose around JSON is intentionally not repaired.
    """

    parse_candidate = _unwrap_complete_json_fence(raw_response)

    try:
        decision = json.loads(parse_candidate)
    except json.JSONDecodeError as exc:
        return ToolSelectionResult(
            status="parse_error",
            tool_name=None,
            tool_input="",
            raw_response=raw_response,
            error=(
                "Tool-selection response is not valid JSON: "
                f"{exc.msg}."
            ),
            # Before Phase 2, malformed JSON became an explicit no-tool
            # dictionary. Preserve that downstream routing behavior through
            # the compatibility adapter while retaining parse_error here.
            _legacy_tool_name="none",
            _legacy_tool_input="",
        )

    if not isinstance(decision, dict):
        return _build_invalid_schema_result(
            raw_response=raw_response,
            error="Tool-selection JSON must be an object.",
            parsed_value=decision,
        )

    if "tool_name" not in decision or "tool_input" not in decision:
        return _build_invalid_schema_result(
            raw_response=raw_response,
            error=(
                "Tool-selection JSON must contain both 'tool_name' and "
                "'tool_input'."
            ),
            parsed_value=decision,
        )

    tool_name = decision["tool_name"]
    tool_input = decision["tool_input"]

    if not isinstance(tool_name, str) or not isinstance(tool_input, str):
        return _build_invalid_schema_result(
            raw_response=raw_response,
            error=(
                "Tool-selection fields 'tool_name' and 'tool_input' must "
                "both be strings."
            ),
            parsed_value=decision,
        )

    if tool_name == "none":
        return ToolSelectionResult(
            status="no_tool",
            tool_name=None,
            tool_input=tool_input,
            raw_response=raw_response,
            _legacy_tool_name="none",
            _legacy_tool_input=tool_input,
        )

    if tool_name not in SUPPORTED_TOOL_NAMES:
        return ToolSelectionResult(
            status="unsupported_tool",
            tool_name=tool_name,
            tool_input=tool_input,
            raw_response=raw_response,
            error=f"Unsupported tool name: {tool_name}.",
            _legacy_tool_name=tool_name,
            _legacy_tool_input=tool_input,
        )

    return ToolSelectionResult(
        status="selected",
        tool_name=tool_name,
        tool_input=tool_input,
        raw_response=raw_response,
        _legacy_tool_name=tool_name,
        _legacy_tool_input=tool_input,
    )


def select_tool(
    message: str,
    *,
    llm_provider: BaseLLMProvider | None = None,
) -> ToolSelectionResult:
    """
    Ask the LLM to decide which tool should be used.

    Provider exceptions intentionally propagate so provider execution failure
    remains distinct from tool-selection protocol failure.
    """

    provider = llm_provider or get_llm_provider()

    # The actual prompt lives in app/prompts/tool_prompts.py.
    # This keeps prompt engineering separate from tool execution logic.
    prompt = build_tool_selection_prompt(message)

    with start_span("ai.tool_selection", **{"ai.prompt_id": "tool.selection.v1"}) as span:
        raw_response = provider.generate(prompt)
        result = parse_tool_selection_response(raw_response)
        normalization = tool_selection_normalization(raw_response)
        span.set_attribute("tool_selection.status", result.status)
        span.set_attribute("tool_selection.normalization", normalization)
        if result.tool_name:
            span.set_attribute("tool_selection.tool_name", result.tool_name)
        log_event(
            logger,
            logging.INFO,
            "tool_selection_completed",
            tool_selection_status=result.status,
            tool_selection_normalization=normalization,
            tool_name=result.tool_name,
        )
        return result
