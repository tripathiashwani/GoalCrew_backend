# app/modules/reflections/service.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import PodMember  # adjust import
from app.db.models.goal_progress_events import GoalProgressEvent
from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_goals import PodGoal 
from app.db.models.pod_goal_participants import PodGoalParticipant
from app.db.models.reflections import Reflection
from app.db.models.reflection_goals import ReflectionGoal
from app.db.models.user import User  # adjust import
from app.utils.file_upload import save_reflection_attachment
from app.config import config
from app.db.models.reflection_attachments import ReflectionAttachment

from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType

from app.utils.logger import get_logger
exception_logger=get_logger("Exceptions_logs")



async def _ensure_active_member(db: AsyncSession, pod_id: UUID, user_id: UUID) -> None:
    stmt = select(PodMember.id).where(
        PodMember.pod_id == pod_id,
        PodMember.user_id == user_id,
        PodMember.is_active.is_(True),
    )
    exists = (await db.execute(stmt)).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=403, detail="Not an active member of this pod")


from app.db.models.reflection_attachments import ReflectionAttachment

async def _load_reflection_with_goals(db: AsyncSession, reflection_id: UUID) -> Reflection:
    try:
        stmt = (
            select(Reflection)
            .where(Reflection.id == reflection_id)
            .options(
                selectinload(Reflection.goals).selectinload(ReflectionGoal.goal),
                selectinload(Reflection.attachments),  # ✅ ADD THIS
            )
        )

        ref = (await db.execute(stmt)).scalar_one_or_none()
        if not ref:
            raise HTTPException(status_code=404, detail="Reflection not found")
        return ref
    
    except Exception as e:
        exception_logger.exception(f"Error while load_reflection with goals {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

def _to_response(ref: Reflection):
    return {
        "id": ref.id,
        "pod_id": ref.pod_id,
        "user_id": ref.user_id,
        "reflection_date": ref.reflection_date,
        "content": ref.content,
        "mood": ref.mood,
        "created_at": ref.created_at,
        "updated_at": ref.updated_at,

        "goals": [
            {
                "goal_id": rg.goal_id,
                "goal_title": getattr(rg.goal, "title", None) if rg.goal else None,
                "completed": bool(rg.completed),
                "progress_value": rg.weekly_progress_value,
            }
            for rg in (ref.goals or [])
        ],

        # ✅ ADD THIS BLOCK
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file_url,
                "file_type": att.file_type,
                "uploaded_at": att.uploaded_at,
            }
            for att in (ref.attachments or [])
        ],
    }


