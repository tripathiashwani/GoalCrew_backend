# app/cli/run_checkin_reminders.py
import asyncio
from datetime import datetime, timezone
from app.db.session import async_session
from app.modules.notifications.service import NotificationService
from app.modules.reminders.service import run_checkin_reminders

from app.utils.logger import get_logger
from app.modules.events.dispatcher import dispatcher

logger = get_logger("checkin-reminder-cli")

async def main():
    logger.info("⏰ Starting check-in reminder job")

    async with async_session() as db:
        # 🔑 REGISTER HANDLER
        notification_service = NotificationService(db)
        dispatcher.register(notification_service.handle_event)

        await run_checkin_reminders(db, datetime.now(timezone.utc))


    logger.info("✅ Check-in reminder job finished")

if __name__ == "__main__":
    asyncio.run(main())
