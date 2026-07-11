import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReflectionReaction(Base):
    __tablename__ = "reflection_reactions"
    __table_args__ = (
        Index("idx_reflection_reactions_reflection", "reflection_id"),
        Index("idx_reflection_reactions_user", "user_id"),
        Index("idx_reflection_reactions_reaction", "reaction"),
        UniqueConstraint("reflection_id", "user_id", "reaction"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reflection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reflections.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reaction = Column(String(10), nullable=False)  # 👏 🔥 ❤️ 💡
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    reflection = relationship("Reflection", back_populates="reactions")
    user = relationship("User")
