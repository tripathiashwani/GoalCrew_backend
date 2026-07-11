# app/cli/reconcile_goal_streaks_weekly.py

import asyncio
from app.services.goal_streak_reconciliation_service_weekly import (
    GoalStreakReconciliationServiceWeekly,
)
from app.utils.logger import get_logger

logger = get_logger("streak-reconciliation-cli")


async def main():
    logger.info("🚀 Starting goal streak reconciliation CLI")
    service = GoalStreakReconciliationServiceWeekly()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
