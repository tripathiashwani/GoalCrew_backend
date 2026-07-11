from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ReflectionCommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class ReflectionCommentCreate(ReflectionCommentBase):
    pass


class ReflectionCommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class ReflectionCommentUser(BaseModel):
    id: UUID
    username: str
    profile_photo_url :Optional[str] =None


class ReflectionCommentResponse(BaseModel):
    id: UUID
    reflection_id: UUID
    user: ReflectionCommentUser
    content: str
    created_at: datetime
    

    class Config:
        from_attributes = True

class PaginatedReflectionCommentsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ReflectionCommentResponse]
