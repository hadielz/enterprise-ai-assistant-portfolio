"""
Experiment-runner and report tests.
"""

import json
from pathlib import Path

from evals.experiment import Experiment
from evals.report import ExperimentReport
from evals.runner import (
    execute_case,
    main,
    run_experiment,
)
from evals.schema import (
    EvaluationCase,
    EvaluatorSpec,
)


def make_active_case(
    *,
    expected_route: str = "chat",
    actual_route: str = "chat",
    required: bool = True,
) -> EvaluationCase:
    return EvaluationCase(
        case_id=(
            f"active-{expected_route}-{actual_route}"
        ),
        dataset="runner-tests",
        description="Active runner case",
        target="contract_fixture",
        input={},
        fixture_output={
            "route": actual_route,
        },
        evaluators=(
            EvaluatorSpec(
                name="route_match",
                config={
                    "expected": expected_route,
                },
            ),
        ),
        required=required,
        status="active",
    )


def test_runner_passes_matching_case():
    report = run_experiment(
        experiment=Experiment(
            name="passing-run",
        ),
        cases=[
            make_active_case(),
        ],
    )

    assert report.passed is True
    assert report.passed_cases == 1
    assert report.required_failures == 0


def test_runner_fails_required_case():
    report = run_experiment(
        experiment=Experiment(
            name="failing-run",
        ),
        cases=[
            make_active_case(
                expected_route="tool",
                actual_route="chat",
            ),
        ],
    )

    assert report.passed is False
    assert report.failed_cases == 1
    assert report.required_failures == 1


def test_optional_failure_does_not_fail_experiment():
    report = run_experiment(
        experiment=Experiment(
            name="optional-failure",
        ),
        cases=[
            make_active_case(
                expected_route="tool",
                actual_route="chat",
                required=False,
            ),
        ],
    )

    assert report.passed is True
    assert report.failed_cases == 1
    assert report.required_failures == 0


def test_reserved_case_is_skipped():
    case = EvaluationCase(
        case_id="reserved-case",
        dataset="runner-tests",
        description="Reserved workflow contract",
        target="langgraph_controlled",
        input={},
        fixture_output=None,
        evaluators=(
            EvaluatorSpec(
                name="route_match",
                config={
                    "expected": "tool",
                },
            ),
        ),
        required=True,
        status="reserved",
    )

    result = execute_case(
        case,
        experiment=Experiment(
            name="reserved-run",
        ),
    )

    assert result.status == "skipped"
    assert result.passed is False


def test_report_writes_configuration_and_results(
    tmp_path: Path,
):
    experiment = Experiment(
        name="report-test",
        prompt_ids=(
            "assistant.system.v1",
        ),
        provider="deterministic",
        model="fixture-v1",
    )

    report = run_experiment(
        experiment=experiment,
        cases=[
            make_active_case(),
        ],
    )

    output_path = report.write_json(
        tmp_path / "report.json"
    )

    data = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert data["summary"]["passed"] is True
    assert data["experiment"]["provider"] == (
        "deterministic"
    )
    assert data["experiment"]["prompt_ids"] == [
        "assistant.system.v1",
    ]
    assert data["cases"][0]["status"] == "passed"


def test_cli_returns_zero_for_repository_datasets(
    tmp_path: Path,
):
    output = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "--experiment-name",
            "pytest-v1b",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert output.exists()


def test_report_type_is_explicit():
    report = run_experiment(
        experiment=Experiment(
            name="type-test",
        ),
        cases=[
            make_active_case(),
        ],
    )

    assert isinstance(
        report,
        ExperimentReport,
    )