"""
Structured tool-selection contract.

Architecture Notes
------------------
Purpose:
    Preserve the model's tool-selection outcome as an explicit internal
    result instead of representing every non-selected outcome as
    {"tool_name": "none", "tool_input": ""}.

Why:
    A valid no-tool decision is semantically different from malformed JSON,
    an invalid response schema, or an unsupported tool name. Quality
    evaluation and later observability need to distinguish those outcomes.

Compatibility:
    Phase 2 keeps the existing production routing semantics through
    to_legacy_decision(). The tool router can therefore consume the new
    structured result while producing the same user-facing behavior as the
    pre-Phase-2 dictionary contract.

Provider failures:
    Provider exceptions are intentionally not converted into a
    ToolSelectionResult here. Provider/fallback behavior belongs to the LLM
    provider boundary and is tested separately from selector-protocol errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ToolSelectionStatus = Literal[
    "selected",
    "no_tool",
    "parse_error",
    "invalid_schema",
    "unsupported_tool",
]


SUPPORTED_TOOL_NAMES = {
    "calculator",
    "ticket_creator",
}


@dataclass(frozen=True)
class ToolSelectionResult:
    """
    Structured result returned by the production tool selector.

    `tool_name` and `tool_input` describe only a validated decision.
    Invalid outputs keep their original raw response and an error message.

    The private legacy fields preserve the pre-v1C routing interpretation
    while downstream code migrates deliberately to the structured contract.
    """

    status: ToolSelectionStatus
    tool_name: str | None
    tool_input: str
    raw_response: str
    error: str | None = None

    _legacy_tool_name: Any = None
    _legacy_tool_input: Any = ""
    _legacy_mapping_available: bool = True

    @property
    def valid_no_tool_decision(self) -> bool:
        """Return True only for a valid model decision to use no tool."""

        return self.status == "no_tool"

    @property
    def selected(self) -> bool:
        """Return True only when a supported tool was validly selected."""

        return self.status == "selected"

    def to_legacy_decision(self) -> dict[str, Any]:
        """
        Return the dictionary shape used before AI Quality v1C Phase 2.

        This compatibility adapter lets route_tool() preserve existing
        production behavior while select_tool() exposes richer semantics to
        controlled evaluations and future observability.

        Top-level JSON values that were not objects previously failed when
        `.get()` was accessed. We preserve that failure class instead of
        silently turning such values into a no-tool decision.
        """

        if not self._legacy_mapping_available:
            raise AttributeError(
                "Tool-selection JSON value does not provide object-style "
                "field access."
            )

        return {
            "tool_name": self._legacy_tool_name,
            "tool_input": self._legacy_tool_input,
        }
