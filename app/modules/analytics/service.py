from app.modules.analytics.schemas import WeeklySummaryResponse


class AnalyticsService:
    async def get_weekly_summary(self, user_id: str) -> WeeklySummaryResponse:
        return WeeklySummaryResponse(total_goals=0, completed_goals=0)
