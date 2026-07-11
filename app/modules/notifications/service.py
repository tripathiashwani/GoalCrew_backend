# app/modules/notifications/service.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession


from app.db.models.notification import Notification
from app.db.models.reflections import Reflection
from app.db.models.activity_log import ActivityLog
from app.db.models.user_preferences import UserPreference
from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType
from app.modules.notifications.receivers import resolve_pod_members_except_actor, resolve_reflection_owner, resolve_self
from app.modules.notifications.rules import NOTIFICATION_RULES , LOG_RULES
from app.utils.logger import get_logger
logger = get_logger("NotificationService")

_RECEIVER_RESOLVERS = {
    "self": resolve_self,
    "reflection_owner": resolve_reflection_owner,
    "pod_members_except_actor": resolve_pod_members_except_actor,
}



class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle_event(self, event: DomainEvent) -> None:
        logger.info(f"handle _event calle with data:{event}")


        log_rule = LOG_RULES.get(event.type)
        if log_rule:
                
            try:

                ctx: dict[str, Any] = dict(event.context or {})

                if "target_ids" not in ctx:
                    ctx["target_ids"]=[]

                if "details" not in ctx:
                    ctx["details"] = ""
                    
                self.db.add(
                            ActivityLog(
                                actor_id=event.actor_id,
                                pod_id=event.pod_id,
                                type=log_rule["type"],
                                action=log_rule["action"],
                                details=ctx["details"],
                                target_ids=ctx["target_ids"]
                            )
                        )
                logger.info(f"activity log created for action :{event.type}")
                await self.db.commit()
            
            except Exception as e:
                logger.info(f"error while saving activity log:{str(e)}")
            
        rule = NOTIFICATION_RULES.get(event.type)


        if rule:
            try:
                
                resolver = _RECEIVER_RESOLVERS[rule["receiver_strategy"]]
                receiver_ids = await resolver(self.db, event)
                if not receiver_ids:
                    return

                # -------------------------------------------------
                # 🔕 USER PREFERENCE FILTER
                # Apply to *ALL pod-scoped notifications*
                # -------------------------------------------------
                if event.pod_id is not None:
                    stmt = select(UserPreference.user_id).where(
                        UserPreference.user_id.in_(receiver_ids),
                        UserPreference.pod_updates_enabled.is_(True),
                    )

                    allowed_ids = set((await self.db.execute(stmt)).scalars().all())

                    receiver_ids = [uid for uid in receiver_ids if uid in allowed_ids]

                    if not receiver_ids:
                        return
                # -------------------------------------------------

                # Render copy via context (keep it simple for now)
                ctx: dict[str, Any] = dict(event.context or {})
                if "actor_name" not in ctx:
                    ctx["actor_name"] = "Someone"

                title = rule["title"].format(**ctx)
                body = rule["body"].format(**ctx)
                

                for user_id in receiver_ids:
                    self.db.add(
                        Notification(
                            user_id=user_id,
                            actor_id=event.actor_id,
                            pod_id=event.pod_id,
                            type=event.type,
                            title=title,
                            body=body,
                            entity_type=rule.get("entity_type") or event.entity_type,
                            entity_id=event.entity_id,
                            is_read=False,
                        )
                    )

                

                # DB write only. Push/SMS later.
                await self.db.commit()
                logger.info("notification event created")
            except Exception as e:
                logger.info(f"error while saving notification:{str(e)}")

        
        
        
        

async def list_notifications(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
):
    page_size = min(page_size, 50)
    offset = (page - 1) * page_size

    conditions = [Notification.user_id == user_id]

    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    if start_date:
        conditions.append(Notification.created_at >= start_date)

    if end_date:
        conditions.append(Notification.created_at <= end_date)

    base_stmt = select(Notification).where(and_(*conditions))

    total = await db.scalar(
        select(func.count()).select_from(base_stmt.subquery())
    )

    stmt = (
        base_stmt
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    items = (await db.execute(stmt)).scalars().all()

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def get_unread_count(
    db: AsyncSession,
    user_id: UUID,
) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )


async def mark_as_read(
    db: AsyncSession,
    user_id: UUID,
    notification_id: UUID,
):
    stmt = (
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )

    result = await db.execute(stmt)
    await db.commit()

    return result.rowcount > 0

async def mark_all_as_read(
    db: AsyncSession,
    user_id: UUID,
):
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
