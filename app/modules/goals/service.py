from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, literal_column, select, func
from fastapi import HTTPException
from uuid import UUID
from datetime import date, timedelta

from app.db.models.goal_progress_events import GoalProgressEvent
from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_goal_participants import PodGoalParticipant
from app.db.models.pod_goals import (
    PodGoal
)
from app.db.models.reflections import Reflection
from app.db.models.reflection_goals import ReflectionGoal
from app.db.models.pod_members import PodMember
from app.db.models.user import User
from app.modules.goals.schemas import GoalCreateRequest, GoalUpdateRequest
from app.modules.events.dispatcher import dispatcher
from app.modules.notifications.constants import NotificationType
from app.modules.events.schemas import DomainEvent

from datetime import date, timedelta

from app.utils.logger import get_logger
from app.utils.require_pod_member import _require_pod_member

logger = get_logger("goals-service")
exception_logger=get_logger("Exceptions_logs")

def validate_frequency_update(goal: PodGoal, payload: GoalUpdateRequest):
    try:
        final_type = payload.frequency_type or goal.frequency_type
        final_value = (
            payload.frequency_value
            if payload.frequency_value is not None
            else goal.frequency_value
        )

        if final_type == "daily":
            if final_value not in (None, 1):
                raise HTTPException(
                    status_code=400,
                    detail="Daily goals must have frequency_value = 1",
                )

        elif final_type == "weekly":
            if final_value is None:
                raise HTTPException(
                    status_code=400,
                    detail="Weekly goals require frequency_value (1–7)",
                )
            if not 1 <= final_value <= 7:
                raise HTTPException(
                    status_code=400,
                    detail="Weekly frequency_value must be between 1 and 7",
                )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid frequency_type",
            )
        
    except Exception as e:
        exception_logger.exception(f"Error while validation_frequency_update {str(e)} with goal :{goal.title}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


def validate_measurement(payload):
    if payload.requires_measurement:

        if not payload.measurement_unit:
            raise HTTPException(400, "measurement unit is required")
        if payload.measurement_target is None or payload.measurement_target <= 0:
            raise HTTPException(400, "measurement target must be > 0")
    else:
        payload.measurement_unit = None
        payload.measurement_target = None

def validate_measurement_update(goal: PodGoal, payload: GoalUpdateRequest):
    # Determine final requires_measurement
    final_requires = (
        payload.requires_measurement
        if payload.requires_measurement is not None
        else bool(goal.requires_measurement)
    )

    # Determine final values (use payload if provided, else existing)
    final_description = payload.description if payload.description is not None else goal.description
    final_unit = payload.measurement_unit if payload.measurement_unit is not None else goal.measurement_unit
    final_target = payload.measurement_target if payload.measurement_target is not None else goal.measurement_target

    if final_requires:

        if not final_unit:
            raise HTTPException(400, "measurement unit is required")
        if final_target is None or final_target <= 0:
            raise HTTPException(400, "measurement target must be > 0")
    else:
        # if user is turning measurement OFF, we'll clear fields after update
        return



# ---------- CREATE GOAL ----------

async def create_goal(
    session: AsyncSession, pod_id: UUID, user: User, payload
):
    try:
        emit_event = False  
        logger.info("create goal service called ")
        member = await _require_pod_member(session, pod_id, user.id)
        if member.role not in ("owner", "admin", "member"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        validate_measurement(payload)

        goal = PodGoal(
            pod_id=pod_id,
            title=payload.title,
            category=payload.category,
            requires_measurement=payload.requires_measurement,

            # Measurement
            description=payload.description,
            measurement_unit=payload.measurement_unit,
            measurement_target=payload.measurement_target,

            why_it_matters=payload.why_it_matters,

            frequency_type=payload.frequency_type,
            frequency_value=payload.frequency_value,

            start_date=payload.start_date,
            end_date=payload.end_date,
            status="active",
            created_by=user.id,
        )


        session.add(goal)
        await session.flush()

        participant = PodGoalParticipant(
            pod_id=pod_id,
            goal_id=goal.id,
            user_id=user.id,
            joined_at=date.today(),
            is_active=True,
        )

        streak = GoalStreak(
            goal_id=goal.id,
            user_id=user.id,
            current_streak=0,
            longest_streak=0,
        )

        session.add_all([participant, streak])
        await session.commit()
        
        logger.info("emitting even to create notification and activity log ")
        await dispatcher.emit(
            DomainEvent(
                type=NotificationType.POD_NEW_GOAL,
                actor_id=user.id,
                pod_id=pod_id,
                entity_type="goal",
                entity_id=pod_id,
                context={
                    "actor_name": user.name or "Someone",
                    "details":f"{user.name} created new goal" or "Someone"
                },
            )
        )

        return {
            "id": goal.id,
            "title": goal.title,
            "category": goal.category,

            "requires_measurement": bool(goal.requires_measurement),
            "description": goal.description,
            "measurement_unit": goal.measurement_unit,
            "measurement_target": goal.measurement_target,

            "frequency_type": goal.frequency_type,
            "frequency_value": goal.frequency_value,
            "status": goal.status,
        }
    
    except Exception as e:
        logger.info(f"Error while create_goal {str(e)} with user :{user.email}")
        exception_logger.exception(f"Error while create_goal {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

# ---------- LIST GOALS ----------

from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from collections import defaultdict

async def _list_goals_for_current_user(
    session: AsyncSession,
    pod_id: UUID,
    user_id: UUID,
):
    # my_today_status reflects completion for the UI's "today",
    # which corresponds to effective_date = today - 1
    # because reflections are submitted for the previous day.

    try:


        now_date = date.today()
        effective_date = now_date - timedelta(days=1)

        start_of_week = effective_date - timedelta(days=effective_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        effective_frequency = func.coalesce(PodGoal.frequency_value, 1)

        # alias for counting all participants
        AllParticipants = aliased(PodGoalParticipant)
        # join for "my membership" (restrict results)
        MyParticipant = aliased(PodGoalParticipant)
        TodayProgress = aliased(GoalProgressEvent)

        weekly_completed_days = func.count(
            func.distinct(
                case(
                    (
                        (TodayProgress.progress_date.between(start_of_week, end_of_week))
                        & (TodayProgress.completed.is_(True)),
                        TodayProgress.progress_date,
                    ),
                    else_=None,
                )
            )
        )
        
        completed_on_effective_date = (
            func.max(
                case(
                    (
                        (TodayProgress.progress_date == effective_date)
                        & (TodayProgress.completed.is_(True)),
                        1,
                    ),
                    else_=0,
                )
            )
        )

        failed_on_effective_date = (
            func.max(
                case(
                    (
                        (TodayProgress.progress_date == effective_date)
                        & (TodayProgress.completed.is_(False)),
                        1,
                    ),
                    else_=0,
                )
            )
        )

        stmt = (
            select(
                PodGoal,
                func.count(AllParticipants.id).label("participant_count"),
                MyParticipant.is_active.label("is_active"),
                func.coalesce(GoalStreak.current_streak, 0).label("current_streak"),
                weekly_completed_days.label("days_achieved_this_week"),
                case(
                    # DAILY YES
                    (
                        (PodGoal.frequency_type == "daily")
                        & (
                            func.max(
                                case(
                                    (
                                        (TodayProgress.progress_date == effective_date)
                                        & (TodayProgress.completed.is_(True)),
                                        1,
                                    ),
                                    else_=0,
                                )
                            ) == 1
                        ),
                        "yes",
                    ),
                    # DAILY NO
                    (
                        (PodGoal.frequency_type == "daily")
                        & (
                            func.max(
                                case(
                                    (
                                        (TodayProgress.progress_date == effective_date)
                                        & (TodayProgress.completed.is_(False)),
                                        1,
                                    ),
                                    else_=0,
                                )
                            ) == 1
                        ),
                        "no",
                    ),
                    # -----------------------
                    # WEEKLY 
                    # -----------------------
                    # if user explicitly marked no today, show no
                    (
                        (PodGoal.frequency_type == "weekly") & (failed_on_effective_date == 1),
                        "no",
                    ),
                    # completed today => yes
                    (
                        (PodGoal.frequency_type == "weekly") & (completed_on_effective_date == 1),
                        "yes",
                    ),
                    # weekly target met => yes
                    # (
                    #     (PodGoal.frequency_type == "weekly")
                    #     & (weekly_completed_days >= effective_frequency),
                    #     "yes",
                    # ),
                    # otherwise weekly => no
                    (
                        (PodGoal.frequency_type == "weekly"),
                        "no",
                    ),
                    else_=None,
                ).label("today_status"),
            )
            .join(
                MyParticipant,
                (MyParticipant.goal_id == PodGoal.id)
                & (MyParticipant.user_id == user_id),
            )
            .outerjoin(
                AllParticipants,
                (AllParticipants.goal_id == PodGoal.id)
                & (AllParticipants.is_active.is_(True)),
            )
            .outerjoin(
                GoalStreak,
                (GoalStreak.goal_id == PodGoal.id)
                & (GoalStreak.user_id == user_id),
            )
            .outerjoin(
                TodayProgress,
                (TodayProgress.goal_id == PodGoal.id)
                & (TodayProgress.user_id == user_id)
                & (TodayProgress.pod_id == pod_id),
            )
            .where(
                PodGoal.pod_id == pod_id,
                PodGoal.status == "active",
            )
            .group_by(PodGoal.id,MyParticipant.is_active, GoalStreak.current_streak)
            .order_by(PodGoal.created_at.desc())
        )

        return (await session.execute(stmt)).all()
    
    except Exception as e:
        logger.info(f"Error while list_goal_for_current_user {str(e)} with user :{user_id}")
        exception_logger.exception(f"Error while create_goal {str(e)} with user :{user_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

from sqlalchemy.orm import aliased

async def _list_goals_for_all_users(
    session: AsyncSession,
    pod_id: UUID,
):
    try:
        now_date = date.today()
        effective_date = now_date - timedelta(days=1)

        start_of_week = effective_date - timedelta(days=effective_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        UserParticipant = aliased(PodGoalParticipant)
        AllParticipants = aliased(PodGoalParticipant)
        TodayProgress = aliased(GoalProgressEvent)
        effective_frequency = func.coalesce(PodGoal.frequency_value, 1)
        weekly_completed_days = func.count(
            func.distinct(
                case(
                    (
                        (TodayProgress.progress_date.between(start_of_week, end_of_week))
                        & (TodayProgress.completed.is_(True)),
                        TodayProgress.progress_date,
                    ),
                    else_=None,
                )
            )
        )


        stmt = (
            select(
                UserParticipant.user_id.label("user_id"),
                PodGoal,
                func.count(AllParticipants.id).label("participant_count"),
                UserParticipant.is_active.label("is_active"),
                func.coalesce(GoalStreak.current_streak, 0).label("current_streak"),
                weekly_completed_days.label("days_achieved_this_week"),
                case(
                    # DAILY YES
                    (
                        (PodGoal.frequency_type == "daily")
                        & (
                            func.max(
                                case(
                                    (
                                        (TodayProgress.progress_date == effective_date)
                                        & (TodayProgress.completed.is_(True)),
                                        1,
                                    ),
                                    else_=0,
                                )
                            ) == 1
                        ),
                        "yes",
                    ),
                    # DAILY NO
                    (
                        (PodGoal.frequency_type == "daily")
                        & (
                            func.max(
                                case(
                                    (
                                        (TodayProgress.progress_date == effective_date)
                                        & (TodayProgress.completed.is_(False)),
                                        1,
                                    ),
                                    else_=0,
                                )
                            ) == 1
                        ),
                        "no",
                    ),
                    # WEEKLY YES
                    (
                        (PodGoal.frequency_type == "weekly")
                        & (weekly_completed_days >= effective_frequency),
                        "yes",
                    ),
                    # WEEKLY NO
                    (
                        (PodGoal.frequency_type == "weekly")
                        & (weekly_completed_days < effective_frequency),
                        "no",
                    ),
                    else_=None,
                ).label("today_status"),
            )
            .select_from(PodGoal)
            # user participates in goal
            .join(
                UserParticipant,
                (UserParticipant.goal_id == PodGoal.id)
                & (UserParticipant.pod_id == pod_id),
            )
            # user must be active pod member
            .join(
                PodMember,
                (PodMember.user_id == UserParticipant.user_id)
                & (PodMember.pod_id == pod_id)
                & (PodMember.is_active.is_(True)),
            )
            # count all participants
            .outerjoin(
                AllParticipants,
                (AllParticipants.goal_id == PodGoal.id)
                & (AllParticipants.is_active.is_(True)),
            )
            .outerjoin(
                GoalStreak,
                (GoalStreak.goal_id == PodGoal.id)
                & (GoalStreak.user_id == UserParticipant.user_id),
            )
            .outerjoin(
                TodayProgress,
                (TodayProgress.goal_id == PodGoal.id)
                & (TodayProgress.user_id == UserParticipant.user_id)
                & (TodayProgress.pod_id == pod_id),
            )
            .where(
                PodGoal.pod_id == pod_id,
                PodGoal.status == "active",
            )
            .group_by(
                UserParticipant.user_id,
                PodGoal.id,
                UserParticipant.is_active,
                GoalStreak.current_streak,
            )
            .order_by(
                UserParticipant.user_id,
                PodGoal.created_at.desc(),
            )
        )

        logger.info(
            "Executing all-users goals query",
            extra={"pod_id": str(pod_id)},
        )

        return (await session.execute(stmt)).all()

    except Exception as e:
        exception_logger.info(f"error while list_goal_for_all_users :{str(e)} with pod :{pod_id}")
        logger.exception(
            "Query failed in _list_goals_for_all_users",
            extra={"pod_id": str(pod_id)},
        )
        raise

async def list_goals(
    session: AsyncSession,
    pod_id: UUID,
    user: User,
    all_users: bool = False,
):
    await _require_pod_member(session, pod_id, user.id)

    try:
        grouped: dict[UUID, list[dict]] = defaultdict(list)

        if all_users:
            logger.info("Listing goals for all users", extra={"pod_id": str(pod_id)})

            rows = await _list_goals_for_all_users(session, pod_id)

            for (
                user_id,
                goal,
                participant_count,
                is_active,
                current_streak,
                days_achieved_this_week,
                today_status,
            ) in rows:
                grouped[user_id].append(
                    {
                        "id": goal.id,
                        "title": goal.title,
                        "category": goal.category,
                        "requires_measurement": bool(goal.requires_measurement),
                        "description": goal.description,
                        "measurement_unit": goal.measurement_unit,
                        "measurement_target": goal.measurement_target,
                        "frequency_type": goal.frequency_type,
                        "frequency_value": goal.frequency_value or 1,
                        "days_achieved_this_week": int(days_achieved_this_week or 0),
                        "participant_count": int(participant_count or 0),
                        "my_joined": True,
                        "is_active": is_active,
                        "current_streak": int(current_streak or 0),
                        "today_status": today_status,
                    }
                )

        else:
            rows = await _list_goals_for_current_user(
                session=session,
                pod_id=pod_id,
                user_id=user.id,
            )

            for (
                goal,
                participant_count,
                is_active,
                current_streak,
                days_achieved_this_week,
                today_status,
            ) in rows:
                grouped[user.id].append(
                    {
                        "id": goal.id,
                        "title": goal.title,
                        "category": goal.category,
                        "requires_measurement": bool(goal.requires_measurement),
                        "description": goal.description,
                        "measurement_unit": goal.measurement_unit,
                        "measurement_target": goal.measurement_target,
                        "frequency_type": goal.frequency_type,
                        "frequency_value": goal.frequency_value or 1,
                        "days_achieved_this_week": int(days_achieved_this_week or 0),
                        "participant_count": int(participant_count or 0),
                        "my_joined": True,
                        "is_active": is_active,
                        "current_streak": int(current_streak or 0),
                        "today_status": today_status,
                    }
                )

        # ✅ FINAL RESPONSE SHAPE
        return [
            {
                "user_id": user_id,
                "goals": goals,
            }
            for user_id, goals in grouped.items()
        ]

    except Exception as e:
        logger.info(f"Error while list_goals {str(e)} with user :{user.email}")
        exception_logger.exception(f"Error while create_goal {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=500,
            detail=f"{str(e)}",
        )

    except Exception:
        logger.error(
            "Failed to list goals",
            exc_info=True,
            extra={
                "pod_id": str(pod_id),
                "user_id": str(user.id),
                "all_users": all_users,
            },
        )
        raise HTTPException(status_code=500, detail="Failed to fetch goals")



# ---------- GET GOAL DETAILS ----------



async def get_goal(
    session: AsyncSession, pod_id: UUID, goal_id: UUID, user: User
):
    
    try:
        
        goal = await session.scalar(
            select(PodGoal).where(
                PodGoal.id == goal_id,
                PodGoal.pod_id == pod_id
            )
        )
        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        participant = await session.scalar(
            select(PodGoalParticipant).where(
                PodGoalParticipant.goal_id == goal_id,
                PodGoalParticipant.user_id == user.id,
            )
        )

        streak = await session.scalar(
            select(GoalStreak).where(
                GoalStreak.goal_id == goal_id,
                GoalStreak.user_id == user.id,
            )
        )

        # 🔥 Heatmap logic
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        rows = (
            await session.execute(
                select(
                    Reflection.reflection_date,
                    func.count(Reflection.id),
                )
                .join(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
                .where(
                    ReflectionGoal.goal_id == goal_id,
                    Reflection.user_id == user.id,
                    Reflection.reflection_date >= start_date,
                    Reflection.reflection_date <= end_date,
                    ReflectionGoal.completed==True
                )
                .group_by(Reflection.reflection_date)
            )
        ).all()

        counts_by_date = {row[0]: int(row[1]) for row in rows}
        max_count = max(counts_by_date.values()) if counts_by_date else 0

        days = []
        cursor = start_date

        while cursor <= end_date:
            count = counts_by_date.get(cursor, 0)


            if count == 0 :
                level = 0
            elif count ==1:
                level = 4

        
            else:
                level = 0

            days.append(
                {   
                    "date": cursor,
                    "count": count,
                    "level": level,
                }
            )

            cursor += timedelta(days=1)

        
        today = date.today()
        seven_days_ago = today - timedelta(days=6)  # inclusive = 7 days
        month_start = today.replace(day=1)

        days_achieved_last_7 = await session.scalar(
            select(func.count(func.distinct(Reflection.reflection_date)))
            .join(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
            .where(
                ReflectionGoal.goal_id == goal_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date >= seven_days_ago,
                Reflection.reflection_date <= today,
                ReflectionGoal.completed==True
            )
        ) or 0


        times_completed_this_month = await session.scalar(
            select(func.count(Reflection.id))
            .join(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
            .where(
                ReflectionGoal.goal_id == goal_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date >= month_start,
                Reflection.reflection_date <= today,
                ReflectionGoal.completed==True
            )
        ) or 0




        return {
            "id": goal.id,
            "title": goal.title,
            "category": goal.category,
            "requires_measurement": bool(goal.requires_measurement),
            "description": goal.description,
            "measurement_unit": goal.measurement_unit,
            "measurement_target": goal.measurement_target,
            "why_it_matters": goal.why_it_matters,
            "success_definition": goal.success_definition,
            "frequency_type": goal.frequency_type,
            "frequency_value": goal.frequency_value,
            "start_date": goal.start_date,
            "end_date": goal.end_date,
            "status": goal.status,
            "is_active": participant.is_active if participant else False,
            "created_by": goal.created_by,
            "my_role": "participant" if participant else None,
            "current_streak": streak.current_streak if streak else 0,
            "longest_streak": streak.longest_streak if streak else 0,
            "days_achieved_last_7": days_achieved_last_7,
            "times_completed_this_month": times_completed_this_month,
            "days": days,
        }
    
    except Exception as e:
        logger.info(f"Error while get_goal {str(e)} with user :{user.email}")
        exception_logger.exception(f"Error while create_goal {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

async def create_goals_batch(
    session: AsyncSession,
    pod_id: UUID,
    user: User,
    goals: list[GoalCreateRequest],
):
    try:
        logger.info("create goal batch called")
        # 1) Validate membership (and permissions like create_goal)
        member = await session.scalar(
            select(PodMember).where(
                PodMember.pod_id == pod_id,
                PodMember.user_id == user.id,
                PodMember.is_active.is_(True),
            )
        )
        if not member:
            logger.info(f"user with no pod member trying to add create goals batch")
            raise HTTPException(status_code=403, detail="Not a pod member")

        # OPTIONAL: keep consistent with create_goal
        if member.role not in ("owner", "admin","member"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # 2) Validate input
        if not goals:
            raise HTTPException(status_code=400, detail="No goals provided")
        if len(goals) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 goals allowed")

        created = []
        target_ids=[]

        for g in goals:
            # frequency_value is required by schema, but keep defensive check
            if g.frequency_value is None:
                raise HTTPException(status_code=400, detail="frequency_value is required")
            validate_measurement(g)

            goal = PodGoal(
                pod_id=pod_id,
                title=g.title,
                category=g.category,
                requires_measurement=g.requires_measurement,
                description=g.description,
                measurement_unit=g.measurement_unit,
                measurement_target=g.measurement_target,
                why_it_matters=g.why_it_matters,
                frequency_type=g.frequency_type,
                frequency_value=g.frequency_value,
                start_date=g.start_date,
                end_date=g.end_date,
                created_by=user.id,
                status="active",
            )
            session.add(goal)

            await session.flush()  # ensures goal.id exists
            target_ids.append(goal.id)

            # Add creator as participant (same as create_goal)
            participant = PodGoalParticipant(
                pod_id=pod_id,
                goal_id=goal.id,
                user_id=user.id,
                joined_at=date.today(),
                is_active=True,
            )

            streak = GoalStreak(
                goal_id=goal.id,
                user_id=user.id,
                current_streak=0,
                longest_streak=0,
            )

            session.add_all([participant, streak])
            created.append(goal)


            logger.info("emitting even to create notification and activity log ")
            await dispatcher.emit(
                DomainEvent(
                    type=NotificationType.POD_NEW_GOAL,
                    actor_id=user.id,
                    pod_id=pod_id,
                    entity_type="goal",
                    entity_id=pod_id,
                    context={
                        "actor_name": user.name or "Someone",
                        "details":f"{user.name} created new goals" or "Someone",
                        "target_ids":[goal.id]
                    },
                )
            )

        await session.commit()


        

        return [
            {
                "id": g.id,
                "title": g.title,
                "category": g.category,
                "description": g.description,
                "requires_measurement": bool(g.requires_measurement),
                "measurement_unit": g.measurement_unit,
                "measurement_target": g.measurement_target,
                "frequency_type": g.frequency_type,
                "frequency_value": g.frequency_value,
                "status": g.status,
            }
            for g in created
        ]
    
    except Exception as e:
        logger.info(f"Error while create_goal_batch {str(e)} with user :{user.email}")
        exception_logger.exception(f"Error while create_goal_batch {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


# ---------- UPDATE GOAL DETAILS ----------

async def update_goal(
    session: AsyncSession,
    pod_id: UUID,
    goal_id: UUID,
    user,
    payload: GoalUpdateRequest,
):
    try:
        # 1️⃣ Ensure user belongs to pod
        await _require_pod_member(session, pod_id, user.id)

        # 2️⃣ Fetch goal (scoped to pod)
        goal = await session.scalar(
            select(PodGoal).where(
                PodGoal.id == goal_id,
                PodGoal.pod_id == pod_id,
            )
        )

        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        # 3️⃣ Authorization
        # Adjust rule if needed (e.g. admins)
        if goal.created_by != user.id:
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to update this goal",
            )

        # 4️⃣ Apply partial updates
        validate_measurement_update(goal, payload)
        validate_frequency_update(goal, payload)
        # 4️⃣ Validate updates

        update_data = payload.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(goal, field, value)

        # 6️⃣ Fetch participant & streak (same as get_goal)
        participant = await session.scalar(
            select(PodGoalParticipant).where(
                PodGoalParticipant.goal_id == goal_id,
                PodGoalParticipant.user_id == user.id,
            )
        )

        if payload.is_active is not None:
            participant.is_active = payload.is_active
        
        if payload.requires_measurement is False:
            goal.description = None
            goal.measurement_unit = None
            goal.measurement_target = None
        # 5️⃣ Persist
        await session.commit()
        await session.refresh(goal)



        streak = await session.scalar(
            select(GoalStreak).where(
                GoalStreak.goal_id == goal_id,
                GoalStreak.user_id == user.id,
            )
        )


        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        rows = (
            await session.execute(
                select(
                    Reflection.reflection_date,
                    func.count(Reflection.id),
                )
                .join(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
                .where(
                    ReflectionGoal.goal_id == goal_id,
                    Reflection.user_id == user.id,
                    Reflection.reflection_date >= start_date,
                    Reflection.reflection_date <= end_date,
                )
                .group_by(Reflection.reflection_date)
            )
        ).all()

        counts_by_date = {row[0]: int(row[1]) for row in rows}
        max_count = max(counts_by_date.values()) if counts_by_date else 0

        days = []
        cursor = start_date

        while cursor <= end_date:
            count = counts_by_date.get(cursor, 0)


            if count == 0 :
                level = 0
            elif count ==1:
                level = 4

        
            else:
                level = 0

            days.append(
                {   
                    "date": cursor,
                    "count": count,
                    "level": level,
                }
            )

            cursor += timedelta(days=1)

        
        today = date.today()
        seven_days_ago = today - timedelta(days=6)  # inclusive = 7 days
        month_start = today.replace(day=1)

        days_achieved_last_7 = await session.scalar(
            select(func.count(func.distinct(Reflection.reflection_date)))
            .join(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
            .where(
                ReflectionGoal.goal_id == goal_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date >= seven_days_ago,
                Reflection.reflection_date <= today,
            )
        ) or 0


        times_completed_this_month = await session.scalar(
            select(func.count(Reflection.id))
            .join(ReflectionGoal, ReflectionGoal.reflection_id == Reflection.id)
            .where(
                ReflectionGoal.goal_id == goal_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date >= month_start,
                Reflection.reflection_date <= today,
            )
        ) or 0


        # 7️⃣ Return updated detail response
        return {
            "id": goal.id,
            "title": goal.title,
            "category": goal.category,
            "description": goal.description,
            "requires_measurement": bool(goal.requires_measurement),
            "measurement_unit": goal.measurement_unit,
            "measurement_target": goal.measurement_target,
            "why_it_matters": goal.why_it_matters,
            "success_definition": goal.success_definition,
            "frequency_type": goal.frequency_type,
            "frequency_value": goal.frequency_value,
            "start_date": goal.start_date,
            "end_date": goal.end_date,
            "status": goal.status,
            "is_active":participant.is_active,
            "created_by": goal.created_by,
            "my_role": "participant" if participant else None,
            "current_streak": streak.current_streak if streak else 0,
            "longest_streak": streak.longest_streak if streak else 0,
            "days_achieved_last_7": days_achieved_last_7,
            "times_completed_this_month": times_completed_this_month,
            "days": days,
        }
    
    except Exception as e:
        logger.info(f"Error while update_goal {str(e)} with goal id :{goal_id}")
        exception_logger.exception(f"Error while update_goal {str(e)} with goal_id :{goal_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )






async def delete_goal(
    session: AsyncSession,
    pod_id: UUID,
    goal_id: UUID,
    user: User,
):
    try:
        goal = await session.scalar(
            select(PodGoal).where(
                PodGoal.id == goal_id,
                PodGoal.pod_id == pod_id
            )
        )

        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        await session.delete(goal)
        await session.commit()

    except Exception as e:
        logger.info(f"Error while delete_goal {str(e)} with user and goal id :{user.email} , {goal_id}")
        exception_logger.exception(f"Error while delete_goal {str(e)} with user :{user.email} and goal id :{goal_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )
