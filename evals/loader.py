"""
Evaluation dataset loading and validation.

Architecture Notes
------------------
Purpose:
    Convert JSON datasets into validated EvaluationCase objects.

Validation:
    Invalid or duplicate case identifiers fail before execution. A
    quality gate must never silently ignore malformed contracts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from evals.schema import EvaluationCase


DEFAULT_DATASET_DIRECTORY = (
    Path(__file__).resolve().parent / "datasets"
)


def discover_dataset_paths(
    dataset_directory: Path = DEFAULT_DATASET_DIRECTORY,
) -> list[Path]:
    """
    Return all JSON dataset files in deterministic order.
    """

    return sorted(dataset_directory.glob("*.json"))


def load_dataset(path: Path) -> list[EvaluationCase]:
    """
    Load and validate one JSON dataset.
    """

    try:
        raw_data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Dataset '{path}' contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(raw_data, dict):
        raise ValueError(
            f"Dataset '{path}' must contain a JSON object."
        )

    dataset_name = raw_data.get("name")

    if not isinstance(dataset_name, str) or not dataset_name.strip():
        raise ValueError(
            f"Dataset '{path}' requires a non-empty 'name'."
        )

    raw_cases = raw_data.get("cases")

    if not isinstance(raw_cases, list):
        raise ValueError(
            f"Dataset '{dataset_name}' requires a 'cases' array."
        )

    cases = [
        EvaluationCase.from_dict(
            item,
            dataset=dataset_name.strip(),
        )
        for item in raw_cases
    ]

    _validate_unique_case_ids(cases)

    return cases


def load_datasets(
    paths: Iterable[Path],
) -> list[EvaluationCase]:
    """
    Load multiple datasets and validate global case-ID uniqueness.
    """

    cases: list[EvaluationCase] = []

    for path in paths:
        cases.extend(load_dataset(path))

    _validate_unique_case_ids(cases)

    return cases


def load_all_datasets(
    dataset_directory: Path = DEFAULT_DATASET_DIRECTORY,
) -> list[EvaluationCase]:
    """
    Discover and load every evaluation dataset.
    """

    paths = discover_dataset_paths(dataset_directory)

    if not paths:
        raise ValueError(
            f"No evaluation datasets found in "
            f"'{dataset_directory}'."
        )

    return load_datasets(paths)


def _validate_unique_case_ids(
    cases: Iterable[EvaluationCase],
) -> None:
    seen: set[str] = set()

    for case in cases:
        if case.case_id in seen:
            raise ValueError(
                f"Duplicate evaluation case ID: "
                f"'{case.case_id}'."
            )

        seen.add(case.case_id)