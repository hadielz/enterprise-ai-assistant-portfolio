"""
Shared evaluator infrastructure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from evals.schema import (
    EvaluationCase,
    EvaluationResult,
    EvaluatorSpec,
    TargetResult,
)


MISSING = object()


def resolve_path(
    value: Any,
    path: str,
    *,
    default: Any = MISSING,
) -> Any:
    """
    Resolve a dotted path through nested dictionaries and lists.

    Examples:
        route
        metadata.status_code
        messages.0.role
    """

    if path == "":
        return value

    current = value

    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                if default is not MISSING:
                    return default

                raise KeyError(
                    f"Path '{path}' does not exist."
                )

            current = current[part]
            continue

        if isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError) as exc:
                if default is not MISSING:
                    return default

                raise KeyError(
                    f"Path '{path}' does not exist."
                ) from exc

            continue

        if default is not MISSING:
            return default

        raise KeyError(
            f"Path '{path}' does not exist."
        )

    return current


class DeterministicEvaluator(ABC):
    """
    Base interface for code-based deterministic evaluators.
    """

    name: str

    @abstractmethod
    def evaluate(
        self,
        case: EvaluationCase,
        target_result: TargetResult,
        spec: EvaluatorSpec,
    ) -> EvaluationResult:
        raise NotImplementedError


class EvaluatorRegistry:
    """
    Registry of deterministic evaluators.
    """

    def __init__(self) -> None:
        self._evaluators: dict[
            str,
            DeterministicEvaluator,
        ] = {}

    def register(
        self,
        evaluator: DeterministicEvaluator,
    ) -> None:
        if evaluator.name in self._evaluators:
            raise ValueError(
                f"Evaluator '{evaluator.name}' is already registered."
            )

        self._evaluators[evaluator.name] = evaluator

    def get(
        self,
        name: str,
    ) -> DeterministicEvaluator:
        try:
            return self._evaluators[name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown evaluator '{name}'."
            ) from exc