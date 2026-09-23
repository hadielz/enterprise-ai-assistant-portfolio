"""
Generic exact-value evaluator.
"""

from evals.evaluators.common import (
    DeterministicEvaluator,
    resolve_path,
)
from evals.schema import (
    EvaluationCase,
    EvaluationResult,
    EvaluatorSpec,
    TargetResult,
)


class ExactMatchEvaluator(DeterministicEvaluator):
    """
    Compare one target-output path with one exact expected value.
    """

    name = "exact_match"

    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        path = spec.config.get("path")
        expected = spec.config.get("expected")

        if not isinstance(path, str):
            raise ValueError(
                "exact_match requires a string 'path'."
            )

        actual = resolve_path(
            target_result.output,
            path,
            default=None,
        )

        passed = actual == expected

        return EvaluationResult(
            evaluator=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"'{path}' exactly matched the expected value."
                if passed
                else (
                    f"'{path}' did not match the expected value."
                )
            ),
            expected=expected,
            actual=actual,
        )