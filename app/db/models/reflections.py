import uuid
from sqlalchemy import (
    Column,
    Index,
    String,
    Boolean,
    Integer,
    Float,
    Text,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class Reflection(Base):
    __tablename__ = "reflections"
    __table_args__ = (
        Index("idx_reflections_user", "user_id"),
        Index("idx_reflections_pod", "pod_id"),
        Index("idx_reflections_date", "reflection_date"),
        Index("idx_reflections_user_date", "user_id", "reflection_date"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pod_id = Column(UUID(as_uuid=True), ForeignKey("pods.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
    reflection_date = Column(Date, nullable=False)
    content = Column(Text)
    mood = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    goals = relationship("ReflectionGoal", cascade="all, delete-orphan")
    reactions = relationship(
        "ReflectionReaction",
        back_populates="reflection",
        cascade="all, delete-orphan",
    )

    attachments = relationship(
        "ReflectionAttachment",
        back_populates="reflection",
        cascade="all, delete-orphan",
    )

    comments = relationship(
        "ReflectionComment",
        back_populates="reflection",
        cascade="all, delete-orphan",
        order_by="ReflectionComment.created_at",
    )
