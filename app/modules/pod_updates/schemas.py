# app/modules/pod_updates/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, datetime


SortBy = Literal["reflection_date", "created_at"]
SortOrder = Literal["asc", "desc"]


class PodUpdateUser(BaseModel):
    id: UUID
    username: Optional[str] = None
    profile_photo_url :Optional[str] =None

class ReflectionAttachmentResponse(BaseModel):
    id: UUID
    file_url: str
    file_type: Literal["image", "gif"]
    uploaded_at: datetime

class Comment(BaseModel):
    id: UUID
    content: str
    commented_by:str
    commented_at:datetime
    profile_photo_url :Optional[str] =None

class GoalItem(BaseModel):
    id: UUID
    title: str
    category: Optional[str] = None
    description: Optional[str] = None
    success_definition: Optional[str] = None
    current_streak: int = 0
    checked_yes: bool = False
    frequency_type: Optional[str] = None
    frequency_value:Optional[int] = None
    days_achieved_this_week: Optional[int] = None
    requiresMeasurement: Optional[bool] = None
    measurementTarget: Optional[float] = None
    measurementUnit:Optional[str] = None



class PodUpdateItem(BaseModel):
    id: UUID
    pod_id: UUID
    user: PodUpdateUser

    reflection_date: date
    content: Optional[str] = None
    mood: Optional[str] = None

    # goals_total: int = 0
    # goals_yes: int = 0
    # goals_no: int = 0
    
    # goals_yes_title_list: Optional[List[str]] = None
    # goals_no_title_list: Optional[List[str]] = None
    goals: List[GoalItem] = Field(default_factory=list)
    has_attachment : bool = False
    attachments: Optional[ReflectionAttachmentResponse]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    comments:Optional[List[Comment]] = Field(default_factory=list)
    


    


class PodUpdatesResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[PodUpdateItem] = Field(default_factory=list)


class PodUpdatesQuery(BaseModel):
    # this is optional if you want to validate query params centrally
    page: int = 1
    page_size: int = 10
    sort_by: SortBy = "reflection_date"
    sort_order: SortOrder = "desc"

    # filters
    user_id: Optional[UUID] = None
    mood: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    q: Optional[str] = None  # search in content

class PodUpdateGoalDetail(BaseModel):
    id: UUID
    title: str
    category: Optional[str] = None
    description: Optional[str] = None
    success_definition: Optional[str] = None
    current_streak: int = 0
    checked_yes: bool = False
    frequency_type: Optional[str] = None
    frequency_value: Optional[int] = None
    requiresMeasurement: Optional[bool] = None
    measurementTarget: Optional[float] = None
    measurementUnit:Optional[str] = None
    days_achieved_this_week: Optional[int] = None


class PodUpdateDetailResponse(BaseModel):
    id: UUID
    pod_id: UUID
    user: PodUpdateUser

    reflection_date: date
    content: Optional[str] = None
    mood: Optional[str] = None

    goals: List[PodUpdateGoalDetail] = Field(default_factory=list)
    attachments: List[ReflectionAttachmentResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
