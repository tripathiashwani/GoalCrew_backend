import uuid
from sqlalchemy import (
    Column,
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

class PodSettings(Base):
    __tablename__ = "pod_settings"

    pod_id = Column(UUID(as_uuid=True), ForeignKey("pods.id", ondelete="CASCADE"), primary_key=True)
    allow_invites = Column(Boolean, default=True)
    allow_member_posts = Column(Boolean, default=True)
    weekly_summary_enabled = Column(Boolean, default=True)
    timezone = Column(String)

    pod = relationship("Pod", back_populates="settings")
