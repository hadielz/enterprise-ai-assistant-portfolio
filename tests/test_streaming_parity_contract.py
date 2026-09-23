"""Controlled streaming/non-streaming parity regression tests."""

import json

from evals.experiment import Experiment
from evals.schema import EvaluationCase, EvaluatorSpec
from evals.targets import StreamingParityControlledTarget


def make_case(case_id: str, input_data: dict) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        dataset="phase6-unit",
        description="Controlled parity case",
        target="streaming_parity_controlled",
        input=input_data,
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={"path": "semantic_mode_equal", "expected": True},
            ),
        ),
    )


def test_calculator_parity_uses_real_tool_workflow_once_per_path():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "calculator-parity",
            {
                "message": "Calculate 15 * 4.",
                "selector_output": (
                    '{"tool_name":"calculator","tool_input":"15 * 4"}'
                ),
            },
        ),
        Experiment(name="phase6-calculator"),
    ).output

    assert result["route_equal"] is True
    assert result["semantic_mode_equal"] is True
    assert result["tool_equal"] is True
    assert result["tool_result_equal"] is True
    assert result["non_streaming"]["route"] == "tool"
    assert result["streaming"]["route"] == "tool"
    assert result["non_streaming"]["tool_name"] == "calculator"
    assert "60" in result["non_streaming"]["tool_result"]["tool_result"]
    assert result["persistence_once_each"] is True
    assert result["summary_once_each"] is True


def test_ticket_parity_has_no_duplicate_side_effect_inside_either_path():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "ticket-parity",
            {
                "message": "Create a ticket for my WiFi issue.",
                "selector_output": (
                    '{"tool_name":"ticket_creator",'
                    '"tool_input":"WiFi issue"}'
                ),
            },
        ),
        Experiment(name="phase6-ticket"),
    ).output

    assert result["tool_equal"] is True
    assert result["tool_result_equal"] is True
    assert result["ticket_side_effect_once_each"] is True
    assert result["non_streaming"]["ticket_calls"] == ["WiFi issue"]
    assert result["streaming"]["ticket_calls"] == ["WiFi issue"]


def test_no_tool_empty_retrieval_preserves_known_route_representation_difference():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "no-tool-parity",
            {
                "message": "Explain what an API is.",
                "selector_output": '{"tool_name":"none","tool_input":""}',
                "retrieval_context": "",
                "retrieval_sources": [],
            },
        ),
        Experiment(name="phase6-no-tool"),
    ).output

    assert result["selection_status_equal"] is True
    assert result["non_streaming"]["selection_status"] == "no_tool"
    assert result["streaming"]["selection_status"] == "no_tool"
    assert result["semantic_mode_equal"] is True
    assert result["non_streaming"]["effective_answer_mode"] == "chat"
    assert result["streaming"]["effective_answer_mode"] == "chat"
    assert result["non_streaming"]["route"] == "rag"
    assert result["streaming"]["route"] == "chat"
    assert result["route_equal"] is False
    assert result["known_route_representation_difference"] is True


def test_rag_parity_preserves_sources_and_prompt_contract():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "rag-parity",
            {
                "message": "What is the hotel reimbursement limit?",
                "selector_output": '{"tool_name":"none","tool_input":""}',
                "retrieval_context": (
                    "Hotel reimbursement is limited to 150 euros per night."
                ),
                "retrieval_sources": ["travel_policy.txt#chunk-4"],
            },
        ),
        Experiment(name="phase6-rag"),
    ).output

    assert result["route_equal"] is True
    assert result["semantic_mode_equal"] is True
    assert result["retrieval_used_equal"] is True
    assert result["sources_equal"] is True
    assert result["prompt_contract_equal"] is True
    assert result["non_streaming"]["sources"] == [
        "travel_policy.txt#chunk-4"
    ]
    assert result["streaming"]["sources"] == [
        "travel_policy.txt#chunk-4"
    ]


def test_malformed_selector_remains_parse_error_in_both_paths():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "malformed-parity",
            {
                "message": "Calculate 2 + 2.",
                "selector_output": "calculator(2 + 2)",
                "retrieval_context": "",
            },
        ),
        Experiment(name="phase6-malformed"),
    ).output

    assert result["selection_status_equal"] is True
    assert result["non_streaming"]["selection_status"] == "parse_error"
    assert result["streaming"]["selection_status"] == "parse_error"
    assert result["non_streaming"]["valid_no_tool_decision"] is False
    assert result["streaming"]["valid_no_tool_decision"] is False
    assert result["non_streaming"]["status"] == "completed"
    assert result["streaming"]["status"] == "completed"


