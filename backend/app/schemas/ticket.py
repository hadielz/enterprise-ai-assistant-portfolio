"""Pydantic schemas for the bounded persisted ticket API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


TicketStatus = Literal["created", "in_progress", "resolved"]


class TicketResponse(BaseModel):
    ticket_id: str
    requester_username: str
    description: str
    status: TicketStatus
    created_at: datetime
    updated_at: datetime


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus
