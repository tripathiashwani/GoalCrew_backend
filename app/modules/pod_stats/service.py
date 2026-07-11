from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.db.models.reflection_comments import ReflectionComment
from app.db.models.reflection_reactions import ReflectionReaction
from app.db.models.reflections import Reflection
from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_members import PodMember
from app.db.models.pod_goal_participants import PodGoalParticipant
from app.db.models.goal_progress_events import GoalProgressEvent
from app.db.models.user import User
from app.modules.pod_stats.schema import PodStatsResponse, PersonalStats, PodStats


def _start_end_of_week(today: date):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


async def get_pod_stats(
    db: AsyncSession,
    pod_id: UUID,
    user: User,
) -> PodStatsResponse:
    # ─────────────────────────────────────────────
    # Ensure active pod member
    # ─────────────────────────────────────────────
    member = await db.scalar(
        select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == user.id,
            PodMember.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a pod member")

    now_date = date.today()
    effective_date = now_date - timedelta(days=1)

    start_week, end_week = _start_end_of_week(effective_date)


    # ─────────────────────────────────────────────
    # PERSONAL STATS
    # ─────────────────────────────────────────────

    # 1️⃣ Weekly check-ins
    weekly_checkins = await db.scalar(
        select(func.count(Reflection.id)).where(
            Reflection.pod_id == pod_id,
            Reflection.user_id == user.id,
            Reflection.reflection_date.between(start_week, end_week),
        )
    ) or 0

    # 2️⃣ Active goals
    active_goals = await db.scalar(
        select(func.count(PodGoalParticipant.id)).where(
            PodGoalParticipant.user_id == user.id,
            PodGoalParticipant.pod_id == pod_id,
            PodGoalParticipant.is_active.is_(True),
        )
    ) or 0

    # 3️⃣ Check-in completion %
    # (weekly for now; can be expanded later)
    days_elapsed = max((effective_date - start_week).days + 1, 1)
    check_ins_pct = min(int((weekly_checkins / days_elapsed) * 100), 100)

    # 4️⃣ Support score (simple v1)

    support_actions = await db.scalar(
        select(func.count())
        .select_from(ReflectionReaction)
        .join(Reflection, Reflection.id == ReflectionReaction.reflection_id)
        .where(
            ReflectionReaction.user_id == user.id,
            Reflection.pod_id == pod_id,
            Reflection.user_id != user.id,  # supporting others
            Reflection.reflection_date.between(start_week, end_week),
        )
    ) or 0

    comment_actions = await db.scalar(
        select(func.count())
        .select_from(ReflectionComment)
        .join(Reflection, Reflection.id == ReflectionComment.reflection_id)
        .where(
            ReflectionComment.user_id == user.id,
            Reflection.pod_id == pod_id,
            Reflection.user_id != user.id,
            Reflection.reflection_date.between(start_week, end_week),
        )
    ) or 0

    support_events = support_actions + comment_actions
    support_pct = min(support_events * 10, 100)

    personal = PersonalStats(
        check_ins_pct=check_ins_pct,
        support_pct=support_pct,
        active_goals=active_goals,
        weekly_checkins=weekly_checkins,
    )

    # ─────────────────────────────────────────────
    # POD STATS
    # ─────────────────────────────────────────────

    # 5️⃣ Total members
    total_members = await db.scalar(
        select(func.count(PodMember.id)).where(
            PodMember.pod_id == pod_id,
            PodMember.is_active.is_(True),
        )
    ) or 0

    # 6️⃣ Members checked in this week
    members_checked_in = await db.scalar(
        select(func.count(distinct(Reflection.user_id))).where(
            Reflection.pod_id == pod_id,
            Reflection.reflection_date.between(start_week, end_week),
        )
    ) or 0

    # 7️⃣ Average streak
    avg_streak = await db.scalar(
        select(func.coalesce(func.avg(GoalStreak.current_streak), 0))
        .join(
            PodGoalParticipant,
            (PodGoalParticipant.goal_id == GoalStreak.goal_id)
            & (PodGoalParticipant.user_id == GoalStreak.user_id),
        )
        .where(
            PodGoalParticipant.is_active.is_(True),
        )
    ) or 0

    avg_streak = int(avg_streak)

    # 8️⃣ Pod health score (weighted)
    member_ratio = (members_checked_in / total_members) if total_members else 0
    pod_health_pct = int(
        min(
            (
                member_ratio * 40
                + min(avg_streak, 7) / 7 * 30
                + min(weekly_checkins, 7) / 7 * 30
            ),
            100,
        )
    )

    pod = PodStats(
        members_checked_in=members_checked_in,
        total_members=total_members,
        avg_streak=avg_streak,
        pod_health_pct=pod_health_pct,
    )

    return PodStatsResponse(
        personal=personal,
        pod=pod,
    )




# app/modules/pod_stats/service.py

from sqlalchemy import select, func, union_all, cast, Date
from datetime import timedelta
from app.db.models.reflections import Reflection
from app.db.models.reflection_comments import ReflectionComment
from datetime import date
from .schema import PodContributionHeatmapResponse, HeatmapDay
# app/modules/pod_stats/service.py

from datetime import timedelta
from collections import defaultdict
from sqlalchemy import select, func, distinct


async def get_pod_contribution_heatmap(
    db: AsyncSession,
    pod_id: UUID,
    user: User,
) -> PodContributionHeatmapResponse:

    today = date.today()
    from_date = today - timedelta(days=30)

    # 1️⃣ Reflections per day
    reflections = (
        await db.execute(
            select(
                Reflection.reflection_date,
                func.count(distinct(Reflection.id))
            )
            .where(
                Reflection.pod_id == pod_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date.between(from_date, today),
            )
            .group_by(Reflection.reflection_date)
        )
    ).all()



    daily_counts = defaultdict(int)

    for d, c in reflections:
        daily_counts[d] += c

    # for d, c in comments:
    #     daily_counts[d] += c

    max_count = max(daily_counts.values(), default=0)

    def intensity(count: int) -> int:
        if count == 0:
            return 0
        if count == 1:
            return 1
        if count == 2:
            return 2
        if count <= 4:
            return 3
        return 4

    days = []
    current = from_date
    while current <= today:
        count = daily_counts.get(current, 0)
        days.append(
            HeatmapDay(
                date=current,
                count=count,
                level=intensity(count),
            )
        )
        current += timedelta(days=1)

    
    last_7_days = today - timedelta(days=6)

    start_of_month = today.replace(day=1)

    days_checkedin_last_7 = (
        await db.scalar(
            select(func.count(distinct(Reflection.reflection_date)))
            .where(
                Reflection.pod_id == pod_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date.between(last_7_days, today),
            )
        )
    ) or 0


    times_checkedin_this_month = (
        await db.scalar(
            select(func.count(Reflection.id))
            .where(
                Reflection.pod_id == pod_id,
                Reflection.user_id == user.id,
                Reflection.reflection_date.between(start_of_month, today),
            )
        )
    ) or 0




    return PodContributionHeatmapResponse(
        pod_id=pod_id,
        from_date=from_date,
        to_date=today,
        total_days=len(days),
        max_count=max_count,
        days=days,
        days_checkedin_last_7=days_checkedin_last_7,
        times_checkedin_this_month=times_checkedin_this_month
    )

