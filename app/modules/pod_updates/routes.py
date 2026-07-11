# app/api/v1/pod_updates.py
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date
from typing import Optional, Literal

from app.db.session import get_session
from app.db.models.user import User
from app.dependencies import get_current_user
from app.modules.pod_updates import schemas, service
from app.utils.logger import get_logger
from fastapi import HTTPException
logger = get_logger("pod_updates")

exception_logger=get_logger("Exceptions_logs")

router = APIRouter(prefix="/pods/{pod_id}/updates", tags=["Pod Updates"])


@router.get("", response_model=schemas.PodUpdatesResponse)
async def get_pod_updates(
    pod_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),

    # pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),

    # sorting
    sort_by: Literal["reflection_date", "created_at"] = Query("reflection_date"),
    sort_order: Literal["asc", "desc"] = Query("desc"),

    # filters
    user_id: Optional[UUID] = Query(None),
    mood: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    q: Optional[str] = Query(None),
):
    
    try:
        logger.info(f"Fetching pod updates for pod_id: {pod_id} by user: {user.id}")
        data = await service.list_pod_updates(
            session,
            pod_id,
            user,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            user_id=user_id,
            mood=mood,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        return data
    
    except Exception as e:
        logger.info(f"Error while get_pod_updated {str(e)} with user :{user.email} and pod id:{pod_id}")
        exception_logger.exception(f"Error while get_pod_updates {str(e)} with user :{user.email}  and pod_id :{pod_id}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


@router.get(
    "/{reflection_id}",
    response_model=schemas.PodUpdateDetailResponse,
)
async def get_pod_update(
    pod_id: UUID,
    reflection_id: UUID,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Get full reflection details:
    - content
    - mood
    - per-goal completion
    """
    return await service.get_pod_update(
        db=db,
        pod_id=pod_id,
        reflection_id=reflection_id,
        user=user,
    )

@router.delete(
    "/{reflection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pod_update(
    pod_id: UUID,
    reflection_id: UUID,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Delete a reflection.
    Allowed:
    - author
    - pod owner/admin
    """
    await service.delete_pod_update(
        db=db,
        pod_id=pod_id,
        reflection_id=reflection_id,
        user=user,
    )
    return None
