"""
Route-selection evaluator.
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


class RouteMatchEvaluator(DeterministicEvaluator):
    """
    Verify the selected application route.
    """

    name = "route_match"

    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        expected = spec.config.get("expected")
        actual = target_result.output.get("route")

        if not isinstance(expected, str):
            raise ValueError(
                "route_match requires string 'expected'."
            )

        passed = actual == expected

        return EvaluationResult(
            evaluator=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"Route matched '{expected}'."
                if passed
                else (
                    f"Expected route '{expected}' but received "
                    f"'{actual}'."
                )
            ),
            expected=expected,
            actual=actual,
        )