"""
Experiment configuration.

Architecture Notes
------------------
Purpose:
    Describe one named execution of one or more evaluation datasets
    against a particular target configuration.

Why this is separate from the runner:
    The runner executes experiments. It should not own the identity of
    prompt versions, provider settings, model settings, or arbitrary
    experimental configuration.

Future:
    v1C can compare controlled workflow versions.
    Later milestones can compare real providers or retrievers without
    redesigning report generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Experiment:
    """
    Immutable experiment identity and configuration.
    """

    name: str

    experiment_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    prompt_ids: tuple[str, ...] = ()

    provider: str = "deterministic"
    model: str = "none"

    configuration: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["prompt_ids"] = list(self.prompt_ids)
        return data