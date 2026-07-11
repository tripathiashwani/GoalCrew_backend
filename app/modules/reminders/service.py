# app/modules/reminders/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
from datetime import date
from sqlalchemy import select, func

from app.db.models.sms_log import SmsLog
from app.db.models.user import User
from app.db.models.user_preferences import UserPreference
from app.db.models.reflections import Reflection
from app.db.models.notification import Notification
from app.db.models.pod_members import PodMember
from app.db.models.reflection_comments import ReflectionComment
from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType
from app.modules.sms.twilio_service import TwilioSmsService
from app.utils.logger import get_logger

logger = get_logger("checkin-reminder-cli")

async def run_checkin_reminders(db: AsyncSession, now: datetime) -> None:
    """
    Send a reminder if the user has NOT added today's reflection
    by (or after) their preferred check-in time.
    """
    logger.info(f"Registered dispatcher handlers: {len(dispatcher._handlers)}")

    current_time = now.time().replace(second=0, microsecond=0)
    today = now.date()

    sms = TwilioSmsService()
    
    # ✅ join prefs + user so we can access phone_number + country_code
    rows = (
        await db.execute(
            select(UserPreference, User)
            .join(User, User.id == UserPreference.user_id)
            .where(UserPreference.checkin_time.is_not(None))
        )
    ).all()
    
    for pref , user in rows:
        logger.info(
            f"Evaluating reminder for user={pref.user_id} "
            f"time={current_time} today={today}"
            f" User Preffered time ={pref.checkin_time} Frequency ={pref.checkin_frequency}"
        )

        # 0️⃣ Goal Reminder Check
        if hasattr(pref, "reminder") and not pref.reminder:
            continue

        # 1️⃣ Too early → skip
        # if current_time < pref.checkin_time:
        #     continue

        # 2️⃣ Frequency check
        # if pref.checkin_frequency == "weekly" and now.weekday() != 0:
        #     continue
        # if pref.checkin_frequency == "monthly" and today.day != 1:
        #     continue

        # 3️⃣ Already reflected today?
        already_reflected = await db.scalar(
            select(Reflection.id).where(
                Reflection.user_id == pref.user_id,
                Reflection.reflection_date == today,
            )
        )
        if already_reflected:
            continue

        # 4️⃣ Already reminded today?
        already_reminded = await db.scalar(
            select(Notification.id).where(
                Notification.user_id == pref.user_id,
                Notification.type == NotificationType.DAILY_GOAL_REMINDER,
                func.date(Notification.created_at) == today,
            )
        )
        if already_reminded:
            continue
        logger.info(f"Emitting DAILY_GOAL_REMINDER for user={pref.user_id}")

        # 5️⃣ Emit reminder
        await dispatcher.emit(
            DomainEvent(
                type=NotificationType.DAILY_GOAL_REMINDER,
                actor_id=None,
                pod_id= None,
                entity_type="system",
                entity_id=None,
                context={"receiver_id": pref.user_id},
            )
        )

        # 6️⃣ SMS reminder 
        sms_enabled = getattr(pref, "sms_reminder", False)
        if not sms_enabled:
            continue

        # phone checks
        if not user.phone_number:
            logger.warning("📵 No phone number, skipping SMS", extra={"user_id": str(user.id)})
            continue

        # build phone (you have separate fields)
        phone = f"{user.country_code or ''}{user.phone_number}".strip()
        if not phone:
            logger.warning("📵 Invalid phone, skipping SMS", extra={"user_id": str(user.id)})
            continue

        logger.info("Skipping SMS Reminder as not setup")
        message = "Take a moment to check in. Log yesterday’s progress in Goal Crew and keep your momentum alive. https://goalcrew.com/"

        await sms.send_sms(
            db=db,
            user=user,
            message_type="daily_goal_reminder",
            body=message,
        ) 
        logger.info("SMS Checkin reminder sent")






async def run_evening_reminders(db: AsyncSession, now: datetime) -> None:
    logger.info("Running evening engagement reminders")

    today = now.date()

    rows = (
        await db.execute(
            select(UserPreference, User)
            .join(User, User.id == UserPreference.user_id)
            .where(
                UserPreference.reminder.is_(True),
            )
        )
    ).all()

    for pref, user in rows:
        user_id = user.id

        # 1️⃣ Already reminded today?
        already_reminded = await db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.type == NotificationType.DAILY_ENGAGEMENT_REMINDER,
                func.date(Notification.created_at) == today,
            )
        )
        if already_reminded:
            continue

        sms_enabled = getattr(pref, "sms_reminder", False)
        if not sms_enabled:
            continue


        # ✅ 5️⃣ Send reminder
        logger.info(f"Sending engagement reminder to user={user_id}")

        await dispatcher.emit(
            DomainEvent(
                type=NotificationType.DAILY_ENGAGEMENT_REMINDER,
                actor_id=None,
                pod_id=None,
                entity_type="system",
                entity_id=None,
                context={"receiver_id": user_id},
            )
        )

        sms_enabled = getattr(pref, "sms_reminder", False)


        if not sms_enabled:
            continue

        # phone checks
        if not user.phone_number:
            logger.warning("📵 No phone number, skipping SMS", extra={"user_id": str(user.id)})
            continue

        # build phone (you have separate fields)
        phone = f"{user.country_code or ''}{user.phone_number}".strip()
        if not phone:
            logger.warning("📵 Invalid phone, skipping SMS", extra={"user_id": str(user.id)})
            continue

        logger.info("Skipping SMS Reminder as not setup")

        # (Optional) SMS
        sms=TwilioSmsService()
        if pref.sms_reminder and user.phone_number:
            phone = f"{user.country_code or ''}{user.phone_number}".strip()
            if phone:
                logger.info("SMS reminder eligible")
                await sms.send_sms(
                    db=db,
                    user=user,
                    message_type="daily_engagement_reminder",
                    body="Make sure you engaged with your pod today, offered some advice, and supported your community.",
                )

                logger.info("SMS evening reminder sent")
