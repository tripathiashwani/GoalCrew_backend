# schemas/reflection_reactions.py

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Dict, List


class ReflectionReactionCreate(BaseModel):
    reaction: str = Field(..., min_length=1, max_length=10)


class ReflectionReactionUser(BaseModel):
    id: UUID
    username: str


class ReflectionReactionResponse(BaseModel):
    id: UUID
    reaction: str
    user: ReflectionReactionUser
    created_at: datetime


class ReflectionReactionSummary(BaseModel):
    counts: Dict[str, int]          # {"🔥": 3, "❤️": 5}
    my_reaction: str | None           # "❤️"

class ReactionRemovePayload(BaseModel):
    reaction: str
