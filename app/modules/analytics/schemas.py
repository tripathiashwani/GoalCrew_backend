from pydantic import BaseModel


class WeeklySummaryResponse(BaseModel):
    total_goals: int
    completed_goals: int
