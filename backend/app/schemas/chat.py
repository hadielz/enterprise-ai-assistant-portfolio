"""
Data models for the chat API.
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Chat request submitted by the frontend.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="User message sent to the assistant",
    )

    conversation_id: str = Field(
        "default",
        min_length=1,
        max_length=100,
        description="Public conversation identifier",
    )


class ChatResponse(BaseModel):
    """
    Response returned by the non-streaming chat endpoint.
    """

    response: str
    used_rag: bool = False
    sources: list[str] = Field(default_factory=list)
    conversation_id: str = "default"
    tool_used: str | None = None
    agent_steps: list[str] = Field(default_factory=list)