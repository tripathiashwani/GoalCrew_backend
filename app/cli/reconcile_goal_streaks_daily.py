# app/cli/reconcile_goal_streaks_daily.py

import asyncio
from app.services.goal_streak_reconciliation_service_daily import (
    GoalStreakReconciliationServiceDaily,
)
from app.utils.logger import get_logger

logger = get_logger("streak-reconciliation-cli")


async def main():
    logger.info("🚀 Starting goal streak reconciliation CLI")
    service = GoalStreakReconciliationServiceDaily()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
