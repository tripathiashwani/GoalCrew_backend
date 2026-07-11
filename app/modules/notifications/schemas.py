# app/modules/notifications/schemas.py
from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: Optional[str]
    pod_id : Optional[UUID]
    actor_id: Optional[UUID]
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    page: int
    page_size: int
    total: int


class UnreadCountResponse(BaseModel):
    unread_count: int
