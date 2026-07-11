# app/modules/pod_stats/schema.py
from pydantic import BaseModel
from datetime import date
from typing import List
from pydantic import BaseModel, Field
from uuid import UUID



class PersonalStats(BaseModel):
    check_ins_pct: int
    support_pct: int
    active_goals: int
    weekly_checkins: int

class PodStats(BaseModel):
    members_checked_in: int
    total_members: int
    avg_streak: int
    pod_health_pct: int

class PodStatsResponse(BaseModel):
    personal: PersonalStats
    pod: PodStats







class ContributionDay(BaseModel):
    date: date
    count: int = Field(ge=0)


# app/modules/pod_stats/schemas.py

class HeatmapDay(BaseModel):
    date: date
    count: int
    level: int  # 0–4


class PodContributionHeatmapResponse(BaseModel):
    pod_id: UUID
    from_date: date
    to_date: date
    total_days: int
    max_count: int
    days_checkedin_last_7: int
    times_checkedin_this_month: int
    days: list[HeatmapDay]

