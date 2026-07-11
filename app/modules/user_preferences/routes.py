# app/modules/user_preferences/routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

from app.dependencies import get_current_user
from app.modules.user_preferences.schemas import UserPreferenceRead, UserPreferenceUpdate
from app.modules.user_preferences.services import UserPreferenceService


router = APIRouter(prefix="/users", tags=["Users"])
service = UserPreferenceService()


@router.get(
    "/preferences",
    response_model=UserPreferenceRead,
)
async def get_preferences(
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.get_user_preferences(db, user)


@router.patch(
    "/preferences",
    response_model=UserPreferenceRead,
)
async def update_preferences(
    payload: UserPreferenceUpdate,
    db: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.update_user_preferences(db, user, payload)
