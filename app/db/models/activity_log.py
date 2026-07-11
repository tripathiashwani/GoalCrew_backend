import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"



    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
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
    action: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    details: Mapped[str] = mapped_column(
        String(1000),
        nullable=True,
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # -------------------------
    # Relationships
    # -------------------------


    actor = relationship(
        "User",
        foreign_keys=[actor_id],
    )

    pod = relationship(
        "Pod",
        foreign_keys=[pod_id],
        back_populates="activity_logs",
    )

    target_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
    ARRAY(UUID(as_uuid=True)),
    nullable=True,
)
