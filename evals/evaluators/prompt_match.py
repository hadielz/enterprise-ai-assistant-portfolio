"""
Prompt-identifier evaluator.
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


class PromptMatchEvaluator(DeterministicEvaluator):
    """
    Verify prompt IDs attached to one route or generation result.
    """

    name = "prompt_match"

    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        expected = spec.config.get("expected")

        if not isinstance(expected, list) or not all(
            isinstance(prompt_id, str)
            for prompt_id in expected
        ):
            raise ValueError(
                "prompt_match requires a string list in 'expected'."
            )

        actual = target_result.output.get(
            "prompt_ids",
            [],
        )

        if not isinstance(actual, list):
            actual = []

        missing = [
            prompt_id
            for prompt_id in expected
            if prompt_id not in actual
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
                "All required prompt identifiers were attached."
                if passed
                else (
                    f"Missing prompt identifiers: {missing}."
                )
            ),
            expected=expected,
            actual=actual,
        )