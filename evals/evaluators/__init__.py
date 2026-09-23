"""
Default deterministic evaluator registry.
"""

from evals.evaluators.common import EvaluatorRegistry
from evals.evaluators.contains import ContainsEvaluator
from evals.evaluators.exact_match import (
    ExactMatchEvaluator,
)
from evals.evaluators.prompt_match import (
    PromptMatchEvaluator,
)
from evals.evaluators.route_match import (
    RouteMatchEvaluator,
)
from evals.evaluators.source_match import (
    SourceMatchEvaluator,
)
from evals.evaluators.tool_match import ToolMatchEvaluator


def build_default_evaluator_registry() -> EvaluatorRegistry:
    """
    Build the deterministic evaluator registry used in v1B.
    """

    registry = EvaluatorRegistry()

    registry.register(ExactMatchEvaluator())
    registry.register(ContainsEvaluator())
    registry.register(RouteMatchEvaluator())
    registry.register(ToolMatchEvaluator())
    registry.register(SourceMatchEvaluator())
    registry.register(PromptMatchEvaluator())

    return registry


__all__ = [
    "build_default_evaluator_registry",
]