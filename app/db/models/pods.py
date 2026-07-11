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


class Pod(Base):
    __tablename__ = "pods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    focus_area = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
    max_members = Column(Integer, default=5)
    is_private = Column(Boolean, default=True)
    invite_code = Column(String, unique=True, nullable=False)
    status = Column(String, default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    creator = relationship("User", back_populates="pods_created")
    members = relationship("PodMember", cascade="all, delete-orphan", back_populates="pod")
    goals = relationship("PodGoal", cascade="all, delete-orphan", back_populates="pod")
    settings = relationship("PodSettings", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="pod")
    activity_logs = relationship(
        "ActivityLog",
        back_populates="pod",
        cascade="all, delete-orphan",
    )