"""R1 deterministic side-effect safety tests."""

from app.tools.safe_actions import evaluate_ticket_action
from app.tools.tool_router import route_tool


def ticket_selector(_: str) -> dict:
    """Simulate an LLM that proposes ticket creation for every request."""

    return {
        "tool_name": "ticket_creator",
        "tool_input": "WiFi issue",
    }


def test_explicit_ticket_request_allows_side_effect():
    calls: list[str] = []

    result = route_tool(
        "Create a ticket for my broken WiFi.",
        tool_selector=ticket_selector,
        ticket_creator=lambda description: (
            calls.append(description)
            or {
                "ticket_id": "CONTROLLED-1",
                "status": "created",
                "description": description,
            }
        ),
    )

    assert calls == ["WiFi issue"]
    assert result is not None
    assert result["tool_name"] == "ticket_creator"


def test_explicit_report_to_it_allows_side_effect():
    decision = evaluate_ticket_action(
        "My VPN is not working. Please report it to IT."
    )

    assert decision.status == "allowed"
    assert decision.action_allowed is True


def test_troubleshooting_request_suppresses_ticket_even_when_selector_requests_it():
    calls: list[str] = []

    result = route_tool(
        "My WiFi is broken. What should I do?",
        tool_selector=ticket_selector,
        ticket_creator=lambda description: calls.append(description) or {},
    )

    assert result is None
    assert calls == []


def test_ambiguous_support_request_requires_confirmation_without_side_effect():
    calls: list[str] = []

    result = route_tool(
        "I need support with my WiFi.",
        tool_selector=ticket_selector,
        ticket_creator=lambda description: calls.append(description) or {},
    )

    assert calls == []
    assert result is not None
    assert result["tool_name"] is None
    assert result["requested_tool_name"] == "ticket_creator"
    assert result["action_status"] == "confirmation_required"
    assert result["side_effect_executed"] is False
    assert "explicit request" in result["confirmation_message"]


def test_question_about_creating_ticket_does_not_authorize_side_effect():
    calls: list[str] = []

    result = route_tool(
        "How do I create a support ticket?",
        tool_selector=ticket_selector,
        ticket_creator=lambda description: calls.append(description) or {},
    )

    assert result is None
    assert calls == []


def test_safe_default_requires_confirmation_for_unrecognized_ticket_intent():
    decision = evaluate_ticket_action("Please handle this WiFi problem for me.")

    assert decision.status == "confirmation_required"
    assert decision.action_allowed is False


def test_negated_ticket_language_never_executes_side_effect():
    calls: list[str] = []

    messages = (
        "Don't create a ticket for my WiFi.",
        "Do not open a ticket for this.",
        "I don't want you to create a ticket.",
        "Please do not report this to IT.",
        "No ticket, please just help me troubleshoot.",
        "Without a support ticket, what can I try?",
    )

    for message in messages:
        result = route_tool(
            message,
            tool_selector=ticket_selector,
            ticket_creator=lambda description: (
                calls.append(description) or {}
            ),
        )

        assert result is None

    assert calls == []


def test_informational_ticket_language_never_executes_side_effect():
    calls: list[str] = []

    messages = (
        "Should I create a ticket for this?",
        "Can I create a ticket for this?",
        "Can you tell me how to create a ticket?",
        "Could you explain how to open an incident?",
    )

    for message in messages:
        result = route_tool(
            message,
            tool_selector=ticket_selector,
            ticket_creator=lambda description: (
                calls.append(description) or {}
            ),
        )

        assert result is None

    assert calls == []

    assert evaluate_ticket_action(
        "Could you create a support ticket for my WiFi?"
    ).action_allowed is True
