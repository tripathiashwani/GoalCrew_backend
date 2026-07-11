from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ---------- Requests ----------

class PodCreateRequest(BaseModel):
    name: str
    focus_area: str
    description: Optional[str] = None
    max_members: int = 5
    is_private: bool = True


class PodUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_members: Optional[int] = None
    is_private: Optional[bool] = None


class JoinPodRequest(BaseModel):
    invite_code: str


class UpdateMemberRoleRequest(BaseModel):
    role: str  # owner / admin / member


# ---------- Responses ----------

class PodResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    focus_area: str
    invite_code:str 
    role: str
    member_count: int
    max_members: int
    is_private: bool

class PodDetailResponse(BaseModel):
    id: UUID
    name: str
    focus_area: str
    description: Optional[str]
    invite_code: str
    max_members: int
    is_private: bool
    created_by: UUID
    my_role: str
    created_at: datetime


class PodMemberResponse(BaseModel):
    user_id: UUID
    username: str
    role: str
    joined_at: datetime
    profile_photo_url: Optional[str] = None
    is_active: bool

class ToggleMemberActiveRequest(BaseModel):
    is_active: bool

class PodMemberToggleResponse(BaseModel):
    user_id: UUID
    is_active: bool
    role: str