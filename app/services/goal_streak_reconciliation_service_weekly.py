# app/services/goal_streak_reconciliation_service_weekly.py

from datetime import date, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_goals import PodGoal
from app.db.models.goal_progress_events import GoalProgressEvent
from app.db.session import async_session
from app.utils.logger import get_logger

logger = get_logger("streak-reconciliation")

class GoalStreakReconciliationServiceWeekly:
    async def run(self):
        logger.info("🔥 Weekly Goal streak reconciliation started")

        async with async_session() as session:
            await self._reset_broken_weekly_streaks(session)

        logger.info("✅ Weekly Goal streak reconciliation finished")

    async def _reset_broken_weekly_streaks(self, session: AsyncSession):
        today = date.today()

        # Last fully closed Monday–Sunday week
        last_week_end = today - timedelta(days=today.weekday() + 1)
        last_week_start = last_week_end - timedelta(days=6)

        logger.info(
            "📅 Evaluating weekly streaks",
            extra={
                "week_start": str(last_week_start),
                "week_end": str(last_week_end),
            },
        )

        # Subquery: completed days per goal/user in last week
        completed_days_subq = (
            select(
                GoalProgressEvent.goal_id.label("goal_id"),
                GoalProgressEvent.user_id.label("user_id"),
                func.count(
                    func.distinct(GoalProgressEvent.progress_date)
                ).label("days_completed"),
            )
            .where(
                GoalProgressEvent.completed.is_(True),
                GoalProgressEvent.progress_date.between(
                    last_week_start, last_week_end
                ),
            )
            .group_by(
                GoalProgressEvent.goal_id,
                GoalProgressEvent.user_id,
            )
            .subquery()
        )

        stmt = (
            select(GoalStreak, PodGoal, func.coalesce(completed_days_subq.c.days_completed, 0))
            .join(PodGoal, PodGoal.id == GoalStreak.goal_id)
            .outerjoin(
                completed_days_subq,
                (completed_days_subq.c.goal_id == GoalStreak.goal_id)
                & (completed_days_subq.c.user_id == GoalStreak.user_id),
            )
            .where(
                PodGoal.frequency_type == "weekly",
                GoalStreak.current_streak > 0,
            )
        )

        result = await session.execute(stmt)
        rows = result.all()

        reset_count = 0

        for streak, goal, days_completed in rows:
            required = goal.frequency_value or 1

            if days_completed < required:
                logger.info(
                    "❌ Resetting weekly streak",
                    extra={
                        "goal_id": str(goal.id),
                        "user_id": str(streak.user_id),
                        "completed_days": days_completed,
                        "required": required,
                    },
                )

                streak.current_streak = 0
                streak.last_completed_date = None
                reset_count += 1

        if reset_count:
            await session.commit()

        logger.info(
            "🧮 Weekly streak reconciliation summary",
            extra={"reset_streaks": reset_count},
        )
