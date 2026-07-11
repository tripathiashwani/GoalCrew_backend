import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from fastapi import HTTPException, status
from app.db.models.pod_members import PodMember
from app.db.models.pods import Pod
from sqlalchemy.orm import aliased
from app.db.models.user import User
from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType
from app.db.models.pod_goal_participants import PodGoalParticipant
from app.db.models.pod_goals import PodGoal

from app.utils.logger import get_logger
exception_logger=get_logger("Exceptions_logs")


def generate_invite_code() -> str:
    return uuid.uuid4().hex[:6].upper()


# ---------- CREATE POD ----------

async def create_pod(db: AsyncSession, user: User, payload):

    try:

        pod = Pod(
            name=payload.name,
            focus_area=payload.focus_area,
            description=payload.description,
            max_members=payload.max_members,
            is_private=payload.is_private,
            invite_code=generate_invite_code(),
            created_by=user.id,
        )

        db.add(pod)
        await db.flush()  # get pod.id

        member = PodMember(
            pod_id=pod.id,
            user_id=user.id,
            role="owner",
            joined_via="direct",
        )

        db.add(member)
        await db.commit()
        await db.refresh(pod)


        
        await dispatcher.emit(
            DomainEvent(
                type=NotificationType.POD_CREATED,
                actor_id=user.id,
                pod_id=pod.id,
                entity_type="pod",
                entity_id=pod.id,
                context={
                    "actor_name": user.name or "Someone",
                    "details":f"{user.name} created new pod" or "Someone",
                    "target_ids":[pod.id]
                },
            )
        )

        return pod
    except Exception as e:
        exception_logger.exception(f"Error while create_pod {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


# ---------- LIST MY PODS ----------

async def list_my_pods(db: AsyncSession, user: User):

    try:
        MemberAll = aliased(PodMember)
        MemberMe = aliased(PodMember)

        stmt = (
            select(
                Pod,
                MemberMe.role,
                func.count(MemberAll.id).label("member_count"),
            )
            # join to get *my* membership (for filtering + role)
            .join(MemberMe, MemberMe.pod_id == Pod.id)
            # join to count *all* members
            .join(MemberAll, MemberAll.pod_id == Pod.id)
            .where(
                MemberMe.user_id == user.id,
                MemberMe.is_active.is_(True),
                MemberAll.is_active.is_(True),
            )
            .group_by(Pod.id, MemberMe.role)
        )

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": pod.id,
                "name": pod.name,
                "description": pod.description,
                "max_members": pod.max_members,
                "is_private": pod.is_private,
                "focus_area": pod.focus_area,
                "invite_code": pod.invite_code,
                "role": role,
                "member_count": member_count,
            }
            for pod, role, member_count,  in rows
        ]
    
    except Exception as e:
        exception_logger.exception(f"Error while add_reflection {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


# ---------- GET POD ----------

async def get_pod(db: AsyncSession, pod_id: uuid.UUID, user: User):
    try:
        stmt = select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == user.id,
            PodMember.is_active.is_(True),
        )

        member = (await db.execute(stmt)).scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=403, detail="Not a pod member")

        pod = await db.get(Pod, pod_id)
        if not pod:
            raise HTTPException(status_code=404, detail="Pod not found")

        return pod, member.role
    except Exception as e:
        exception_logger.exception(f"Error while get_pod {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


# ---------- UPDATE POD ----------

async def update_pod(db: AsyncSession, pod: Pod, role: str, payload):
    try:

        if role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        for field, value in payload.dict(exclude_unset=True).items():
            setattr(pod, field, value)

        await db.commit()
        await db.refresh(pod)
        return pod
    
    except Exception as e:
        exception_logger.exception(f"Error while update_pod {str(e)} with payload :{payload}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )




# ---------- JOIN POD ----------


async def join_pod_by_code(db: AsyncSession, user: User, invite_code: str):
    try:
    # 1️⃣ Get pod
        stmt = select(Pod).where(
            Pod.invite_code == invite_code,
            Pod.status == "active",
        )

        pod = (await db.execute(stmt)).scalar_one_or_none()
        if not pod:
            raise HTTPException(status_code=404, detail="Invalid invite code")

        # 2️⃣ Check if already a member
        stmt = select(PodMember).where(
            PodMember.pod_id == pod.id,
            PodMember.user_id == user.id,
            PodMember.is_active.is_(True),
        )

        if (await db.execute(stmt)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Already a member")
        


        

        # 3️⃣ COUNT members (🔥 THIS IS THE FIX)
        stmt = select(func.count(PodMember.id)).where(
            PodMember.pod_id == pod.id,
            PodMember.is_active.is_(True),
        )

        member_count = (await db.execute(stmt)).scalar_one()

        # if member_count >= pod.max_members:
        #     raise HTTPException(status_code=400, detail="Pod is full")
        


        # 2️⃣ Check if already a member and inactive
        inactive_stmt = select(PodMember).where(
            PodMember.pod_id == pod.id,
            PodMember.user_id == user.id,
            PodMember.is_active.is_(False),
        )

        inactive_member=(await db.execute(inactive_stmt)).scalar_one_or_none()

        if inactive_member:
            inactive_member.joined_via="invite_code"
            inactive_member.is_active=True
            inactive_member.role="member"
            

        else:
            # 4️⃣ Add member
            member = PodMember(
                pod_id=pod.id,
                user_id=user.id,
                role="member",
                joined_via="invite_code",
                is_active=True,
            )

            db.add(member)

        await db.commit()

        # 5️⃣ 🔔 EMIT EVENT (THIS IS THE KEY PART)
        await dispatcher.emit(
            DomainEvent(
                type=NotificationType.POD_MEMBER_JOIN,
                actor_id=user.id,
                pod_id=pod.id,
                entity_type="pod",
                entity_id=pod.id,
                context={
                    "actor_name": user.name,
                    "pod_name": pod.name,
                    "target_ids":[pod.id]
                },
            )
        )
        return pod
    except Exception as e:
        exception_logger.exception(f"Error while join_pod_by_code {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

# ---------- LEAVE POD ----------

async def leave_pod(db: AsyncSession, pod_id: uuid.UUID, user: User):

    try:

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
        await db.commit()

    except Exception as e:
        exception_logger.exception(f"Error while leave_pod {str(e)} with user :{user.email}")
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

        if not member:
            raise HTTPException(status_code=404, detail="Not a pod member")

        # 2️⃣ If owner → transfer ownership
        if member.role != "owner":
            raise HTTPException(status_code=404, detail="Not a pod owner")
        

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
        exception_logger.exception(f"Error while delete_pod {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )




# ---------- LIST MEMBERS ----------

async def list_members(db: AsyncSession, pod_id: uuid.UUID, user: User):
    try:

        me = await db.scalar(
            select(PodMember).where(
                PodMember.pod_id == pod_id,
                PodMember.user_id == user.id,
                PodMember.is_active.is_(True),
            )
        )
        if not me:
            raise HTTPException(status_code=403, detail="Not a pod member")

        stmt = (
            select(PodMember, User)
            .join(User, User.id == PodMember.user_id)
            .where(PodMember.pod_id == pod_id)
        )

        # non-owner sees only active
        if me.role != "owner":
            stmt = stmt.where(PodMember.is_active.is_(True))

        return (await db.execute(stmt)).all()
    
    except Exception as e:
        exception_logger.exception(f"Error while list_members {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )
# ---------- UPDATE MEMBER ROLE ----------

async def update_member_role(
    db: AsyncSession,
    pod_id: uuid.UUID,
    target_user_id: uuid.UUID,
    user: User,
    role: str,
):
    try:
        stmt = select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == user.id,
            PodMember.role == "owner",
            PodMember.is_active.is_(True),
        )

        if not (await db.execute(stmt)).scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Only owner can update roles")

        stmt = select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == target_user_id,
        )

        target = (await db.execute(stmt)).scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Member not found")

        target.role = role
        await db.commit()
    except Exception as e:
        exception_logger.exception(f"Error while update_member_role {str(e)} with user :{user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

async def toggle_member_active(
    db,
    pod_id: uuid.UUID,
    target_user_id: uuid.UUID,
    actor_user,
    is_active: bool,
):
    try:
        # 1) Only owner can toggle
        owner_stmt = select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == actor_user.id,
            PodMember.role == "owner",
            PodMember.is_active.is_(True),
        )
        owner = (await db.execute(owner_stmt)).scalar_one_or_none()
        if not owner:
            raise HTTPException(status_code=403, detail="Only owner can activate/deactivate members")

        # 2) Owner cannot deactivate self via this endpoint
        if target_user_id == actor_user.id:
            raise HTTPException(status_code=400, detail="Owner cannot deactivate themself")

        # 3) Find target member (allow toggling even if currently inactive)
        target_stmt = select(PodMember).where(
            PodMember.pod_id == pod_id,
            PodMember.user_id == target_user_id,
        )
        target = (await db.execute(target_stmt)).scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Member not found")

        # 4) If deactivating: ensure there will still be at least 1 active member
        if is_active is False and target.is_active is True:
            count_stmt = select(func.count(PodMember.id)).where(
                PodMember.pod_id == pod_id,
                PodMember.is_active.is_(True),
            )
            active_count = (await db.execute(count_stmt)).scalar_one()

            # if this member is active and would be deactivated
            if active_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate the last active member")

            # Optional extra safety: never leave pod without an owner
            if target.role == "owner":
                raise HTTPException(status_code=400, detail="Cannot deactivate the owner")

        # 5) Apply toggle
        target.is_active = is_active

        # Optional: if re-activating, you may want to reset role from something else
        # (you already do role="member" in join flow for inactive members)

        await db.commit()
        await db.refresh(target)
        return target
    except Exception as e:
        exception_logger.exception(f"Error while toggle_member_active {str(e)} with target_user_id :{target_user_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )