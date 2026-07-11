from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    type: str
    actor_id: Optional[UUID] = None
    pod_id: Optional[UUID] =None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    context: dict[str, Any] = Field(default_factory=dict)


class LogEvent(BaseModel):
    type: str
    actor_id: Optional[UUID] = None
    pod_id: Optional[UUID] =None
    action:str
    details: dict[str, Any] = Field(default_factory=dict)
