"""
Schemas for conversation-history APIs.

These models define the JSON returned when listing or reopening
persisted conversations.
"""

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """
    One stored message in a conversation.
    """

    role: str
    content: str


class ConversationSummaryItem(BaseModel):
    """
    Lightweight information displayed in the conversation list.
    """

    conversation_id: str
    preview: str = ""
    message_count: int = 0


class ConversationDetail(BaseModel):
    """
    Complete transcript for one conversation.
    """

    conversation_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    summary: str = ""