from pydantic import BaseModel
from typing import Literal, Optional, List
from uuid import UUID
from datetime import date


# ---------- Requests ----------

class GoalCreateRequest(BaseModel):
    title: str
    category: Optional[str] = None

    # Quantatitive OR Qualitative
    requires_measurement: bool = False

    # Measurement 
    # Only required if requires_measurement = True
    description: Optional[str] = None               # measurement_label
    measurement_unit:  Optional[str] = None           # "minutes", "ounces"
    measurement_target: Optional[float] = None        # 30, 64, etc

    why_it_matters: Optional[str] = None

    # Frequency (unchanged for now)
    frequency_type: str
    frequency_value: int

    start_date: Optional[date] = None
    end_date: Optional[date] = None


class GoalUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None

    requires_measurement: Optional[bool] = None
    # Measurement
    description: Optional[str] = None
    measurement_unit: Optional[str] = None
    measurement_target: Optional[float] = None

    why_it_matters: Optional[str] = None

    frequency_type: Optional[str] = None
    frequency_value: Optional[int] = None

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None

class GoalBatchCreateRequest(BaseModel):
    goals: list[GoalCreateRequest]

# ---------- Responses ----------

class GoalListItem(BaseModel):
    id: UUID
    title: str
    category: Optional[str]

    requires_measurement: bool = False
    # Measurement 
    description: Optional[str] = None
    measurement_unit: Optional[str] = None
    measurement_target: Optional[float] = None

    frequency_type: str
    frequency_value: int
    days_achieved_this_week: int
    participant_count: int
    my_joined: bool
    is_active: bool
    current_streak: int
    today_status: Optional[Literal["yes", "no"]]


class UserGoalListResponse(BaseModel):
    user_id: UUID
    goals: list[GoalListItem]


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


class GoalParticipantResponse(BaseModel):
    user_id: UUID
    name: str
    joined_at: date
    current_streak: int


class GoalProgressEventResponse(BaseModel):
    date: date
    completed: bool
    progress_value: Optional[float]


class MyGoalProgressResponse(BaseModel):
    goal_id: UUID
    frequency_type: str
    events: List[GoalProgressEventResponse]

