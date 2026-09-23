"""
Deterministic safety policy for side-effecting support-ticket actions.

Architecture Notes
------------------
Purpose:
    The LLM tool selector may propose ticket_creator, but model output is not
    sufficient authority to execute a side effect. The original user message
    must independently satisfy this deterministic application policy.

R1 contract:
    - explicit ticket creation/reporting request -> action allowed
    - troubleshooting-only request -> no ticket action
    - ambiguous support/escalation request -> confirmation required

R2 replaces the simulator with a persisted MCP-backed ticket workflow while
preserving this policy as the pre-execution authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


TicketActionStatus = Literal[
    "allowed",
    "troubleshooting",
    "confirmation_required",
]


CONFIRMATION_REQUIRED_MESSAGE = (
    "I can create a support ticket, but I will not do that without an "
    "explicit request. If you want a ticket created, please say so clearly, "
    "for example: 'Create a ticket for my WiFi issue.'"
)


@dataclass(frozen=True)
class TicketActionDecision:
    """Application-level decision about whether ticket creation may execute."""

    status: TicketActionStatus
    reason: str

    @property
    def action_allowed(self) -> bool:
        return self.status == "allowed"

    @property
    def confirmation_required(self) -> bool:
        return self.status == "confirmation_required"


# These patterns intentionally require explicit action language. A selector
# choosing ticket_creator without such language cannot execute the side effect.
_NEGATED_TICKET_PATTERNS = (
    re.compile(
        r"\b(?:do\s+not|don't|dont|never)\b.{0,60}"
        r"\b(?:create|open|file|submit|raise|log|report)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:do\s+not|don't|dont|never)\b.{0,60}"
        r"\b(?:ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"\bno\s+(?:support\s+)?(?:ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"\bwithout\s+(?:a\s+)?(?:support\s+)?(?:ticket|incident)\b",
        re.I,
    ),
)

_NON_ACTION_TICKET_QUESTION_PATTERNS = (
    re.compile(
        r"\bhow (?:do|can|should) i\b.{0,30}"
        r"\b(create|open|file|submit|raise|log)\b.{0,30}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:what is|what's) the (?:process|procedure)\b.{0,40}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:should|can|could|may) i\b.{0,40}"
        r"\b(create|open|file|submit|raise|log)\b.{0,30}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:can|could|would) you\b.{0,30}"
        r"\b(?:tell|show|explain)\b.{0,50}"
        r"\b(create|open|file|submit|raise|log)\b.{0,30}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
)

_EXPLICIT_TICKET_PATTERNS = (
    re.compile(
        r"(?:^|[.!?]\s+)(?:please\s+)?"
        r"(create|open|file|submit|raise|log)\b.{0,40}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[.!?]\s+)"
        r"(?:can|could|would|will)\s+you\s+(?:please\s+)?"
        r"(create|open|file|submit|raise|log)\b.{0,40}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[.!?]\s+)"
        r"i\s+(?:want|need|would\s+like)\s+(?:you\s+)?to\s+"
        r"(create|open|file|submit|raise|log)\b.{0,40}"
        r"\b(ticket|incident)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[.!?]\s+)(?:please\s+)?"
        r"report\b.{0,50}\b(?:to|with)\b.{0,20}"
        r"\b(?:it|support|help\s*desk)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[.!?]\s+)"
        r"(?:can|could|would|will)\s+you\s+(?:please\s+)?"
        r"report\b.{0,50}\b(?:to|with)\b.{0,20}"
        r"\b(?:it|support|help\s*desk)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[.!?]\s+)"
        r"i\s+(?:want|need|would\s+like)\s+(?:you\s+)?to\s+"
        r"report\b.{0,50}\b(?:to|with)\b.{0,20}"
        r"\b(?:it|support|help\s*desk)\b",
        re.I,
    ),
)

_TROUBLESHOOTING_PATTERNS = (
    re.compile(r"\bwhat should i do\b", re.I),
    re.compile(r"\bhow (?:do|can|should) i (?:fix|solve|troubleshoot)\b", re.I),
    re.compile(r"\bhow (?:do|can) i get .* working\b", re.I),
    re.compile(r"\bcan you help me (?:fix|troubleshoot)\b", re.I),
    re.compile(r"\btroubleshoot\b", re.I),
)


def evaluate_ticket_action(message: str) -> TicketActionDecision:
    """
    Classify the original user message for ticket side-effect safety.

    The safe default is confirmation_required: if the model selected a ticket
    but the user's text is neither explicitly authorizing creation nor clearly
    asking only for troubleshooting, the application asks for an explicit
    request instead of executing the action.
    """

    normalized = " ".join(message.split())

    if any(
        pattern.search(normalized)
        for pattern in _NEGATED_TICKET_PATTERNS
    ):
        return TicketActionDecision(
            status="troubleshooting",
            reason=(
                "The user explicitly rejected ticket creation, so the "
                "application must not execute the side effect."
            ),
        )

    if any(
        pattern.search(normalized)
        for pattern in _NON_ACTION_TICKET_QUESTION_PATTERNS
    ):
        return TicketActionDecision(
            status="troubleshooting",
            reason=(
                "The user asked about the ticket process rather than "
                "authorizing a ticket side effect."
            ),
        )

    if any(pattern.search(normalized) for pattern in _EXPLICIT_TICKET_PATTERNS):
        return TicketActionDecision(
            status="allowed",
            reason="The user explicitly requested ticket creation/reporting.",
        )

    if any(pattern.search(normalized) for pattern in _TROUBLESHOOTING_PATTERNS):
        return TicketActionDecision(
            status="troubleshooting",
            reason="The user requested troubleshooting rather than a ticket side effect.",
        )

    return TicketActionDecision(
        status="confirmation_required",
        reason=(
            "The selector proposed a ticket but the user did not explicitly "
            "authorize ticket creation."
        ),
    )
