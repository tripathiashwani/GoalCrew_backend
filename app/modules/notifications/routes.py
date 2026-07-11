# app/modules/notifications/routes.py
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException

from app.db.session import get_session
from app.dependencies import get_current_user
from app.modules.notifications import service, schemas

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=schemas.NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    unread_only: bool = Query(False),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db=Depends(get_session),
    user=Depends(get_current_user),
):
    data = await service.list_notifications(
        db=db,
        user_id=user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
        start_date=start_date,
        end_date=end_date,
    )

    return data

@router.get("/unread-count", response_model=schemas.UnreadCountResponse)
async def unread_count(
    db=Depends(get_session),
    user=Depends(get_current_user),
):
    count = await service.get_unread_count(db, user.id)
    return {"unread_count": count}

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    db=Depends(get_session),
    user=Depends(get_current_user),
):
    success = await service.mark_as_read(db, user.id, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"success": True}

@router.post("/read-all")
async def mark_all_notifications_read(
    db=Depends(get_session),
    user=Depends(get_current_user),
):
    await service.mark_all_as_read(db, user.id)
    return {"success": True}
