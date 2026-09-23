"""
Core evaluation data structures.

Architecture Notes
------------------
Purpose:
    Define stable boundaries between datasets, targets, evaluators,
    case execution, experiments, and reports.

Why dataclasses:
    Evaluation infrastructure benefits from explicit structured objects.
    Passing loosely structured dictionaries throughout the framework
    would make later v1C integration harder to validate and maintain.

Separation:
    EvaluationCase describes the contract.
    TargetResult describes what a target produced.
    EvaluationResult describes one deterministic assertion.
    CaseResult combines target execution and all evaluator outcomes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


CaseStatus = Literal["active", "reserved"]
ResultStatus = Literal["passed", "failed", "skipped", "error"]


@dataclass(frozen=True)
class EvaluatorSpec:
    """
    Configuration for one evaluator applied to a case.

    `name` resolves an evaluator from the registry.

    `config` contains evaluator-specific settings such as:
        - expected value
        - actual output path
        - required substrings
        - case-sensitivity rules
    """

    name: str
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluatorSpec":
        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Every evaluator specification requires a non-empty "
                "'name'."
            )

        config = data.get("config", {})

        if not isinstance(config, dict):
            raise ValueError(
                f"Evaluator '{name}' config must be a JSON object."
            )

        return cls(
            name=name.strip(),
            config=config,
        )


@dataclass(frozen=True)
class EvaluationCase:
    """
    One deterministic evaluation contract.

    Active cases:
        Execute a registered deterministic target during v1B.

    Reserved cases:
        Preserve a real workflow contract for v1C. They are reported as
        skipped and are never counted as passing.

    `fixture_output` is permitted only for the deterministic fixture
    target. It represents controlled target output, not real production
    output.
    """

    case_id: str
    dataset: str
    description: str
    target: str

    input: dict[str, Any]
    evaluators: tuple[EvaluatorSpec, ...]

    required: bool = True
    status: CaseStatus = "active"

    fixture_output: dict[str, Any] | None = None

    tags: tuple[str, ...] = ()
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        dataset: str,
    ) -> "EvaluationCase":
        case_id = data.get("id")

        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(
                f"Dataset '{dataset}' contains a case without a valid "
                "'id'."
            )

        description = data.get("description")

        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f"Evaluation case '{case_id}' requires a description."
            )

        target = data.get("target")

        if not isinstance(target, str) or not target.strip():
            raise ValueError(
                f"Evaluation case '{case_id}' requires a target."
            )

        case_input = data.get("input", {})

        if not isinstance(case_input, dict):
            raise ValueError(
                f"Evaluation case '{case_id}' input must be an object."
            )

        raw_evaluators = data.get("evaluators")

        if not isinstance(raw_evaluators, list) or not raw_evaluators:
            raise ValueError(
                f"Evaluation case '{case_id}' requires at least one "
                "evaluator."
            )

        evaluators = tuple(
            EvaluatorSpec.from_dict(item)
            for item in raw_evaluators
        )

        status = data.get("status", "active")

        if status not in {"active", "reserved"}:
            raise ValueError(
                f"Evaluation case '{case_id}' has unsupported status "
                f"'{status}'."
            )

        required = data.get("required", True)

        if not isinstance(required, bool):
            raise ValueError(
                f"Evaluation case '{case_id}' required must be boolean."
            )

        fixture_output = data.get("fixture_output")

        if fixture_output is not None and not isinstance(
            fixture_output,
            dict,
        ):
            raise ValueError(
                f"Evaluation case '{case_id}' fixture_output must be "
                "an object or null."
            )

        raw_tags = data.get("tags", [])

        if not isinstance(raw_tags, list) or not all(
            isinstance(tag, str)
            for tag in raw_tags
        ):
            raise ValueError(
                f"Evaluation case '{case_id}' tags must be strings."
            )

        notes = data.get("notes", "")

        if not isinstance(notes, str):
            raise ValueError(
                f"Evaluation case '{case_id}' notes must be a string."
            )

        metadata = data.get("metadata", {})

        if not isinstance(metadata, dict):
            raise ValueError(
                f"Evaluation case '{case_id}' metadata must be an "
                "object."
            )

        if (
            status == "active"
            and target == "contract_fixture"
            and fixture_output is None
        ):
            raise ValueError(
                f"Active fixture case '{case_id}' requires "
                "fixture_output."
            )

        return cls(
            case_id=case_id.strip(),
            dataset=dataset,
            description=description.strip(),
            target=target.strip(),
            input=case_input,
            evaluators=evaluators,
            required=required,
            status=status,
            fixture_output=fixture_output,
            tags=tuple(raw_tags),
            notes=notes,
            metadata=metadata,
        )


@dataclass(frozen=True)
class TargetResult:
    """
    Structured output returned by an evaluation target.
    """

    output: dict[str, Any]
    latency_ms: float
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    """
    Result from one deterministic evaluator.
    """

    evaluator: str
    passed: bool
    score: float
    reason: str
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaseResult:
    """
    Complete result for one evaluation case.
    """

    case_id: str
    dataset: str
    description: str
    target: str

    required: bool
    status: ResultStatus

    passed: bool
    score: float
    latency_ms: float

    evaluations: tuple[EvaluationResult, ...] = ()

    target_output: dict[str, Any] | None = None
    error: str | None = None

    tags: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "dataset": self.dataset,
            "description": self.description,
            "target": self.target,
            "required": self.required,
            "status": self.status,
            "passed": self.passed,
            "score": self.score,
            "latency_ms": self.latency_ms,
            "evaluations": [
                evaluation.to_dict()
                for evaluation in self.evaluations
            ],
            "target_output": self.target_output,
            "error": self.error,
            "tags": list(self.tags),
            "notes": self.notes,
        }