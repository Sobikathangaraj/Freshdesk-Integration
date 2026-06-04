# Pydantic models for request/response validation

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CreateTicketRequest(BaseModel):
    subject: str
    description: str
    email: str
    priority: int = 1       # 1=Low, 2=Medium, 3=High, 4=Urgent
    status: int = 2         # 2=Open, 3=Pending, 4=Resolved, 5=Closed
    name: Optional[str] = None
    tags: Optional[List[str]] = []


class UpdateTicketRequest(BaseModel):
    subject: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[int] = None
    tags: Optional[List[str]] = None


class ReplyRequest(BaseModel):
    ticket_id: int
    body: str                        # HTML or plain text reply body
    from_email: Optional[str] = None


class FreshdeskWebhookPayload(BaseModel):
    freshdesk_webhook: Optional[dict] = None