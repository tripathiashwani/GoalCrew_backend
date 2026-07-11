import uuid
from datetime import time, datetime

from sqlalchemy import (
    String,
    Boolean,
    Time,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    #  Check-in reminders
    # Allowed: daily | weekly | monthly
    checkin_frequency: Mapped[str] = mapped_column(
        String(20),
        default="daily",
        nullable=False,
    )

    checkin_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    #  Pod updates
    pod_updates_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Reminder
    reminder: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )

    # SMS_reminder 
    sms_reminder: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )
    
    # Photo expiration
    # Allowed: 24h | 5d | 7d
    photo_expiration: Mapped[str] = mapped_column(
        String(10),
        default="7d",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    #  Relationship
    user = relationship("User", back_populates="preferences")
