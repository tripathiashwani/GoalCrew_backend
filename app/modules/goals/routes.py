from fastapi import APIRouter, Depends,status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_session
from app.dependencies import get_current_user
from app.modules.goals import schemas, service

router = APIRouter(
    prefix="/pods/{pod_id}/goals",
    tags=["Pod Goals"],
)


@router.post("", status_code=201)
async def create_goal(
    pod_id: UUID,
    payload: schemas.GoalCreateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.create_goal(session, pod_id, user, payload)


from fastapi import Query

@router.get("", response_model=list[schemas.UserGoalListResponse])
async def list_goals(
    pod_id: UUID,
    all_users: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.list_goals(
        session=session,
        pod_id=pod_id,
        user=user,
        all_users=all_users,
    )


@router.get("/{goal_id}", response_model=schemas.GoalDetailResponse)
async def get_goal(
    pod_id: UUID,
    goal_id: UUID,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.get_goal(session, pod_id, goal_id, user)

@router.patch("/{goal_id}", response_model=schemas.GoalDetailResponse)
async def update_goal(
    pod_id: UUID,
    goal_id: UUID,
    payload: schemas.GoalUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.update_goal(
        session=session,
        pod_id=pod_id,
        goal_id=goal_id,
        user=user,
        payload=payload,
    )

@router.post("/batch", status_code=201)
async def create_goals_batch(
    pod_id: UUID,
    payload: schemas.GoalBatchCreateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.create_goals_batch(session, pod_id, user, payload.goals)






@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT,)
async def delete_goal(
    pod_id: UUID,
    goal_id: UUID,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    await service.delete_goal(session, pod_id, goal_id, user)
    return None
