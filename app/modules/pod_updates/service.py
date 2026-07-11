# app/modules/pod_updates/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exists, select, func, case, and_
from fastapi import HTTPException
from uuid import UUID
from datetime import date
from datetime import  timedelta


from app.db.models.pod_goals import PodGoal
from app.db.models.pod_members import PodMember
from app.db.models.reflection_attachments import ReflectionAttachment
from app.db.models.reflection_goals import ReflectionGoal
from app.db.models.goal_progress_events import GoalProgressEvent
from app.db.models.reflection_comments import ReflectionComment
from app.db.models.goal_streaks import GoalStreak
from app.db.models.user import User
from app.db.models.reflections import Reflection
from collections import defaultdict
from sqlalchemy.orm import aliased
from app.utils.logger import get_logger


logger = get_logger("pod-service")
exception_logger=get_logger("Exceptions_logs")


async def _ensure_active_member(db: AsyncSession, pod_id: UUID, user_id: UUID):
    member = await db.scalar(
        select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == user_id,
            PodMember.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a pod member")
    return member


async def list_pod_updates(
    db: AsyncSession,
    pod_id: UUID,
    user: User,
    *,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "reflection_date",   # reflection_date | created_at
    sort_order: str = "desc",          # asc | desc
    # filters
    user_id: UUID | None = None,
    mood: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
):
    try:
        await _ensure_active_member(db, pod_id, user.id)

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 50:
            page_size = 50

        # ----- Base WHERE conditions -----
        where_clauses = [Reflection.pod_id == pod_id]

        if user_id:
            where_clauses.append(Reflection.user_id == user_id)

        if mood:
            where_clauses.append(Reflection.mood == mood)

        if date_from:
            where_clauses.append(Reflection.reflection_date >= date_from)

        if date_to:
            where_clauses.append(Reflection.reflection_date <= date_to)

        if q:
            # simple content search (ILIKE)
            where_clauses.append(Reflection.content.ilike(f"%{q}%"))

        # ----- Sorting -----
        if sort_by == "reflection_date":
            if sort_order == "asc":
                order_expr = [
                    Reflection.reflection_date.asc(),
                    Reflection.created_at.asc(),
                ]
            else:
                order_expr = [
                    Reflection.reflection_date.desc(),
                    Reflection.created_at.desc(),
                ]
        else:  # sort_by == "created_at"
            order_expr = (
                [Reflection.created_at.asc()]
                if sort_order == "asc"
                else [Reflection.created_at.desc()]
            )

    
        offset = (page - 1) * page_size

        # ----- Total count -----
        total_stmt = select(func.count(Reflection.id)).where(and_(*where_clauses))
        total = (await db.execute(total_stmt)).scalar_one()


        now_date = date.today()
        effective_date = now_date - timedelta(days=1)

        start_of_week = effective_date - timedelta(days=effective_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)


        TodayProgress = aliased(GoalProgressEvent)

        

        weekly_progress_subq = (
            select(
                GoalProgressEvent.goal_id.label("goal_id"),
                func.count(
                    func.distinct(GoalProgressEvent.progress_date)
                ).label("days_achieved_this_week"),
            )
            .where(
                GoalProgressEvent.pod_id == pod_id,
                # GoalProgressEvent.user_id == user.id,
                GoalProgressEvent.completed.is_(True),
                GoalProgressEvent.progress_date.between(start_of_week, end_of_week),
            )
            .group_by(GoalProgressEvent.goal_id)
        ).subquery()


        # ----- Main query -----

        stmt = (
            select(
                Reflection,

                # user
                User.id.label("u_id"),
                User.username.label("u_username"),
                User.profile_photo_url.label("profile_photo_url"),

                # attachment (nullable)
                ReflectionAttachment.id.label("att_id"),
                ReflectionAttachment.file_url.label("att_file_url"),
                ReflectionAttachment.file_type.label("att_file_type"),
                ReflectionAttachment.uploaded_at.label("att_uploaded_at"),
            )
            .join(User, User.id == Reflection.user_id)
            .outerjoin(
                ReflectionAttachment,
                ReflectionAttachment.reflection_id == Reflection.id,
            )
            .where(and_(*where_clauses))
            .group_by(
            Reflection.id,
            User.id,
            ReflectionAttachment.id
        )

            .order_by(*order_expr, Reflection.id.desc())
            .offset(offset)
            .limit(page_size)
        )

        rows = (await db.execute(stmt)).all()
        reflection_ids = [r.id for (r, *_) in rows]

        if reflection_ids:
            goals_stmt = (
            select(
                ReflectionGoal.reflection_id,
                PodGoal.id.label("goal_id"),
                PodGoal.title,
                PodGoal.category,
                PodGoal.description,
                PodGoal.frequency_type,
                PodGoal.frequency_value,
                PodGoal.success_definition, 
                PodGoal.requires_measurement,
                PodGoal.measurement_unit,
                PodGoal.measurement_target,
                ReflectionGoal.weekly_progress_value.label("days_achieved_this_week"),
                ReflectionGoal.completed.label("checked_yes"),
                func.coalesce(GoalStreak.current_streak, 0).label("current_streak"),
            )
            .join(PodGoal, PodGoal.id == ReflectionGoal.goal_id)
            .outerjoin(
                GoalStreak,
                and_(
                    GoalStreak.goal_id == PodGoal.id,
                    GoalStreak.user_id == user.id,
                ),
            )
            .outerjoin(
                TodayProgress,
                (TodayProgress.goal_id == PodGoal.id)
                & (TodayProgress.user_id == user_id)
                & (TodayProgress.pod_id == pod_id),
            )
            .where(ReflectionGoal.reflection_id.in_(reflection_ids))
        )
            

            goal_rows = (await db.execute(goals_stmt)).all()
            

            goals_by_reflection: dict[UUID, list] = defaultdict(list)

            for (
            reflection_id,
            goal_id,
            title,
            category,
            description,
            frequency_type,
            frequency_value,
            success_definition,
            requires_measurement,
            measurement_unit, 
            measurement_target,
            days_achieved_this_week,
            checked_yes,
            current_streak,
        ) in goal_rows:
                goals_by_reflection[reflection_id].append(
                    {
                        "id": goal_id,
                        "title": title,
                        "category": category,
                        "description": description,
                        "frequency_type":frequency_type,
                        "frequency_value":frequency_value,
                        "success_definition": success_definition,
                        "requiresMeasurement":requires_measurement,
                        "measurementTarget":measurement_target,
                        "measurementUnit":measurement_unit,
                        "days_achieved_this_week":days_achieved_this_week or 0,
                        "current_streak": int(current_streak or 0),
                        "checked_yes": bool(checked_yes),
                    }
                )

        

        comment_rank = func.row_number().over(
            partition_by=ReflectionComment.reflection_id,
            order_by=ReflectionComment.created_at.desc(),
        ).label("rnk")

        comment_subq = (
            select(
                ReflectionComment.id.label("c_id"),
                ReflectionComment.reflection_id.label("c_reflection_id"),
                ReflectionComment.content.label("c_content"),
                ReflectionComment.created_at.label("c_created_at"),
                User.username.label("c_username"),
                User.profile_photo_url.label("c_profile_photo_url"),
                comment_rank,
            )
            .join(User, User.id == ReflectionComment.user_id)
            .where(ReflectionComment.reflection_id.in_(reflection_ids))
        ).subquery()

        recent_comments_stmt = (
            select(comment_subq)
            .where(comment_subq.c.rnk <= 3)
        )

        comment_rows = (await db.execute(recent_comments_stmt)).all()

        comments_by_reflection: dict[UUID, list] = defaultdict(list)

        for row in comment_rows:
            comments_by_reflection[row.c_reflection_id].append(
                {
                    "id": row.c_id,
                    "content": row.c_content,
                    "commented_by": row.c_username,
                    "profile_photo_url":row.c_profile_photo_url,
                    "commented_at": row.c_created_at,
                }
            )




        items = []

        for (
            reflection,
            u_id,
            u_username,
            u_profile_photo_url,
            att_id,
            att_file_url,
            att_file_type,
            att_uploaded_at,
        ) in rows:

            attachment = None
            has_attachment = False
            if att_id:
                has_attachment = True
                attachment = {
                    "id": att_id,
                    "file_url": att_file_url,
                    "file_type": att_file_type,
                    "uploaded_at": att_uploaded_at,
                }
            
            reflection_goals = goals_by_reflection.get(reflection.id, [])

            reflection_comments = comments_by_reflection.get(reflection.id, [])

            


            items.append(
                {
                    "id": reflection.id,
                    "pod_id": reflection.pod_id,
                    "user": {
                        "id": u_id,
                        "username": u_username,
                        "profile_photo_url": u_profile_photo_url,
                    },
                    "reflection_date": reflection.reflection_date,
                    "content": reflection.content,
                    "mood": reflection.mood,

                    # ✅ NEW
                    "goals": reflection_goals,
                    "comments": reflection_comments,

                    "has_attachment": has_attachment,
                    "attachments": attachment,
                    "created_at": reflection.created_at,
                    "updated_at": reflection.updated_at,
                }
            )



        return {
            "page": page,
            "page_size": page_size,
            "total": int(total or 0),
            "items": items,
        }
    
    except Exception as e:
        logger.info(f"Error while list_pod_updateds {str(e)} with user :{user.email} and pod id:{pod_id}")
        exception_logger.exception(f"Error while list_pod_updates {str(e)} with user :{user.email}  and pod_id :{pod_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def get_pod_update(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    user: User,
):
    try:
        await _ensure_active_member(db, pod_id, user.id)

        now_date = date.today()
        effective_date = now_date - timedelta(days=1)

        start_of_week = effective_date - timedelta(days=effective_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)


        TodayProgress = aliased(GoalProgressEvent) 

        weekly_progress_subq = (
            select(
                GoalProgressEvent.goal_id.label("goal_id"),
                func.count(
                    func.distinct(GoalProgressEvent.progress_date)
                ).label("days_achieved_this_week"),
            )
            .where(
                GoalProgressEvent.pod_id == pod_id,
                # GoalProgressEvent.user_id == user.id,
                GoalProgressEvent.completed.is_(True),
                GoalProgressEvent.progress_date.between(start_of_week, end_of_week),
            )
            .group_by(GoalProgressEvent.goal_id)
        ).subquery()

    
        GoalStreakAlias = aliased(GoalStreak)
        stmt = (
        select(
            Reflection,
            User,

            # reflection-goal
            ReflectionGoal.completed,

            # goal fields
            PodGoal.id,
            PodGoal.title,
            PodGoal.category,
            PodGoal.description,
            PodGoal.success_definition,
            PodGoal.frequency_type,
            PodGoal.frequency_value,
            PodGoal.requires_measurement,
            PodGoal.measurement_unit,
            PodGoal.measurement_target,

            # streak
            func.coalesce(GoalStreakAlias.current_streak, 0),

            # func.coalesce(
            #     weekly_progress_subq.c.days_achieved_this_week, 0
            # ).label("days_achieved_this_week"),
            ReflectionGoal.weekly_progress_value.label("days_achieved_this_week"),

            # attachments
            ReflectionAttachment.id,
            ReflectionAttachment.file_url,
            ReflectionAttachment.file_type,
            ReflectionAttachment.uploaded_at,
        )
        .join(User, User.id == Reflection.user_id)
        .outerjoin(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
        .outerjoin(PodGoal, PodGoal.id == ReflectionGoal.goal_id)
        .outerjoin(
            GoalStreakAlias,
            (GoalStreakAlias.goal_id == PodGoal.id)
            & (GoalStreakAlias.user_id == Reflection.user_id),
        )
        .outerjoin(
            ReflectionAttachment,
            ReflectionAttachment.reflection_id == Reflection.id,
        )
        .where(
            Reflection.id == reflection_id,
            Reflection.pod_id == pod_id,
        )
    )


        rows = (await db.execute(stmt)).all()
        if not rows:
            raise HTTPException(status_code=404, detail="Post not found")

        reflection, author, *_ = rows[0]

        goals = []
        attachments_map = {}

    


    
        goals_map = {}
        attachments_map = {}

        for (
            _,
            _,
            completed,
            goal_id,
            title,
            category,
            description,
            success_definition,
            
            frequency_type,
            frequency_value,
            requires_measurement,
            measurement_unit, 
            measurement_target,
            current_streak,
            days_achieved_this_week,
            att_id,
            file_url,
            file_type,
            uploaded_at,
        ) in rows:

            # Goals (dedupe by goal_id)
            if goal_id and goal_id not in goals_map:
                goals_map[goal_id] = {
                    "id": goal_id,
                    "title": title,
                    "completed": completed,
                    "checked_yes": bool(completed),
                    "category": category,
                    "description": description,
                    "success_definition": success_definition,
                    "requiresMeasurement":requires_measurement,
                    "measurementTarget":measurement_target,
                    "days_achieved_this_week":days_achieved_this_week,
                    "measurementUnit":measurement_unit,
                    "frequency_type": frequency_type,
                    "frequency_value":frequency_value,
                    "current_streak": int(current_streak or 0),
                }
            
            

            # Attachments (dedupe)
            if att_id and att_id not in attachments_map:
                attachments_map[att_id] = {
                    "id": att_id,
                    "file_url": file_url,
                    "file_type": file_type,
                    "uploaded_at": uploaded_at,
                }



        return {
        "id": reflection.id,
        "pod_id": reflection.pod_id,
        "user": {
            "id": author.id,
            "username": author.name,
            "profile_photo_url": author.profile_photo_url,
        },
        "reflection_date": reflection.reflection_date,
        "content": reflection.content,
        "mood": reflection.mood,
        "goals": list(goals_map.values()),
        "attachments": list(attachments_map.values()),
        "created_at": reflection.created_at,
        "updated_at": reflection.updated_at,
    }

    except Exception as e:
        logger.info(f"Error while get_pod_updated {str(e)} with user :{user.email} and pod id:{pod_id}")
        exception_logger.exception(f"Error while get_pod_updates {str(e)} with user :{user.email}  and pod_id :{pod_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )




async def delete_pod_update(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    user: User,
):
    
    try:
        member = await _ensure_active_member(db, pod_id, user.id)

        reflection = await db.scalar(
            select(Reflection).where(
                Reflection.id == reflection_id,
                Reflection.pod_id == pod_id,
            )
        )

        if not reflection:
            raise HTTPException(status_code=404, detail="Post not found")

        if reflection.user_id != user.id and member.role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Not allowed to delete this post")

        await db.delete(reflection)
        await db.commit()

    except Exception as e:
        logger.info(f"Error while delete_pod_update {str(e)} with user :{user.email} and pod id:{pod_id}")
        exception_logger.exception(f"Error while get_pod_updates {str(e)} with user :{user.email}  and pod_id :{pod_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )
