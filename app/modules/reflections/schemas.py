from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


# ---------- Requests ----------

class ReflectionGoalInput(BaseModel):
    goal_id: UUID
    completed: bool = False
    progress_value: Optional[float] = None
    days_achieved_this_week:Optional[int] = None


class ReflectionUpsertRequest(BaseModel):
    reflection_date: date
    content: Optional[str] = None
    mood: Optional[str] = None
    goals: List[ReflectionGoalInput] = Field(default_factory=list)


# ---------- Attachments ----------

class ReflectionAttachmentResponse(BaseModel):
    id: UUID
    file_url: str
    file_type: str  # image | gif
    uploaded_at: datetime


# ---------- Responses ----------

class ReflectionGoalResponse(BaseModel):
    goal_id: UUID
    goal_title: Optional[str] = None
    completed: bool
    progress_value: Optional[float] = None


class ReflectionResponse(BaseModel):
    id: UUID
    pod_id: UUID
    user_id: UUID
    reflection_date: date

    content: Optional[str] = None
    mood: Optional[str] = None

    goals: List[ReflectionGoalResponse] = Field(default_factory=list)
    attachments: List[ReflectionAttachmentResponse] = Field(default_factory=list)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReflectionListResponse(BaseModel):
    items: List[ReflectionResponse]
