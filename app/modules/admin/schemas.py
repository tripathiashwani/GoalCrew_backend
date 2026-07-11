from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class AdminUserOut(BaseModel):
    id: UUID
    email: str
    username: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    joinedAt: datetime
    lastActive: Optional[datetime] = None
    podsCount: int
    checkInsCount: int
    streak: int
    status: str  # 'active' | 'inactive' | 'suspended'

    class Config:
        from_attributes = True




from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from uuid import UUID

class AdminPodMemberOut(BaseModel):
    id: UUID
    username: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[str] = None

class AdminPodOut(BaseModel):
    id: UUID
    name: str
    icon: Optional[str] = None
    joinCode: str
    createdAt: datetime
    members: List[AdminPodMemberOut]

class AdminCommentOut(BaseModel):
    id: UUID
    podId: UUID
    checkInId: UUID
    userId: UUID
    username: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    text: str
    gif: Optional[str] = None
    createdAt: datetime




class AdminActivityOut(BaseModel):
    id: UUID
    userId: Optional[UUID] = None
    username: Optional[str] = None
    related_id:Optional[UUID] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    action: str
    details: Optional[str] = None
    timestamp: datetime
    type: str


class AdminActivityResponse(BaseModel):
    activity_logs: List[AdminActivityOut]
    total_reflections: int

class AdminGoalOut(BaseModel):
    id: UUID
    title: str
    category: Optional[str]
    description: Optional[str]
    frequency_type: Optional[str]
    frequency_value: Optional[int]
    created_by_id: UUID
    created_by_username: str
    created_by_name: str
    max_streak: int

    class Config:
        from_attributes = True


from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import Optional


class AdminCheckinOut(BaseModel):
    id: UUID
    pod_id: UUID
    user_id: UUID
    username: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    reflection_date: date
    content: Optional[str] = None
    mood: Optional[str] = None
    created_at: Optional[datetime] = None






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
    frequency_type: Optional[str]
    frequency_value: Optional[int]
    category: Optional[str]
    description: Optional[str]
    measurement_unit:Optional[str]
    measurement_target:Optional[int]
    requires_measurement: Optional[bool] = None
    days_achieved_this_week:Optional[int]
    current_streak: Optional[int] = 0


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
    total: int
    items: list[ReflectionCommentResponse]
    reflectionresponse:ReflectionResponse





class HeatmapDay(BaseModel):
    date: date
    count: int
    level: int  # 0–4

class GoalDetailResponse(BaseModel):
    id: UUID
    title: str
    category: Optional[str]

    requires_measurement: bool = False
    # Measurement 
    description: Optional[str] = None
    measurement_unit: Optional[str] = None
    measurement_target: Optional[float] = None

    why_it_matters: Optional[str]
    success_definition: Optional[str]
    frequency_type: str
    frequency_value: int
    start_date: Optional[date]
    end_date: Optional[date]
    status: str
    is_active: bool
    created_by: UUID
    my_role: Optional[str]
    current_streak: int
    longest_streak: int
    days_achieved_last_7: int
    times_completed_this_month: int
    days: list[HeatmapDay]