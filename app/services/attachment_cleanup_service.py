from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.reflection_attachments import ReflectionAttachment
from app.db.models.reflections import Reflection
from app.db.models.user_preferences import UserPreference
from app.db.session import async_session
from app.utils.logger import get_logger

logger = get_logger("attachment-cleanup")

PHOTO_EXPIRATION_MAP = {
    "24h": timedelta(hours=24),
    "5d": timedelta(days=5),
    "7d": timedelta(days=7),
}


class AttachmentCleanupService:
    def __init__(self, upload_base_dir: Path):
        self.upload_base_dir = upload_base_dir

    async def run(self):
        logger.info("🧹 Attachment cleanup job started")

        async with async_session() as session:
            await self._cleanup_expired_attachments(session)

        logger.info("✅ Attachment cleanup job finished")

    # 🔥 MUST be sync
    def _compute_cutoff(self, ttl: timedelta) -> datetime:
        """
        Returns naive UTC cutoff datetime
        """
        return (
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
            - ttl
        )

    async def _cleanup_expired_attachments(self, session: AsyncSession):
        # ✅ Naive UTC now
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        stmt = (
            select(
                ReflectionAttachment,
                UserPreference.photo_expiration,
            )
            .join(Reflection, Reflection.id == ReflectionAttachment.reflection_id)
            .join(UserPreference, UserPreference.user_id == Reflection.user_id)
        )

        result = await session.execute(stmt)
        rows = result.all()

        logger.info(f"🔍 Found {len(rows)} attachment candidates")

        deleted_count = 0

        for attachment, photo_expiration in rows:
            ttl = PHOTO_EXPIRATION_MAP.get(photo_expiration)

            if not ttl:
                logger.warning(
                    f"Unknown photo_expiration='{photo_expiration}' "
                    f"attachment_id={attachment.id}"
                )
                continue

            cutoff = self._compute_cutoff(ttl)

            if attachment.uploaded_at >= cutoff:
                continue

            self._delete_file(attachment.file_url)
            await session.delete(attachment)
            deleted_count += 1

        if deleted_count:
            await session.commit()

        logger.info(f"🗑️ Deleted {deleted_count} expired attachments")

    def _delete_file(self, file_url: str):
        try:
            absolute_path = self.upload_base_dir / file_url.lstrip("/")

            if absolute_path.exists():
                absolute_path.unlink()
                logger.info(f"Deleted file: {absolute_path}")
            else:
                logger.warning(f"File not found: {absolute_path}")

        except Exception:
            logger.exception(f"Failed deleting file {file_url}")
