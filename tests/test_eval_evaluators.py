"""
Deterministic evaluator tests.
"""

from evals.evaluators import (
    build_default_evaluator_registry,
)
from evals.schema import (
    EvaluationCase,
    EvaluatorSpec,
    TargetResult,
)


def make_case() -> EvaluationCase:
    return EvaluationCase(
        case_id="evaluator-test",
        dataset="unit",
        description="Evaluator unit test",
        target="contract_fixture",
        input={},
        fixture_output={},
        evaluators=(
            EvaluatorSpec(
                name="exact_match",
                config={
                    "path": "route",
                    "expected": "tool",
                },
            ),
        ),
    )


def make_result() -> TargetResult:
    return TargetResult(
        output={
            "route": "tool",
            "tool_name": "calculator",
            "response": "The result is 600.",
            "sources": [
                "policy.txt#chunk-1",
            ],
            "prompt_ids": [
                "assistant.system.v1",
                "tool.answer.v1",
            ],
        },
        latency_ms=1.0,
    )


def test_exact_match_passes():
    registry = build_default_evaluator_registry()

    result = registry.get(
        "exact_match"
    ).evaluate(
        make_case(),
        make_result(),
        EvaluatorSpec(
            name="exact_match",
            config={
                "path": "route",
                "expected": "tool",
            },
        ),
    )

    assert result.passed is True
    assert result.score == 1.0


def test_contains_reports_partial_score():
    registry = build_default_evaluator_registry()

    result = registry.get(
        "contains"
    ).evaluate(
        make_case(),
        make_result(),
        EvaluatorSpec(
            name="contains",
            config={
                "path": "response",
                "values": [
                    "600",
                    "verified",
                ],
            },
        ),
    )

    assert result.passed is False
    assert result.score == 0.5


def test_route_match_detects_wrong_route():
    registry = build_default_evaluator_registry()

    result = registry.get(
        "route_match"
    ).evaluate(
        make_case(),
        make_result(),
        EvaluatorSpec(
            name="route_match",
            config={
                "expected": "rag",
            },
        ),
    )

    assert result.passed is False
    assert result.actual == "tool"


def test_tool_match_passes():
    registry = build_default_evaluator_registry()

    result = registry.get(
        "tool_match"
    ).evaluate(
        make_case(),
        make_result(),
        EvaluatorSpec(
            name="tool_match",
            config={
                "expected": "calculator",
            },
        ),
    )

    assert result.passed is True


def test_source_match_requires_all_sources():
    registry = build_default_evaluator_registry()

    result = registry.get(
        "source_match"
    ).evaluate(
        make_case(),
        make_result(),
        EvaluatorSpec(
            name="source_match",
            config={
                "expected": [
                    "policy.txt#chunk-1",
                    "policy.txt#chunk-2",
                ],
            },
        ),
    )

    assert result.passed is False
    assert result.score == 0.5


def test_prompt_match_requires_prompt_ids():
    registry = build_default_evaluator_registry()

    result = registry.get(
        "prompt_match"
    ).evaluate(
        make_case(),
        make_result(),
        EvaluatorSpec(
            name="prompt_match",
            config={
                "expected": [
                    "assistant.system.v1",
                    "tool.answer.v1",
                ],
            },
        ),
    )

    assert result.passed is True