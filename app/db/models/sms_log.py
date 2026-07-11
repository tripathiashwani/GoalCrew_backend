# app/db/models/sms_log.py
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class SmsLog(Base):
    __tablename__ = "sms_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(String(25), nullable=False)

    message_type: Mapped[str] = mapped_column(
        String(50),  # daily_goal_reminder / weekly_goal_reminder
        nullable=False,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)

    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    provider_message_id: Mapped[str | None] = mapped_column(String(100))

    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
