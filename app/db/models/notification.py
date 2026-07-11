import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import backref

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        Index("idx_notifications_user", "user_id"),
        Index("idx_notifications_user_read", "user_id", "is_read"),
        Index("idx_notifications_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Receiver
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Actor (who caused it)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Pod Id
    pod_id : Mapped[uuid.UUID|None] = mapped_column(UUID(as_uuid=True),ForeignKey("pods.id", ondelete="SET NULL"),nullable=True)

    # Type of notification
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Display content
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # What this notification refers to
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,  # reflection | pod | goal | comment | system
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Read state
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # -------------------------
    # Relationships
    # -------------------------
    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref=backref("notifications", passive_deletes=True),
        passive_deletes=True
    )

    actor = relationship(
        "User",
        foreign_keys=[actor_id],
    )

    pod = relationship(
        "Pod",
        foreign_keys=[pod_id],
        back_populates="notifications",
    )