def test_real_provider_fallback_semantics_are_preserved_in_both_paths():
    providers = [
        {
            "provider_name": "primary-provider",
            "model_name": "primary-model",
            "behavior": "raise_error",
            "response": "",
            "chunks": [],
            "error_message": "primary unavailable",
        },
        {
            "provider_name": "fallback-provider",
            "model_name": "fallback-model",
            "behavior": "return",
            "response": "Controlled fallback answer.",
            "chunks": ["Controlled fallback ", "answer."],
            "error_message": "unused",
        },
    ]

    result = StreamingParityControlledTarget().execute(
        make_case(
            "fallback-parity",
            {
                "message": "Calculate 5 * 5.",
                "selector_output": (
                    '{"tool_name":"calculator","tool_input":"5 * 5"}'
                ),
                "answer_providers": providers,
            },
        ),
        Experiment(name="phase6-fallback"),
    ).output

    expected_order = ["primary-provider", "fallback-provider"]
    assert result["non_streaming"]["provider_call_order"] == expected_order
    assert result["streaming"]["provider_call_order"] == expected_order
    assert result["non_streaming"]["status"] == "completed"
    assert result["streaming"]["status"] == "completed"
    assert result["persistence_once_each"] is True


def test_all_provider_failure_characterizes_real_handling_difference():
    failing_providers = [
        {
            "provider_name": "primary-provider",
            "model_name": "primary-model",
            "behavior": "raise_error",
            "response": "",
            "chunks": [],
            "error_message": "primary unavailable",
        },
        {
            "provider_name": "fallback-provider",
            "model_name": "fallback-model",
            "behavior": "raise_error",
            "response": "",
            "chunks": [],
            "error_message": "fallback unavailable",
        },
    ]

    result = StreamingParityControlledTarget().execute(
        make_case(
            "all-provider-failure",
            {
                "message": "Explain what an API is.",
                "selector_output": '{"tool_name":"none","tool_input":""}',
                "retrieval_context": "",
                "answer_providers": failing_providers,
            },
        ),
        Experiment(name="phase6-provider-failure"),
    ).output

    assert result["non_streaming"]["status"] == "error"
    assert result["non_streaming"]["error_type"] == "LLMProviderError"
    assert result["non_streaming"]["persisted_exchange_count"] == 0
    assert result["non_streaming"]["summary_call_count"] == 0

    assert result["streaming"]["status"] == "completed_with_failure_message"
    assert "temporarily unavailable" in result["streaming"]["response"]
    assert result["streaming"]["persisted_exchange_count"] == 1
    assert result["streaming"]["summary_call_count"] == 1


def test_streaming_parity_output_is_json_serializable():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "json-serializable-parity",
            {
                "message": "Explain what an API is.",
                "selector_output": '{"tool_name":"none","tool_input":""}',
                "retrieval_context": "",
                "retrieval_sources": [],
            },
        ),
        Experiment(name="phase6-json-serialization"),
    ).output

    json.dumps(result) 


def test_ambiguous_ticket_request_requires_confirmation_in_both_paths():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "ambiguous-ticket-safe-action",
            {
                "message": "I need support with my WiFi.",
                "selector_output": (
                    '{"tool_name":"ticket_creator",'
                    '"tool_input":"WiFi support"}'
                ),
            },
        ),
        Experiment(name="r1-ambiguous-ticket"),
    ).output

    assert result["route_equal"] is True
    assert result["semantic_mode_equal"] is True
    assert result["non_streaming"]["route"] == "confirmation"
    assert result["streaming"]["route"] == "confirmation"
    assert result["non_streaming"]["action_status"] == "confirmation_required"
    assert result["streaming"]["action_status"] == "confirmation_required"
    assert result["non_streaming"]["ticket_created"] is False
    assert result["streaming"]["ticket_created"] is False
    assert result["non_streaming"]["ticket_calls"] == []
    assert result["streaming"]["ticket_calls"] == []
    assert result["non_streaming"]["provider_call_order"] == []
    assert result["streaming"]["provider_call_order"] == []
    assert "explicit request" in result["non_streaming"]["response"]
    assert "explicit request" in result["streaming"]["response"]


def test_troubleshooting_selected_as_ticket_is_suppressed_in_both_paths():
    result = StreamingParityControlledTarget().execute(
        make_case(
            "troubleshooting-safe-action",
            {
                "message": "My WiFi is broken. What should I do?",
                "selector_output": (
                    '{"tool_name":"ticket_creator",'
                    '"tool_input":"WiFi is broken"}'
                ),
                "retrieval_context": "",
            },
        ),
        Experiment(name="r1-troubleshooting-ticket"),
    ).output

    assert result["non_streaming"]["ticket_created"] is False
    assert result["streaming"]["ticket_created"] is False
    assert result["non_streaming"]["ticket_calls"] == []
    assert result["streaming"]["ticket_calls"] == []
    assert result["non_streaming"]["effective_answer_mode"] == "chat"
    assert result["streaming"]["effective_answer_mode"] == "chat"
