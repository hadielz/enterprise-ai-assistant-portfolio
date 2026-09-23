"""
Evaluation dataset loader tests.
"""

import json
from pathlib import Path

import pytest

from evals.loader import (
    load_all_datasets,
    load_dataset,
)


def test_all_v1b_datasets_load():
    cases = load_all_datasets()

    assert cases
    assert any(
        case.status == "active"
        for case in cases
    )
    assert all(
        case.status == "active"
        for case in cases
    )


def test_case_ids_are_globally_unique():
    cases = load_all_datasets()

    case_ids = [
        case.case_id
        for case in cases
    ]

    assert len(case_ids) == len(set(case_ids))


def test_expected_contract_categories_exist():
    cases = load_all_datasets()

    tags = {
        tag
        for case in cases
        for tag in case.tags
    }

    assert "calculator" in tags
    assert "ticket" in tags
    assert "no-tool" in tags
    assert "rag" in tags
    assert "source-attribution" in tags
    assert "cross-user-isolation" in tags
    assert "no-fabricated-success" in tags
    assert "malformed-json" in tags
    assert "provider-fallback" in tags
    assert "prompt-versioning" in tags
    assert "side-effect-safety" in tags
    assert "parity" in tags


def test_loader_rejects_duplicate_case_ids(
    tmp_path: Path,
):
    path = tmp_path / "duplicate.json"

    path.write_text(
        json.dumps(
            {
                "name": "duplicate_dataset",
                "cases": [
                    {
                        "id": "same-id",
                        "description": "First",
                        "target": "contract_fixture",
                        "input": {},
                        "fixture_output": {
                            "value": 1
                        },
                        "evaluators": [
                            {
                                "name": "exact_match",
                                "config": {
                                    "path": "value",
                                    "expected": 1
                                }
                            }
                        ]
                    },
                    {
                        "id": "same-id",
                        "description": "Second",
                        "target": "contract_fixture",
                        "input": {},
                        "fixture_output": {
                            "value": 2
                        },
                        "evaluators": [
                            {
                                "name": "exact_match",
                                "config": {
                                    "path": "value",
                                    "expected": 2
                                }
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate evaluation case ID",
    ):
        load_dataset(path)


def test_active_fixture_requires_fixture_output(
    tmp_path: Path,
):
    path = tmp_path / "missing-output.json"

    path.write_text(
        json.dumps(
            {
                "name": "invalid_dataset",
                "cases": [
                    {
                        "id": "missing-output",
                        "description": "Invalid fixture",
                        "target": "contract_fixture",
                        "status": "active",
                        "input": {},
                        "evaluators": [
                            {
                                "name": "exact_match",
                                "config": {
                                    "path": "value",
                                    "expected": 1
                                }
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="requires fixture_output",
    ):
        load_dataset(path)