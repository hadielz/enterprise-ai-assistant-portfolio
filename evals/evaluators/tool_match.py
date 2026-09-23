"""
Tool-selection evaluator.
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


class ToolMatchEvaluator(DeterministicEvaluator):
    """
    Verify the selected tool.

    JSON null is used for a genuine no-tool result. This is distinct
    from future parse-error metadata.
    """

    name = "tool_match"

    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        expected = spec.config.get("expected")
        actual = target_result.output.get("tool_name")

        if expected is not None and not isinstance(
            expected,
            str,
        ):
            raise ValueError(
                "tool_match expected must be a string or null."
            )

        passed = actual == expected

        return EvaluationResult(
            evaluator=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"Tool matched '{expected}'."
                if passed
                else (
                    f"Expected tool '{expected}' but received "
                    f"'{actual}'."
                )
            ),
            expected=expected,
            actual=actual,
        )