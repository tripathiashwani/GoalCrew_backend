from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.dependencies import get_current_user
from app.modules.pods import schemas, service
from app.db.session import get_session
from fastapi import HTTPException, status

router = APIRouter(prefix="/pods", tags=["Pods"])


@router.post("", response_model=schemas.PodDetailResponse)
async def create_pod(
    payload: schemas.PodCreateRequest,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    pod = await service.create_pod(db, user, payload)

    return {
        "id": pod.id,
        "name": pod.name,
        "focus_area": pod.focus_area,
        "description": pod.description,
        "invite_code": pod.invite_code,
        "max_members": pod.max_members,
        "is_private": pod.is_private,
        "created_by": pod.created_by,
        "my_role": "owner",
        "created_at": pod.created_at,
    }


@router.get("", response_model=list[schemas.PodResponse])
async def list_my_pods(
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.list_my_pods(db, user)

@router.get("/{pod_id}", response_model=schemas.PodDetailResponse)
async def get_pod(
    pod_id: UUID,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    pod, role = await service.get_pod(db, pod_id, user)

    return {
        "id": pod.id,
        "name": pod.name,
        "focus_area": pod.focus_area,
        "description": pod.description,
        "invite_code": pod.invite_code,
        "max_members": pod.max_members,
        "is_private": pod.is_private,
        "created_by": pod.created_by,
        "my_role": role,
        "created_at": pod.created_at,
    }
@router.patch("/{pod_id}")
async def update_pod(
    pod_id: UUID,
    payload: schemas.PodUpdateRequest,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    pod, role = await service.get_pod(db, pod_id, user)
    await service.update_pod(db, pod, role, payload)
    return {"message": "Pod updated successfully"}


@router.delete("/{pod_id}")
async def delete_pod(
    pod_id: UUID,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    try:

        await service.delete_pod(db, pod_id, user)
        return {"message": "Pod deleted successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


@router.post("/join")
async def join_pod(
    payload: schemas.JoinPodRequest,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    pod = await service.join_pod_by_code(db, user, payload.invite_code)
    return {"pod_id": pod.id, "name": pod.name, "role": "member"}


@router.post("/{pod_id}/leave")
async def leave_pod(
    pod_id: UUID,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    await service.leave_pod(db, pod_id, user)
    return {"message": "You have left the pod"}


@router.get("/{pod_id}/members", response_model=list[schemas.PodMemberResponse])
async def list_members(
    pod_id: UUID,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    rows = await service.list_members(db, pod_id, user)

    return [
        {
            "user_id": member.user_id,
            "username": user.username,
            "role": member.role,
            "joined_at": member.joined_at,
            "profile_photo_url": user.profile_photo_url,
            "is_active":member.is_active,
        }
        for member, user in rows
    ]


@router.patch("/{pod_id}/members/{user_id}")
async def update_member_role(
    pod_id: UUID,
    user_id: UUID,
    payload: schemas.UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    await service.update_member_role(db, pod_id, user_id, user, payload.role)
    return {"message": "Member role updated"}


@router.patch("/{pod_id}/members/{user_id}/active", response_model=schemas.PodMemberToggleResponse)
async def toggle_member_active(
    pod_id: UUID,
    user_id: UUID,
    payload: schemas.ToggleMemberActiveRequest,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    updated = await service.toggle_member_active(db, pod_id, user_id, user, payload.is_active)
    return {
        "user_id": updated.user_id,
        "is_active": updated.is_active,
        "role": updated.role,
    }