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

class ReflectionAttachment(Base):
    __tablename__ = "reflection_attachments"
    __table_args__ = (
        Index("idx_reflection_attachments_reflection", "reflection_id"),
        Index("idx_reflection_attachments_type", "file_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reflection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reflections.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # image / GIF
    uploaded_at = Column(DateTime, server_default=func.now())

    # Relationships
    reflection = relationship("Reflection", back_populates="attachments")
