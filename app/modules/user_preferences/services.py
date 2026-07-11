# app/modules/user_preferences/services.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.db.models.user_preferences import UserPreference
from app.modules.user_preferences.schemas import     UserPreferenceRead,    UserPreferenceUpdate
from app.utils.logger import get_logger
exception_logger=get_logger("Exceptions_logs")

class UserPreferenceService:

    async def get_user_preferences(
        self,
        db: AsyncSession,
        user,
    ) -> UserPreferenceRead:
        try:
            stmt = select(UserPreference).where(
                UserPreference.user_id == user.id
            )
            result = await db.execute(stmt)
            prefs = result.scalar_one_or_none()

            # 🔹 Auto-create if missing
            if not prefs:
                prefs = UserPreference(user_id=user.id)
                db.add(prefs)
                await db.commit()
                await db.refresh(prefs)

            return UserPreferenceRead.model_validate(prefs)
        
        except Exception as e:
            exception_logger.exception(f"Error while get_user_preferences {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )

    async def update_user_preferences(
        self,
        db: AsyncSession,
        user,
        payload: UserPreferenceUpdate,
    ) -> UserPreferenceRead:
        try:
            stmt = select(UserPreference).where(
                UserPreference.user_id == user.id
            )
            result = await db.execute(stmt)
            prefs = result.scalar_one_or_none()

            if not prefs:
                prefs = UserPreference(user_id=user.id)
                db.add(prefs)

            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(prefs, field, value)

            await db.commit()
            await db.refresh(prefs)

            return UserPreferenceRead.model_validate(prefs)
        
        except Exception as e:
            exception_logger.exception(f"Error while update_user_preferences {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )

