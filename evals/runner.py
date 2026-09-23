"""
Deterministic offline experiment runner.

Usage:
    python -m evals.runner

    python -m evals.runner \
        --experiment-name ai-quality-v1b \
        --dataset routing_cases \
        --dataset tool_cases

Exit codes:
    0:
        All required active cases passed.

    1:
        At least one required active case failed or errored.

    2:
        Dataset, argument, or framework configuration error.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.evaluators import (
    build_default_evaluator_registry,
)
from evals.experiment import Experiment
from evals.loader import (
    DEFAULT_DATASET_DIRECTORY,
    discover_dataset_paths,
    load_datasets,
)
from evals.report import ExperimentReport
from evals.schema import (
    CaseResult,
    EvaluationCase,
)
from evals.targets import build_default_target_registry


DEFAULT_RESULTS_DIRECTORY = (
    Path(__file__).resolve().parent / "results"
)


def execute_case(
    case: EvaluationCase,
    *,
    experiment: Experiment,
):
    """
    Execute one evaluation case using default v1B registries.
    """

    target_registry = build_default_target_registry()
    evaluator_registry = (
        build_default_evaluator_registry()
    )

    if case.status == "reserved":
        return CaseResult(
            case_id=case.case_id,
            dataset=case.dataset,
            description=case.description,
            target=case.target,
            required=case.required,
            status="skipped",
            passed=False,
            score=0.0,
            latency_ms=0.0,
            evaluations=(),
            target_output=None,
            error=None,
            tags=case.tags,
            notes=case.notes,
        )

    try:
        target = target_registry.get(case.target)

        target_result = target.execute(
            case,
            experiment,
        )

        evaluations = tuple(
            evaluator_registry.get(
                evaluator_spec.name
            ).evaluate(
                case,
                target_result,
                evaluator_spec,
            )
            for evaluator_spec in case.evaluators
        )

        passed = all(
            evaluation.passed
            for evaluation in evaluations
        )

        score = (
            round(
                sum(
                    evaluation.score
                    for evaluation in evaluations
                )
                / len(evaluations),
                4,
            )
            if evaluations
            else 0.0
        )

        return CaseResult(
            case_id=case.case_id,
            dataset=case.dataset,
            description=case.description,
            target=case.target,
            required=case.required,
            status="passed" if passed else "failed",
            passed=passed,
            score=score,
            latency_ms=target_result.latency_ms,
            evaluations=evaluations,
            target_output=target_result.output,
            error=None,
            tags=case.tags,
            notes=case.notes,
        )

    except Exception as exc:
        return CaseResult(
            case_id=case.case_id,
            dataset=case.dataset,
            description=case.description,
            target=case.target,
            required=case.required,
            status="error",
            passed=False,
            score=0.0,
            latency_ms=0.0,
            evaluations=(),
            target_output=None,
            error=f"{type(exc).__name__}: {exc}",
            tags=case.tags,
            notes=case.notes,
        )


def run_experiment(
    *,
    experiment: Experiment,
    cases: list[EvaluationCase],
) -> ExperimentReport:
    """
    Execute every case and build an aggregate report.
    """

    results = tuple(
        execute_case(
            case,
            experiment=experiment,
        )
        for case in cases
    )

    datasets = tuple(
        sorted(
            {
                case.dataset
                for case in cases
            }
        )
    )

    return ExperimentReport(
        experiment=experiment,
        datasets=datasets,
        cases=results,
    )


def select_dataset_paths(
    dataset_names: list[str],
    *,
    dataset_directory: Path,
) -> list[Path]:
    """
    Resolve dataset command-line names to JSON files.
    """

    available_paths = discover_dataset_paths(
        dataset_directory
    )

    if not dataset_names or "all" in dataset_names:
        return available_paths

    available = {
        path.stem: path
        for path in available_paths
    }

    missing = [
        name
        for name in dataset_names
        if name not in available
    ]

    if missing:
        raise ValueError(
            "Unknown datasets: "
            + ", ".join(sorted(missing))
        )

    return [
        available[name]
        for name in dataset_names
    ]


def build_default_output_path(
    experiment: Experiment,
) -> Path:
    """
    Produce a filesystem-safe report filename.
    """

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    safe_name = "".join(
        character
        if character.isalnum() or character in {"-", "_"}
        else "-"
        for character in experiment.name
    ).strip("-")

    return (
        DEFAULT_RESULTS_DIRECTORY
        / f"{timestamp}-{safe_name}.json"
    )


def print_summary(
    report: ExperimentReport,
    output_path: Path,
) -> None:
    """
    Print a concise human-readable execution summary.
    """

    summary = report.to_dict()["summary"]

    print("")
    print("Deterministic Evaluation Report")
    print("-------------------------------")
    print(
        f"Experiment: {report.experiment.name}"
    )
    print(
        f"Experiment ID: "
        f"{report.experiment.experiment_id}"
    )
    print(
        f"Datasets: {', '.join(report.datasets)}"
    )
    print(
        f"Passed: {summary['passed_cases']}"
    )
    print(
        f"Failed or errored: "
        f"{summary['failed_cases']}"
    )
    print(
        f"Skipped/reserved: "
        f"{summary['skipped_cases']}"
    )
    print(
        f"Required failures: "
        f"{summary['required_failures']}"
    )
    print(
        f"Average score: "
        f"{summary['average_score']:.4f}"
    )
    print(
        f"Report: {output_path}"
    )
    print("")

    failures = [
        result
        for result in report.cases
        if result.status in {"failed", "error"}
    ]

    for result in failures:
        print(
            f"[{result.status.upper()}] "
            f"{result.case_id}"
        )

        if result.error:
            print(f"  {result.error}")

        for evaluation in result.evaluations:
            if not evaluation.passed:
                print(
                    f"  {evaluation.evaluator}: "
                    f"{evaluation.reason}"
                )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic offline AI evaluations."
        )
    )

    parser.add_argument(
        "--experiment-name",
        default="ai-quality-v1b-deterministic-contracts",
    )

    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help=(
            "Dataset filename without .json. Repeat this "
            "argument to select multiple datasets. Defaults "
            "to all datasets."
        ),
    )

    parser.add_argument(
        "--dataset-directory",
        type=Path,
        default=DEFAULT_DATASET_DIRECTORY,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)

    try:
        paths = select_dataset_paths(
            args.dataset,
            dataset_directory=args.dataset_directory,
        )

        if not paths:
            raise ValueError(
                "No evaluation dataset files were selected."
            )

        cases = load_datasets(paths)

        experiment = Experiment(
            name=args.experiment_name,
            prompt_ids=(
                "assistant.system.v1",
                "rag.answer.v1",
                "tool.selection.v1",
                "tool.answer.v1",
                "conversation.summary.v1",
            ),
            provider="deterministic",
            model="contract-fixture-v1",
            configuration={
                "framework_version": "v1B",
                "external_llm_calls": False,
                "external_embedding_calls": False,
                "external_evaluation_services": False,
            },
        )

        report = run_experiment(
            experiment=experiment,
            cases=cases,
        )

        output_path = (
            args.output
            if args.output is not None
            else build_default_output_path(
                experiment
            )
        )

        resolved_output_path = report.write_json(
            output_path
        )

        print_summary(
            report,
            resolved_output_path,
        )

        return 0 if report.passed else 1

    except Exception as exc:
        print(
            f"Evaluation configuration error: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())