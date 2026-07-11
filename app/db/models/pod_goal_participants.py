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

class PodGoalParticipant(Base):
    __tablename__ = "pod_goal_participants"
    __table_args__ = (
        UniqueConstraint("goal_id", "user_id"),
        Index("idx_goal_participants_user", "user_id"),
        Index("idx_goal_participants_goal", "goal_id"),
        Index("idx_goal_participants_active", "is_active"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pod_id = Column(UUID(as_uuid=True), ForeignKey("pods.id", ondelete="CASCADE"))
    goal_id = Column(UUID(as_uuid=True), ForeignKey("pod_goals.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
    joined_at = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    goal = relationship("PodGoal")
    user = relationship("User")