async def add_reflection(
    db: AsyncSession,
    pod_id: UUID,
    user: User,
    reflection_date: date,
    content: Optional[str],
    mood: Optional[str],
    goals_payload: list[dict],
):
    try:

        await _ensure_active_member(db, pod_id, user.id)

        # 1️⃣ ALWAYS create a new reflection (immutable)
        reflection = Reflection(
            pod_id=pod_id,
            user_id=user.id,
            reflection_date=reflection_date,
            content=content,
            mood=mood,
        )
        db.add(reflection)
        await db.flush()  # get reflection.id

        # 2️⃣ Validate goals belong to this pod
        goal_ids = [g["goal_id"] for g in goals_payload]
        goals_map = {}

        if goal_ids:
            rows = (
                await db.execute(
                    select(PodGoal).where(
                        PodGoal.pod_id == pod_id,
                        PodGoal.id.in_(goal_ids),
                        PodGoal.status == "active",
                    )
                )
            ).scalars().all()

            goals_map = {g.id: g for g in rows}

            missing = [str(gid) for gid in goal_ids if gid not in goals_map]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Some goals do not belong to this pod or are inactive: {missing}",
                )

        # 3️⃣ Insert ReflectionGoal + upsert GoalProgressEvent + update streak
        for g in goals_payload:
            goal_id = g["goal_id"]
            completed = bool(g.get("completed", False))
            progress_value = g.get("days_achieved_this_week")
            goal = goals_map.get(goal_id)

            stmt = select(GoalProgressEvent).where(
                GoalProgressEvent.goal_id == goal_id,
                GoalProgressEvent.user_id == user.id,
                GoalProgressEvent.progress_date == reflection_date,
            )
            event = (await db.execute(stmt)).scalar_one_or_none()

            # 🛑 CASE 4: already completed today → skip everything
            if event and event.completed is True:
                continue

            if completed:
                progress_value=progress_value+1


            # ✅ ALWAYS snapshot what this reflection says
            db.add(
                ReflectionGoal(
                    reflection_id=reflection.id,
                    goal_id=goal_id,
                    completed=completed,
                    weekly_progress_value=progress_value,
                )
            )

            if event:
                # CASE 2 / 3
                event.completed = completed
                event.progress_value = progress_value
                event.reflection_id = reflection.id
            else:
                # CASE 1
                db.add(
                    GoalProgressEvent(
                        pod_id=pod_id,
                        goal_id=goal_id,
                        user_id=user.id,
                        reflection_id=reflection.id,
                        progress_date=reflection_date,
                        frequency_type=goal.frequency_type if goal else None,
                        completed=completed,
                        progress_value=progress_value,
                    )
                )

            # Update streak ONLY when we actually processed something
            await update_goal_streak(
                db=db,
                goal_id=goal_id,
                user_id=user.id,
                progress_date=reflection_date,
                completed=completed,
                frequency_type=goal.frequency_type if goal else "daily"
            )
        


        await db.commit()


        await dispatcher.emit(
                DomainEvent(
                    type=NotificationType.CHECK_IN,
                    actor_id=user.id,
                    pod_id=pod_id,
                    entity_type="reflection",
                    entity_id=reflection.id,
                    context={
                        "reflection_owner_id": reflection.user_id,
                        "actor_name": user.name or "Someone",
                        "details":f" Checked in {len(goals_payload)} goal",
                        "target_ids":[reflection.id]
                    },
                )
            )

        reflection = await _load_reflection_with_goals(db, reflection.id)
        return _to_response(reflection)
    
    except Exception as e:
        exception_logger.exception(f"Error while add_reflection {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def list_my_reflections(
    db: AsyncSession,
    pod_id: UUID,
    user: User,
    start: Optional[date] = None,
    end: Optional[date] = None,
):
    
    try:
            
        await _ensure_active_member(db, pod_id, user.id)

        conditions = [
            Reflection.pod_id == pod_id,
            Reflection.user_id == user.id,
        ]
        if start:
            conditions.append(Reflection.reflection_date >= start)
        if end:
            conditions.append(Reflection.reflection_date <= end)

        stmt = (
            select(Reflection)
            .where(and_(*conditions))
            .order_by(Reflection.reflection_date.desc())
            .options(selectinload(Reflection.goals).selectinload(ReflectionGoal.goal))
        )

        refs = (await db.execute(stmt)).scalars().all()
        return {"items": [_to_response(r) for r in refs]}
    
    except Exception as e:
        exception_logger.exception(f"Error while list_my_reflection {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def get_reflection_by_id(db: AsyncSession, pod_id: UUID, user: User, reflection_id: UUID):
    try:
        await _ensure_active_member(db, pod_id, user.id)

        ref = await _load_reflection_with_goals(db, reflection_id)
        if ref.pod_id != pod_id or ref.user_id != user.id:
            raise HTTPException(status_code=404, detail="Reflection not found")
        return _to_response(ref)
    
    except Exception as e:
        exception_logger.exception(f"Error while get_reflection_by_id {str(e)} having reflection_id:{reflection_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def get_reflection_by_date(db: AsyncSession, pod_id: UUID, user: User, reflection_date: date):
    try:
        await _ensure_active_member(db, pod_id, user.id)

        stmt = (
            select(Reflection)
            .where(
                Reflection.pod_id == pod_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date == reflection_date,
            )
            .options(selectinload(Reflection.goals).selectinload(ReflectionGoal.goal))
        )
        ref = (await db.execute(stmt)).scalar_one_or_none()
        if not ref:
            raise HTTPException(status_code=404, detail="Reflection not found")
        return _to_response(ref)
    
    except Exception as e:
        exception_logger.exception(f"Error while get_reflectionby_date {str(e)} with user:{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def delete_reflection(db: AsyncSession, pod_id: UUID, user: User, reflection_id: UUID):
    await _ensure_active_member(db, pod_id, user.id)

    stmt = select(Reflection).where(
        Reflection.id == reflection_id,
        Reflection.pod_id == pod_id,
        Reflection.user_id == user.id,
    )
    ref = (await db.execute(stmt)).scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Reflection not found")

    await db.delete(ref)
    await db.commit()
    return {"success": True}

def iso_week(d: date) -> tuple[int, int]:
    return d.isocalendar().year, d.isocalendar().week

async def update_goal_streak(
    db: AsyncSession,
    goal_id: UUID,
    user_id: UUID,
    progress_date: date,
    completed: bool,
    frequency_type: str,  # daily | weekly
):
    try:
            
        streak = await db.scalar(
            select(GoalStreak).where(
                GoalStreak.goal_id == goal_id,
                GoalStreak.user_id == user_id,
            )
        )

        if not streak:
            streak = GoalStreak(
                goal_id=goal_id,
                user_id=user_id,
                current_streak=0,
                longest_streak=0,
            )
            db.add(streak)
            await db.flush()

        # ---------------------------
        # DAILY GOALS
        # ---------------------------
        if frequency_type == "daily":
            # already processed today
            if streak.last_completed_date == progress_date:
                return

            if completed:
                if streak.last_completed_date == progress_date - timedelta(days=1):
                    streak.current_streak += 1
                else:
                    streak.current_streak = 1

                streak.longest_streak = max(
                    streak.longest_streak,
                    streak.current_streak,
                )
                streak.last_completed_date = progress_date

            else:
                if streak.last_completed_date == progress_date - timedelta(days=1):
                    streak.current_streak = 0

            return

        # ---------------------------
        # WEEKLY GOALS
        # ---------------------------
        if frequency_type == "weekly":
            current_year, current_week = iso_week(progress_date)

            if streak.last_completed_date:
                last_year, last_week = iso_week(streak.last_completed_date)

                # ❌ already completed this week → ignore
                if (current_year, current_week) == (last_year, last_week):
                    return

            if completed:
                if streak.last_completed_date:
                    last_year, last_week = iso_week(streak.last_completed_date)

                    # consecutive week
                    if (
                        current_year == last_year
                        and current_week == last_week + 1
                    ):
                        streak.current_streak += 1
                    else:
                        streak.current_streak = 1
                else:
                    streak.current_streak = 1

                streak.longest_streak = max(
                    streak.longest_streak,
                    streak.current_streak,
                )
                streak.last_completed_date = progress_date
    except Exception as e:
        exception_logger.exception(f"Error while update_goal_Streak {str(e)} with user id:{user_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def add_reflection_attachment(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    user: User,
    file,
):
    try:

        await _ensure_active_member(db, pod_id, user.id)

        reflection = await db.scalar(
            select(Reflection).where(
                Reflection.id == reflection_id,
                Reflection.pod_id == pod_id,
                Reflection.user_id == user.id,
            )
        )

        if not reflection:
            raise HTTPException(status_code=404, detail="Reflection not found")

        file_url, file_type = save_reflection_attachment(
            pod_id=str(pod_id),
            file=file,
            upload_root=config.UPLOAD_DIR,
        )

        db.add(
            ReflectionAttachment(
                reflection_id=reflection.id,
                file_url=file_url,
                file_type=file_type,
            )
        )

        await db.commit()

        reflection = await _load_reflection_with_goals(db, reflection.id)
        return _to_response(reflection)
    
    except Exception as e:
        exception_logger.exception(f"Error while add_reflection_attachment {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )
