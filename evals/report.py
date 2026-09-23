"""
Experiment report generation and persistence.

Architecture Notes
------------------
Purpose:
    Produce one stable machine-readable report containing:
        - experiment configuration
        - aggregate results
        - per-case results
        - failures
        - latency
        - dataset identities

Reports:
    JSON is used so reports can later be consumed by:
        - GitHub Actions
        - dashboards
        - comparison scripts
        - release checks
        - CI quality gates
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.experiment import Experiment
from evals.schema import CaseResult


@dataclass(frozen=True)
class ExperimentReport:
    """
    Aggregate report for one experiment run.
    """

    experiment: Experiment
    datasets: tuple[str, ...]
    cases: tuple[CaseResult, ...]

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def passed_cases(self) -> int:
        return sum(
            result.status == "passed"
            for result in self.cases
        )

    @property
    def failed_cases(self) -> int:
        return sum(
            result.status in {"failed", "error"}
            for result in self.cases
        )

    @property
    def skipped_cases(self) -> int:
        return sum(
            result.status == "skipped"
            for result in self.cases
        )

    @property
    def required_failures(self) -> int:
        return sum(
            result.required
            and result.status in {"failed", "error"}
            for result in self.cases
        )

    @property
    def total_latency_ms(self) -> float:
        return round(
            sum(result.latency_ms for result in self.cases),
            3,
        )

    @property
    def average_score(self) -> float:
        scored_cases = [
            result.score
            for result in self.cases
            if result.status != "skipped"
        ]

        if not scored_cases:
            return 0.0

        return round(
            sum(scored_cases) / len(scored_cases),
            4,
        )

    @property
    def passed(self) -> bool:
        return self.required_failures == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment.to_dict(),
            "summary": {
                "passed": self.passed,
                "total_cases": self.total_cases,
                "passed_cases": self.passed_cases,
                "failed_cases": self.failed_cases,
                "skipped_cases": self.skipped_cases,
                "required_failures": self.required_failures,
                "average_score": self.average_score,
                "total_latency_ms": self.total_latency_ms,
            },
            "datasets": list(self.datasets),
            "failures": [
                result.to_dict()
                for result in self.cases
                if result.status in {"failed", "error"}
            ],
            "cases": [
                result.to_dict()
                for result in self.cases
            ],
        }

    def write_json(self, path: Path) -> Path:
        """
        Write the report and return the resolved output path.
        """

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                self.to_dict(),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        return path.resolve()