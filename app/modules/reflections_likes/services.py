# app/modules/reflections_likes/services.py

from sqlalchemy import select, func
from fastapi import HTTPException
from uuid import UUID

from app.db.models.reflection_reactions import ReflectionReaction
from app.db.models.reflections import Reflection
from app.modules.pod_updates.service import _ensure_active_member

from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType

async def _reaction_summary(db, reflection_id, user_id):
    counts_stmt = (
        select(
            ReflectionReaction.reaction,
            func.count(ReflectionReaction.id),
        )
        .where(ReflectionReaction.reflection_id == reflection_id)
        .group_by(ReflectionReaction.reaction)
    )

    counts = dict((await db.execute(counts_stmt)).all())

    my_stmt = select(ReflectionReaction.reaction).where(
        ReflectionReaction.reflection_id == reflection_id,
        ReflectionReaction.user_id == user_id,
    )

    my_reaction = (await db.execute(my_stmt)).scalar_one_or_none()

    return {
        "counts": counts,
        "my_reaction": my_reaction,
    }


async def list_reactions(
    db,
    pod_id: UUID,
    reflection_id: UUID,
    user,
):
    await _ensure_active_member(db, pod_id, user.id)

    reflection = await db.get(Reflection, reflection_id)
    if not reflection or reflection.pod_id != pod_id:
        raise HTTPException(status_code=404, detail="Reflection not found")

    return await _reaction_summary(db, reflection_id, user.id)

async def toggle_reaction(
    db,
    pod_id,
    reflection_id,
    user,
    reaction: str,
):
    await _ensure_active_member(db, pod_id, user.id)

    reflection = await db.get(Reflection, reflection_id)
    if not reflection or reflection.pod_id != pod_id:
        raise HTTPException(status_code=404, detail="Reflection not found")

    stmt = select(ReflectionReaction).where(
        ReflectionReaction.reflection_id == reflection_id,
        ReflectionReaction.user_id == user.id,
    )

    existing = (await db.execute(stmt)).scalar_one_or_none()
    emit_event = False  

    if existing:
        if existing.reaction == reaction:
            # 🔁 Same reaction → REMOVE
            await db.delete(existing)
        else:
            # 🔄 Different reaction → REPLACE
            existing.reaction = reaction
            emit_event = True
    else:
        # ➕ First reaction
        db.add(
            ReflectionReaction(
                reflection_id=reflection_id,
                user_id=user.id,
                reaction=reaction,
            )
        )
        emit_event = True

    await db.commit()
    # Emit event AFTER commit
    if emit_event:
        await dispatcher.emit(
            DomainEvent(
                type=NotificationType.REFLECTION_REACTION,
                actor_id=user.id,
                pod_id= pod_id,
                entity_type="reflection",
                entity_id=reflection.id,
                context={
                    "reflection_owner_id": reflection.user_id,
                    "actor_name": user.name or "Someone",
                },
            )
        )
    return await _reaction_summary(db, reflection_id, user.id)


async def remove_reaction(
    db,
    pod_id: UUID,
    reflection_id: UUID,
    user,
    reaction: str,
):
    await _ensure_active_member(db, pod_id, user.id)

    stmt = select(ReflectionReaction).where(
        ReflectionReaction.reflection_id == reflection_id,
        ReflectionReaction.user_id == user.id,
        ReflectionReaction.reaction == reaction,
    )

    existing = (await db.execute(stmt)).scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Reaction not found")

    await db.delete(existing)
    await db.commit()

    return await _reaction_summary(db, reflection_id, user.id)
