"""
RAG source-attribution evaluator.
"""

from evals.evaluators.common import (
    DeterministicEvaluator,
)
from evals.schema import (
    EvaluationCase,
    EvaluationResult,
    EvaluatorSpec,
    TargetResult,
)


class SourceMatchEvaluator(DeterministicEvaluator):
    """
    Verify that all required source identifiers are present.
    """

    name = "source_match"

    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        expected = spec.config.get("expected")

        if not isinstance(expected, list) or not all(
            isinstance(source, str)
            for source in expected
        ):
            raise ValueError(
                "source_match requires a string list in 'expected'."
            )

        actual = target_result.output.get("sources", [])

        if not isinstance(actual, list):
            actual = []

        missing = [
            source
            for source in expected
            if source not in actual
        ]

        passed = not missing

        return EvaluationResult(
            evaluator=self.name,
            passed=passed,
            score=(
                1.0
                if passed
                else round(
                    (
                        len(expected) - len(missing)
                    )
                    / len(expected),
                    4,
                )
                if expected
                else 1.0
            ),
            reason=(
                "All required source identifiers were present."
                if passed
                else f"Missing required sources: {missing}."
            ),
            expected=expected,
            actual=actual,
        )