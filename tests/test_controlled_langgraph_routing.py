"""
AI Quality v1C Phase 5 controlled LangGraph routing tests.

These tests execute the real compiled production LangGraph, supervisor,
conditional edges, tool router, Phase 2 selector parser, and calculator.
Only external, nondeterministic, stateful, or side-effecting boundaries are
replaced with deterministic local controls.
"""

from __future__ import annotations

from evals.experiment import Experiment
from evals.schema import EvaluationCase, EvaluatorSpec
from evals.targets import LangGraphControlledTarget


def make_case(
    *,
    case_id: str,
    message: str,
    selector_output: str,
    retrieval_context: str = "",
    retrieval_sources: list[str] | None = None,
    assistant_response: str = "Controlled assistant response.",
) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        dataset="phase5-unit",
        description="Controlled LangGraph routing test",
        target="langgraph_controlled",
        input={
            "message": message,
            "selector_output": selector_output,
            "retrieval_context": retrieval_context,
            "retrieval_sources": retrieval_sources or [],
            "assistant_response": assistant_response,
        },
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "persisted_exchange_count",
                    "expected": 1,
                },
            ),
        ),
    )


def execute(case: EvaluationCase):
    return LangGraphControlledTarget().execute(
        case,
        Experiment(name="phase5-controlled-langgraph"),
    )


def test_calculator_request_uses_real_tool_route_and_calculator():
    result = execute(
        make_case(
            case_id="calculator-route",
            message="Calculate 18 * 27.",
            selector_output=(
                '{"tool_name": "calculator", "tool_input": "18 * 27"}'
            ),
            assistant_response="The calculator result was used.",
        )
    )

    assert result.output["selection_status"] == "selected"
    assert result.output["route"] == "tool"
    assert result.output["tool_name"] == "calculator"
    assert result.output["tool_result"] == {
        "tool_name": "calculator",
        "tool_result": "The result of 18 * 27 is 486.",
    }
    assert result.output["used_rag"] is False
    assert result.output["retrieval_calls"] == []
    assert result.output["prompt_ids"] == [
        "assistant.system.v1",
        "tool.answer.v1",
    ]
    assert result.output["agent_steps"] == [
        "load_context",
        "select_tool",
        "supervisor",
        "generate_answer",
    ]
    assert result.output["ticket_created"] is False
    assert result.configuration["production_langgraph"] is True
    assert result.configuration["production_supervisor"] is True
    assert result.configuration["production_tool_router"] is True
    assert result.configuration["production_calculator"] is True


def test_valid_no_tool_preserves_current_rag_route_with_empty_retrieval():
    message = "Explain what an API is."

    result = execute(
        make_case(
            case_id="no-tool-current-route",
            message=message,
            selector_output=(
                '{"tool_name": "none", "tool_input": ""}'
            ),
            assistant_response="An API lets software systems communicate.",
        )
    )

    assert result.output["selection_status"] == "no_tool"
    assert result.output["valid_no_tool_decision"] is True
    assert result.output["tool_name"] is None

    # Current production semantics: no tool means supervisor route="rag".
    # Empty retrieval later produces an ordinary chat answer, but the state
    # route is deliberately not rewritten to "chat".
    assert result.output["route"] == "rag"
    assert result.output["used_rag"] is False
    assert result.output["effective_answer_mode"] == "chat"
    assert result.output["retrieval_calls"] == [message]
    assert result.output["prompt_ids"] == [
        "assistant.system.v1",
    ]
    assert result.output["agent_steps"] == [
        "load_context",
        "select_tool",
        "supervisor",
        "retrieve_rag",
        "generate_answer",
    ]


def test_explicit_ticket_request_uses_controlled_ticket_side_effect():
    result = execute(
        make_case(
            case_id="explicit-ticket",
            message="Create a support ticket for my WiFi issue.",
            selector_output=(
                '{"tool_name": "ticket_creator", '
                '"tool_input": "WiFi issue"}'
            ),
            assistant_response="A controlled ticket was created.",
        )
    )

    assert result.output["route"] == "tool"
    assert result.output["tool_name"] == "ticket_creator"
    assert result.output["ticket_created"] is True
    assert result.output["ticket_calls"] == ["WiFi issue"]
    assert "CONTROLLED-TICKET-1" in result.output["tool_result"][
        "tool_result"
    ]
    assert result.output["retrieval_calls"] == []
    assert result.output["prompt_ids"] == [
        "assistant.system.v1",
        "tool.answer.v1",
    ]
    assert result.configuration["controlled_ticket_side_effect"] is True
    assert result.configuration["external_ticket_calls"] is False


def test_troubleshooting_with_controlled_no_tool_does_not_create_ticket():
    message = "My WiFi is broken. What should I do?"

    result = execute(
        make_case(
            case_id="troubleshooting-no-tool",
            message=message,
            selector_output=(
                '{"tool_name": "none", "tool_input": ""}'
            ),
            assistant_response="Try reconnecting to WiFi first.",
        )
    )

    assert result.output["selection_status"] == "no_tool"
    assert result.output["ticket_created"] is False
    assert result.output["tool_name"] is None
    assert result.output["route"] == "rag"
    assert result.output["used_rag"] is False
    assert result.output["effective_answer_mode"] == "chat"


def test_ticket_selector_cannot_override_troubleshooting_side_effect_policy():
    """
    R1 changes the old Phase 5 characterization deliberately.

    Even when the controlled selector proposes ticket_creator, the shared
    application safety policy recognizes this as troubleshooting-only input and
    suppresses the ticket side effect before the graph can execute it.
    """

    result = execute(
        make_case(
            case_id="troubleshooting-ticket-selected",
            message="My WiFi is broken. What should I do?",
            selector_output=(
                '{"tool_name": "ticket_creator", '
                '"tool_input": "WiFi is broken"}'
            ),
            assistant_response="Try reconnecting to WiFi first.",
        )
    )

    assert result.output["selection_status"] == "selected"
    assert result.output["route"] == "rag"
    assert result.output["tool_name"] is None
    assert result.output["ticket_created"] is False
    assert result.output["ticket_calls"] == []
    assert result.output["effective_answer_mode"] == "chat"


def test_ambiguous_ticket_selection_requires_confirmation_without_execution():
    result = execute(
        make_case(
            case_id="ambiguous-ticket-confirmation",
            message="I need support with my WiFi.",
            selector_output=(
                '{"tool_name": "ticket_creator", '
                '"tool_input": "WiFi support"}'
            ),
        )
    )

    assert result.output["selection_status"] == "selected"
    assert result.output["route"] == "confirmation"
    assert result.output["action_status"] == "confirmation_required"
    assert result.output["tool_name"] is None
    assert result.output["ticket_created"] is False
    assert result.output["ticket_calls"] == []
    assert "explicit request" in result.output["response"]
    assert result.output["prompt_ids"] == []

def test_phase2_parse_error_remains_distinct_inside_real_graph():
    message = "Calculate 2 + 2."

    result = execute(
        make_case(
            case_id="parse-error-current-route",
            message=message,
            selector_output="calculator(2 + 2)",
            assistant_response="Controlled ordinary answer.",
        )
    )

    assert result.output["selection_status"] == "parse_error"
    assert result.output["valid_no_tool_decision"] is False
    assert result.output["tool_name"] is None

    # Phase 2 compatibility remains unchanged: parse_error maps to the legacy
    # no-tool routing interpretation, so the graph enters the RAG branch.
    assert result.output["route"] == "rag"
    assert result.output["retrieval_calls"] == [message]
