# app/cli/cleanup_attachments.py

import asyncio
from pathlib import Path

from app.config import config
from app.services.attachment_cleanup_service import AttachmentCleanupService
from app.utils.logger import get_logger

logger = get_logger("attachment-cleanup-cli")


async def main():
    logger.info("🚀 Starting attachment cleanup CLI")

    service = AttachmentCleanupService(
        upload_base_dir=Path(config.BASE_DIR)
    )

    await service.run()

    logger.info("🏁 Attachment cleanup CLI finished")


if __name__ == "__main__":
    asyncio.run(main())
