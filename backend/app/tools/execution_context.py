"""Trusted application context supplied to side-effecting tool capabilities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolExecutionContext:
    user_id: int
    request_id: str
