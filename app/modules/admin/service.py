from sqlalchemy.orm import Session
from sqlalchemy import func, select
from fastapi import APIRouter, Depends , HTTPException,Query
from app.db.models import User, Reflection, PodMember, GoalStreak ,ReflectionComment,Pod, ActivityLog, PodGoal, Notification, ReflectionGoal,GoalProgressEvent, PodGoalParticipant
from datetime import datetime, timedelta
from app.utils.logger import get_logger
from sqlalchemy.orm import aliased
import uuid
from sqlalchemy import case, literal_column
from datetime import date, timedelta
from app.modules.admin.schemas import AdminUserOut,AdminCommentOut,AdminPodMemberOut,AdminPodOut,AdminActivityOut, AdminCheckinOut, ReflectionGoalResponse, ReflectionResponse, ReflectionAttachmentResponse
from sqlalchemy import select, delete
from app.modules.reflections.service import _load_reflection_with_goals
from sqlalchemy.orm import with_loader_criteria

from sqlalchemy.orm import selectinload
from firebase_admin import auth as firebase_auth
from typing import Literal, Optional
from uuid import UUID
import time
logger = get_logger("AdminService")

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

class AdminService:

    @staticmethod
    async def get_users(db: AsyncSession):

        try:
            logger.info("get_users called in admin service")

            # reflections count
            reflections_subq = (
                select(
                    Reflection.user_id,
                    func.count(Reflection.id).label("checkins")
                )
                .group_by(Reflection.user_id)
                .subquery()
            )

            # pods count
            pods_subq = (
                select(
                    PodMember.user_id,
                    func.count(PodMember.pod_id).label("pods")
                )
                .group_by(PodMember.user_id)
                .subquery()
            )

            # max streak
            streak_subq = (
                select(
                    GoalStreak.user_id,
                    func.max(GoalStreak.current_streak).label("max_streak")
                )
                .group_by(GoalStreak.user_id)
                .subquery()
            )

            stmt = (
                select(
                    User,
                    func.coalesce(reflections_subq.c.checkins, 0),
                    func.coalesce(pods_subq.c.pods, 0),
                    func.coalesce(streak_subq.c.max_streak, 0),
                )
                .outerjoin(reflections_subq, reflections_subq.c.user_id == User.id)
                .outerjoin(pods_subq, pods_subq.c.user_id == User.id)
                .outerjoin(streak_subq, streak_subq.c.user_id == User.id)
                .order_by(User.created_at.desc())
            )

            result = await db.execute(stmt)
            rows = result.all()

            users = []

            for user, checkins, pods, streak in rows:
                users.append({
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "name":user.name,
                    "phone": f"{user.country_code}{user.phone_number}" if user.phone_number else None,
                    "avatar": user.profile_photo_url,
                    "joinedAt": user.created_at,
                    "lastActive": user.updated_at,
                    "podsCount": int(pods or 0),
                    "checkInsCount": int(checkins or 0),
                    "streak": int(streak or 0),
                    "status": "active",
                })

            logger.info(f"admin users returned: {len(users)}")
            return users
        
        except Exception as e:
            logger.info(f"Error while get user at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    


    async def get_pods(user_id: Optional[UUID],db: AsyncSession):
        """
        Returns AdminPodOut[] matching frontend AdminPod mock:
        - joinCode = Pod.invite_code
        - createdAt = Pod.created_at
        - members = PodMember.user -> {id, username, avatar}
        """

        try:
            stmt = (
                select(Pod)
                .options(
                    selectinload(Pod.members).selectinload(PodMember.user),
                    with_loader_criteria(PodMember, PodMember.is_active == True) 
                )
                .order_by(Pod.created_at.desc())
            )

            if user_id:
                stmt = (
                    stmt.join(PodMember)
                    .where(PodMember.user_id == user_id)
                )

            res = await db.execute(stmt)
            
            pods = res.scalars().unique().all()

            out = []
            for pod in pods:
                members = []
                for pm in pod.members or []:
                    u = pm.user
                    members.append(
                        AdminPodMemberOut(
                            id=u.id,
                            username=u.username or u.name,
                            name=u.name,
                            avatar=u.profile_photo_url,
                        )
                    )

                out.append(
                    AdminPodOut(
                        id=pod.id,
                        name=pod.name,
                        icon=None,  # you don't have icon column
                        joinCode=pod.invite_code,
                        createdAt=pod.created_at,
                        members=members,
                    )
                )

            return out
        
        except Exception as e:
            logger.info(f"Error while get pods at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_comments(db: AsyncSession, limit: int = 200,  user_id: Optional[UUID] = None):
        """
        Returns AdminCommentOut[] matching frontend AdminComment mock:
        - podId = Reflection.pod_id
        - checkInId = ReflectionComment.reflection_id
        - userId = ReflectionComment.user_id
        - text = ReflectionComment.content
        - createdAt = ReflectionComment.created_at
        """

        try:

            stmt = (
                select(ReflectionComment, Reflection, User)
                .join(Reflection, Reflection.id == ReflectionComment.reflection_id)
                .join(User, User.id == ReflectionComment.user_id)
                .order_by(ReflectionComment.created_at.desc())
                .limit(limit)
            )

            logger.info(f"get comments called  having userid:{user_id}")

            if user_id:
                logger.info(f"userid given to get comments:{user_id}")
                
                stmt = (stmt
                    .where(ReflectionComment.user_id == user_id)
                )

            res = await db.execute(stmt)
            rows = res.all()

            out = []
            for comment, reflection, user in rows:
                out.append(
                    AdminCommentOut(
                        id=comment.id,
                        podId=reflection.pod_id,
                        checkInId=comment.reflection_id,
                        userId=comment.user_id,
                        username=user.username or user.name,
                        name=user.name,
                        avatar=user.profile_photo_url,
                        text=comment.content,
                        gif=None,  # no gif field in DB model right now
                        createdAt=comment.created_at,
                    )
                )

            return out
        
        except Exception as e:
            logger.info(f"Error while get comments at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        

    @staticmethod
    async def get_activity_logs(db: AsyncSession, limit: int = 200):
        try:
            logger.info("get activity logs called ")

            stmt = (
                select(ActivityLog)
                .options(selectinload(ActivityLog.actor))
                .order_by(ActivityLog.created_at.desc())
                .limit(limit)
            )

            result = await db.execute(stmt)
            logs = result.scalars().all()
            reflection_count = await db.scalar(
                    select(func.count()).select_from(Reflection)
                )
            out = []

            for log in logs:
                user = log.actor
                # username= log.details.strip().split()[0] if log.details.strip() else ""
                email=user.email if user else ""
                logger.info(f"while getting log email: {email} ")

                out.append(
                    AdminActivityOut(
                        id=log.id,
                        userId=log.actor_id,
                        username=user.username if user and user.username else email,
                        avatar=user.profile_photo_url if user else None,
                        action=log.action,
                        details=log.details,
                        timestamp=log.created_at,
                        type=log.type,
                        name=user.name if user and user.name else email,
                        related_id= log.target_ids[0] if  log.target_ids and len(log.target_ids)>0 else None
                    )
                )

            return {
                "activity_logs": out,
                "total_reflections": reflection_count
            }
        
        except Exception as e:
            logger.info(f"Error while activity log at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


    

    @staticmethod
    async def get_pod_goals(db: AsyncSession, pod_id, user_id: Optional[UUID] = None):

        try:
           

            stmt = (
                select(
                    PodGoal.id,
                    PodGoal.title,
                    PodGoal.category,
                    PodGoal.description,
                    PodGoal.frequency_type,
                    PodGoal.frequency_value,
                    PodGoal.created_by,
                    User.username.label("created_by_username"),
                    User.name.label("created_by_name"),
                    func.coalesce(func.max(GoalStreak.longest_streak), 0).label("max_streak")
                )
                .join(User, User.id == PodGoal.created_by)
                .outerjoin(GoalStreak, GoalStreak.goal_id == PodGoal.id)
                .order_by(PodGoal.created_by.desc())
                .where(PodGoal.pod_id == pod_id)
            )

            # Apply filter if user_id is provided
            if user_id:
                stmt = stmt.where(PodGoal.created_by == user_id)

            stmt = stmt.group_by(
                PodGoal.id,
                PodGoal.title,
                PodGoal.category,
                PodGoal.description,
                PodGoal.frequency_type,
                PodGoal.frequency_value,
                PodGoal.created_by,
                User.username,
                User.name
            )

            result = await db.execute(stmt)

            goals = []
            for row in result.all():
                goals.append({
                    "id": row.id,
                    "title": row.title,
                    "category": row.category,
                    "description": row.description,
                    "frequency_type": row.frequency_type,
                    "frequency_value": row.frequency_value,
                    "created_by_id": row.created_by,
                    "created_by_username": row.created_by_username,
                    "created_by_name": row.created_by_name,
                    "max_streak": row.max_streak,
                })

            return goals
        
        except Exception as e:
            logger.info(f"Error while get pod goals at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))



    @staticmethod
    async def delete_user(user_id: str, db: AsyncSession):

        logger.info("delete_user called in admin service")
        try:

            user = await db.get(User, user_id)

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            await AdminService.delete_user_and_handle_pods(user_id, db)
            
           

            return {"message": "User deleted successfully"}
        
        except Exception as e:
            logger.info(f"Error while deleting user :{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
    


    @staticmethod
    async def delete_comment(comment_id: str, db: AsyncSession):

        try:
            comment = await db.get(ReflectionComment, comment_id)

            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")

            await db.delete(comment)
            await db.commit()

            return {"message": "Comment deleted successfully"}
        
        except Exception as e:
            logger.info(f"Error while deleting comment :{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
    


    

    @staticmethod
    async def delete_user_and_handle_pods(user_id: UUID, db: AsyncSession):

        try:

            user = await db.get(User, user_id)

            if not user:
                return {"message": "User already deleted"}
            
            if user.firebase_uid:
                try:
                    firebase_auth.delete_user(user.firebase_uid)
                    logger.info(f"Firebase user deleted: {user.firebase_uid}")
                except Exception as e:
                    logger.warning(f"Firebase deletion failed: {str(e)}")
                    raise HTTPException(status_code=400, detail=str(e))

            # get pods where user is a member
            stmt = select(PodMember).where(PodMember.user_id == user_id)
            result = await db.execute(stmt)
            memberships = result.scalars().all()

            for membership in memberships:

                pod_id = membership.pod_id

                # get all members of the pod
                stmt = select(PodMember).where(PodMember.pod_id == pod_id).order_by(PodMember.joined_at)
                res = await db.execute(stmt)
                members = res.scalars().all()

                # case 1: only one member -> delete pod
                if len(members) == 1:
                    pod = await db.get(Pod, pod_id)
                    if pod:
                        await db.delete(pod)
                    continue

                # case 2: multiple members
                if membership.role == "owner":

                    # find oldest member excluding this user
                    for m in members:
                        if m.user_id != user_id:
                            m.role = "owner"
                            break

                # remove this membership
                await db.delete(membership)

            # finally delete the user
            await db.delete(user)

            await db.commit()

            return {"message": "User deleted successfully"}
        
        except Exception as e:
            logger.info(f"Error while delete_user_and_handle_pods at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def delete_activity(id: str, db: AsyncSession):

        try:
            activity = await db.get(ActivityLog, id)

            if not activity:
                raise HTTPException(status_code=404, detail="Activity log not found")
            
            if activity.type == "reaction" and activity.target_ids:
                for target_id in activity.target_ids:
                    comment = await db.get(ReflectionComment, target_id)
                    if comment:
                        await db.delete(comment)
                    
            
            if activity.type == "check-in" and activity.target_ids:
                for target_id in activity.target_ids:
                    reflection = await db.get(Reflection, target_id)
                    if reflection:
                        await db.delete(reflection)

            # if activity.type == "pod" and activity.target_ids:
            #     for target_id in activity.target_ids:
            #         pod = await db.get(Pod, target_id)
            #         if pod:
            #             await db.delete(pod)

            
            if activity.type == "goal" and activity.target_ids:
                for target_id in activity.target_ids:
                    goal = await db.get(PodGoal, target_id)
                    if goal:
                        await db.delete(goal)

            
            if activity.type == "account" and activity.target_ids:
                for target_id in activity.target_ids:
                    await AdminService.delete_user_and_handle_pods(target_id, db)
                    


            await db.delete(activity)
            await db.commit()

            return {"message": "Activity log deleted successfully"}
        
        except Exception as e:
            logger.info(f"Error while deleting activity :{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))



    @staticmethod
    async def delete_goal(goal_id: str, db: AsyncSession):

        try:
            goal = await db.get(PodGoal, goal_id)

            if not goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            await db.delete(goal)
            await db.commit()

            return {"message": "Goal deleted successfully"}
        
        except Exception as e:
            logger.info(f"Error while deleting activity :{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        

    @staticmethod
    async def get_checkins(
        db: AsyncSession,
        pod_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 500,
    ):
        
        try:
            
                
            stmt = (
                select(Reflection, User)
                .join(User, User.id == Reflection.user_id)
                .where(Reflection.pod_id == pod_id)
                .order_by(Reflection.created_at.desc())
                .limit(limit)
            )

            if user_id:
                stmt = stmt.where(Reflection.user_id == user_id)

            res = await db.execute(stmt)
            rows = res.all()

            out = []
            for reflection, user in rows:
                out.append(
                    AdminCheckinOut(
                        id=reflection.id,
                        pod_id=reflection.pod_id,
                        user_id=reflection.user_id,
                        username=user.username or user.name,
                        name=user.name ,
                        avatar=user.profile_photo_url,
                        reflection_date=reflection.reflection_date,
                        content=reflection.content,
                        mood=reflection.mood,
                        created_at=reflection.created_at,
                    )
                )

            return out
        
        except Exception as e:
            logger.info(f"Error while get chackins at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
    

    @staticmethod
    async def delete_checkin(db: AsyncSession, reflection_id: UUID):

        try:

            reflection = await db.get(Reflection, reflection_id)

            if not reflection:
                logger.info(f"delete checkin called to delete reflection:{reflection_id}")
                raise HTTPException(status_code=404, detail="Checkin not found")

            await db.delete(reflection)
            await db.commit()
            logger.info(f"checkin deleted with reflection id :{reflection_id}")

            return {"message": "Checkin deleted successfully"}
        
        except Exception as e:
            logger.info(f"Error while delete checkin at admin:{str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        
   

    async def get_reflection_by_id(db: AsyncSession,reflection_id: UUID,):
        try:
           

            ref = await _load_reflection_with_goals(db, reflection_id)
            
            return await AdminService._to_response(ref)
        
        except Exception as e:
            logger.exception(f"Error while get_reflection_by_id {str(e)} having reflection_id:{reflection_id}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )
        

    
    async def get_reflection_goals_with_stats(
        db: AsyncSession,
        reflection_id: UUID,
        user_id: UUID,
        pod_id: UUID,
    ):
        try:
            now_date = date.today()
            effective_date = now_date - timedelta(days=1)

            start_of_week = effective_date - timedelta(days=effective_date.weekday())
            end_of_week = start_of_week + timedelta(days=6)

            Progress = aliased(GoalProgressEvent)
            Streak = aliased(GoalStreak)

            weekly_completed_days = func.count(
                func.distinct(
                    case(
                        (
                            (Progress.progress_date.between(start_of_week, end_of_week))
                            & (Progress.completed.is_(True)),
                            Progress.progress_date,
                        ),
                        else_=None,
                    )
                )
            )

            stmt = (
                select(
                    ReflectionGoal,
                    PodGoal,

                    # ✅ weekly progress
                    weekly_completed_days.label("days_achieved_this_week"),
                    func.coalesce(func.max(Streak.current_streak), 0).label("current_streak"),

                )
                .join(PodGoal, PodGoal.id == ReflectionGoal.goal_id)

                # join progress table
                .outerjoin(
                    Progress,
                    (Progress.goal_id == ReflectionGoal.goal_id)
                    & (Progress.user_id == user_id)
                    & (Progress.pod_id == pod_id),
                )
                .outerjoin(
                    Streak,
                    (Streak.goal_id == ReflectionGoal.goal_id)
                    & (Streak.user_id == user_id),
                )

                # 🔥 IMPORTANT FILTER
                .where(ReflectionGoal.reflection_id == reflection_id)

                .group_by(ReflectionGoal.id, PodGoal.id)
            )

            rows = (await db.execute(stmt)).all()

            # ✅ MAP RESPONSE
            result = []
            for rg, goal, days ,streak in rows:
                result.append(
                    ReflectionGoalResponse(
                        goal_id=rg.goal_id,
                        goal_title=goal.title if goal else None,
                        completed=rg.completed,
                        progress_value=rg.weekly_progress_value,

                        frequency_type=goal.frequency_type if goal else None,
                        frequency_value=goal.frequency_value if goal else None,
                        category=goal.category if goal else None,
                        description=goal.description if goal else None,
                        measurement_unit=goal.measurement_unit if goal else None,
                        measurement_target=goal.measurement_target if goal else None,
                        requires_measurement=goal.requires_measurement if goal else None,

                        days_achieved_this_week=int(days or 0),
                        current_streak=int(streak or 0)
                    )
                )

            return result

        except Exception as e:
            logger.exception(f"Error in get_reflection_goals_with_stats: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


    

    async def list_comments(
        db: AsyncSession,
        reflection_id: UUID,
    ):
        try:
        
            
            logger.info(f"trying to list comments with reflection id at admin comments:{reflection_id}")
            
            # ---- FIND REFLECTION ----
            reflection = await db.get(Reflection, reflection_id)

            # If reflection not found, maybe the ID is actually a comment id
            if not reflection:

                logger.info(
                    f"Reflection not found, checking if ID belongs to a comment: {reflection_id}"
                )

                comment_stmt = select(ReflectionComment).where(
                    ReflectionComment.id == reflection_id
                )

                comment = (await db.execute(comment_stmt)).scalar_one_or_none()

                if not comment:
                    raise HTTPException(
                        status_code=404,
                        detail="Reflection or comment not found",
                    )

                # use reflection_id from the comment
                reflection_id = comment.reflection_id

                logger.info(
                    f"Resolved comment -> reflection_id: {reflection_id}"
                )

                reflection = await db.get(Reflection, reflection_id)

                if not reflection:
                    raise HTTPException(
                        status_code=404,
                        detail="Reflection not found for given comment",
                    )

           

            # ---- ORDER BY (date + time) ----
            order_expr = (
                ReflectionComment.created_at.asc()
            )

            # ---- TOTAL COUNT ----
            total_stmt = (
                select(func.count(ReflectionComment.id))
                .where(ReflectionComment.reflection_id == reflection_id)
            )
            total = (await db.execute(total_stmt)).scalar_one()

            # ---- MAIN QUERY ----
            stmt = (
                select(
                    ReflectionComment,
                    User.id.label("u_id"),
                    User.name.label("u_name"),
                    User.profile_photo_url.label("u_profile_photo_url")
                )
                .join(User, User.id == ReflectionComment.user_id)
                .where(ReflectionComment.reflection_id == reflection_id)
                .order_by(order_expr, ReflectionComment.id.asc())  # stable ordering
            )

            rows = (await db.execute(stmt)).all()

            items = [
                {
                    "id": c.id,
                    "reflection_id": c.reflection_id,
                    "content": c.content,
                    "created_at": c.created_at,
                    "user": {
                        "id": u_id,
                        "username": u_name,
                        "profile_photo_url":u_profile_photo_url
                    },
                }
                for c, u_id, u_name ,u_profile_photo_url in rows
            ]

            reflection = await _load_reflection_with_goals(db, reflection_id)

            goals = await AdminService.get_reflection_goals_with_stats(
                db,
                reflection_id=reflection.id,
                user_id=reflection.user_id,
                pod_id=reflection.pod_id,
            )

            reflectionresponse = ReflectionResponse(
                id=reflection.id,
                pod_id=reflection.pod_id,
                user_id=reflection.user_id,
                reflection_date=reflection.reflection_date,
                content=reflection.content,
                mood=reflection.mood,
                created_at=reflection.created_at,
                updated_at=reflection.updated_at,
                goals=goals,  # ✅ IMPORTANT
                attachments=[
                    ReflectionAttachmentResponse(
                        id=a.id,
                        file_url=a.file_url,
                        file_type=a.file_type,
                        uploaded_at=a.uploaded_at,
                    )
                    for a in (reflection.attachments or [])
                ],
            )

            return {
                "total": int(total),
                "reflectionresponse":reflectionresponse,
                "items": items,
            }
        
        except Exception as e:
            logger.exception(f"Error while list_comments at admin {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )
        


    

    async def get_goal(
        session: AsyncSession, pod_id: Optional[UUID], goal_id: UUID, user: User
    ):
        
        try:
            
            logger.info(f"get_goal service called to get goal details for api having goal id:{goal_id}")
            
         

            if pod_id:

                goal = await session.scalar(
                    select(PodGoal).where(
                        PodGoal.id == goal_id,
                        PodGoal.pod_id == pod_id
                    )
                )

            else:

                # pod_id not provided → fetch using goal_id
                goal = await session.scalar(
                    select(PodGoal).where(
                        PodGoal.id == goal_id
                    )
                )

                if goal:
                    pod_id = goal.pod_id


            if not goal:
                raise HTTPException(
                    status_code=404,
                    detail="Goal not found"
                )

            logger.info(
                f"Resolved pod_id={pod_id} for goal_id={goal_id}"
            )
            

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
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )
        


    async def delete_pod(
        db: AsyncSession, pod_id: uuid.UUID, user: User
    ):
        try:
            # 1️⃣ Fetch membership
            member = await db.scalar(
                select(PodMember)
                .where(
                    PodMember.pod_id == pod_id,
                    PodMember.user_id == user.id,
                    PodMember.is_active.is_(True),
                )
            )

          
            pod = await db.scalar(
                select(Pod).where(Pod.id == pod_id)
            )
            if not pod:
                raise HTTPException(status_code=404, detail="Pod not found")
            

            # delete POD 
            await db.delete(pod)
            await db.commit()

            return {"success": True}
        
        except Exception as e:
            logger.exception(f"Error while delete_pod {str(e)} with user :{user.email}")
            raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )




    async def leave_pod(db: AsyncSession, pod_id: uuid.UUID, user_id:uuid.UUID):

        try:
            user=(await db.execute(
                select(User).where(
                User.id == user_id
            ))).scalar_one_or_none()

            stmt = select(Pod).where(
                Pod.id == pod_id,
                Pod.status == "active",
            )

            pod = (await db.execute(stmt)).scalar_one_or_none()

            if not pod:
                raise HTTPException(status_code=404, detail="Invalid invite code")
            

            stmt = select(PodMember).where(
                PodMember.pod_id == pod_id,
                PodMember.user_id == user.id,
                PodMember.is_active.is_(True),
            )

            member = (await db.execute(stmt)).scalar_one_or_none()
            if not member:
                raise HTTPException(status_code=404, detail="Not a member")
            

            stmt = select(func.count(PodMember.id)).where(
                PodMember.pod_id == pod_id,
                PodMember.is_active.is_(True),
            )

            member_count = (await db.execute(stmt)).scalar_one()

            if member_count <=1:
                raise HTTPException(status_code=400, detail="You can't leave the pod")

            if member.role == "owner":
                next_owner = await db.scalar(
                    select(PodMember)
                    .where(
                        PodMember.pod_id == pod_id,
                        PodMember.user_id != user.id,
                        PodMember.is_active.is_(True),
                    )
                    .order_by(PodMember.joined_at.asc())
                    .limit(1)
                )

                if next_owner:
                    next_owner.role = "owner"
                else:
                    # optional: no members left
                    # you may delete pod OR allow owner to leave
                    pass

            member.is_active = False

            logger.info(f"user with userid :{user_id} has been removed from pod :{pod_id}")
            await db.commit()

        except Exception as e:
            logger.exception(f"Error while leave_pod {str(e)} with user :{user.email}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )


