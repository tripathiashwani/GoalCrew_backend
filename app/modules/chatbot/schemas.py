from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    pod_id: UUID | None = None


class ChatResponse(BaseModel):
    answer: str
    query_used: str | None = None