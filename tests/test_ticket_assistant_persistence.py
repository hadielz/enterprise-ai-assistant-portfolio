"""Exactly-once persisted assistant ticket side-effect tests."""

from sqlalchemy import select

from app.agents.dependencies import AgentDependencies
from app.agents.enterprise_agent import build_enterprise_agent
from app.database.models import Ticket, User
from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.services.chat_dependencies import ChatServiceDependencies
from app.services.chat_service import generate_response, stream_response
from app.tickets.service import create_ticket_for_requester
from app.tools.tool_router import route_tool


class AnswerProvider(BaseLLMProvider):
    def generate(self, message: str, history=None) -> str:
        return "Ticket creation confirmed."

    def stream(self, message: str, history=None):
        yield "Ticket creation "
        yield "confirmed."


def _user(db_session, username="assistant-owner"):
    user = User(
        username=username,
        display_name=username.title(),
        password_hash="test-hash",
        role="employee",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _route_with_persistence(db_session):
    def selector(_):
        return {"tool_name": "ticket_creator", "tool_input": "VPN is broken"}

    def creator(description, *, execution_context):
        ticket = create_ticket_for_requester(
            db_session,
            requester_user_id=execution_context.user_id,
            description=description,
            action_id=execution_context.request_id,
        )
        return {
            "ticket_id": ticket.public_id,
            "status": ticket.status,
            "description": ticket.description,
        }

    def routed(message, **kwargs):
        return route_tool(
            message,
            execution_context=kwargs.get("execution_context"),
            tool_selector=selector,
            ticket_creator=creator,
        )

    return routed


def test_non_streaming_explicit_request_creates_exactly_one_ticket(db_session):
    user = _user(db_session, "nonstream-ticket-owner")
    routed = _route_with_persistence(db_session)
    agent = build_enterprise_agent(
        AgentDependencies(
            get_recent_messages=lambda **_: [],
            get_summary=lambda **_: "",
            build_history_context=AgentDependencies().build_history_context,
            route_tool=routed,
            retrieve_context=lambda _: {"context": "", "sources": []},
            get_llm_provider=lambda: AnswerProvider(),
            add_exchange=lambda **_: None,
            maybe_summarize_conversation=lambda **_: None,
        )
    )

    result = generate_response(
        message="Create a ticket for my broken VPN.",
        conversation_id="ticket-nonstream",
        user_id=user.id,
        session=db_session,
        dependencies=ChatServiceDependencies(enterprise_agent=agent),
    )

    assert result["tool_used"] == "ticket_creator"
    assert db_session.query(Ticket).count() == 1


def test_streaming_explicit_request_creates_exactly_one_ticket(db_session):
    user = _user(db_session, "stream-ticket-owner")
    routed = _route_with_persistence(db_session)

    chunks = list(
        stream_response(
            message="Create a ticket for my broken VPN.",
            conversation_id="ticket-stream",
            user_id=user.id,
            session=db_session,
            dependencies=ChatServiceDependencies(
                get_llm_provider=lambda: AnswerProvider(),
                get_recent_messages=lambda **_: [],
                get_summary=lambda **_: "",
                route_tool=routed,
                retrieve_context=lambda _: {"context": "", "sources": []},
                add_exchange=lambda **_: None,
                maybe_summarize_conversation=lambda **_: None,
            ),
        )
    )

    assert "Ticket creation" in "".join(chunks)
    assert db_session.query(Ticket).count() == 1

def test_r1_guarded_requests_create_zero_persisted_tickets(db_session):
    user = _user(db_session, "guarded-ticket-owner")

    def selector(_):
        return {"tool_name": "ticket_creator", "tool_input": "WiFi issue"}

    def creator(description, *, execution_context):
        ticket = create_ticket_for_requester(
            db_session,
            requester_user_id=execution_context.user_id,
            description=description,
            action_id=execution_context.request_id,
        )
        return {
            "ticket_id": ticket.public_id,
            "status": ticket.status,
            "description": ticket.description,
        }

    guarded_messages = [
        "Don't create a ticket for my WiFi.",
        "Please do not report this to IT.",
        "Should I create a ticket for this?",
        "Can you tell me how to create a ticket?",
        "My WiFi is broken. What should I do?",
        "I need support with my WiFi.",
    ]

    from app.tools.execution_context import ToolExecutionContext

    for index, message in enumerate(guarded_messages):
        route_tool(
            message,
            execution_context=ToolExecutionContext(
                user_id=user.id,
                request_id=f"guarded-{index}",
            ),
            tool_selector=selector,
            ticket_creator=creator,
        )

    assert db_session.query(Ticket).count() == 0

def test_ticket_capability_failure_creates_no_row_or_fake_success(db_session):
    from app.mcp.client import TicketCapabilityError
    from app.tools.execution_context import ToolExecutionContext

    user = _user(db_session, "failed-ticket-owner")

    def selector(_):
        return {"tool_name": "ticket_creator", "tool_input": "VPN outage"}

    def failing_creator(description, *, execution_context):
        raise TicketCapabilityError("controlled MCP failure")

    def routed(message, **kwargs):
        return route_tool(
            message,
            execution_context=kwargs.get("execution_context"),
            tool_selector=selector,
            ticket_creator=failing_creator,
        )

    agent = build_enterprise_agent(
        AgentDependencies(
            get_recent_messages=lambda **_: [],
            get_summary=lambda **_: "",
            build_history_context=AgentDependencies().build_history_context,
            route_tool=routed,
            retrieve_context=lambda _: {"context": "", "sources": []},
            get_llm_provider=lambda: AnswerProvider(),
            add_exchange=lambda **_: None,
            maybe_summarize_conversation=lambda **_: None,
        )
    )

    result = generate_response(
        message="Create a ticket for my VPN outage.",
        conversation_id="failed-ticket",
        user_id=user.id,
        session=db_session,
        dependencies=ChatServiceDependencies(enterprise_agent=agent),
    )

    assert "could not be created" in result["response"]
    assert "created successfully" not in result["response"]
    assert db_session.query(Ticket).count() == 0

def test_streaming_ticket_capability_failure_creates_no_row_or_fake_success(db_session):
    from app.mcp.client import TicketCapabilityError

    user = _user(db_session, "failed-stream-ticket-owner")

    def selector(_):
        return {"tool_name": "ticket_creator", "tool_input": "WiFi outage"}

    def failing_creator(description, *, execution_context):
        raise TicketCapabilityError("controlled MCP failure")

    def routed(message, **kwargs):
        return route_tool(
            message,
            execution_context=kwargs.get("execution_context"),
            tool_selector=selector,
            ticket_creator=failing_creator,
        )

    response = "".join(
        stream_response(
            message="Create a ticket for my WiFi outage.",
            conversation_id="failed-stream-ticket",
            user_id=user.id,
            session=db_session,
            dependencies=ChatServiceDependencies(
                get_llm_provider=lambda: AnswerProvider(),
                get_recent_messages=lambda **_: [],
                get_summary=lambda **_: "",
                route_tool=routed,
                retrieve_context=lambda _: {"context": "", "sources": []},
                add_exchange=lambda **_: None,
                maybe_summarize_conversation=lambda **_: None,
            ),
        )
    )

    assert "could not be created" in response
    assert "created successfully" not in response
    assert db_session.query(Ticket).count() == 0


class FailingAnswerProvider(BaseLLMProvider):
    def generate(self, message: str, history=None) -> str:
        raise LLMProviderError("all controlled providers failed")

    def stream(self, message: str, history=None):
        raise LLMProviderError("all controlled providers failed")
        yield  # pragma: no cover - keeps this a generator for the interface


def test_non_streaming_committed_ticket_survives_answer_provider_failure(db_session):
    user = _user(db_session, "partial-success-owner")
    routed = _route_with_persistence(db_session)
    persisted = []

    agent = build_enterprise_agent(
        AgentDependencies(
            get_recent_messages=lambda **_: [],
            get_summary=lambda **_: "",
            build_history_context=AgentDependencies().build_history_context,
            route_tool=routed,
            retrieve_context=lambda _: {"context": "", "sources": []},
            get_llm_provider=lambda: FailingAnswerProvider(),
            add_exchange=lambda **kwargs: persisted.append(kwargs),
            maybe_summarize_conversation=lambda **_: None,
        )
    )

    result = generate_response(
        message="Create a ticket for my broken VPN.",
        conversation_id="partial-success-nonstream",
        user_id=user.id,
        session=db_session,
        dependencies=ChatServiceDependencies(enterprise_agent=agent),
    )

    ticket = db_session.query(Ticket).one()
    assert result["tool_used"] == "ticket_creator"
    assert ticket.public_id in result["response"]
    assert "created successfully and is persisted" in result["response"]
    assert len(persisted) == 1
    assert persisted[0]["assistant_message"] == result["response"]
    assert db_session.query(Ticket).count() == 1


def test_streaming_committed_ticket_survives_answer_provider_failure(db_session):
    user = _user(db_session, "partial-success-stream-owner")
    routed = _route_with_persistence(db_session)
    persisted = []

    response = "".join(
        stream_response(
            message="Create a ticket for my broken VPN.",
            conversation_id="partial-success-stream",
            user_id=user.id,
            session=db_session,
            dependencies=ChatServiceDependencies(
                get_llm_provider=lambda: FailingAnswerProvider(),
                get_recent_messages=lambda **_: [],
                get_summary=lambda **_: "",
                route_tool=routed,
                retrieve_context=lambda _: {"context": "", "sources": []},
                add_exchange=lambda **kwargs: persisted.append(kwargs),
                maybe_summarize_conversation=lambda **_: None,
            ),
        )
    )

    ticket = db_session.query(Ticket).one()
    assert ticket.public_id in response
    assert "created successfully and is persisted" in response
    assert len(persisted) == 1
    assert persisted[0]["assistant_message"] == response
    assert db_session.query(Ticket).count() == 1


class PartiallyFailingAnswerProvider(BaseLLMProvider):
    def generate(self, message: str, history=None) -> str:
        raise AssertionError("Non-streaming generation is not used in this test")

    def stream(self, message: str, history=None):
        yield "Partial provider wording"
        raise LLMProviderError("provider failed after streaming started")


def test_streaming_committed_ticket_appends_fallback_after_partial_provider_output(
    db_session,
):
    user = _user(db_session, "partial-output-ticket-owner")
    routed = _route_with_persistence(db_session)
    persisted = []

    response = "".join(
        stream_response(
            message="Create a ticket for my broken VPN.",
            conversation_id="partial-output-ticket",
            user_id=user.id,
            session=db_session,
            dependencies=ChatServiceDependencies(
                get_llm_provider=lambda: PartiallyFailingAnswerProvider(),
                get_recent_messages=lambda **_: [],
                get_summary=lambda **_: "",
                route_tool=routed,
                retrieve_context=lambda _: {"context": "", "sources": []},
                add_exchange=lambda **kwargs: persisted.append(kwargs),
                maybe_summarize_conversation=lambda **_: None,
            ),
        )
    )

    ticket = db_session.query(Ticket).one()
    assert response.startswith("Partial provider wording\n\n")
    assert ticket.public_id in response
    assert "created successfully and is persisted" in response
    assert len(persisted) == 1
    assert persisted[0]["assistant_message"] == response
    assert db_session.query(Ticket).count() == 1
