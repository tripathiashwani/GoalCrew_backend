# app/services/goal_streak_reconciliation_service_daily.py

from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_goals import PodGoal
from app.db.session import async_session
from app.utils.logger import get_logger

logger = get_logger("streak-reconciliation")


class GoalStreakReconciliationServiceDaily:
    async def run(self):
        logger.info("🔥 Goal streak reconciliation started")

        async with async_session() as session:
            await self._reset_broken_daily_streaks(session)

        logger.info("✅ Goal streak reconciliation finished")

    async def _reset_broken_daily_streaks(self, session: AsyncSession):
        today = date.today()
        cutoff_date = today - timedelta(days=2)

        stmt = (
            select(GoalStreak)
            .join(PodGoal, PodGoal.id == GoalStreak.goal_id)
            .where(
                PodGoal.frequency_type == "daily",
                GoalStreak.last_completed_date.is_not(None),
                GoalStreak.last_completed_date < cutoff_date,
                GoalStreak.current_streak > 0,
            )
        )

        result = await session.execute(stmt)
        streaks = result.scalars().all()

        logger.info(f"🧮 Found {len(streaks)} broken streaks")

        for streak in streaks:
            logger.info(
                f"❌ Resetting streak "
                f"goal={streak.goal_id} "
                f"user={streak.user_id} "
                f"last_completed={streak.last_completed_date}"
            )

            streak.current_streak = 0
            streak.last_completed_date = None


        if streaks:
            await session.commit()

