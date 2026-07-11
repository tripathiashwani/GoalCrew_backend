# app/modules/notifications/receivers.py
from __future__ import annotations

from typing import List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pod_members import PodMember
from app.modules.events.schemas import DomainEvent


async def resolve_self(db: AsyncSession, event: DomainEvent) -> List[UUID]:
    # Receiver must be provided in context
    receiver_id = event.context.get("receiver_id")
    return [receiver_id] if receiver_id else []


async def resolve_reflection_owner(db: AsyncSession, event: DomainEvent) -> List[UUID]:
    # reflection_owner_id must be provided in context
    owner_id = event.context.get("reflection_owner_id")
    if not owner_id:
        return []
    # Don’t notify actor about their own action
    if event.actor_id and owner_id == event.actor_id:
        return []
    return [owner_id]


async def resolve_pod_members_except_actor(db: AsyncSession, event: DomainEvent) -> List[UUID]:
    pod_id = event.pod_id
    if not pod_id:
        return []

    stmt = select(PodMember.user_id).where(
        PodMember.pod_id == pod_id,
        PodMember.is_active.is_(True),
    )
    rows = (await db.execute(stmt)).scalars().all()

    actor_id = event.actor_id
    if actor_id:
        return [uid for uid in rows if uid != actor_id]
    return list(rows)
