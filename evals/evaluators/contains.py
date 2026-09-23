"""
Deterministic content-presence evaluator.
"""

from typing import Any

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


class ContainsEvaluator(DeterministicEvaluator):
    """
    Verify that a string or collection contains required values.
    """

    name = "contains"

    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        path = spec.config.get("path")
        required_values = spec.config.get("values")
        case_sensitive = spec.config.get(
            "case_sensitive",
            True,
        )

        if not isinstance(path, str):
            raise ValueError(
                "contains requires a string 'path'."
            )

        if (
            not isinstance(required_values, list)
            or not required_values
        ):
            raise ValueError(
                "contains requires a non-empty 'values' list."
            )

        actual = resolve_path(
            target_result.output,
            path,
            default=None,
        )

        missing = [
            value
            for value in required_values
            if not _contains(
                actual,
                value,
                case_sensitive=case_sensitive,
            )
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
                        len(required_values) - len(missing)
                    )
                    / len(required_values),
                    4,
                )
            ),
            reason=(
                f"'{path}' contained every required value."
                if passed
                else (
                    f"'{path}' was missing required values: "
                    f"{missing}."
                )
            ),
            expected=required_values,
            actual=actual,
        )


def _contains(
    actual: Any,
    expected: Any,
    *,
    case_sensitive: bool,
) -> bool:
    if isinstance(actual, str):
        expected_text = str(expected)

        if case_sensitive:
            return expected_text in actual

        return expected_text.casefold() in actual.casefold()

    if isinstance(actual, (list, tuple, set)):
        if case_sensitive:
            return expected in actual

        expected_text = str(expected).casefold()

        return any(
            str(item).casefold() == expected_text
            for item in actual
        )

    if isinstance(actual, dict):
        return expected in actual

    return False