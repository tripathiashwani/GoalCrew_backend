from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, literal_column, select, func

from app.db.models.pod_members import PodMember
from app.utils.logger import get_logger

logger = get_logger("Service")
async def _require_pod_member(
    session: AsyncSession, pod_id: UUID, user_id: UUID
) -> PodMember:
    try:
        member = await session.scalar(
            select(PodMember).where(
                PodMember.pod_id == pod_id,
                PodMember.user_id == user_id,
                PodMember.is_active.is_(True),
            )
        )
    except Exception as e:
        logger.error(
            "DB error while checking pod membership",
            exc_info=True,
            extra={"pod_id": str(pod_id), "user_id": str(user_id)},
        )
        raise HTTPException(status_code=500, detail="Failed to verify pod membership")

    if not member:
        logger.warning(
            "User is not an active pod member",
            extra={"pod_id": str(pod_id), "user_id": str(user_id)},
        )
        raise HTTPException(status_code=403, detail="Not a pod member")

    return member
