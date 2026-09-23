"""
Evaluation-target tests.
"""

import pytest

from evals.experiment import Experiment
from evals.schema import (
    EvaluationCase,
    EvaluatorSpec,
)
from evals.targets import (
    ContractFixtureTarget,
    ProviderFallbackControlledTarget,
    RAGControlledTarget,
    LangGraphControlledTarget,
    ToolSelectorControlledTarget,
    StreamingParityControlledTarget,
    build_default_target_registry,
)


def test_fixture_target_returns_controlled_output():
    target = ContractFixtureTarget()

    case = EvaluationCase(
        case_id="fixture-target",
        dataset="unit",
        description="Fixture target test",
        target="contract_fixture",
        input={
            "message": "Hello",
        },
        fixture_output={
            "route": "chat",
        },
        evaluators=(
            EvaluatorSpec(
                name="route_match",
                config={
                    "expected": "chat",
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(
            name="target-test",
        ),
    )

    assert result.output == {
        "route": "chat",
    }
    assert result.configuration["deterministic"] is True


def test_fixture_target_rejects_missing_output():
    target = ContractFixtureTarget()

    case = EvaluationCase(
        case_id="missing-fixture-output",
        dataset="unit",
        description="Missing fixture output",
        target="contract_fixture",
        input={},
        fixture_output=None,
        evaluators=(
            EvaluatorSpec(
                name="route_match",
                config={
                    "expected": "chat",
                },
            ),
        ),
        status="reserved",
    )

    with pytest.raises(
        ValueError,
        match="has no fixture_output",
    ):
        target.execute(
            case,
            Experiment(
                name="target-test",
            ),
        )


def test_tool_selector_controlled_target_uses_real_parser():
    target = ToolSelectorControlledTarget()

    case = EvaluationCase(
        case_id="controlled-tool-selector",
        dataset="unit",
        description="Controlled tool selector target",
        target="tool_selector_controlled",
        input={
            "message": "Calculate 2 + 3.",
            "provider_output": (
                '{"tool_name": "calculator", "tool_input": "2 + 3"}'
            ),
        },
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "selection_status",
                    "expected": "selected",
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(name="tool-selector-target-test"),
    )

    assert result.output["selection_status"] == "selected"
    assert result.output["tool_name"] == "calculator"
    assert result.output["tool_input"] == "2 + 3"
    assert result.configuration["production_parser"] is True
    assert result.configuration["deterministic"] is True


def test_tool_selector_controlled_target_exposes_parse_error():
    target = ToolSelectorControlledTarget()

    case = EvaluationCase(
        case_id="controlled-tool-selector-parse-error",
        dataset="unit",
        description="Controlled malformed output",
        target="tool_selector_controlled",
        input={
            "message": "Calculate 2 + 3.",
            "provider_output": "calculator(2 + 3)",
        },
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "selection_status",
                    "expected": "parse_error",
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(name="tool-selector-target-test"),
    )

    assert result.output["selection_status"] == "parse_error"
    assert result.output["valid_no_tool_decision"] is False


def test_provider_fallback_controlled_target_uses_real_fallback():
    target = ProviderFallbackControlledTarget()

    case = EvaluationCase(
        case_id="controlled-provider-fallback",
        dataset="unit",
        description="Controlled provider fallback target",
        target="provider_fallback_controlled",
        input={
            "message": "Calculate 7 * 8.",
            "providers": [
                {
                    "configured_name": "primary",
                    "provider_name": "primary-provider",
                    "model_name": "primary-model",
                    "behavior": "raise_error",
                    "response": "",
                    "error_message": "primary unavailable",
                },
                {
                    "configured_name": "fallback",
                    "provider_name": "fallback-provider",
                    "model_name": "fallback-model",
                    "behavior": "return",
                    "response": (
                        '{"tool_name": "calculator", '
                        '"tool_input": "7 * 8"}'
                    ),
                    "error_message": "unused",
                },
            ],
        },
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "provider",
                    "expected": "fallback-provider",
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(name="provider-fallback-target-test"),
    )

    assert result.output["provider_succeeded"] is True
    assert result.output["provider"] == "fallback-provider"
    assert result.output["model"] == "fallback-model"
    assert result.output["fallback_used"] is True
    assert result.output["provider_call_order"] == [
        "primary-provider",
        "fallback-provider",
    ]
    assert result.output["selection_status"] == "selected"
    assert result.output["tool_name"] == "calculator"
    assert result.configuration["production_factory"] is True
    assert result.configuration["production_fallback"] is True


def test_provider_fallback_controlled_target_keeps_protocol_failure_separate():
    target = ProviderFallbackControlledTarget()

    case = EvaluationCase(
        case_id="controlled-provider-malformed-protocol",
        dataset="unit",
        description="Successful provider with malformed selector output",
        target="provider_fallback_controlled",
        input={
            "message": "Calculate 2 + 3.",
            "providers": [
                {
                    "configured_name": "primary",
                    "provider_name": "primary-provider",
                    "model_name": "primary-model",
                    "behavior": "return",
                    "response": "calculator(2 + 3)",
                    "error_message": "unused",
                },
                {
                    "configured_name": "fallback",
                    "provider_name": "fallback-provider",
                    "model_name": "fallback-model",
                    "behavior": "return",
                    "response": (
                        '{"tool_name": "calculator", '
                        '"tool_input": "2 + 3"}'
                    ),
                    "error_message": "unused",
                },
            ],
        },
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "selection_status",
                    "expected": "parse_error",
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(name="provider-protocol-boundary-test"),
    )

    assert result.output["provider"] == "primary-provider"
    assert result.output["fallback_used"] is False
    assert result.output["provider_call_order"] == [
        "primary-provider"
    ]
    assert result.output["selection_status"] == "parse_error"


def test_rag_controlled_target_uses_real_retriever_boundary():
    target = RAGControlledTarget()

    case = EvaluationCase(
        case_id="controlled-rag",
        dataset="unit",
        description="Controlled RAG target",
        target="rag_controlled",
        input={
            "message": "What is the hotel reimbursement limit?",
            "controlled_documents": [
                {
                    "source": "travel_policy.txt#chunk-4",
                    "content": (
                        "Hotel reimbursement is limited to "
                        "150 euros per night."
                    ),
                }
            ],
        },
        evaluators=(
            EvaluatorSpec(
                name="source_match",
                config={
                    "expected": ["travel_policy.txt#chunk-4"],
                },
            ),
        ),
    )

    result = target.execute(
        case,
        Experiment(name="rag-target-test"),
    )

    assert result.output["retrieval_succeeded"] is True
    assert result.output["used_rag"] is True
    assert result.output["sources"] == [
        "travel_policy.txt#chunk-4"
    ]
    assert "150 euros per night" in result.output["rag_prompt"]
    assert result.configuration["production_retriever"] is True
    assert result.configuration["langgraph_routing_executed"] is False


def test_default_registry_contains_phase5_langgraph_target():
    registry = build_default_target_registry()

    assert registry.get(
        "contract_fixture"
    ).name == "contract_fixture"

    assert registry.get(
        "tool_selector_controlled"
    ).name == "tool_selector_controlled"

    assert registry.get(
        "provider_fallback_controlled"
    ).name == "provider_fallback_controlled"

    assert registry.get(
        "rag_controlled"
    ).name == "rag_controlled"

    assert registry.get(
        "langgraph_controlled"
    ).name == "langgraph_controlled"

    assert registry.get(
        "streaming_parity_controlled"
    ).name == "streaming_parity_controlled"
