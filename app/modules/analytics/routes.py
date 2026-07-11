from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.modules.analytics.schemas import WeeklySummaryResponse
from app.modules.analytics.service import AnalyticsService

router = APIRouter()


@router.get("/weekly_summary", response_model=WeeklySummaryResponse)
async def weekly_summary(current_user=Depends(get_current_user)) -> WeeklySummaryResponse:
    return WeeklySummaryResponse(total_goals=0, completed_goals=0)
