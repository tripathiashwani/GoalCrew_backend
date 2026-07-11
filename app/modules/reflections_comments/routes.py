from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_session
from app.dependencies import get_current_user
from app.modules.reflections_comments  import services
from app.modules.reflections_comments.schemas import PaginatedReflectionCommentsResponse, ReflectionCommentCreate, ReflectionCommentResponse, ReflectionCommentUpdate 

router = APIRouter(
    prefix="/pods/{pod_id}/reflections/{reflection_id}/comments",
    tags=["Reflection Comments"],
)

@router.get(
    "",
    response_model=PaginatedReflectionCommentsResponse,
)
async def list_comments(
    pod_id: UUID,
    reflection_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order: Literal["asc", "desc"] = Query("asc"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await services.list_comments(
        session,
        pod_id,
        reflection_id,
        user,
        page=page,
        page_size=page_size,
        order=order,
    )

@router.post("", response_model=ReflectionCommentResponse)
async def add_comment(
    pod_id: UUID,
    reflection_id: UUID,
    payload: ReflectionCommentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await services.add_comment(
        session, pod_id, reflection_id, user, payload.content
    )


@router.patch("/{comment_id}", response_model=ReflectionCommentResponse)
async def update_comment(
    pod_id: UUID,
    reflection_id: UUID,
    comment_id: UUID,
    payload: ReflectionCommentUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await services.update_comment(
        session,
        pod_id,
        reflection_id,
        comment_id,
        user,
        payload.content,
    )

@router.delete("/{comment_id}")
async def delete_comment(
    pod_id: UUID,
    reflection_id: UUID,
    comment_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await services.delete_comment(
        session, pod_id, reflection_id, comment_id, user
    )
